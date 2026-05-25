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


# ── Deterministic engagement adjustment for live scores ──────────────
# Applied AFTER Gemini's creative score to make audience-response impact
# explicit and reproducible. Pre-scores have no metrics so this is skipped.
ENGAGEMENT_WEIGHT = 0.20  # 20% of final score comes from real engagement vs benchmark
CREATIVE_WEIGHT = 1.0 - ENGAGEMENT_WEIGHT  # 80% creative


def _compute_engagement_score(metrics: Dict, platform: str, media_type: str) -> Optional[int]:
    """
    Return 0-100 score based on how this post's ER + reach-penetration compare
    to fashion benchmarks. None if insufficient data.
    """
    er = metrics.get("engagement_rate") or 0
    penetration = metrics.get("reach_penetration_pct") or 0  # already in % (0-100)
    significance = metrics.get("er_significance")

    if significance in ("noise", "unknown") or not penetration:
        return None  # not enough signal to adjust

    is_reel = media_type in ("VIDEO", "REELS")

    # Fashion-vertical thresholds, same as UI benchmarks
    if platform == "facebook":
        er_thresholds = [0.04, 0.15, 0.5]
        reach_thresholds = [2, 5, 10]
    elif is_reel:
        er_thresholds = [2.0, 4.0, 7.0]
        reach_thresholds = [20, 50, 100]
    else:
        er_thresholds = [0.68, 1.5, 3.0]
        reach_thresholds = [10, 20, 40]

    er_pct = er * 100
    # Map each metric to a 0-100 sub-score using benchmark anchors
    def _anchored(value, thresholds):
        weak_max, ok_max, good_max = thresholds
        if value < weak_max:        return max(0, (value / weak_max) * 25)        # 0-25
        if value < ok_max:          return 25 + ((value - weak_max) / (ok_max - weak_max)) * 25   # 25-50
        if value < good_max:        return 50 + ((value - ok_max) / (good_max - ok_max)) * 25     # 50-75
        return min(100, 75 + ((value - good_max) / good_max) * 25)                # 75-100+

    er_score = _anchored(er_pct, er_thresholds)
    reach_score = _anchored(penetration, reach_thresholds)
    # Blend 60% ER + 40% reach (ER is the harder signal, reach matters but is more volatile)
    return round(0.6 * er_score + 0.4 * reach_score)


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


async def _fetch_media_bytes(url: Optional[str], cap_mb: int = 18) -> tuple:
    """
    Download a Meta CDN image/video URL → (bytes, mime).
    Returns (None, None) on any failure. Capped to cap_mb to fit Gemini limits.
    """
    if not url:
        return (None, None)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return (None, None)
            data = r.content
            if len(data) > cap_mb * 1024 * 1024:
                # Too big for inline Gemini — skip rather than truncate (would corrupt media)
                logger.debug(f"Media {len(data)} bytes exceeds {cap_mb}MB cap, skipping bytes pass")
                return (None, None)
            mime = r.headers.get("content-type", "").split(";")[0].strip() or "application/octet-stream"
            if not (mime.startswith("image/") or mime.startswith("video/")):
                return (None, None)
            return (data, mime)
    except Exception as e:
        logger.debug(f"Media fetch failed: {e}")
        return (None, None)


async def score_post(post: Dict[str, Any], paid_metrics: Optional[Dict] = None) -> Dict[str, Any]:
    """Score a single post. Returns scored object with rationale + recommendations."""
    _configure()
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured", "post_id": post.get("id")}

    metrics = _enrich_with_paid_metrics(post, paid_metrics)

    # Download the actual media so Gemini can do real visual analysis (closes the
    # pre-vs-actual visual-score gap). Falls back to text-only if download fails.
    media_url = post.get("media_url") or post.get("thumbnail_url")
    media_bytes, media_mime = await _fetch_media_bytes(media_url)
    has_visual = bool(media_bytes and media_mime)

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
}, indent=2, default=str)}

{"The actual image/video is attached. Use it for visual / brand / mobile / pacing scoring. Do real pixel-level analysis — composition, lighting, brand presence, mobile-safe framing, edit rhythm." if has_visual else "Note: media bytes could not be fetched (URL expired or too large). Score visual/pacing/brand from caption + media_type only; mark these criteria around 5 (neutral) unless caption strongly hints otherwise."}

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
                "temperature": 0.4,  # Aligned with score_draft_post for fair pre/actual comparison
            },
        )
        # Build multimodal input: attached media bytes first, then prompt
        if has_visual:
            inputs = [{"mime_type": media_mime, "data": media_bytes}, prompt]
        else:
            inputs = [prompt]
        resp = await model.generate_content_async(inputs)
        result = json.loads(resp.text.strip())
        # Override Gemini's fuzzy overall + tier with deterministic weighted math
        sub = result.get("scores", {}) or {}
        creative_score = _compute_overall(sub)

        # Live-score blend: 80% creative + 20% engagement (when metrics available).
        # Pre-scores have no metrics, so creative_score stands alone — this is
        # exactly the 20-point swing range the user sees as the pre-vs-live gap.
        # Need reach_penetration_pct on metrics, so enrich here if not yet done.
        from app.config.settings import settings as _s
        engagement_score = _compute_engagement_score(metrics, post.get("platform", ""), post.get("media_type", ""))
        if engagement_score is not None:
            blended = round(CREATIVE_WEIGHT * creative_score + ENGAGEMENT_WEIGHT * engagement_score)
            result["overall_score"] = blended
            result["creative_only_score"] = creative_score
            result["engagement_score"] = engagement_score
            result["engagement_adjustment"] = blended - creative_score  # signed delta for transparency
        else:
            result["overall_score"] = creative_score
            result["creative_only_score"] = creative_score
            result["engagement_score"] = None
            result["engagement_adjustment"] = 0
        result["tier"] = _compute_tier(result["overall_score"])
        result["scoring_weights"] = SCORING_WEIGHTS  # surface to UI for transparency
        result["live_blend_weights"] = {"creative": CREATIVE_WEIGHT, "engagement": ENGAGEMENT_WEIGHT}
        result["post_id"] = post.get("id")
        result["permalink_url"] = post.get("permalink_url")
        result["media_url"] = post.get("media_url") or post.get("thumbnail_url")
        result["platform"] = post.get("platform")
        result["created_time"] = post.get("created_time")
        result["caption"] = (post.get("message") or "")[:500]  # Original caption shown in UI
        result["media_type"] = post.get("media_type")
        result["metrics"] = metrics
        result["visual_analysis_used"] = has_visual  # transparency: did Gemini actually see the media?
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
    media_files: Optional[List[tuple]] = None,
) -> Dict[str, Any]:
    """
    Score a DRAFT post (not yet published) using the same rubric as live posts.

    Single-file (backward compat): pass media_bytes + media_mime.
    Carousel (up to 20): pass media_files as list of (bytes, mime_type) tuples.
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

{
  (f"The {len(media_files)} carousel slides are attached in order (slide 1 = cover/hook). Analyze: (1) cover slide's hook strength — first frame decides 70%+ of stop rate, (2) consistency across slides (theme, palette, brand), (3) progression / payoff in last slide, (4) why a viewer would swipe through all of them. Score 'pacing' on slide sequencing." if (media_files and len(media_files) > 1) else
   "The image/video is attached. Analyze it for: composition, lighting, brand presence, on-platform mobile framing, hook strength (first frame), and pacing if video." if (media_bytes or media_files)
   else "No media uploaded — score visual/pacing as 5 (neutral baseline) and weight the analysis on caption + message.")
}

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

        # Build Gemini input: each slide in order, then the text prompt
        inputs = []
        if media_files:
            for (b, mime) in media_files:
                if b and mime:
                    inputs.append({"mime_type": mime, "data": b})
        elif media_bytes and media_mime:
            inputs.append({"mime_type": media_mime, "data": media_bytes})
        inputs.append(prompt)

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


def _enrich_with_reach_penetration(scored: Dict[str, Any], follower_counts: Dict[str, int]) -> None:
    """
    Add reach_penetration_pct + er_significance flag based on follower counts.
    Industry thresholds:
      - FB: reach >= 5% of followers for ER to be statistically meaningful
      - IG: reach >= 10% of followers
    Below those, ER is mostly internal-staff noise.
    """
    metrics = scored.get("metrics") or {}
    platform = scored.get("platform")
    followers = follower_counts.get(platform, 0) or 0
    reach = metrics.get("reach", 0) or 0

    if not followers:
        metrics["reach_penetration_pct"] = None
        metrics["er_significance"] = "unknown"
        metrics["followers_at_score_time"] = 0
    else:
        penetration = (reach / followers) if followers else 0
        metrics["reach_penetration_pct"] = round(penetration * 100, 2)
        metrics["followers_at_score_time"] = followers
        # ER significance gate
        if platform == "facebook":
            floor = 0.05  # 5% of followers
        elif platform == "instagram":
            floor = 0.10  # 10% of followers
        else:
            floor = 0.05
        if penetration < floor * 0.5:
            metrics["er_significance"] = "noise"  # very low — internal-only likely
        elif penetration < floor:
            metrics["er_significance"] = "low"    # below threshold — interpret cautiously
        else:
            metrics["er_significance"] = "normal" # above threshold — ER% meaningful
    scored["metrics"] = metrics


async def _fetch_follower_counts(meta_social) -> Dict[str, int]:
    """Get current FB + IG follower counts (used to compute reach penetration)."""
    counts = {"facebook": 0, "instagram": 0}
    try:
        fb = await meta_social.get_page_overview()
        counts["facebook"] = int(fb.get("followers") or fb.get("fan_count") or 0)
    except Exception as e:
        logger.debug(f"FB follower fetch failed: {e}")
    try:
        ig = await meta_social.get_instagram_overview()
        counts["instagram"] = int(ig.get("followers") or 0)
    except Exception as e:
        logger.debug(f"IG follower fetch failed: {e}")
    return counts


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

    # 0) Fetch current follower counts (used for reach-penetration significance)
    follower_counts = await _fetch_follower_counts(meta_social)

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
            _enrich_with_reach_penetration(scored, follower_counts)
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
