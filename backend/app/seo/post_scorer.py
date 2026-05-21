"""
Social Post Scorer (Gemini)
Scores Facebook + Instagram posts on industry-standard creative criteria
and generates concrete improvement recommendations.

Industry rubric (0-10 each):
  - hook         : Attention grab in first 3s / first line
  - message      : Clarity of value prop / call-to-action
  - visual       : Image/video quality + composition
  - brand        : Consistency, recognizability
  - mobile       : Mobile-first framing (vertical, large text, safe zones)
  - script       : Copywriting quality (caption / VO)
  - pacing       : Edit rhythm (videos) or narrative flow (images)

Combined with paid metrics (CPL, CTR, spend) when available.
"""
import json
import logging
import re
from typing import Dict, List, Optional, Any  # noqa: F401

import google.generativeai as genai

from app.config.settings import settings

logger = logging.getLogger("roas_engine.post_scorer")

MODEL_NAME = "gemini-2.5-flash"

# Industry-standard creative scoring weights for paid social (Meta/IG)
# Sources: Meta Creative Best Practices, Motion / Atria / Sparkitto benchmarks
# Rationale: hook decides 70%+ of view-through; message and visual control conversion.
SCORING_WEIGHTS = {
    "hook":    0.25,  # First 3s / first line drives stop rate
    "message": 0.15,  # Value prop + CTA clarity
    "visual":  0.15,  # Production / composition / lighting
    "script":  0.15,  # Copywriting craft
    "brand":   0.10,  # Brand identity strength
    "mobile":  0.10,  # Mobile-native framing
    "pacing":  0.10,  # Edit rhythm / narrative flow
}

# Tier thresholds applied to overall_score (0-100)
TIER_THRESHOLDS = {
    "A": 80,  # Hero — scale spend
    "B": 65,  # Strong — keep running
    "C": 50,  # Mediocre — iterate
    "D": 0,   # Weak — retire or rebuild
}


def _normalize_caption_for_hash(caption: str) -> str:
    """Same normalization used by /score-draft endpoint — must stay in sync."""
    import re
    if not caption:
        return ""
    s = caption.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"https?://\S+", "", s)
    return s[:500]


async def _find_matching_draft(caption: str):
    """
    Look up a draft pre-score by caption hash.
    Tries strict hash (full normalized) first, then loose hash (first 100 chars).
    Returns None if no match.
    """
    import hashlib
    from app import db as _db
    norm = _normalize_caption_for_hash(caption)
    if len(norm) < 20:  # Avoid false matches on tiny captions
        return None
    # Strict: full normalized caption
    full_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    try:
        d = await _db.get_draft_score(full_hash)
        if d:
            return d
    except Exception:
        pass
    # Loose: first 100 chars (matches if caption was lightly edited before publish)
    prefix = norm[:100]
    if len(prefix) >= 20:
        prefix_hash = hashlib.sha256(prefix.encode("utf-8")).hexdigest()
        try:
            return await _db.get_draft_score(prefix_hash)
        except Exception:
            return None
    return None


def _compute_overall(scores: Dict[str, float]) -> int:
    """Deterministic weighted-average of the 7 creative criteria, 0-100."""
    total = 0.0
    for criterion, weight in SCORING_WEIGHTS.items():
        total += (scores.get(criterion) or 0) * weight  # each score is 0-10
    return round(total * 10)  # × 10 -> 0-100


def _compute_tier(overall: int) -> str:
    for tier, threshold in TIER_THRESHOLDS.items():
        if overall >= threshold:
            return tier
    return "D"

SYSTEM_PROMPT = """You are a senior performance creative strategist who scores brand
social media posts (Facebook + Instagram) on industry-standard rubrics and writes
concrete, actionable rewrites.

You score each post on 7 criteria, 0-10:
- hook: opens with a strong attention grabber (first line / first 3 seconds)
- message: value prop + CTA are crystal clear, no fluff
- visual: image/video looks professional; good composition + lighting
- brand: brand identity is unmistakable (logo, colors, voice)
- mobile: optimized for mobile (vertical 9:16 for video, big text, safe zones)
- script: caption/VO copywriting is sharp, benefit-led, on tone
- pacing: video edits keep attention; image flow tells a story

You receive performance data (impressions, engagement, clicks, spend, CPL, CTR)
to weight your judgment. Underperforming posts deserve harsher critique.

Return STRICT JSON. No markdown, no commentary."""


def _configure():
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)


def _enrich_with_paid_metrics(post: Dict, paid_lookup: Optional[Dict] = None) -> Dict:
    """
    If we have a campaign-level CPL/CTR/spend that ties to this post (via creative ID
    or message hash match), merge it. Otherwise compute organic engagement rate.
    """
    impressions = post.get("impressions", 0) or 0
    clicks = post.get("clicks", 0) or 0
    likes = post.get("likes", 0) or 0
    comments = post.get("comments", 0) or 0
    saves = post.get("saves", 0) or 0
    shares = post.get("shares", 0) or 0
    views = (post.get("video_views", 0) or post.get("plays", 0)
             or post.get("views", 0) or 0)
    reach = post.get("reach", impressions) or impressions
    engagements = (post.get("engaged_users", 0)
                   or (likes + comments + saves + shares))

    metrics = {
        "impressions": impressions,
        "reach": reach,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "engagements": engagements,
        "engagement_rate": (engagements / reach) if reach else 0,
        "clicks": clicks,
        "ctr": (clicks / impressions) if impressions else 0,
    }
    if paid_lookup:
        metrics.update(paid_lookup)
    return metrics


async def score_post(post: Dict[str, Any], paid_metrics: Optional[Dict] = None) -> Dict[str, Any]:
    """Score a single post. Returns scored object with rationale + recommendations."""
    _configure()
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured", "post_id": post.get("id")}

    metrics = _enrich_with_paid_metrics(post, paid_metrics)

    schema = {
        "scores": {
            "hook": "int 0-10",
            "message": "int 0-10",
            "visual": "int 0-10",
            "brand": "int 0-10",
            "mobile": "int 0-10",
            "script": "int 0-10",
            "pacing": "int 0-10",
        },
        "overall_score": "int 0-100 (weighted composite)",
        "tier": "A | B | C | D",
        "strengths": ["1-2 sentences"],
        "weaknesses": ["1-2 sentences"],
        "recommendations": [
            "Specific, actionable rewrite or shoot direction (1-3 items)"
        ],
        "suggested_caption": "string — a rewritten caption that fixes the issues, on brand voice",
        "suggested_hook": "string — 6-12 words, first line / first 3 seconds",
    }

    prompt = f"""Score this {post.get('platform','social')} post and write improvements.

POST DATA:
{json.dumps({
    "platform": post.get("platform"),
    "media_type": post.get("media_type"),
    "caption": (post.get("message") or "")[:1500],
    "permalink": post.get("permalink_url"),
    "media_url": post.get("media_url"),
    "thumbnail_url": post.get("thumbnail_url"),
}, indent=2, default=str)}

PERFORMANCE METRICS:
{json.dumps(metrics, indent=2)}

OUTPUT (return JSON matching this schema exactly):
{json.dumps(schema, indent=2)}
"""

    try:
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.5,
            },
        )
        resp = await model.generate_content_async(prompt)
        result = json.loads(resp.text.strip())
        # Override Gemini's fuzzy overall + tier with deterministic weighted math
        sub = result.get("scores", {}) or {}
        result["overall_score"] = _compute_overall(sub)
        result["tier"] = _compute_tier(result["overall_score"])
        result["scoring_weights"] = SCORING_WEIGHTS  # surface to UI for transparency
        result["post_id"] = post.get("id")
        result["permalink_url"] = post.get("permalink_url")
        result["media_url"] = post.get("media_url") or post.get("thumbnail_url")
        result["platform"] = post.get("platform")
        result["created_time"] = post.get("created_time")
        result["caption"] = (post.get("message") or "")[:500]  # Original caption shown in UI
        result["media_type"] = post.get("media_type")
        result["metrics"] = metrics
        return result
    except Exception as e:
        logger.error(f"Post scoring failed for {post.get('id')}: {e}")
        return {"error": str(e), "post_id": post.get("id")}


async def score_draft_post(
    caption: str,
    platform: str = "instagram",
    media_type: str = "IMAGE",
    media_bytes: Optional[bytes] = None,
    media_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Score a DRAFT post (not yet published) using the same rubric as live posts.
    Accepts raw bytes for image/video so Gemini can analyze the visual directly.
    Returns scoring + suggested rewrites (same schema as score_post).
    """
    _configure()
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    schema = {
        "scores": {
            "hook": "int 0-10",
            "message": "int 0-10",
            "visual": "int 0-10",
            "brand": "int 0-10",
            "mobile": "int 0-10",
            "script": "int 0-10",
            "pacing": "int 0-10",
        },
        "strengths": ["1-2 sentences"],
        "weaknesses": ["1-2 sentences"],
        "recommendations": [
            "Specific, actionable rewrite or shoot direction (1-3 items)"
        ],
        "suggested_caption": "string — rewritten caption on brand voice",
        "suggested_hook": "string — 6-12 words, first line / first 3 seconds",
        "predicted_performance": "string — one sentence calling out expected stop-rate / engagement risk",
    }

    prompt = f"""Score this DRAFT {platform} post BEFORE publishing.
No live metrics exist yet — judge purely on creative quality and predicted performance.

DRAFT POST:
{json.dumps({
    "platform": platform,
    "media_type": media_type,
    "caption": (caption or "")[:1500],
}, indent=2)}

{"The image/video is attached. Analyze it for: composition, lighting, brand presence, on-platform mobile framing, hook strength (first frame), and pacing if video." if media_bytes else "No media uploaded — score visual/pacing as 5 (neutral baseline) and weight the analysis on caption + message."}

OUTPUT (return JSON matching this schema exactly):
{json.dumps(schema, indent=2)}
"""

    try:
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.4,
            },
        )

        # Build Gemini input: text + optional inline media
        if media_bytes and media_mime:
            inputs = [
                {"mime_type": media_mime, "data": media_bytes},
                prompt,
            ]
        else:
            inputs = [prompt]

        resp = await model.generate_content_async(inputs)
        result = json.loads(resp.text.strip())

        # Apply the same deterministic weighting as live posts
        sub = result.get("scores", {}) or {}
        result["overall_score"] = _compute_overall(sub)
        result["tier"] = _compute_tier(result["overall_score"])
        result["scoring_weights"] = SCORING_WEIGHTS
        result["caption"] = (caption or "")[:500]
        result["platform"] = platform
        result["media_type"] = media_type
        result["is_draft"] = True
        return result
    except Exception as e:
        logger.error(f"Draft scoring failed: {e}")
        return {"error": str(e)}


async def score_recent_posts(
    meta_social,
    max_posts: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip_already_scored: bool = True,
) -> List[Dict[str, Any]]:
    """
    Pull recent FB + IG posts in the given date range, score new ones,
    and return ALL scored posts in range (existing + new).
    Already-scored posts are loaded from Firestore and not re-scored.
    """
    from app import db as _db

    # 1) Load already-scored posts in this range from Firestore
    existing = await _db.get_scored_posts(limit=500, start_date=start_date, end_date=end_date)
    existing_ids = {p.get("post_id") for p in existing}

    # 2) Fetch recent posts and filter to the date range, skipping already scored
    posts: List[Dict] = []
    try:
        ig_posts = await meta_social.list_recent_instagram_posts(limit=max_posts * 3)
        posts.extend(ig_posts)
    except Exception as e:
        logger.warning(f"IG posts fetch failed: {e}")
    try:
        fb_posts = await meta_social.list_recent_facebook_posts(limit=max_posts * 3)
        posts.extend(fb_posts)
    except Exception as e:
        logger.warning(f"FB posts fetch failed: {e}")

    # Date filter
    def _in_range(p):
        ct = (p.get("created_time") or "")[:10]
        if start_date and ct < start_date:
            return False
        if end_date and ct > end_date:
            return False
        return True

    in_range = [p for p in posts if _in_range(p)]
    # Skip already-scored
    if skip_already_scored:
        in_range = [p for p in in_range if p.get("id") not in existing_ids]
    # Cap by max_posts
    in_range.sort(key=lambda p: (p.get("created_time") or ""), reverse=True)
    in_range = in_range[:max_posts]

    # 3) Score the new posts
    new_results = []
    for p in in_range:
        scored = await score_post(p)
        if "error" not in scored:
            # Try to attach a matching pre-score draft (caption-hash lookup)
            try:
                pre = await _find_matching_draft(scored.get("caption", ""))
                if pre:
                    scored["pre_score"] = {
                        "overall_score": pre.get("overall_score"),
                        "tier": pre.get("tier"),
                        "scored_at": pre.get("scored_at"),
                        "caption_hash": pre.get("caption_hash"),
                        "delta": (scored.get("overall_score") or 0) - (pre.get("overall_score") or 0),
                    }
                    # Persist the actual score back onto the draft for accuracy tracking
                    await _db.attach_actual_to_draft(pre["caption_hash"], {
                        "overall_score": scored.get("overall_score"),
                        "tier": scored.get("tier"),
                        "post_id": scored.get("post_id"),
                        "scored_at": scored.get("created_time"),
                    })
            except Exception as e:
                logger.debug(f"Draft lookup failed for post: {e}")

            try:
                await _db.save_scored_post(scored)
            except Exception as e:
                logger.warning(f"Failed to persist scored post: {e}")
            new_results.append(scored)

    # 4) Return existing + newly-scored
    combined = existing + new_results
    # De-dupe by post_id (existing list might overlap if we just scored)
    seen = set()
    deduped = []
    for r in combined:
        pid = r.get("post_id")
        if pid in seen:
            continue
        seen.add(pid)
        deduped.append(r)
    deduped.sort(key=lambda r: (r.get("created_time") or ""), reverse=True)
    return deduped
