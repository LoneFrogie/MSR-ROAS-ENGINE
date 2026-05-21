"""
ROAS Optimization Engine — FastAPI Application Entry Point
"""
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.optimizers.decision_engine import AutonomousDecisionEngine
from app.scheduler.scheduler import EngineScheduler
from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("roas_engine.main")

# Global engine instance
engine = AutonomousDecisionEngine()
scheduler: EngineScheduler = None


def _init_connectors():
    """Initialize platform connectors. Uses demo mode if DEMO_MODE=true or no real credentials found."""
    demo_mode = getattr(settings, "DEMO_MODE", True)

    if demo_mode:
        from app.demo_mode import create_demo_connectors
        engine.google_ads, engine.meta_ads, engine.gsc = create_demo_connectors()
        logger.info("*** DEMO MODE — using simulated data ***")
        return

    try:
        if settings.GOOGLE_ADS_CUSTOMER_ID and settings.GOOGLE_ADS_DEVELOPER_TOKEN:
            from app.connectors.google_ads import GoogleAdsConnector
            engine.google_ads = GoogleAdsConnector()
            logger.info("Google Ads connector initialized.")
    except Exception as e:
        logger.warning(f"Google Ads connector not initialized: {e}")

    try:
        if settings.META_AD_ACCOUNT_ID and settings.META_ACCESS_TOKEN:
            from app.connectors.meta_ads import MetaAdsConnector
            engine.meta_ads = MetaAdsConnector()
            logger.info("Meta Ads connector initialized.")
    except Exception as e:
        logger.warning(f"Meta Ads connector not initialized: {e}")

    try:
        if settings.META_ACCESS_TOKEN and (settings.META_PAGE_ID or settings.META_INSTAGRAM_BUSINESS_ID):
            from app.connectors.meta_social import MetaSocialConnector
            engine.meta_social = MetaSocialConnector()
            logger.info("Meta Social (FB/IG) connector initialized.")
    except Exception as e:
        logger.warning(f"Meta Social connector not initialized: {e}")

    try:
        if settings.GSC_CREDENTIALS_JSON and settings.GSC_SITE_URL:
            from app.connectors.google_search_console import GoogleSearchConsoleConnector
            engine.gsc = GoogleSearchConsoleConnector()
            logger.info("Google Search Console connector initialized.")
    except Exception as e:
        logger.warning(f"GSC connector not initialized: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize Firestore persistence (soft failure for local dev without GCP creds)
    from app.db import init_db, get_pending_actions
    try:
        await init_db()
        await engine.learning.load_from_db()
        logger.info("Firestore initialized, learning state loaded.")
    except Exception as e:
        logger.warning(f"Firestore startup skipped (likely local dev without creds): {e}")

    # Rehydrate the last snapshot from Firestore so the dashboard isn't empty
    # immediately after a container restart while the next cycle runs.
    try:
        from app.db import get_latest_snapshot
        from app.models.schemas import PerformanceSnapshot
        latest = await get_latest_snapshot()
        if latest:
            try:
                # Reconstruct PerformanceSnapshot from raw dict
                latest.pop("id", None)
                latest.pop("created_at", None)
                # platform_breakdown / alerts may already be dicts (Firestore stores them as objects)
                snap = PerformanceSnapshot(**latest)
                engine.last_snapshot = snap
                logger.info(f"Rehydrated last snapshot from Firestore: ROAS={snap.blended_roas:.2f}")
            except Exception as e:
                # If schema mismatch, keep raw dict so /snapshot fallback can still serve it
                logger.warning(f"Could not parse snapshot into model: {e}")
    except Exception as e:
        logger.error(f"Snapshot rehydration failed: {e}")

    # Rehydrate pending actions from Firestore so they survive restarts
    try:
        from app.models.schemas import (
            OptimizationAction, ActionType, ActionStatus,
            DecisionConfidence, Platform,
        )
        pending_rows = await get_pending_actions(limit=500)
        for row in pending_rows:
            try:
                action = OptimizationAction(
                    id=row["id"],
                    platform=Platform(row["platform"]),
                    campaign_id=row.get("campaign_id"),
                    adgroup_id=row.get("adgroup_id"),
                    action_type=ActionType(row["action_type"]),
                    old_value=row.get("old_value"),
                    new_value=row.get("new_value"),
                    reason=row.get("reason", ""),
                    confidence=row.get("confidence", 0.0),
                    confidence_level=DecisionConfidence(row["confidence_level"]) if row.get("confidence_level") else None,
                    status=ActionStatus.PENDING,
                    details=row.get("details") or {},
                )
                engine.pending_actions.append(action)
            except Exception as e:
                logger.warning(f"Failed to rehydrate action {row.get('id')}: {e}")
        logger.info(f"Rehydrated {len(engine.pending_actions)} pending actions from Firestore")
    except Exception as e:
        logger.error(f"Pending action rehydration failed: {e}")

    _init_connectors()

    scheduler = EngineScheduler(engine)
    scheduler.start()
    logger.info("Scheduler started — engine is live.")

    # Schedule initial cycle 30s after startup so uvicorn has time to bind port 8080.
    # The Google Ads SDK is synchronous and would block the event loop if run during
    # startup, breaking Cloud Run's startup probe.
    import asyncio

    async def _delayed_initial_cycle():
        await asyncio.sleep(30)
        try:
            logger.info("Running initial optimization cycle (delayed)...")
            await engine.run_optimization_cycle()
            logger.info("Initial optimization cycle complete.")
        except Exception as e:
            logger.error(f"Initial optimization cycle failed: {e}")

    asyncio.create_task(_delayed_initial_cycle())

    yield
    if scheduler:
        scheduler.stop()
    logger.info("Engine shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# ─── Serve Frontend Static Files (Cloud Run / Docker) ───
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.is_dir():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # SPA fallback: all non-API routes return index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }
