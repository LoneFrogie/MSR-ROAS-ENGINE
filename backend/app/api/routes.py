"""
API Routes
FastAPI router exposing engine status, snapshots, actions, and manual triggers.
"""
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Body
from pydantic import BaseModel

from app.models.schemas import (
    PerformanceSnapshot, OptimizationAction, UnifiedCampaign
)
from app.config.settings import settings

router = APIRouter()

# Dependency: engine instance injected from app state
def get_engine():
    from app.main import engine
    return engine


class StatusResponse(BaseModel):
    status: str
    version: str
    last_cycle: Optional[datetime]
    active_campaigns: int
    total_actions: int


class TriggerResponse(BaseModel):
    message: str
    triggered_at: datetime


@router.get("/status", response_model=StatusResponse)
async def get_status(engine=Depends(get_engine)):
    snapshot = engine.get_last_snapshot()
    return StatusResponse(
        status="running",
        version="1.0.0",
        last_cycle=snapshot.timestamp if snapshot else None,
        active_campaigns=snapshot.num_active_campaigns if snapshot else 0,
        total_actions=len(engine.get_action_history()),
    )


@router.get("/snapshot")
async def get_snapshot(engine=Depends(get_engine)):
    """
    Return the most recent performance snapshot.
    Falls back to the latest persisted snapshot in Firestore if no
    in-memory snapshot exists yet (e.g. just after a container restart).
    """
    snapshot = engine.get_last_snapshot()
    if snapshot:
        # Pydantic model — serialise via .dict() then JSON-encode
        return snapshot.dict() if hasattr(snapshot, "dict") else snapshot

    # Fallback: pull the most recent snapshot row from Firestore
    try:
        from app import db as _db
        latest = await _db.get_latest_snapshot()
        if latest:
            return latest
    except Exception as e:
        import logging
        logging.getLogger("roas_engine").warning(f"Snapshot Firestore fallback failed: {e}")

    raise HTTPException(status_code=404, detail="No snapshot available yet — first optimization cycle still running.")


@router.get("/campaigns", response_model=List[UnifiedCampaign])
async def get_campaigns(engine=Depends(get_engine)):
    return engine.current_campaigns


@router.get("/actions", response_model=List[OptimizationAction])
async def get_actions(
    limit: int = 50,
    engine=Depends(get_engine),
):
    history = engine.get_action_history()
    return history[-limit:]


@router.get("/platform-summary")
async def get_platform_summary(engine=Depends(get_engine)) -> Dict:
    return engine.get_platform_summary()


@router.post("/trigger/optimize", response_model=TriggerResponse)
async def trigger_optimize(
    background_tasks: BackgroundTasks,
    engine=Depends(get_engine),
):
    background_tasks.add_task(engine.run_optimization_cycle)
    return TriggerResponse(
        message="Optimization cycle triggered.",
        triggered_at=datetime.now(),
    )


@router.post("/trigger/sync", response_model=TriggerResponse)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    engine=Depends(get_engine),
):
    background_tasks.add_task(engine._sync_all_platforms)
    return TriggerResponse(
        message="Platform sync triggered.",
        triggered_at=datetime.now(),
    )


@router.post("/trigger/anomaly-check", response_model=TriggerResponse)
async def trigger_anomaly_check(
    background_tasks: BackgroundTasks,
    engine=Depends(get_engine),
):
    async def _check():
        await engine._sync_all_platforms()
        engine._check_for_anomalies()

    background_tasks.add_task(_check)
    return TriggerResponse(
        message="Anomaly check triggered.",
        triggered_at=datetime.now(),
    )


@router.get("/seo/overview")
async def get_seo_overview(engine=Depends(get_engine)):
    """Full SEO intelligence: site health, keyword opportunities, content gaps, quick wins, cannibalization."""
    if not engine.gsc:
        # Graceful fallback when Google Search Console isn't connected
        return {
            "site_health": {
                "site_url": (settings.BRAND_DOMAIN or "your-site"),
                "total_clicks": 0, "total_impressions": 0,
                "avg_position": 0, "avg_ctr": 0,
                "ranking_pages_top3": 0, "ranking_pages_top10": 0, "ranking_pages_top20": 0,
            },
            "organic_queries": [],
            "page_performance": [],
            "keyword_opportunities": [],
            "content_gaps": [],
            "quick_wins": [],
            "cannibalization": [],
            "competitors": [],
            "autonomous_actions": {
                "total": 0, "bid_reductions": [], "cannibalization_fixes": [],
                "content_gaps": [], "quick_wins": [], "total_estimated_savings": 0,
            },
            "_notice": "Connect Google Search Console (GSC_CREDENTIALS_JSON, GSC_SITE_URL) to unlock organic SEO intelligence.",
        }

    from app.analyzers.seo_analyzer import SEOAnalyzer
    analyzer = SEOAnalyzer()

    from datetime import date, timedelta
    from app.config.settings import runtime_settings
    lookback_days = int(runtime_settings.get("LOOKBACK_DAYS"))
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    organic_queries = await engine.gsc.get_top_queries(start_date, end_date)
    search_terms = []
    if engine.google_ads:
        search_terms = await engine.google_ads.get_search_terms_report(start_date, end_date)
    page_performance = await engine.gsc.get_page_performance(start_date, end_date)
    query_page_matrix = await engine.gsc.get_query_page_matrix(start_date, end_date)
    site_health = await engine.gsc.get_site_health(start_date, end_date)

    keyword_opportunities = analyzer.find_keyword_opportunities(organic_queries, search_terms)
    content_gaps = analyzer.find_content_gaps(organic_queries, search_terms)
    quick_wins = analyzer.find_quick_wins(organic_queries)
    cannibalization = analyzer.detect_keyword_cannibalization(query_page_matrix)
    seo_actions = analyzer.generate_seo_actions(organic_queries, search_terms, query_page_matrix)

    # Compute competitor data if available
    competitors = []
    try:
        from app.demo_mode import _gen_competitor_data
        competitors = _gen_competitor_data()
    except Exception:
        pass

    return {
        "site_health": {
            "site_url": site_health.site_url if hasattr(site_health, 'site_url') else "brand.com",
            "total_clicks": site_health.total_clicks,
            "total_impressions": site_health.total_impressions,
            "avg_position": site_health.avg_position,
            "avg_ctr": site_health.avg_ctr,
            "ranking_pages_top3": getattr(site_health, 'ranking_pages_top3', 0),
            "ranking_pages_top10": getattr(site_health, 'ranking_pages_top10', 0),
            "ranking_pages_top20": getattr(site_health, 'ranking_pages_top20', 0),
        },
        "organic_queries": organic_queries,
        "page_performance": page_performance,
        "keyword_opportunities": keyword_opportunities,
        "content_gaps": content_gaps,
        "quick_wins": quick_wins,
        "cannibalization": cannibalization,
        "competitors": competitors,
        "autonomous_actions": {
            "total": len(seo_actions),
            "bid_reductions": [
                {
                    "action_type": a.action_type.value,
                    "search_term": a.details.get("search_term", ""),
                    "organic_position": a.details.get("organic_position"),
                    "paid_spend": a.details.get("paid_spend", 0),
                    "estimated_savings": a.details.get("estimated_savings", 0),
                    "confidence": a.confidence,
                    "reason": a.reason,
                }
                for a in seo_actions
                if a.details.get("type") == "seo_bid_reduction"
            ],
            "cannibalization_fixes": [
                {
                    "query": a.details.get("query", ""),
                    "primary_page": a.details.get("primary_page", ""),
                    "secondary_pages": a.details.get("secondary_pages", []),
                    "fix_steps": a.details.get("fix_steps", []),
                    "confidence": a.confidence,
                    "reason": a.reason,
                }
                for a in seo_actions
                if a.details.get("type") == "cannibalization_fix"
            ],
            "content_gaps": [
                {
                    "search_term": a.details.get("search_term", ""),
                    "paid_spend": a.details.get("paid_spend", 0),
                    "estimated_annual_savings": a.details.get("estimated_annual_savings", 0),
                    "content_brief": a.details.get("content_brief", {}),
                    "confidence": a.confidence,
                    "reason": a.reason,
                }
                for a in seo_actions
                if a.details.get("type") == "content_gap"
            ],
            "quick_wins": [
                {
                    "query": a.details.get("query", ""),
                    "current_position": a.details.get("current_position"),
                    "estimated_click_lift": a.details.get("estimated_click_lift", 0),
                    "optimization_steps": a.details.get("optimization_steps", []),
                    "confidence": a.confidence,
                    "reason": a.reason,
                }
                for a in seo_actions
                if a.details.get("type") == "quick_win"
            ],
            "total_estimated_savings": sum(
                a.details.get("estimated_savings", 0)
                for a in seo_actions
                if a.details.get("type") == "seo_bid_reduction"
            ),
        },
    }


@router.get("/seo/crawl")
async def get_site_crawl(engine=Depends(get_engine)):
    """On-page SEO audit: crawls website pages and analyzes meta tags, headings, content, images, links, schema."""
    from app.config.settings import settings

    if settings.DEMO_MODE:
        from app.demo_mode import _gen_site_crawl
        return _gen_site_crawl()

    # Live crawl
    from app.crawlers.site_crawler import SiteCrawler
    site_url = settings.BRAND_SITEMAP_URL.replace("/sitemap.xml", "") if settings.BRAND_SITEMAP_URL else f"https://{settings.BRAND_DOMAIN}"
    crawler = SiteCrawler(base_url=site_url, max_pages=20)
    try:
        result = await crawler.crawl_site()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")


@router.post("/seo/crawl")
async def trigger_site_crawl(
    urls: Optional[List[str]] = None,
    engine=Depends(get_engine),
):
    """Trigger a crawl of specific URLs or auto-discover from sitemap."""
    from app.config.settings import settings

    if settings.DEMO_MODE:
        from app.demo_mode import _gen_site_crawl
        return _gen_site_crawl()

    from app.crawlers.site_crawler import SiteCrawler
    site_url = settings.BRAND_SITEMAP_URL.replace("/sitemap.xml", "") if settings.BRAND_SITEMAP_URL else f"https://{settings.BRAND_DOMAIN}"
    crawler = SiteCrawler(base_url=site_url, max_pages=20)
    try:
        result = await crawler.crawl_site(urls=urls)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")


@router.get("/geo/overview")
async def get_geo_overview(engine=Depends(get_engine)):
    """Full GEO intelligence: country-level performance, bid modifier recommendations."""
    from app.analyzers.geo_optimizer import GeoOptimizer
    optimizer = GeoOptimizer()

    google_geo = []
    meta_geo = []

    if engine.google_ads:
        google_geo = await engine.google_ads.get_geo_performance()
    if engine.meta_ads:
        meta_geo = await engine.meta_ads.get_geo_performance()

    geo_summary = optimizer.analyze_geo_performance(google_geo, meta_geo)
    bid_actions = optimizer.generate_bid_modifier_actions(geo_summary)

    # Sort by spend descending
    geo_list = sorted(geo_summary.values(), key=lambda x: x["spend"], reverse=True)

    return {
        "geo_performance": geo_list,
        "bid_modifier_actions": [
            {
                "country": a.details.get("country", ""),
                "action_type": a.action_type.value,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "confidence": a.confidence,
                "reason": a.reason,
                "spend": a.details.get("spend", 0),
                "roas": a.details.get("roas", 0),
            }
            for a in bid_actions
        ],
        "summary": {
            "total_countries": len(geo_summary),
            "total_spend": sum(d["spend"] for d in geo_summary.values()),
            "total_revenue": sum(d["revenue"] for d in geo_summary.values()),
            "avg_roas": (
                sum(d["revenue"] for d in geo_summary.values()) /
                sum(d["spend"] for d in geo_summary.values())
                if sum(d["spend"] for d in geo_summary.values()) > 0 else 0
            ),
            "scale_up_countries": len([a for a in bid_actions if a.new_value and a.new_value > 1.0]),
            "scale_down_countries": len([a for a in bid_actions if a.new_value and 0 < a.new_value < 1.0]),
            "exclude_countries": len([a for a in bid_actions if a.new_value == 0.0]),
        },
    }


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/config")
async def get_config():
    from app.config.settings import runtime_settings, settings
    cfg = runtime_settings.get_all()
    cfg["demo_mode"] = settings.DEMO_MODE
    return cfg


@router.put("/config")
async def update_config(updates: Dict):
    from app.config.settings import runtime_settings, CONFIGURABLE_KEYS
    errors = []
    updated = {}

    for key, value in updates.items():
        config_key = key.upper()
        if config_key not in CONFIGURABLE_KEYS:
            errors.append(f"Unknown setting: {key}")
            continue
        try:
            runtime_settings.set(config_key, value)
            updated[key] = runtime_settings.get(config_key)
        except ValueError as e:
            errors.append(str(e))

    if errors and not updated:
        raise HTTPException(status_code=400, detail={"errors": errors})

    cfg = runtime_settings.get_all()
    result = {"config": cfg, "updated": list(updated.keys())}
    if errors:
        result["warnings"] = errors
    return result


# ─── Action Approval Endpoints ───────────────────────────────────

@router.get("/actions/pending", response_model=List[OptimizationAction])
async def get_pending_actions(engine=Depends(get_engine)):
    return engine.get_pending_actions()


@router.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, engine=Depends(get_engine)):
    action = await engine.approve_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Pending action '{action_id}' not found.")
    return {"message": "Action approved", "action": action}


@router.post("/actions/{action_id}/reject")
async def reject_action(action_id: str, reason: str = "", engine=Depends(get_engine)):
    action = await engine.reject_action(action_id, reason)
    if not action:
        raise HTTPException(status_code=404, detail=f"Pending action '{action_id}' not found.")
    return {"message": "Action rejected", "action": action}


@router.post("/actions/approve-all")
async def approve_all_actions(engine=Depends(get_engine)):
    count = await engine.approve_all_pending()
    return {"message": f"{count} actions approved", "count": count}


@router.post("/campaigns/{platform}/{campaign_id}/enable")
async def reenable_campaign(platform: str, campaign_id: str, engine=Depends(get_engine)):
    """
    Re-enable a campaign on its platform.
    Useful for undoing earlier auto-pauses.
    """
    from app.models.schemas import Platform
    p = platform.lower()
    if p in ("google", "google_ads") and engine.google_ads:
        ok = await engine.google_ads.enable_campaign(campaign_id)
    elif p in ("meta", "meta_ads", "facebook") and engine.meta_ads:
        ok = await engine.meta_ads.enable_campaign(campaign_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}' or connector not initialized.")
    if not ok:
        raise HTTPException(status_code=500, detail="Platform call failed.")
    return {"message": f"Campaign {campaign_id} enabled on {p}"}


@router.post("/campaigns/bulk-enable")
async def bulk_enable_campaigns(
    platform: str,
    campaign_ids: List[str],
    engine=Depends(get_engine),
):
    """Bulk re-enable campaigns (e.g. to undo earlier auto-pauses on Meta)."""
    p = platform.lower()
    connector = None
    if p in ("google", "google_ads"):
        connector = engine.google_ads
    elif p in ("meta", "meta_ads", "facebook"):
        connector = engine.meta_ads
    if not connector:
        raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}'.")

    results = []
    for cid in campaign_ids:
        try:
            ok = await connector.enable_campaign(cid)
            results.append({"campaign_id": cid, "ok": ok})
        except Exception as e:
            results.append({"campaign_id": cid, "ok": False, "error": str(e)})
    return {"results": results, "total": len(results), "succeeded": sum(1 for r in results if r["ok"])}


# ─── Refresh metrics on already-scored posts (no re-scoring) ────────

@router.post("/social/posts/refresh-metrics")
async def refresh_scored_post_metrics(engine=Depends(get_engine)):
    """
    For every previously-scored post in Firestore, re-fetch metrics from Meta
    Graph API and update the `metrics` field. Preserves Gemini's text suggestions.
    Returns counts of {updated, unchanged, failed}.
    """
    if not engine.meta_social:
        raise HTTPException(503, "Meta connector not configured")

    from app import db as _db
    posts = await _db.get_scored_posts(limit=500)
    updated, unchanged, failed = 0, 0, 0
    for p in posts:
        post_id = p.get("post_id")
        platform = p.get("platform")
        if not post_id or not platform:
            failed += 1
            continue
        try:
            fresh = await engine.meta_social.get_post_metrics(platform, post_id)
            if not fresh:
                failed += 1
                continue
            old = p.get("metrics") or {}
            # Merge — keep ctr/clicks (paid) if present, overwrite organic
            merged = {**old, **fresh}
            if merged != old:
                p["metrics"] = merged
                await _db.save_scored_post(p)
                updated += 1
            else:
                unchanged += 1
        except Exception as e:
            import logging
            logging.getLogger("roas_engine").warning(
                f"Refresh metrics failed for {platform}/{post_id}: {e}"
            )
            failed += 1

    return {"total": len(posts), "updated": updated, "unchanged": unchanged, "failed": failed}


# ─── Social Post Scoring Rubric (so UI can display weights) ─────────

@router.get("/social/posts/scoring-config")
async def get_post_scoring_config():
    """Returns the criteria, weights, and tier thresholds — drives the UI info panel."""
    from app.seo.post_scorer import SCORING_WEIGHTS, TIER_THRESHOLDS
    return {
        "criteria": [
            {"key": "hook",    "label": "Hook",    "description": "Attention grab in first 3s / first line",     "weight": SCORING_WEIGHTS["hook"]},
            {"key": "message", "label": "Message", "description": "Value prop + CTA clarity",                    "weight": SCORING_WEIGHTS["message"]},
            {"key": "visual",  "label": "Visual",  "description": "Image/video quality, composition, lighting",  "weight": SCORING_WEIGHTS["visual"]},
            {"key": "script",  "label": "Script",  "description": "Copywriting craft — sharp, benefit-led",      "weight": SCORING_WEIGHTS["script"]},
            {"key": "brand",   "label": "Brand",   "description": "Brand identity (logo, colors, voice)",         "weight": SCORING_WEIGHTS["brand"]},
            {"key": "mobile",  "label": "Mobile",  "description": "Mobile-native framing (vertical, safe zones)", "weight": SCORING_WEIGHTS["mobile"]},
            {"key": "pacing",  "label": "Pacing",  "description": "Edit rhythm / narrative flow",                 "weight": SCORING_WEIGHTS["pacing"]},
        ],
        "tier_thresholds": TIER_THRESHOLDS,
        "formula": "overall_score (0-100) = Σ (criterion_score × weight) × 10",
        "context_signals": "Engagement metrics (reach, CTR, engagement rate, CPL) are passed to the AI as context — they influence individual criterion scores but are not a scored criterion themselves.",
    }


# ─── Homepage Theme Schema Snippet ──────────────────────────────────

@router.get("/seo/theme-snippet")
async def get_theme_schema_snippet(engine=Depends(get_engine)):
    """
    Returns a Liquid + JSON-LD snippet to paste into Shopify's theme.liquid.
    Covers homepage Organization + WebSite schema, populated from real brand data
    (Shopify shop info + Meta page + IG profile).
    """
    import json as _json

    brand_name = "MS. READ"
    brand_url = f"https://{settings.BRAND_DOMAIN}" if settings.BRAND_DOMAIN else None
    brand_logo = None
    description = None
    same_as = []

    # Pull real shop data if Shopify connected
    if settings.SHOPIFY_SHOP_DOMAIN and (settings.SHOPIFY_ACCESS_TOKEN or settings.SHOPIFY_CLIENT_ID):
        try:
            from app.connectors.shopify import ShopifyConnector
            shop = await ShopifyConnector().get_shop()
            brand_name = shop.get("name") or brand_name
            brand_url = f"https://{shop.get('domain') or settings.BRAND_DOMAIN}"
            description = shop.get("description") or shop.get("about")
        except Exception as e:
            import logging
            logging.getLogger("roas_engine").warning(f"Shop fetch for snippet failed: {e}")

    # Add social profiles if available
    if engine.meta_social:
        try:
            fb = await engine.meta_social.get_page_overview()
            if fb.get("url"):
                same_as.append(fb["url"])
        except Exception:
            pass
        try:
            ig = await engine.meta_social.get_instagram_overview()
            if ig.get("username"):
                same_as.append(f"https://instagram.com/{ig['username']}")
        except Exception:
            pass

    # Build the JSON-LD blocks
    organization_ld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand_name,
        "url": brand_url,
    }
    if description:
        organization_ld["description"] = description
    if same_as:
        organization_ld["sameAs"] = same_as

    website_ld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": brand_name,
        "url": brand_url,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{brand_url}/search?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }

    # Liquid wrapper — only renders on the homepage (template == 'index')
    liquid_snippet = (
        "{%- comment -%} ROAS Engine: homepage schema. Renders only on the home page. {%- endcomment -%}\n"
        "{%- if template contains 'index' -%}\n"
        "<script type=\"application/ld+json\">\n"
        + _json.dumps(organization_ld, indent=2, ensure_ascii=False)
        + "\n</script>\n<script type=\"application/ld+json\">\n"
        + _json.dumps(website_ld, indent=2, ensure_ascii=False)
        + "\n</script>\n"
        "{%- endif -%}\n"
    )

    return {
        "snippet": liquid_snippet,
        "organization_ld": organization_ld,
        "website_ld": website_ld,
        "instructions": [
            "1. In Shopify Admin: Online Store → Themes → ⋯ on your active theme → Edit code",
            "2. Open Layout → theme.liquid",
            "3. Find the closing </head> tag",
            "4. Paste the snippet just BEFORE </head>",
            "5. Click Save",
            "6. Test on https://search.google.com/test/rich-results — paste your homepage URL",
        ],
    }


# ─── Social KPIs (FB/IG) ────────────────────────────────────────────

@router.get("/social/overview")
async def get_social_overview(engine=Depends(get_engine)):
    """FB Page + IG Business followers, growth, reach, engagement (28d)."""
    if not engine.meta_social:
        return {
            "facebook": {}, "instagram": {},
            "_notice": "Connect META_PAGE_ID + META_INSTAGRAM_BUSINESS_ID for social KPIs.",
        }
    try:
        import asyncio
        fb_task = engine.meta_social.get_page_overview()
        ig_task = engine.meta_social.get_instagram_overview()
        fb, ig = await asyncio.gather(fb_task, ig_task, return_exceptions=True)
        if isinstance(fb, Exception):
            fb = {"error": str(fb)}
        if isinstance(ig, Exception):
            ig = {"error": str(ig)}
        return {"facebook": fb or {}, "instagram": ig or {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Social overview failed: {e}")


@router.get("/social/posts/scored")
async def get_scored_posts(
    max_posts: int = 4,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    score_new: bool = True,
    engine=Depends(get_engine),
):
    """
    Returns scored posts in the given date range.
    - Already-scored posts are loaded from Firestore (no re-scoring).
    - If score_new=true, additionally scores up to max_posts NEW posts in range.
    Date format: YYYY-MM-DD. Defaults: last 28 days.
    """
    from datetime import date, timedelta
    from app import db as _db

    # Default range: last 28 days
    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=28)).isoformat()

    if score_new:
        if not engine.meta_social:
            # Fall back to whatever is already saved
            saved = await _db.get_scored_posts(start_date=start_date, end_date=end_date)
            return {"count": len(saved), "posts": saved, "warning": "Meta Social not connected — showing saved scores only."}
        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY not set.")
        from app.seo.post_scorer import score_recent_posts
        results = await score_recent_posts(
            engine.meta_social,
            max_posts=max_posts,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        results = await _db.get_scored_posts(start_date=start_date, end_date=end_date)

    return {
        "count": len(results),
        "posts": results,
        "start_date": start_date,
        "end_date": end_date,
    }


@router.get("/social/posts/saved")
async def list_saved_scored_posts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Returns previously-scored posts only (no new scoring). Fast — for tab loads."""
    from app import db as _db
    saved = await _db.get_scored_posts(start_date=start_date, end_date=end_date)
    return {"count": len(saved), "posts": saved}


# ─── SEO Suggestion / AI-driven SEO Fixes ───────────────────────────

@router.post("/seo/suggestions/generate")
async def generate_seo_suggestions(
    max_pages: int = 5,
    engine=Depends(get_engine),
):
    """
    Crawl the site, run AI suggestions on the worst-scoring pages,
    and queue SEO_FIX actions in the approval queue.
    """
    from app.config.settings import settings
    from app.seo.ai_suggester import suggest_for_pages
    from app.crawlers.site_crawler import SiteCrawler
    from app.models.schemas import (
        OptimizationAction, ActionType, ActionStatus,
        DecisionConfidence, Platform,
    )
    from datetime import datetime

    # 1. Crawl the site
    if settings.DEMO_MODE:
        from app.demo_mode import _gen_site_crawl
        crawl = _gen_site_crawl()
        audits = crawl.get("pages", [])
    else:
        site_url = (
            settings.BRAND_SITEMAP_URL.replace("/sitemap.xml", "")
            if settings.BRAND_SITEMAP_URL else f"https://{settings.BRAND_DOMAIN}"
        )
        crawler = SiteCrawler(base_url=site_url, max_pages=20)
        crawl = await crawler.crawl_site()
        audits = crawl.get("pages", [])

    if not audits:
        raise HTTPException(status_code=404, detail="No pages crawled.")

    # 2. Connect to Shopify (optional — used to enrich + resolve resource ids)
    shopify_connector = None
    has_static_token = bool(settings.SHOPIFY_ACCESS_TOKEN or settings.SHOPIFY_ADMIN_API_TOKEN)
    has_oauth = bool(settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET)
    domain = settings.SHOPIFY_SHOP_DOMAIN or settings.SHOPIFY_STORE_URL
    if domain and (has_static_token or has_oauth):
        from app.connectors.shopify import ShopifyConnector
        try:
            shopify_connector = ShopifyConnector()
            import logging
            logging.getLogger("roas_engine").info(f"Shopify connector ready (oauth={has_oauth}, static_token={has_static_token})")
        except Exception as e:
            shopify_connector = None
            print(f"Shopify init failed: {e}")

    # 3. Run AI suggestions on worst pages
    suggestions = await suggest_for_pages(
        audits, max_pages=max_pages, shopify_connector=shopify_connector,
    )

    # 4. Queue each suggestion as a pending SEO_FIX action
    queued = []
    for s in suggestions:
        if s.get("error"):
            continue
        # Build a fix dict only with non-null fields
        fixes = {}
        for k in ("seo_title", "meta_description", "h1", "body_html"):
            if s.get(k):
                fixes[k] = s[k]
        # Schema JSON-LD: serialise as compact JSON string so it survives transport
        if s.get("schema_jsonld"):
            try:
                import json as _json
                fixes["schema_jsonld"] = _json.dumps(s["schema_jsonld"], indent=2, ensure_ascii=False)
            except Exception:
                pass
        if not fixes and not s.get("alt_text_suggestions"):
            continue  # nothing to fix

        # Find the original audit for the URL
        url = s.get("url")
        original = next((a for a in audits if a.get("url") == url), {})

        action = OptimizationAction(
            platform=Platform.SEO,
            campaign_id=None,
            action_type=ActionType.SEO_FIX,
            confidence=0.85,
            confidence_level=DecisionConfidence.HIGH,
            reason=s.get("rationale", "AI-generated SEO improvement"),
            old_value=None,
            new_value=None,
            status=ActionStatus.PENDING,
            details={
                "url": url,
                "shopify_resource": s.get("shopify_resource"),
                "current": {
                    "title": original.get("title"),
                    "meta_description": original.get("meta_description"),
                    "h1": (original.get("h1_tags") or [None])[0] if original.get("h1_tags") else None,
                    "score": original.get("score"),
                },
                "fixes": fixes,
                "alt_text_suggestions": s.get("alt_text_suggestions", []),
                "model": s.get("model"),
            },
        )
        engine.pending_actions.append(action)
        # Persist to Firestore so it survives restarts
        try:
            from app import db as _db
            await _db.save_action(action)
        except Exception as _e:
            pass
        queued.append({
            "id": action.id,
            "url": url,
            "fixes": fixes,
            "rationale": s.get("rationale"),
            "shopify_resource": s.get("shopify_resource"),
        })

    return {
        "generated": len(queued),
        "suggestions": queued,
        "message": f"{len(queued)} SEO suggestions queued for approval",
    }


@router.post("/seo/suggestions/{action_id}/approve")
async def approve_seo_suggestion(
    action_id: str,
    selected_fields: Optional[List[str]] = Body(default=None),
    engine=Depends(get_engine),
):
    """
    Approve an SEO suggestion, optionally limiting to a subset of fields.
    If selected_fields is provided, only those fields apply; remaining fields
    stay pending so user can review/approve separately.
    """
    from app.models.schemas import (
        ActionType, ActionStatus, OptimizationAction, DecisionConfidence,
    )
    from app import db as _db

    # Find the pending action
    target = next(
        (a for a in engine.pending_actions
         if a.id == action_id and a.action_type == ActionType.SEO_FIX),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"SEO suggestion '{action_id}' not found.")

    all_fixes = dict((target.details or {}).get("fixes", {}))

    # If user only picked some fields, split the action
    if selected_fields and set(selected_fields) != set(all_fixes.keys()):
        applied = {k: v for k, v in all_fixes.items() if k in selected_fields}
        leftover = {k: v for k, v in all_fixes.items() if k not in selected_fields}
        if not applied:
            raise HTTPException(status_code=400, detail="No matching fields in selection.")

        # 1) Update the original action to only contain the applied fields, then approve
        target.details["fixes"] = applied
        target.details["applied_fields"] = list(applied.keys())
        approved = await engine.approve_action(action_id)

        # 2) Create a NEW pending action for the leftover fields
        if leftover:
            new_action = OptimizationAction(
                platform=target.platform,
                campaign_id=target.campaign_id,
                action_type=ActionType.SEO_FIX,
                confidence=target.confidence,
                confidence_level=target.confidence_level,
                reason=target.reason,
                status=ActionStatus.PENDING,
                details={
                    **{k: v for k, v in target.details.items()
                       if k not in ("fixes", "applied_fields")},
                    "fixes": leftover,
                    "split_from": action_id,
                },
            )
            engine.pending_actions.append(new_action)
            try:
                await _db.save_action(new_action)
            except Exception:
                pass

        return {"message": "SEO suggestion partially approved",
                "applied": list(applied.keys()),
                "remaining_pending": list(leftover.keys()),
                "action": approved}

    # Otherwise approve all fixes
    action = await engine.approve_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Pending action '{action_id}' not found.")
    return {"message": "SEO suggestion approved", "action": action}


@router.post("/seo/suggestions/{action_id}/reject-field")
async def reject_seo_field(
    action_id: str,
    field: str,
    engine=Depends(get_engine),
):
    """Remove a single field from a pending suggestion (without applying it)."""
    from app.models.schemas import ActionType
    from app import db as _db

    target = next(
        (a for a in engine.pending_actions
         if a.id == action_id and a.action_type == ActionType.SEO_FIX),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"SEO suggestion '{action_id}' not found.")

    fixes = (target.details or {}).get("fixes", {})
    if field not in fixes:
        raise HTTPException(status_code=400, detail=f"Field '{field}' not in suggestion.")

    fixes.pop(field)
    if not fixes:
        # No fixes left — reject the entire suggestion
        rejected = await engine.reject_action(action_id, reason=f"All fields rejected (last: {field})")
        return {"message": "Suggestion fully rejected (all fields removed)",
                "action": rejected}

    # Save updated suggestion
    target.details["fixes"] = fixes
    try:
        await _db.save_action(target)
    except Exception:
        pass
    return {"message": f"Field '{field}' rejected", "remaining_fields": list(fixes.keys())}


@router.get("/seo/suggestions/pending")
async def get_pending_seo_suggestions(engine=Depends(get_engine)):
    """List pending SEO_FIX actions with current vs suggested diff data."""
    from app.models.schemas import ActionType
    pending = [
        a for a in engine.pending_actions
        if a.action_type == ActionType.SEO_FIX
    ]
    return [
        {
            "id": a.id,
            "url": (a.details or {}).get("url"),
            "rationale": a.reason,
            "current": (a.details or {}).get("current", {}),
            "fixes": (a.details or {}).get("fixes", {}),
            "alt_text_suggestions": (a.details or {}).get("alt_text_suggestions", []),
            "shopify_resource": (a.details or {}).get("shopify_resource"),
            "confidence": a.confidence,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in pending
    ]


# ─── Learning / Self-Improvement Endpoints ──────────────────────────

@router.get("/learning/stats")
async def get_learning_stats(engine=Depends(get_engine)):
    return await engine.learning.get_stats()


@router.get("/learning/history")
async def get_learning_history(limit: int = 50, engine=Depends(get_engine)):
    return await engine.learning.get_history(limit)
