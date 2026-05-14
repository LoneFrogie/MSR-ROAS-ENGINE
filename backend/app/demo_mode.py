"""
Demo Mode — replaces real API connectors with mock data generators.
Allows the full engine to run without any live credentials.
"""
import random
import logging
from datetime import date, timedelta
from typing import List, Dict
from unittest.mock import AsyncMock

from app.models.schemas import (
    UnifiedCampaign, Platform, CampaignStatus, SEOSiteHealth
)

logger = logging.getLogger("roas_engine.demo")

random.seed(42)

GOOGLE_TEMPLATES = [
    {"name": "Brand - Search",        "budget": 500,  "roas_range": (5.0, 8.0),  "conv": (80, 150)},
    {"name": "Generic - Search",      "budget": 800,  "roas_range": (3.0, 5.5),  "conv": (40, 100)},
    {"name": "Shopping - All Products","budget": 1200, "roas_range": (4.0, 7.0),  "conv": (60, 130)},
    {"name": "Retargeting - RLSA",    "budget": 400,  "roas_range": (6.0, 10.0), "conv": (50, 90)},
    {"name": "Competitor - Search",   "budget": 300,  "roas_range": (1.2, 3.0),  "conv": (10, 40)},
    {"name": "Display - Prospecting", "budget": 600,  "roas_range": (0.5, 2.0),  "conv": (5, 25)},
    {"name": "YouTube - Brand",       "budget": 350,  "roas_range": (1.8, 4.0),  "conv": (15, 50)},
    {"name": "Performance Max",       "budget": 1000, "roas_range": (3.5, 6.0),  "conv": (70, 140)},
    {"name": "DSA - All Pages",       "budget": 250,  "roas_range": (2.0, 4.5),  "conv": (20, 60)},
    {"name": "RLSA - Cart Abandoners","budget": 450,  "roas_range": (7.0, 12.0), "conv": (90, 180)},
    {"name": "Low-Performer Test",    "budget": 200,  "roas_range": (0.3, 0.9),  "conv": (2, 10)},
    {"name": "New Product Launch",    "budget": 700,  "roas_range": (1.5, 3.5),  "conv": (20, 55)},
]

META_TEMPLATES = [
    {"name": "Prospecting - TOF",       "budget": 600,  "roas_range": (2.5, 5.0),  "conv": (30, 80)},
    {"name": "Retargeting - MOF",       "budget": 450,  "roas_range": (4.0, 8.0),  "conv": (50, 100)},
    {"name": "Lookalike - Purchasers",  "budget": 700,  "roas_range": (3.5, 6.5),  "conv": (45, 95)},
    {"name": "Dynamic Product Ads",     "budget": 900,  "roas_range": (5.0, 9.0),  "conv": (80, 160)},
    {"name": "Catalog - Retargeting",   "budget": 500,  "roas_range": (6.0, 11.0), "conv": (70, 130)},
    {"name": "Broad - Video Views",     "budget": 300,  "roas_range": (0.8, 2.5),  "conv": (5, 20)},
    {"name": "Interest - Skincare",     "budget": 400,  "roas_range": (1.5, 4.0),  "conv": (15, 50)},
    {"name": "Lookalike - High LTV",    "budget": 550,  "roas_range": (4.5, 7.5),  "conv": (60, 110)},
    {"name": "Brand Awareness",         "budget": 200,  "roas_range": (0.4, 1.2),  "conv": (2, 12)},
    {"name": "Conversion - BOFU",       "budget": 800,  "roas_range": (5.5, 10.0), "conv": (90, 170)},
]

GEO_COUNTRIES = [
    {"code": "MY", "name": "Malaysia",    "roas_range": (3.5, 6.5)},
    {"code": "SG", "name": "Singapore",   "roas_range": (4.0, 8.0)},
    {"code": "US", "name": "United States","roas_range": (5.0, 9.0)},
    {"code": "GB", "name": "United Kingdom","roas_range": (4.5, 7.0)},
    {"code": "AU", "name": "Australia",   "roas_range": (3.0, 6.0)},
    {"code": "ID", "name": "Indonesia",   "roas_range": (1.5, 3.5)},
    {"code": "TH", "name": "Thailand",    "roas_range": (1.2, 2.5)},
    {"code": "PH", "name": "Philippines", "roas_range": (0.8, 2.0)},
    {"code": "IN", "name": "India",       "roas_range": (0.5, 1.5)},
    {"code": "VN", "name": "Vietnam",     "roas_range": (0.3, 1.0)},
    {"code": "HK", "name": "Hong Kong",   "roas_range": (5.5, 10.0)},
    {"code": "JP", "name": "Japan",       "roas_range": (2.0, 4.5)},
]


def _gen_campaign(tmpl, platform, idx, lookback=14):
    roas = random.uniform(*tmpl["roas_range"])
    conversions = random.randint(*tmpl["conv"])
    spend = tmpl["budget"] * lookback * random.uniform(0.85, 1.0)
    revenue = spend * roas
    clicks = int(conversions * random.uniform(25, 60))
    impressions = int(clicks * random.uniform(8, 20))
    prefix = "g" if platform == Platform.GOOGLE_ADS else "m"
    return UnifiedCampaign(
        platform=platform,
        platform_campaign_id=f"{prefix}_{idx+1:04d}",
        name=tmpl["name"],
        status=CampaignStatus.ACTIVE,
        daily_budget=float(tmpl["budget"]),
        spend=round(spend, 2),
        revenue=round(revenue, 2),
        conversions=conversions,
        clicks=clicks,
        impressions=impressions,
    )


def _gen_geo(platform_label):
    geo = []
    for c in GEO_COUNTRIES:
        roas = random.uniform(*c["roas_range"])
        spend = random.uniform(50, 500)
        geo.append({
            "country": c["code"],
            "country_criterion_id": c["code"],
            "campaign_id": "ALL",
            "campaign_name": "ALL",
            "spend": round(spend, 2),
            "revenue": round(spend * roas, 2),
            "conversions": random.randint(2, 50),
            "clicks": random.randint(30, 400),
            "platform": platform_label,
        })
    return geo


def _gen_organic_queries():
    queries = [
        {"query": "best skincare products",       "position": 1.2,  "impressions": 8000,  "clicks": 900,  "ctr": 0.1125, "page": "https://brand.com/best-skincare"},
        {"query": "moisturizer for dry skin",      "position": 2.5,  "impressions": 5000,  "clicks": 450,  "ctr": 0.090,  "page": "https://brand.com/moisturizers"},
        {"query": "anti aging serum",              "position": 5.1,  "impressions": 4500,  "clicks": 180,  "ctr": 0.040,  "page": "https://brand.com/anti-aging"},
        {"query": "vitamin c serum review",        "position": 8.3,  "impressions": 3200,  "clicks": 96,   "ctr": 0.030,  "page": "https://brand.com/blog/vitamin-c-review"},
        {"query": "natural skincare routine",      "position": 12.4, "impressions": 2800,  "clicks": 42,   "ctr": 0.015,  "page": "https://brand.com/blog/natural-routine"},
        {"query": "buy sunscreen online",          "position": 15.7, "impressions": 2100,  "clicks": 21,   "ctr": 0.010,  "page": "https://brand.com/sunscreen"},
        {"query": "retinol cream benefits",        "position": 18.0, "impressions": 1800,  "clicks": 9,    "ctr": 0.005,  "page": "https://brand.com/blog/retinol-benefits"},
        {"query": "hyaluronic acid serum",         "position": 3.2,  "impressions": 6200,  "clicks": 620,  "ctr": 0.100,  "page": "https://brand.com/hyaluronic-acid"},
        {"query": "brand.com reviews",             "position": 1.0,  "impressions": 3000,  "clicks": 870,  "ctr": 0.290,  "page": "https://brand.com/reviews"},
        {"query": "niacinamide serum",             "position": 6.8,  "impressions": 2500,  "clicks": 75,   "ctr": 0.030,  "page": "https://brand.com/niacinamide"},
        {"query": "korean skincare products",      "position": 4.5,  "impressions": 7200,  "clicks": 360,  "ctr": 0.050,  "page": "https://brand.com/korean-skincare"},
        {"query": "organic face wash",             "position": 9.2,  "impressions": 3100,  "clicks": 62,   "ctr": 0.020,  "page": "https://brand.com/face-wash"},
        {"query": "best eye cream 2026",           "position": 7.1,  "impressions": 4800,  "clicks": 144,  "ctr": 0.030,  "page": "https://brand.com/eye-cream"},
        {"query": "collagen supplements review",   "position": 14.3, "impressions": 2600,  "clicks": 26,   "ctr": 0.010,  "page": "https://brand.com/blog/collagen"},
        {"query": "how to reduce wrinkles",        "position": 11.5, "impressions": 5400,  "clicks": 54,   "ctr": 0.010,  "page": "https://brand.com/blog/reduce-wrinkles"},
        {"query": "spf 50 moisturizer",            "position": 3.8,  "impressions": 3900,  "clicks": 312,  "ctr": 0.080,  "page": "https://brand.com/spf-moisturizer"},
        {"query": "affordable skincare brands",    "position": 16.2, "impressions": 6100,  "clicks": 30,   "ctr": 0.005,  "page": "https://brand.com/about"},
        {"query": "peptide serum for face",        "position": 19.8, "impressions": 1500,  "clicks": 8,    "ctr": 0.005,  "page": "https://brand.com/peptide-serum"},
        {"query": "dark spot corrector",           "position": 10.2, "impressions": 4100,  "clicks": 82,   "ctr": 0.020,  "page": "https://brand.com/dark-spot"},
        {"query": "skincare gift set",             "position": 2.1,  "impressions": 2200,  "clicks": 330,  "ctr": 0.150,  "page": "https://brand.com/gift-sets"},
    ]
    return queries


def _gen_search_terms():
    terms = [
        {"search_term": "best skincare products",   "campaign": "Generic - Search",  "spend": 120, "revenue": 480,  "conversions": 12, "clicks": 60,  "impressions": 1200},
        {"search_term": "moisturizer for dry skin",  "campaign": "Generic - Search",  "spend": 95,  "revenue": 380,  "conversions": 9,  "clicks": 48,  "impressions": 960},
        {"search_term": "anti aging serum",          "campaign": "Generic - Search",  "spend": 200, "revenue": 600,  "conversions": 15, "clicks": 100, "impressions": 2000},
        {"search_term": "buy sunscreen online",      "campaign": "Shopping - All",    "spend": 150, "revenue": 900,  "conversions": 22, "clicks": 75,  "impressions": 1500},
        {"search_term": "retinol night cream",       "campaign": "Generic - Search",  "spend": 80,  "revenue": 160,  "conversions": 4,  "clicks": 40,  "impressions": 800},
        {"search_term": "hyaluronic acid serum",     "campaign": "Brand - Search",    "spend": 60,  "revenue": 600,  "conversions": 18, "clicks": 30,  "impressions": 600},
        {"search_term": "cheap face moisturizer",    "campaign": "Generic - Search",  "spend": 110, "revenue": 110,  "conversions": 3,  "clicks": 55,  "impressions": 1100},
        {"search_term": "korean skincare products",  "campaign": "Generic - Search",  "spend": 180, "revenue": 720,  "conversions": 18, "clicks": 90,  "impressions": 1800},
        {"search_term": "niacinamide benefits",      "campaign": "Generic - Search",  "spend": 65,  "revenue": 325,  "conversions": 8,  "clicks": 32,  "impressions": 650},
        {"search_term": "peptide face cream",        "campaign": "Shopping - All",    "spend": 140, "revenue": 420,  "conversions": 10, "clicks": 70,  "impressions": 1400},
        {"search_term": "best eye cream",            "campaign": "Generic - Search",  "spend": 175, "revenue": 875,  "conversions": 21, "clicks": 87,  "impressions": 1750},
        {"search_term": "spf moisturizer daily",     "campaign": "Brand - Search",    "spend": 55,  "revenue": 440,  "conversions": 11, "clicks": 27,  "impressions": 550},
        {"search_term": "collagen face cream",       "campaign": "Generic - Search",  "spend": 90,  "revenue": 180,  "conversions": 4,  "clicks": 45,  "impressions": 900},
        {"search_term": "organic cleanser",          "campaign": "Shopping - All",    "spend": 130, "revenue": 390,  "conversions": 9,  "clicks": 65,  "impressions": 1300},
        {"search_term": "dark circle treatment",     "campaign": "Generic - Search",  "spend": 70,  "revenue": 70,   "conversions": 2,  "clicks": 35,  "impressions": 700},
        {"search_term": "gift set skincare luxury",  "campaign": "Brand - Search",    "spend": 45,  "revenue": 675,  "conversions": 15, "clicks": 22,  "impressions": 450},
    ]
    return terms


def _gen_query_page_matrix():
    """Generate query-page matrix for cannibalization detection."""
    return [
        {"query": "best skincare products", "page": "https://brand.com/best-skincare",       "impressions": 5500, "clicks": 650, "position": 1.2},
        {"query": "best skincare products", "page": "https://brand.com/blog/top-10-skincare", "impressions": 2500, "clicks": 120, "position": 4.8},
        {"query": "anti aging serum",       "page": "https://brand.com/anti-aging",           "impressions": 3200, "clicks": 140, "position": 5.1},
        {"query": "anti aging serum",       "page": "https://brand.com/blog/retinol-benefits","impressions": 1300, "clicks": 26,  "position": 12.5},
        {"query": "hyaluronic acid serum",  "page": "https://brand.com/hyaluronic-acid",      "impressions": 4800, "clicks": 480, "position": 3.2},
        {"query": "hyaluronic acid serum",  "page": "https://brand.com/moisturizers",         "impressions": 1400, "clicks": 42,  "position": 9.6},
        {"query": "korean skincare",        "page": "https://brand.com/korean-skincare",      "impressions": 5100, "clicks": 255, "position": 4.5},
        {"query": "korean skincare",        "page": "https://brand.com/best-skincare",        "impressions": 2100, "clicks": 63,  "position": 8.2},
        {"query": "moisturizer for dry skin","page": "https://brand.com/moisturizers",        "impressions": 5000, "clicks": 450, "position": 2.5},
        {"query": "niacinamide serum",      "page": "https://brand.com/niacinamide",          "impressions": 2500, "clicks": 75,  "position": 6.8},
        {"query": "spf 50 moisturizer",     "page": "https://brand.com/spf-moisturizer",     "impressions": 3900, "clicks": 312, "position": 3.8},
        {"query": "dark spot corrector",    "page": "https://brand.com/dark-spot",            "impressions": 4100, "clicks": 82,  "position": 10.2},
        {"query": "dark spot corrector",    "page": "https://brand.com/niacinamide",          "impressions": 1200, "clicks": 18,  "position": 14.1},
        {"query": "vitamin c serum review", "page": "https://brand.com/blog/vitamin-c-review","impressions": 3200, "clicks": 96,  "position": 8.3},
    ]


def _gen_page_performance():
    """Generate per-page performance data for SEO analysis."""
    return [
        {"page": "https://brand.com/best-skincare",        "clicks": 770,  "impressions": 10100, "ctr": 0.076, "position": 2.8,  "queries": 45},
        {"page": "https://brand.com/moisturizers",          "clicks": 492,  "impressions": 6400,  "ctr": 0.077, "position": 3.5,  "queries": 28},
        {"page": "https://brand.com/hyaluronic-acid",       "clicks": 522,  "impressions": 6200,  "ctr": 0.084, "position": 4.1,  "queries": 15},
        {"page": "https://brand.com/anti-aging",            "clicks": 166,  "impressions": 4500,  "ctr": 0.037, "position": 6.2,  "queries": 32},
        {"page": "https://brand.com/korean-skincare",       "clicks": 318,  "impressions": 7200,  "ctr": 0.044, "position": 5.0,  "queries": 22},
        {"page": "https://brand.com/reviews",               "clicks": 870,  "impressions": 3000,  "ctr": 0.290, "position": 1.0,  "queries": 8},
        {"page": "https://brand.com/spf-moisturizer",       "clicks": 312,  "impressions": 3900,  "ctr": 0.080, "position": 3.8,  "queries": 12},
        {"page": "https://brand.com/gift-sets",             "clicks": 330,  "impressions": 2200,  "ctr": 0.150, "position": 2.1,  "queries": 6},
        {"page": "https://brand.com/niacinamide",           "clicks": 93,   "impressions": 3700,  "ctr": 0.025, "position": 8.4,  "queries": 18},
        {"page": "https://brand.com/blog/vitamin-c-review", "clicks": 96,   "impressions": 3200,  "ctr": 0.030, "position": 8.3,  "queries": 10},
        {"page": "https://brand.com/eye-cream",             "clicks": 144,  "impressions": 4800,  "ctr": 0.030, "position": 7.1,  "queries": 14},
        {"page": "https://brand.com/sunscreen",             "clicks": 21,   "impressions": 2100,  "ctr": 0.010, "position": 15.7, "queries": 9},
        {"page": "https://brand.com/dark-spot",             "clicks": 100,  "impressions": 5300,  "ctr": 0.019, "position": 11.0, "queries": 20},
        {"page": "https://brand.com/face-wash",             "clicks": 62,   "impressions": 3100,  "ctr": 0.020, "position": 9.2,  "queries": 11},
        {"page": "https://brand.com/blog/natural-routine",  "clicks": 42,   "impressions": 2800,  "ctr": 0.015, "position": 12.4, "queries": 7},
        {"page": "https://brand.com/blog/retinol-benefits", "clicks": 35,   "impressions": 3100,  "ctr": 0.011, "position": 15.2, "queries": 12},
        {"page": "https://brand.com/blog/collagen",         "clicks": 26,   "impressions": 2600,  "ctr": 0.010, "position": 14.3, "queries": 5},
        {"page": "https://brand.com/peptide-serum",         "clicks": 8,    "impressions": 1500,  "ctr": 0.005, "position": 19.8, "queries": 4},
        {"page": "https://brand.com/about",                 "clicks": 30,   "impressions": 6100,  "ctr": 0.005, "position": 16.2, "queries": 3},
    ]


def _gen_competitor_data():
    """Generate competitor keyword overlap data."""
    return [
        {"competitor": "theordinary.com",   "overlap_keywords": 45, "our_wins": 18, "their_wins": 22, "ties": 5,  "gap_keywords": ["caffeine solution", "aha bha peel", "squalane cleanser"]},
        {"competitor": "paulaschoice.com",  "overlap_keywords": 38, "our_wins": 15, "their_wins": 18, "ties": 5,  "gap_keywords": ["bha exfoliant", "retinol body treatment", "omega moisturizer"]},
        {"competitor": "cerave.com",        "overlap_keywords": 52, "our_wins": 12, "their_wins": 35, "ties": 5,  "gap_keywords": ["ceramide cleanser", "healing ointment", "am facial moisturizer"]},
        {"competitor": "skincarerx.com",    "overlap_keywords": 28, "our_wins": 10, "their_wins": 14, "ties": 4,  "gap_keywords": ["professional skincare", "medical grade products"]},
        {"competitor": "sephora.com",       "overlap_keywords": 61, "our_wins": 8,  "their_wins": 48, "ties": 5,  "gap_keywords": ["luxury skincare sets", "new arrivals skincare", "mini skincare"]},
    ]


def _gen_site_crawl():
    """Generate realistic demo on-page SEO crawl results."""
    pages = [
        {
            "url": "https://brand.com/",
            "status_code": 200, "load_time_ms": 1240, "page_size_kb": 285.3,
            "title": "Brand - Premium Skincare Products | Shop Online",
            "title_length": 50, "meta_description": "Discover premium skincare products backed by science. Shop moisturizers, serums, and sunscreens with free shipping on orders over $50.",
            "meta_description_length": 132, "canonical_url": "https://brand.com/", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Premium Skincare For Every Skin Type"],
            "h2_tags": ["Best Sellers", "New Arrivals", "Skincare Routines", "Customer Reviews"],
            "heading_count": 8, "word_count": 1450, "text_to_html_ratio": 28.5,
            "total_images": 18, "images_without_alt": 2, "alt_text_coverage": 88.9,
            "internal_links": 42, "external_links": 3,
            "has_og_tags": True, "og_tags": {"og:title": "Brand - Premium Skincare", "og:type": "website", "og:image": "https://brand.com/og-home.jpg"},
            "has_structured_data": True, "structured_data_types": ["Organization", "WebSite"],
            "issues": [
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "2/18 images lack alt text (88.9% coverage)"}
            ],
            "score": 95,
        },
        {
            "url": "https://brand.com/best-skincare",
            "status_code": 200, "load_time_ms": 980, "page_size_kb": 195.7,
            "title": "Best Skincare Products 2026 - Top Rated by Dermatologists",
            "title_length": 56, "meta_description": "Our top-rated skincare products chosen by dermatologists. From vitamin C serums to retinol creams, find your perfect routine.",
            "meta_description_length": 122, "canonical_url": "https://brand.com/best-skincare", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Best Skincare Products 2026"],
            "h2_tags": ["Top Moisturizers", "Best Serums", "Sunscreen Picks", "How We Test"],
            "heading_count": 11, "word_count": 2200, "text_to_html_ratio": 35.2,
            "total_images": 12, "images_without_alt": 0, "alt_text_coverage": 100.0,
            "internal_links": 28, "external_links": 5,
            "has_og_tags": True, "og_tags": {"og:title": "Best Skincare Products 2026", "og:type": "article"},
            "has_structured_data": True, "structured_data_types": ["Article", "BreadcrumbList"],
            "issues": [],
            "score": 100,
        },
        {
            "url": "https://brand.com/moisturizers",
            "status_code": 200, "load_time_ms": 1100, "page_size_kb": 220.1,
            "title": "Moisturizers for All Skin Types | Brand",
            "title_length": 41, "meta_description": "Shop our collection of moisturizers for dry, oily, and combination skin.",
            "meta_description_length": 71, "canonical_url": "https://brand.com/moisturizers", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Moisturizers"],
            "h2_tags": ["For Dry Skin", "For Oily Skin", "For Combination Skin"],
            "heading_count": 7, "word_count": 850, "text_to_html_ratio": 22.1,
            "total_images": 15, "images_without_alt": 4, "alt_text_coverage": 73.3,
            "internal_links": 22, "external_links": 1,
            "has_og_tags": True, "og_tags": {"og:title": "Moisturizers | Brand"},
            "has_structured_data": True, "structured_data_types": ["CollectionPage", "BreadcrumbList"],
            "issues": [
                {"severity": "warning", "issue": "Short Meta Description", "detail": "71 chars (aim for 150-160)"},
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "4/15 images lack alt text (73.3% coverage)"},
            ],
            "score": 86,
        },
        {
            "url": "https://brand.com/anti-aging",
            "status_code": 200, "load_time_ms": 1350, "page_size_kb": 310.5,
            "title": "Anti-Aging Skincare",
            "title_length": 19, "meta_description": "",
            "meta_description_length": 0, "canonical_url": "", "has_canonical": False,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Anti-Aging Products"],
            "h2_tags": ["Serums", "Creams"],
            "heading_count": 4, "word_count": 420, "text_to_html_ratio": 15.8,
            "total_images": 8, "images_without_alt": 3, "alt_text_coverage": 62.5,
            "internal_links": 12, "external_links": 0,
            "has_og_tags": False, "og_tags": {},
            "has_structured_data": False, "structured_data_types": [],
            "issues": [
                {"severity": "warning", "issue": "Short Title", "detail": "Title is 19 chars (aim for 50-60)"},
                {"severity": "critical", "issue": "Missing Meta Description", "detail": "No meta description found"},
                {"severity": "info", "issue": "No Canonical Tag", "detail": "Add canonical to prevent duplicate content"},
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "3/8 images lack alt text (62.5% coverage)"},
                {"severity": "info", "issue": "No Structured Data", "detail": "Add JSON-LD schema for rich snippets"},
                {"severity": "info", "issue": "No Open Graph Tags", "detail": "Add OG tags for better social sharing"},
                {"severity": "info", "issue": "Low Text Ratio", "detail": "15.8% text-to-HTML (aim for >25%)"},
            ],
            "score": 58,
        },
        {
            "url": "https://brand.com/hyaluronic-acid",
            "status_code": 200, "load_time_ms": 890, "page_size_kb": 175.2,
            "title": "Hyaluronic Acid Serum - Deep Hydration | Brand",
            "title_length": 46, "meta_description": "Our best-selling hyaluronic acid serum delivers deep hydration. Plumps fine lines, locks in moisture for 72 hours. Free shipping over $50.",
            "meta_description_length": 138, "canonical_url": "https://brand.com/hyaluronic-acid", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Hyaluronic Acid Serum"],
            "h2_tags": ["Benefits", "How to Use", "Ingredients", "Reviews"],
            "heading_count": 9, "word_count": 1800, "text_to_html_ratio": 32.4,
            "total_images": 6, "images_without_alt": 0, "alt_text_coverage": 100.0,
            "internal_links": 18, "external_links": 2,
            "has_og_tags": True, "og_tags": {"og:title": "Hyaluronic Acid Serum", "og:type": "product"},
            "has_structured_data": True, "structured_data_types": ["Product", "BreadcrumbList"],
            "issues": [],
            "score": 100,
        },
        {
            "url": "https://brand.com/korean-skincare",
            "status_code": 200, "load_time_ms": 1500, "page_size_kb": 380.2,
            "title": "Korean Skincare Products - K-Beauty Collection | Brand",
            "title_length": 54, "meta_description": "Explore our curated K-Beauty collection featuring the best Korean skincare products. Sheet masks, essences, and more.",
            "meta_description_length": 115, "canonical_url": "https://brand.com/korean-skincare", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Korean Skincare Collection", "K-Beauty Essentials"],
            "h2_tags": ["Sheet Masks", "Essences & Toners", "Moisturizers"],
            "heading_count": 8, "word_count": 1100, "text_to_html_ratio": 18.6,
            "total_images": 22, "images_without_alt": 6, "alt_text_coverage": 72.7,
            "internal_links": 35, "external_links": 4,
            "has_og_tags": True, "og_tags": {"og:title": "Korean Skincare | Brand"},
            "has_structured_data": True, "structured_data_types": ["CollectionPage"],
            "issues": [
                {"severity": "warning", "issue": "Multiple H1 Tags", "detail": "Found 2 H1 tags (use only one)"},
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "6/22 images lack alt text (72.7% coverage)"},
                {"severity": "warning", "issue": "Large Page Size", "detail": "380KB — optimize for speed"},
                {"severity": "info", "issue": "Low Text Ratio", "detail": "18.6% text-to-HTML (aim for >25%)"},
            ],
            "score": 78,
        },
        {
            "url": "https://brand.com/sunscreen",
            "status_code": 200, "load_time_ms": 2100, "page_size_kb": 150.8,
            "title": "Sunscreen",
            "title_length": 10, "meta_description": "Buy sunscreen.",
            "meta_description_length": 14, "canonical_url": "", "has_canonical": False,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": [],
            "h2_tags": ["SPF 30", "SPF 50"],
            "heading_count": 2, "word_count": 180, "text_to_html_ratio": 12.3,
            "total_images": 5, "images_without_alt": 5, "alt_text_coverage": 0.0,
            "internal_links": 4, "external_links": 0,
            "has_og_tags": False, "og_tags": {},
            "has_structured_data": False, "structured_data_types": [],
            "issues": [
                {"severity": "warning", "issue": "Short Title", "detail": "Title is 10 chars (aim for 50-60)"},
                {"severity": "warning", "issue": "Short Meta Description", "detail": "14 chars (aim for 150-160)"},
                {"severity": "critical", "issue": "Missing H1", "detail": "Page has no H1 tag"},
                {"severity": "warning", "issue": "Thin Content", "detail": "Only 180 words (aim for 800+)"},
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "5/5 images lack alt text (0% coverage)"},
                {"severity": "info", "issue": "No Canonical Tag", "detail": "Add canonical to prevent duplicate content"},
                {"severity": "info", "issue": "No Structured Data", "detail": "Add JSON-LD schema for rich snippets"},
                {"severity": "info", "issue": "No Open Graph Tags", "detail": "Add OG tags for better social sharing"},
                {"severity": "info", "issue": "Low Text Ratio", "detail": "12.3% text-to-HTML (aim for >25%)"},
                {"severity": "warning", "issue": "Few Internal Links", "detail": "Only 4 internal links — add more"},
            ],
            "score": 32,
        },
        {
            "url": "https://brand.com/blog/vitamin-c-review",
            "status_code": 200, "load_time_ms": 750, "page_size_kb": 120.4,
            "title": "Vitamin C Serum Review 2026 - Does It Actually Work? | Brand Blog",
            "title_length": 64, "meta_description": "We tested 10 vitamin C serums over 8 weeks. See our honest review with before/after photos and dermatologist recommendations.",
            "meta_description_length": 123, "canonical_url": "https://brand.com/blog/vitamin-c-review", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Vitamin C Serum Review 2026"],
            "h2_tags": ["What Is Vitamin C?", "Our Testing Method", "Results", "Top Picks", "FAQ"],
            "heading_count": 12, "word_count": 3200, "text_to_html_ratio": 42.1,
            "total_images": 8, "images_without_alt": 1, "alt_text_coverage": 87.5,
            "internal_links": 15, "external_links": 8,
            "has_og_tags": True, "og_tags": {"og:title": "Vitamin C Serum Review 2026", "og:type": "article"},
            "has_structured_data": True, "structured_data_types": ["Article", "FAQPage", "BreadcrumbList"],
            "issues": [
                {"severity": "info", "issue": "Long Title", "detail": "Title is 64 chars (may truncate in SERPs)"},
            ],
            "score": 95,
        },
        {
            "url": "https://brand.com/blog/natural-routine",
            "status_code": 200, "load_time_ms": 680, "page_size_kb": 95.2,
            "title": "Natural Skincare Routine - Step by Step Guide | Brand Blog",
            "title_length": 57, "meta_description": "Build a natural skincare routine that works. Our step-by-step guide covers cleansing, toning, moisturizing, and sun protection with clean ingredients.",
            "meta_description_length": 152, "canonical_url": "https://brand.com/blog/natural-routine", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["The Complete Natural Skincare Routine"],
            "h2_tags": ["Step 1: Cleanse", "Step 2: Tone", "Step 3: Serum", "Step 4: Moisturize", "Step 5: SPF"],
            "heading_count": 10, "word_count": 2800, "text_to_html_ratio": 45.3,
            "total_images": 5, "images_without_alt": 0, "alt_text_coverage": 100.0,
            "internal_links": 12, "external_links": 3,
            "has_og_tags": True, "og_tags": {"og:title": "Natural Skincare Routine Guide"},
            "has_structured_data": True, "structured_data_types": ["Article", "HowTo", "BreadcrumbList"],
            "issues": [],
            "score": 100,
        },
        {
            "url": "https://brand.com/spf-moisturizer",
            "status_code": 200, "load_time_ms": 920, "page_size_kb": 168.9,
            "title": "SPF 50 Moisturizer - Daily Sun Protection | Brand",
            "title_length": 49, "meta_description": "Lightweight SPF 50 moisturizer that protects and hydrates. No white cast, suitable for all skin tones.",
            "meta_description_length": 101, "canonical_url": "https://brand.com/spf-moisturizer", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["SPF 50 Daily Moisturizer"],
            "h2_tags": ["Key Benefits", "How to Apply", "Ingredients", "Customer Reviews"],
            "heading_count": 8, "word_count": 1400, "text_to_html_ratio": 30.1,
            "total_images": 7, "images_without_alt": 1, "alt_text_coverage": 85.7,
            "internal_links": 16, "external_links": 1,
            "has_og_tags": True, "og_tags": {"og:title": "SPF 50 Moisturizer", "og:type": "product"},
            "has_structured_data": True, "structured_data_types": ["Product", "BreadcrumbList"],
            "issues": [],
            "score": 97,
        },
        {
            "url": "https://brand.com/gift-sets",
            "status_code": 200, "load_time_ms": 1050, "page_size_kb": 245.6,
            "title": "Skincare Gift Sets - Perfect Presents | Brand",
            "title_length": 45, "meta_description": "Find the perfect skincare gift set for any occasion. Curated collections for her, him, and skincare beginners.",
            "meta_description_length": 109, "canonical_url": "https://brand.com/gift-sets", "has_canonical": True,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["Skincare Gift Sets"],
            "h2_tags": ["For Her", "For Him", "Starter Kits", "Luxury Sets"],
            "heading_count": 7, "word_count": 950, "text_to_html_ratio": 24.5,
            "total_images": 14, "images_without_alt": 3, "alt_text_coverage": 78.6,
            "internal_links": 20, "external_links": 0,
            "has_og_tags": True, "og_tags": {"og:title": "Skincare Gift Sets | Brand"},
            "has_structured_data": True, "structured_data_types": ["CollectionPage"],
            "issues": [
                {"severity": "warning", "issue": "Missing Alt Text", "detail": "3/14 images lack alt text (78.6% coverage)"},
            ],
            "score": 90,
        },
        {
            "url": "https://brand.com/about",
            "status_code": 200, "load_time_ms": 580, "page_size_kb": 85.3,
            "title": "About Us | Brand",
            "title_length": 16, "meta_description": "",
            "meta_description_length": 0, "canonical_url": "", "has_canonical": False,
            "viewport_meta": True, "robots_meta": "", "language": "en",
            "h1_tags": ["About Brand"],
            "h2_tags": ["Our Story", "Our Mission"],
            "heading_count": 4, "word_count": 520, "text_to_html_ratio": 38.2,
            "total_images": 3, "images_without_alt": 1, "alt_text_coverage": 66.7,
            "internal_links": 8, "external_links": 5,
            "has_og_tags": False, "og_tags": {},
            "has_structured_data": False, "structured_data_types": [],
            "issues": [
                {"severity": "warning", "issue": "Short Title", "detail": "Title is 16 chars (aim for 50-60)"},
                {"severity": "critical", "issue": "Missing Meta Description", "detail": "No meta description found"},
                {"severity": "info", "issue": "No Canonical Tag", "detail": "Add canonical to prevent duplicate content"},
                {"severity": "info", "issue": "No Structured Data", "detail": "Add JSON-LD schema for rich snippets"},
                {"severity": "info", "issue": "No Open Graph Tags", "detail": "Add OG tags for better social sharing"},
            ],
            "score": 68,
        },
    ]

    # Build summary from pages
    total_issues = sum(len(p["issues"]) for p in pages)
    critical = sum(1 for p in pages for i in p["issues"] if i["severity"] == "critical")
    warnings = sum(1 for p in pages for i in p["issues"] if i["severity"] == "warning")
    infos = sum(1 for p in pages for i in p["issues"] if i["severity"] == "info")
    avg_score = sum(p["score"] for p in pages) / len(pages)
    avg_wc = sum(p["word_count"] for p in pages) / len(pages)
    avg_load = sum(p["load_time_ms"] for p in pages) / len(pages)
    total_imgs = sum(p["total_images"] for p in pages)
    missing_alt = sum(p["images_without_alt"] for p in pages)

    # Aggregate top issues
    issue_counts = {}
    for p in pages:
        for i in p["issues"]:
            key = i["issue"]
            issue_counts[key] = issue_counts.get(key, 0) + 1
    top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    from datetime import datetime
    return {
        "pages": sorted(pages, key=lambda p: p["score"]),
        "summary": {
            "pages_crawled": len(pages),
            "avg_seo_score": round(avg_score, 1),
            "total_issues": total_issues,
            "critical_issues": critical,
            "warning_issues": warnings,
            "info_issues": infos,
            "avg_word_count": round(avg_wc),
            "avg_load_time_ms": round(avg_load, 1),
            "total_images": total_imgs,
            "images_missing_alt": missing_alt,
            "alt_coverage_pct": round(((total_imgs - missing_alt) / total_imgs * 100) if total_imgs > 0 else 100, 1),
            "pages_missing_title": 0,
            "pages_missing_meta_desc": sum(1 for p in pages if not p["meta_description"]),
            "pages_missing_h1": sum(1 for p in pages if not p["h1_tags"]),
            "pages_missing_canonical": sum(1 for p in pages if not p["has_canonical"]),
            "pages_with_schema": sum(1 for p in pages if p["has_structured_data"]),
            "pages_with_og": sum(1 for p in pages if p["has_og_tags"]),
            "pages_mobile_ready": sum(1 for p in pages if p["viewport_meta"]),
            "top_issues": [{"issue": k, "count": v} for k, v in top_issues],
        },
        "crawled_at": datetime.now().isoformat(),
    }


def create_demo_connectors():
    """Create mock connectors that return realistic simulated data."""
    random.seed(42)

    google_campaigns = [_gen_campaign(t, Platform.GOOGLE_ADS, i) for i, t in enumerate(GOOGLE_TEMPLATES)]
    meta_campaigns = [_gen_campaign(t, Platform.META_ADS, i) for i, t in enumerate(META_TEMPLATES)]

    # Google Ads mock
    google_ads = AsyncMock()
    google_ads.get_campaigns = AsyncMock(return_value=google_campaigns)
    google_ads.get_geo_performance = AsyncMock(return_value=_gen_geo("google"))
    google_ads.get_keyword_performance = AsyncMock(return_value=[])
    google_ads.get_search_terms_report = AsyncMock(return_value=_gen_search_terms())
    google_ads.update_campaign_budget = AsyncMock(return_value=True)
    google_ads.pause_campaign = AsyncMock(return_value=True)
    google_ads.enable_campaign = AsyncMock(return_value=True)

    # Meta Ads mock
    meta_ads = AsyncMock()
    meta_ads.get_campaigns = AsyncMock(return_value=meta_campaigns)
    meta_ads.get_geo_performance = AsyncMock(return_value=_gen_geo("meta"))
    meta_ads.update_campaign_budget = AsyncMock(return_value=True)
    meta_ads.pause_campaign = AsyncMock(return_value=True)
    meta_ads.enable_campaign = AsyncMock(return_value=True)

    # GSC mock
    gsc = AsyncMock()
    gsc.get_top_queries = AsyncMock(return_value=_gen_organic_queries())
    gsc.get_page_performance = AsyncMock(return_value=_gen_page_performance())
    gsc.get_query_page_matrix = AsyncMock(return_value=_gen_query_page_matrix())
    gsc.get_search_analytics = AsyncMock(return_value=_gen_organic_queries())
    gsc.get_site_health = AsyncMock(return_value=SEOSiteHealth(
        site_url="https://brand.com",
        total_clicks=4457,
        total_impressions=81700,
        avg_position=7.8,
        avg_ctr=0.055,
        top_queries=["best skincare products", "brand.com reviews", "hyaluronic acid serum", "korean skincare products", "spf 50 moisturizer"],
        ranking_pages_top3=5,
        ranking_pages_top10=10,
        ranking_pages_top20=17,
    ))

    logger.info("Demo connectors initialized with simulated data.")
    return google_ads, meta_ads, gsc
