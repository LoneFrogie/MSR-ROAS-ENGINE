"""
Trend Scout — researches what's currently viral on TikTok + Instagram
using Gemini 2.5 Flash with Google Search grounding for live web data.

Returns a scored "inspiration board" so the team can see WHAT is working
and adapt the top hooks to brand voice.
"""
from __future__ import annotations

import json
import logging
import asyncio
from typing import Dict, List, Optional, Any

import google.generativeai as genai

from app.config.settings import settings
from app.seo.post_scorer import SCORING_WEIGHTS, _compute_overall, _compute_tier

logger = logging.getLogger("roas_engine.trend_scout")

MODEL_NAME = "gemini-2.5-flash"

TREND_SYSTEM_PROMPT = """You are a viral content researcher specialising in fashion,
lifestyle, and women's apparel marketing. You analyse what's currently working on
Instagram and TikTok using fresh web data, then explain WHY each trend works using
the same 7-criteria rubric we score live posts on:
hook · message · visual · brand · mobile · script · pacing.

Return STRICT JSON. No markdown. No commentary."""


async def get_trending_content(
    industry: str = "fashion plus-size women",
    region: str = "Malaysia / Southeast Asia",
    platforms: List[str] = None,
    count: int = 10,
) -> Dict[str, Any]:
    """
    Returns a scored inspiration board of currently-viral content.
    Each item includes platform, hook, theme, why_it_works, hashtags, scores.
    """
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured", "trends": []}

    genai.configure(api_key=settings.GEMINI_API_KEY)
    platforms = platforms or ["instagram", "tiktok"]
    platform_str = " + ".join(p.capitalize() for p in platforms)

    schema = {
        "trends": [
            {
                "platform": "instagram | tiktok",
                "content_type": "Reel | Photo | Carousel | TikTok video | Story",
                "hook": "string — opening line or first 3 seconds, 6-15 words",
                "theme": "string — what the post is about, one sentence",
                "creator_or_brand": "string — handle or brand name if known, or 'multiple creators'",
                "why_it_works": "string — 2-3 sentences explaining the virality mechanic",
                "hashtags": ["#tag1", "#tag2", "#tag3"],
                "format_template": "string — replicable template, e.g. 'POV: trying X for the first time'",
                "scores": {
                    "hook": "int 0-10",
                    "message": "int 0-10",
                    "visual": "int 0-10",
                    "brand": "int 0-10",
                    "mobile": "int 0-10",
                    "script": "int 0-10",
                    "pacing": "int 0-10",
                },
                "adaptability_for_ms_read": "int 0-10 — how easily this can be adapted for a plus-size women's fashion brand",
                "search_query": "string — a 4-8 word search query that surfaces real-world examples of this trend",
                "example_post_url": "string OR null — REAL URL of one actual viral post you found during grounding (instagram.com/p/..., instagram.com/reel/..., tiktok.com/@user/video/...). MUST be a URL you actually saw in search results, never invented. If unsure, return null.",
                "primary_hashtag": "string — the single most identifying hashtag for this trend (no #)",
            }
        ],
        "summary": "string — 2-3 sentence overview of the dominant content patterns this week",
        "as_of": "ISO date — when the research was performed",
    }

    prompt = f"""Research what's CURRENTLY (this week) going viral on {platform_str}
in the {industry} niche, focused on {region} when possible (global if local is sparse).

Use Google Search to find FRESH content. Pull from the last 7 days. Prioritise:
- High engagement-rate posts (>3% on IG, >5% on TikTok Reels equivalent)
- Trending hashtags + audio in the niche
- Content formats getting copied widely (POV, GRWM, transformation, before/after, micro-tutorials, UGC reviews)

For each trend, score it on the 7-criteria rubric. Be honest — not every viral
post scores high on every dimension. A meme can score 9/hook + 4/brand.

Return EXACTLY {count} trends ranked by virality strength + adaptability for a
plus-size women's fashion brand (MS. READ, sells modest-friendly larger-size clothing
in Malaysia/SEA).

CRITICAL — example_post_url rules:
- Only fill it if you ACTUALLY saw the URL in search results during grounding.
- Allowed shapes: instagram.com/p/SHORTCODE, instagram.com/reel/SHORTCODE, tiktok.com/@USER/video/ID
- If you didn't find a real URL, return null. NEVER invent a URL.
- Generic profile URLs (instagram.com/some_user) are not acceptable — we need the specific post.

OUTPUT JSON matching this schema:
{json.dumps(schema, indent=2)}
"""

    grounding_citations: List[Dict[str, str]] = []
    try:
        # Try with Google Search grounding (gemini-2.5-flash supports this)
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=TREND_SYSTEM_PROMPT,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.4,
            },
            tools={"google_search_retrieval": {}},
        )
        resp = await model.generate_content_async(prompt)
        result = json.loads(resp.text.strip())

        # Extract REAL grounding citations from response metadata (not from JSON output —
        # those are hallucinated). Format: candidates[0].grounding_metadata.grounding_chunks
        try:
            for cand in (resp.candidates or []):
                gm = getattr(cand, "grounding_metadata", None) or getattr(cand, "groundingMetadata", None)
                if not gm:
                    continue
                chunks = getattr(gm, "grounding_chunks", None) or getattr(gm, "groundingChunks", None) or []
                for ch in chunks:
                    web = getattr(ch, "web", None)
                    if not web:
                        continue
                    uri = getattr(web, "uri", None)
                    title = getattr(web, "title", None) or ""
                    if uri:
                        grounding_citations.append({"url": uri, "title": title})
        except Exception as ge:
            logger.debug(f"Could not parse grounding metadata: {ge}")
    except Exception as e:
        # Fallback: no grounding (relies on Gemini's training-data knowledge)
        logger.warning(f"Grounded retrieval failed, falling back to ungrounded: {e}")
        try:
            model = genai.GenerativeModel(
                MODEL_NAME,
                system_instruction=TREND_SYSTEM_PROMPT + "\nNote: Google Search is unavailable; use your most recent training knowledge.",
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.4,
                },
            )
            resp = await model.generate_content_async(prompt)
            result = json.loads(resp.text.strip())
        except Exception as e2:
            logger.error(f"Trend research failed: {e2}")
            return {"error": str(e2), "trends": []}

    # Validate example_post_url + build platform-native deeplinks + grounding citations
    import re
    import uuid
    from urllib.parse import quote_plus
    from datetime import datetime as _dt

    # Patterns for valid TikTok/IG post URLs (specific posts only — no profile URLs)
    IG_POST = re.compile(r"^https?://(www\.)?instagram\.com/(p|reel|reels|tv)/[A-Za-z0-9_-]+/?", re.I)
    TT_POST = re.compile(r"^https?://(www\.)?tiktok\.com/@[A-Za-z0-9._-]+/video/\d+", re.I)

    def _is_valid_post_url(u: str) -> bool:
        if not u or not isinstance(u, str):
            return False
        return bool(IG_POST.match(u) or TT_POST.match(u))

    # Extract any valid platform-post URLs from grounding citations (real URLs Gemini saw)
    platform_post_urls = [c for c in grounding_citations if _is_valid_post_url(c.get("url", ""))]

    trends_list = result.get("trends", []) or []
    for i, t in enumerate(trends_list):
        sub = t.get("scores", {}) or {}
        t["overall_score"] = _compute_overall(sub)
        t["tier"] = _compute_tier(t["overall_score"])
        t["trend_id"] = uuid.uuid4().hex[:12]

        platform = (t.get("platform") or "").lower()
        hashtag = (t.get("primary_hashtag") or "").lstrip("#").strip()
        sq = t.get("search_query") or t.get("hook") or t.get("theme") or "viral fashion content"

        # ─ Resolve the "exact content" link in priority order ─
        # 1. Gemini's example_post_url IF it actually parses as a real post URL
        example_url = t.get("example_post_url")
        if example_url and _is_valid_post_url(example_url):
            t["direct_post_url"] = example_url
            t["direct_post_source"] = "Example post"
        elif platform_post_urls:
            # 2. Reuse a real platform-post URL from grounding citations (round-robin)
            picked = platform_post_urls[i % len(platform_post_urls)]
            t["direct_post_url"] = picked.get("url")
            t["direct_post_source"] = "From research citations"
            # Drop Gemini's invalid example_post_url to avoid confusion
            t["example_post_url"] = None
        else:
            t["direct_post_url"] = None
            t["example_post_url"] = None
            t["direct_post_source"] = None

        # ─ Always-working platform-native search deeplinks ─
        platform_links = []
        if platform == "tiktok":
            if hashtag:
                platform_links.append({"label": f"#{hashtag} on TikTok", "url": f"https://www.tiktok.com/tag/{quote_plus(hashtag)}"})
            platform_links.append({"label": "Search TikTok", "url": f"https://www.tiktok.com/search?q={quote_plus(sq[:200])}"})
        elif platform == "instagram":
            if hashtag:
                platform_links.append({"label": f"#{hashtag} on Instagram", "url": f"https://www.instagram.com/explore/tags/{quote_plus(hashtag)}/"})
            platform_links.append({"label": "Search Instagram", "url": f"https://www.instagram.com/explore/search/keyword/?q={quote_plus(sq[:200])}"})
        # Google search as universal fallback
        platform_links.append({"label": "Search Google", "url": f"https://www.google.com/search?q={quote_plus(sq[:200])}"})
        t["platform_links"] = platform_links

        # Attach 1-3 real grounding citations as supporting evidence
        if grounding_citations:
            start = (i * 2) % len(grounding_citations)
            t["grounding_sources"] = grounding_citations[start:start + 3]
        else:
            t["grounding_sources"] = []

    result["scoring_weights"] = SCORING_WEIGHTS
    result["fetched_at"] = _dt.utcnow().isoformat()
    result["all_grounding_sources"] = grounding_citations
    return result


async def adapt_trend_to_brand(
    trend: Dict[str, Any],
    brand_voice: str = "MS. READ — modest, body-positive, plus-size women's fashion in Malaysia. Warm, empowering, never preachy. Bahasa English mix OK.",
    target_platform: str = "instagram",
) -> Dict[str, Any]:
    """
    Take a trending content template and adapt it to MS. READ brand voice.
    Returns adapted hook + caption + media direction.
    """
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    genai.configure(api_key=settings.GEMINI_API_KEY)

    schema = {
        "adapted_hook": "string — first line / first 3 seconds, on brand voice, 6-15 words",
        "adapted_caption": "string — full caption, on brand voice, with CTA",
        "media_direction": "string — how to shoot/edit the visual to match the trend while staying on brand",
        "hashtag_mix": ["#tag1", "#tag2", "#tag3"],
        "predicted_performance": "string — one sentence on expected engagement vs the original trend",
    }

    prompt = f"""Adapt this viral trend to a brand's voice.

ORIGINAL TREND:
{json.dumps({
    "platform": trend.get("platform"),
    "hook": trend.get("hook"),
    "theme": trend.get("theme"),
    "format_template": trend.get("format_template"),
    "why_it_works": trend.get("why_it_works"),
    "hashtags": trend.get("hashtags"),
}, indent=2)}

BRAND VOICE:
{brand_voice}

TARGET PLATFORM: {target_platform}

Rewrite the hook and full caption to fit the brand voice. Keep the viral
mechanic intact. Add a clear CTA. Suggest hashtags that mix trending + brand.

OUTPUT JSON:
{json.dumps(schema, indent=2)}
"""

    try:
        model = genai.GenerativeModel(
            MODEL_NAME,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.6,
            },
        )
        resp = await model.generate_content_async(prompt)
        return json.loads(resp.text.strip())
    except Exception as e:
        logger.error(f"Brand adaptation failed: {e}")
        return {"error": str(e)}
