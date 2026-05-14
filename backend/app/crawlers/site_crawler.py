"""
On-Page SEO Crawler
Fetches website pages and analyzes on-page SEO factors:
  - Title tags, meta descriptions, canonical tags
  - Heading structure (H1-H6)
  - Content length and keyword density
  - Image alt text coverage
  - Internal/external link counts
  - Open Graph and structured data presence
  - Page load size estimate
  - Mobile viewport meta tag
"""
import logging
import re
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger("roas_engine.site_crawler")

# Try to import BeautifulSoup; if missing, crawler will degrade gracefully
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.warning("beautifulsoup4 not installed — site crawler will not work. Run: pip install beautifulsoup4 lxml")


class PageAudit:
    """Results of crawling and analyzing a single page."""

    def __init__(self, url: str):
        self.url = url
        self.status_code: int = 0
        self.load_time_ms: float = 0
        self.page_size_bytes: int = 0

        # Meta
        self.title: str = ""
        self.title_length: int = 0
        self.meta_description: str = ""
        self.meta_description_length: int = 0
        self.canonical_url: str = ""
        self.has_canonical: bool = False
        self.viewport_meta: bool = False
        self.robots_meta: str = ""
        self.language: str = ""

        # Headings
        self.h1_tags: List[str] = []
        self.h2_tags: List[str] = []
        self.h3_tags: List[str] = []
        self.heading_count: int = 0

        # Content
        self.word_count: int = 0
        self.text_to_html_ratio: float = 0.0

        # Images
        self.total_images: int = 0
        self.images_without_alt: int = 0
        self.alt_text_coverage: float = 0.0

        # Links
        self.internal_links: int = 0
        self.external_links: int = 0
        self.broken_links: List[str] = []

        # Structured data & OG
        self.has_og_tags: bool = False
        self.og_tags: Dict[str, str] = {}
        self.has_structured_data: bool = False
        self.structured_data_types: List[str] = []

        # Issues & Score
        self.issues: List[Dict[str, str]] = []
        self.score: int = 100  # starts perfect, deducted per issue

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "load_time_ms": round(self.load_time_ms, 1),
            "page_size_kb": round(self.page_size_bytes / 1024, 1),
            "title": self.title,
            "title_length": self.title_length,
            "meta_description": self.meta_description,
            "meta_description_length": self.meta_description_length,
            "canonical_url": self.canonical_url,
            "has_canonical": self.has_canonical,
            "viewport_meta": self.viewport_meta,
            "robots_meta": self.robots_meta,
            "language": self.language,
            "h1_tags": self.h1_tags,
            "h2_tags": self.h2_tags,
            "heading_count": self.heading_count,
            "word_count": self.word_count,
            "text_to_html_ratio": round(self.text_to_html_ratio, 2),
            "total_images": self.total_images,
            "images_without_alt": self.images_without_alt,
            "alt_text_coverage": round(self.alt_text_coverage, 1),
            "internal_links": self.internal_links,
            "external_links": self.external_links,
            "has_og_tags": self.has_og_tags,
            "og_tags": self.og_tags,
            "has_structured_data": self.has_structured_data,
            "structured_data_types": self.structured_data_types,
            "issues": self.issues,
            "score": self.score,
        }


class SiteCrawler:
    """
    Crawls a website and performs on-page SEO analysis.
    Works with real URLs or returns demo data when in demo mode.
    """

    def __init__(self, base_url: str = "", max_pages: int = 20, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self.timeout = timeout
        parsed = urlparse(self.base_url) if self.base_url else None
        self.domain = parsed.netloc if parsed else ""

    async def crawl_site(self, urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Crawl a list of URLs (or discover from sitemap/homepage) and return
        a full on-page SEO audit.
        """
        if not HAS_BS4:
            raise RuntimeError("beautifulsoup4 is required for site crawling. pip install beautifulsoup4 lxml")

        if not urls:
            urls = await self._discover_urls()

        urls = urls[:self.max_pages]
        audits = await self._crawl_pages(urls)
        summary = self._build_summary(audits)
        return summary

    async def _discover_urls(self) -> List[str]:
        """Try sitemap (incl. sitemap index), fall back to homepage link discovery."""
        urls: List[str] = [self.base_url]  # always include homepage

        # Try sitemap.xml — handle BOTH flat sitemap and sitemap-index
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                discovered = await self._fetch_sitemap_recursive(client, f"{self.base_url}/sitemap.xml")
                # Prioritise variety: pages and collections first, then products
                priority = [u for u in discovered if "/pages/" in u or "/collections/" in u]
                products = [u for u in discovered if "/products/" in u]
                others = [u for u in discovered if u not in priority and u not in products]
                ordered = priority + others + products
                for u in ordered:
                    if u not in urls:
                        urls.append(u)
                if len(urls) > 1:
                    logger.info(f"Discovered {len(urls)} URLs from sitemap (incl. homepage)")
                    return urls[:self.max_pages]
        except Exception as e:
            logger.debug(f"Sitemap fetch failed: {e}")

        # Fall back to homepage link discovery
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.base_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = urljoin(self.base_url, a["href"])
                        parsed = urlparse(href)
                        if parsed.netloc == self.domain and href not in urls:
                            urls.append(href)
        except Exception as e:
            logger.debug(f"Homepage crawl failed: {e}")

        return urls[:self.max_pages]

    async def _fetch_sitemap_recursive(
        self, client: "httpx.AsyncClient", url: str, depth: int = 0,
    ) -> List[str]:
        """
        Recursively fetch a sitemap or sitemap-index.
        - <sitemapindex> → recurse into each child <sitemap><loc>
        - <urlset>       → return each <url><loc>
        Caps recursion at depth 3 and total URLs at self.max_pages * 5
        (we'll trim later when picking which to crawl).
        """
        if depth > 3:
            return []
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            text = resp.text
        except Exception as e:
            logger.debug(f"Sitemap fetch error for {url}: {e}")
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "lxml-xml")

        # Sitemap index → recurse
        if soup.find("sitemapindex"):
            urls: List[str] = []
            for sm in soup.find_all("sitemap"):
                loc = sm.find("loc")
                if loc and loc.text:
                    child = await self._fetch_sitemap_recursive(client, loc.text.strip(), depth + 1)
                    urls.extend(child)
                    # Don't blow past a reasonable cap
                    if len(urls) >= self.max_pages * 5:
                        break
            return urls

        # Flat URL set → collect each <url>'s direct <loc> child only
        # (Shopify nests <image:loc> inside <url> for image sitemaps; ignore those.)
        if soup.find("urlset"):
            urls: List[str] = []
            for u in soup.find_all("url"):
                # find_all with recursive=False to get only direct children
                loc = u.find("loc", recursive=False)
                if loc and loc.text:
                    urls.append(loc.text.strip())
            return urls

        return []

    async def _crawl_pages(self, urls: List[str]) -> List[PageAudit]:
        """Crawl all pages concurrently (limited concurrency)."""
        sem = asyncio.Semaphore(5)
        audits = []

        async def _fetch(url):
            async with sem:
                audit = await self._analyze_page(url)
                if audit:
                    audits.append(audit)

        tasks = [_fetch(url) for url in urls]
        await asyncio.gather(*tasks)
        return audits

    async def _analyze_page(self, url: str) -> Optional[PageAudit]:
        """Fetch and analyze a single page."""
        audit = PageAudit(url)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                start = asyncio.get_event_loop().time()
                resp = await client.get(url, headers={
                    "User-Agent": "ROASEngine-SEO-Crawler/1.0 (+https://roasengine.ai/bot)"
                })
                elapsed = (asyncio.get_event_loop().time() - start) * 1000

            audit.status_code = resp.status_code
            audit.load_time_ms = elapsed
            audit.page_size_bytes = len(resp.content)

            if resp.status_code != 200:
                audit.issues.append({
                    "severity": "critical",
                    "issue": f"HTTP {resp.status_code}",
                    "detail": f"Page returned status {resp.status_code}",
                })
                audit.score -= 30
                return audit

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            self._analyze_meta(soup, audit)
            self._analyze_headings(soup, audit)
            self._analyze_content(soup, html, audit)
            self._analyze_images(soup, audit)
            self._analyze_links(soup, url, audit)
            self._analyze_structured_data(soup, html, audit)
            self._analyze_og_tags(soup, audit)
            self._run_issue_checks(audit)

        except httpx.TimeoutException:
            audit.issues.append({"severity": "critical", "issue": "Timeout", "detail": f"Page took >{self.timeout}s to load"})
            audit.score -= 25
        except Exception as e:
            logger.warning(f"Failed to crawl {url}: {e}")
            audit.issues.append({"severity": "critical", "issue": "Crawl Error", "detail": str(e)})
            audit.score -= 30

        return audit

    def _analyze_meta(self, soup, audit: PageAudit):
        """Extract and score meta tags."""
        # Title
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            audit.title = title_tag.string.strip()
            audit.title_length = len(audit.title)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            audit.meta_description = meta_desc["content"].strip()
            audit.meta_description_length = len(audit.meta_description)

        # Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            audit.has_canonical = True
            audit.canonical_url = canonical["href"]

        # Viewport
        viewport = soup.find("meta", attrs={"name": "viewport"})
        audit.viewport_meta = viewport is not None

        # Robots
        robots = soup.find("meta", attrs={"name": "robots"})
        if robots and robots.get("content"):
            audit.robots_meta = robots["content"]

        # Language
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            audit.language = html_tag["lang"]

    def _analyze_headings(self, soup, audit: PageAudit):
        """Extract heading structure."""
        audit.h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
        audit.h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
        audit.h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")]
        audit.heading_count = len(audit.h1_tags) + len(audit.h2_tags) + len(audit.h3_tags)
        for tag in ["h4", "h5", "h6"]:
            audit.heading_count += len(soup.find_all(tag))

    def _analyze_content(self, soup, html: str, audit: PageAudit):
        """Analyze text content quality."""
        # Remove scripts and styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        words = text.split()
        audit.word_count = len(words)

        html_len = len(html)
        text_len = len(text)
        audit.text_to_html_ratio = (text_len / html_len * 100) if html_len > 0 else 0

    def _analyze_images(self, soup, audit: PageAudit):
        """Check image alt text coverage."""
        images = soup.find_all("img")
        audit.total_images = len(images)
        missing_alt = [img for img in images if not img.get("alt") or img["alt"].strip() == ""]
        audit.images_without_alt = len(missing_alt)
        audit.alt_text_coverage = (
            ((audit.total_images - audit.images_without_alt) / audit.total_images * 100)
            if audit.total_images > 0 else 100.0
        )

    def _analyze_links(self, soup, page_url: str, audit: PageAudit):
        """Count internal vs external links."""
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc == self.domain or parsed.netloc == "":
                audit.internal_links += 1
            else:
                audit.external_links += 1

    def _analyze_structured_data(self, soup, html: str, audit: PageAudit):
        """Check for JSON-LD or microdata."""
        ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        if ld_scripts:
            audit.has_structured_data = True
            import json
            for script in ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and "@type" in data:
                        audit.structured_data_types.append(data["@type"])
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "@type" in item:
                                audit.structured_data_types.append(item["@type"])
                except Exception:
                    pass

        # Check for microdata
        if soup.find(attrs={"itemscope": True}):
            audit.has_structured_data = True

    def _analyze_og_tags(self, soup, audit: PageAudit):
        """Check Open Graph tags."""
        og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
        if og_tags:
            audit.has_og_tags = True
            for tag in og_tags:
                prop = tag.get("property", "")
                content = tag.get("content", "")
                audit.og_tags[prop] = content

    def _run_issue_checks(self, audit: PageAudit):
        """Score the page and flag issues."""
        # Title checks
        if not audit.title:
            audit.issues.append({"severity": "critical", "issue": "Missing Title", "detail": "Page has no <title> tag"})
            audit.score -= 15
        elif audit.title_length < 30:
            audit.issues.append({"severity": "warning", "issue": "Short Title", "detail": f"Title is {audit.title_length} chars (aim for 50-60)"})
            audit.score -= 5
        elif audit.title_length > 60:
            audit.issues.append({"severity": "warning", "issue": "Long Title", "detail": f"Title is {audit.title_length} chars (may truncate in SERPs)"})
            audit.score -= 3

        # Meta description checks
        if not audit.meta_description:
            audit.issues.append({"severity": "critical", "issue": "Missing Meta Description", "detail": "No meta description found"})
            audit.score -= 12
        elif audit.meta_description_length < 70:
            audit.issues.append({"severity": "warning", "issue": "Short Meta Description", "detail": f"{audit.meta_description_length} chars (aim for 150-160)"})
            audit.score -= 4
        elif audit.meta_description_length > 160:
            audit.issues.append({"severity": "info", "issue": "Long Meta Description", "detail": f"{audit.meta_description_length} chars (may truncate)"})
            audit.score -= 2

        # H1 checks
        if len(audit.h1_tags) == 0:
            audit.issues.append({"severity": "critical", "issue": "Missing H1", "detail": "Page has no H1 tag"})
            audit.score -= 10
        elif len(audit.h1_tags) > 1:
            audit.issues.append({"severity": "warning", "issue": "Multiple H1 Tags", "detail": f"Found {len(audit.h1_tags)} H1 tags (use only one)"})
            audit.score -= 5

        # Content length
        if audit.word_count < 300:
            audit.issues.append({"severity": "warning", "issue": "Thin Content", "detail": f"Only {audit.word_count} words (aim for 800+)"})
            audit.score -= 8
        elif audit.word_count < 600:
            audit.issues.append({"severity": "info", "issue": "Light Content", "detail": f"{audit.word_count} words — could benefit from more depth"})
            audit.score -= 3

        # Image alt text
        if audit.total_images > 0 and audit.alt_text_coverage < 80:
            audit.issues.append({
                "severity": "warning",
                "issue": "Missing Alt Text",
                "detail": f"{audit.images_without_alt}/{audit.total_images} images lack alt text ({audit.alt_text_coverage:.0f}% coverage)"
            })
            audit.score -= 5

        # Canonical
        if not audit.has_canonical:
            audit.issues.append({"severity": "info", "issue": "No Canonical Tag", "detail": "Add canonical to prevent duplicate content"})
            audit.score -= 3

        # Viewport
        if not audit.viewport_meta:
            audit.issues.append({"severity": "critical", "issue": "No Viewport Meta", "detail": "Missing viewport meta — poor mobile experience"})
            audit.score -= 10

        # Structured data
        if not audit.has_structured_data:
            audit.issues.append({"severity": "info", "issue": "No Structured Data", "detail": "Add JSON-LD schema for rich snippets"})
            audit.score -= 3

        # OG tags
        if not audit.has_og_tags:
            audit.issues.append({"severity": "info", "issue": "No Open Graph Tags", "detail": "Add OG tags for better social sharing"})
            audit.score -= 2

        # Page size
        if audit.page_size_bytes > 3_000_000:
            audit.issues.append({"severity": "warning", "issue": "Large Page Size", "detail": f"{audit.page_size_bytes/1024:.0f}KB — optimize for speed"})
            audit.score -= 5

        # Load time
        if audit.load_time_ms > 3000:
            audit.issues.append({"severity": "warning", "issue": "Slow Page", "detail": f"{audit.load_time_ms:.0f}ms load time (aim for <2s)"})
            audit.score -= 5

        # Text-to-HTML ratio
        if audit.text_to_html_ratio < 10:
            audit.issues.append({"severity": "info", "issue": "Low Text Ratio", "detail": f"{audit.text_to_html_ratio:.1f}% text-to-HTML (aim for >25%)"})
            audit.score -= 2

        # Internal links
        if audit.internal_links < 3:
            audit.issues.append({"severity": "warning", "issue": "Few Internal Links", "detail": f"Only {audit.internal_links} internal links — add more for link equity"})
            audit.score -= 4

        audit.score = max(0, audit.score)

    def _build_summary(self, audits: List[PageAudit]) -> Dict[str, Any]:
        """Build a site-wide summary from all page audits."""
        if not audits:
            return {"pages": [], "summary": {}, "crawled_at": datetime.now().isoformat()}

        page_dicts = [a.to_dict() for a in audits]

        total_issues = sum(len(a.issues) for a in audits)
        critical_issues = sum(1 for a in audits for i in a.issues if i["severity"] == "critical")
        warning_issues = sum(1 for a in audits for i in a.issues if i["severity"] == "warning")
        info_issues = sum(1 for a in audits for i in a.issues if i["severity"] == "info")

        avg_score = sum(a.score for a in audits) / len(audits)
        avg_word_count = sum(a.word_count for a in audits) / len(audits)
        avg_load_time = sum(a.load_time_ms for a in audits) / len(audits)
        total_images = sum(a.total_images for a in audits)
        total_missing_alt = sum(a.images_without_alt for a in audits)

        pages_missing_title = sum(1 for a in audits if not a.title)
        pages_missing_desc = sum(1 for a in audits if not a.meta_description)
        pages_missing_h1 = sum(1 for a in audits if not a.h1_tags)
        pages_missing_canonical = sum(1 for a in audits if not a.has_canonical)
        pages_with_schema = sum(1 for a in audits if a.has_structured_data)
        pages_with_og = sum(1 for a in audits if a.has_og_tags)
        pages_mobile_ready = sum(1 for a in audits if a.viewport_meta)

        # Aggregate common issues
        issue_counts: Dict[str, int] = {}
        for a in audits:
            for issue in a.issues:
                key = issue["issue"]
                issue_counts[key] = issue_counts.get(key, 0) + 1
        top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "pages": sorted(page_dicts, key=lambda p: p["score"]),
            "summary": {
                "pages_crawled": len(audits),
                "avg_seo_score": round(avg_score, 1),
                "total_issues": total_issues,
                "critical_issues": critical_issues,
                "warning_issues": warning_issues,
                "info_issues": info_issues,
                "avg_word_count": round(avg_word_count),
                "avg_load_time_ms": round(avg_load_time, 1),
                "total_images": total_images,
                "images_missing_alt": total_missing_alt,
                "alt_coverage_pct": round(
                    ((total_images - total_missing_alt) / total_images * 100)
                    if total_images > 0 else 100, 1
                ),
                "pages_missing_title": pages_missing_title,
                "pages_missing_meta_desc": pages_missing_desc,
                "pages_missing_h1": pages_missing_h1,
                "pages_missing_canonical": pages_missing_canonical,
                "pages_with_schema": pages_with_schema,
                "pages_with_og": pages_with_og,
                "pages_mobile_ready": pages_mobile_ready,
                "top_issues": [{"issue": k, "count": v} for k, v in top_issues],
            },
            "crawled_at": datetime.now().isoformat(),
        }
