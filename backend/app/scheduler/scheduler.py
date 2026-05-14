"""
Engine Scheduler
Runs autonomous optimization tasks on schedule using APScheduler.
"""
import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config.settings import settings, runtime_settings
from app.models.schemas import ActionType
from app.optimizers.decision_engine import AutonomousDecisionEngine

logger = logging.getLogger("roas_engine.scheduler")


class EngineScheduler:

    def __init__(self, engine: AutonomousDecisionEngine):
        self.engine = engine
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        # Anomaly check every 15 minutes
        self.scheduler.add_job(
            self._anomaly_check,
            trigger=IntervalTrigger(minutes=15),
            id="anomaly_check",
            name="Anomaly Detection",
            replace_existing=True,
        )

        # Full optimization cycle (default 60 min)
        self.scheduler.add_job(
            self._optimization_cycle,
            trigger=IntervalTrigger(
                minutes=settings.OPTIMIZATION_CYCLE_MINUTES
            ),
            id="optimization_cycle",
            name="ROAS Optimization Cycle",
            replace_existing=True,
        )

        # GEO optimization every 6 hours
        self.scheduler.add_job(
            self._geo_optimization,
            trigger=IntervalTrigger(
                hours=settings.BUDGET_REALLOCATION_FREQUENCY_HOURS
            ),
            id="geo_optimization",
            name="GEO Bid Optimization",
            replace_existing=True,
        )

        # SEO audit every 24 hours (keyword/cannibalization analysis)
        self.scheduler.add_job(
            self._seo_audit,
            trigger=IntervalTrigger(
                hours=settings.SEO_AUDIT_INTERVAL_HOURS
            ),
            id="seo_audit",
            name="SEO Audit",
            replace_existing=True,
        )

        # On-page crawl + AI SEO suggestions (weekly by default)
        self.scheduler.add_job(
            self._onpage_seo_suggestions,
            trigger=IntervalTrigger(
                hours=settings.ONPAGE_SCAN_INTERVAL_HOURS
            ),
            id="onpage_seo_suggestions",
            name="On-Page SEO Crawl + AI Suggestions",
            replace_existing=True,
        )

        # Daily report at configured hour
        self.scheduler.add_job(
            self._daily_report,
            trigger=CronTrigger(hour=settings.REPORT_GENERATION_HOUR, minute=0),
            id="daily_report",
            name="Daily Performance Report",
            replace_existing=True,
        )

    def start(self):
        self.scheduler.start()
        logger.info("ROAS Engine Scheduler started.")

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("ROAS Engine Scheduler stopped.")

    async def _anomaly_check(self):
        logger.info("[Scheduler] Running anomaly check...")
        try:
            await self.engine._sync_all_platforms()
            anomalies = self.engine._check_for_anomalies()
            if anomalies:
                logger.warning(
                    f"[Scheduler] {len(anomalies)} anomalies detected — executing emergency actions."
                )
                approved = await self.engine.evaluate_actions(anomalies)
                for action in approved:
                    action.applied = True
                self.engine.action_history.extend(approved)
            else:
                logger.info("[Scheduler] No anomalies detected.")
        except Exception as e:
            logger.error(f"[Scheduler] Anomaly check failed: {e}")

    async def _optimization_cycle(self):
        logger.info("[Scheduler] Running optimization cycle...")
        try:
            snapshot = await self.engine.run_optimization_cycle()
            logger.info(
                f"[Scheduler] Optimization complete. "
                f"ROAS={snapshot.blended_roas:.2f}, "
                f"actions={snapshot.actions_applied}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] Optimization cycle failed: {e}")

    async def _geo_optimization(self):
        logger.info("[Scheduler] Running GEO optimization...")
        try:
            from app.analyzers.geo_optimizer import GeoOptimizer
            lookback = date.today() - timedelta(days=int(runtime_settings.get("LOOKBACK_DAYS")))
            today = date.today()

            google_geo = []
            meta_geo = []

            if self.engine.google_ads:
                google_geo = await self.engine.google_ads.get_geo_performance(
                    lookback, today
                )
            if self.engine.meta_ads:
                meta_geo = await self.engine.meta_ads.get_geo_performance(
                    lookback, today
                )

            optimizer = GeoOptimizer()
            summary = optimizer.analyze_geo_performance(google_geo, meta_geo)
            actions = optimizer.generate_bid_modifier_actions(summary)
            logger.info(
                f"[Scheduler] GEO optimization: {len(actions)} actions generated."
            )
        except Exception as e:
            logger.error(f"[Scheduler] GEO optimization failed: {e}")

    async def _seo_audit(self):
        logger.info("[Scheduler] Running SEO audit...")
        try:
            from app.analyzers.seo_analyzer import SEOAnalyzer
            lookback = date.today() - timedelta(days=int(runtime_settings.get("LOOKBACK_DAYS")))
            today = date.today()

            organic_queries = []
            paid_search_terms = []
            query_page_matrix = []

            if self.engine.gsc:
                organic_queries = await self.engine.gsc.get_top_queries(
                    lookback, today
                )
                query_page_matrix = await self.engine.gsc.get_query_page_matrix(
                    lookback, today
                )
            if self.engine.google_ads:
                paid_search_terms = await self.engine.google_ads.get_search_terms_report(
                    lookback, today
                )

            analyzer = SEOAnalyzer()

            # Analysis (for logging)
            opportunities = analyzer.find_keyword_opportunities(
                organic_queries, paid_search_terms
            )
            gaps = analyzer.find_content_gaps(organic_queries, paid_search_terms)
            quick_wins = analyzer.find_quick_wins(organic_queries)

            # Generate autonomous actions
            seo_actions = analyzer.generate_seo_actions(
                organic_queries, paid_search_terms, query_page_matrix
            )

            # Route through decision engine for approval
            if seo_actions:
                approved = await self.engine.evaluate_actions(seo_actions)
                for action in approved:
                    action.applied = True
                self.engine.action_history.extend(approved)

                # Count by type
                bid_actions = [a for a in approved if a.action_type in (
                    ActionType.PAUSE_KEYWORD, ActionType.DECREASE_BID
                )]
                seo_fixes = [a for a in approved if a.action_type == ActionType.SEO_FIX]
                total_savings = sum(
                    a.details.get("estimated_savings", 0) for a in bid_actions
                )

                logger.info(
                    f"[Scheduler] SEO audit complete. "
                    f"Opportunities={len(opportunities)}, Gaps={len(gaps)}, "
                    f"QuickWins={len(quick_wins)}. "
                    f"Actions: {len(bid_actions)} bid reductions "
                    f"(est. savings ${total_savings:,.0f}), "
                    f"{len(seo_fixes)} SEO fixes. "
                    f"Total approved: {len(approved)}/{len(seo_actions)}"
                )
            else:
                logger.info(
                    f"[Scheduler] SEO audit complete. "
                    f"Opportunities={len(opportunities)}, "
                    f"Gaps={len(gaps)}, QuickWins={len(quick_wins)}. "
                    f"No actions generated."
                )
        except Exception as e:
            logger.error(f"[Scheduler] SEO audit failed: {e}")

    async def _onpage_seo_suggestions(self):
        """
        Weekly: crawl the site, run Gemini AI suggester on lowest-scoring pages,
        queue SEO_FIX actions for user approval.
        """
        logger.info("[Scheduler] Running on-page SEO crawl + AI suggestions...")
        try:
            from app.crawlers.site_crawler import SiteCrawler
            from app.seo.ai_suggester import suggest_for_pages
            from app.connectors.shopify import ShopifyConnector
            from app.models.schemas import (
                OptimizationAction, ActionType, ActionStatus,
                DecisionConfidence, Platform,
            )

            # Skip if demo mode (no real site to crawl)
            if settings.DEMO_MODE:
                logger.info("[Scheduler] DEMO_MODE — skipping live crawl.")
                return

            # 1. Crawl
            site_url = (
                settings.BRAND_SITEMAP_URL.replace("/sitemap.xml", "")
                if settings.BRAND_SITEMAP_URL else f"https://{settings.BRAND_DOMAIN}"
            )
            crawler = SiteCrawler(base_url=site_url, max_pages=20)
            crawl = await crawler.crawl_site()
            audits = crawl.get("pages", [])
            logger.info(f"[Scheduler] Crawled {len(audits)} pages.")

            if not audits:
                return

            # 2. Connect Shopify if configured (static token OR OAuth client_credentials)
            shopify_connector = None
            has_static_token = bool(settings.SHOPIFY_ACCESS_TOKEN or settings.SHOPIFY_ADMIN_API_TOKEN)
            has_oauth = bool(settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET)
            domain = settings.SHOPIFY_SHOP_DOMAIN or settings.SHOPIFY_STORE_URL
            if domain and (has_static_token or has_oauth):
                try:
                    shopify_connector = ShopifyConnector()
                except Exception as e:
                    logger.warning(f"Shopify init failed: {e}")

            # 3. AI suggest on worst pages
            max_pages = settings.AI_SUGGESTIONS_PER_RUN
            suggestions = await suggest_for_pages(
                audits, max_pages=max_pages, shopify_connector=shopify_connector,
            )

            # 4. Queue as pending actions
            queued = 0
            for s in suggestions:
                if s.get("error"):
                    continue
                fixes = {k: s[k] for k in ("seo_title", "meta_description", "h1", "body_html") if s.get(k)}
                if not fixes and not s.get("alt_text_suggestions"):
                    continue
                url = s.get("url")
                original = next((a for a in audits if a.get("url") == url), {})
                action = OptimizationAction(
                    platform=Platform.SEO,
                    campaign_id=None,
                    action_type=ActionType.SEO_FIX,
                    confidence=0.85,
                    confidence_level=DecisionConfidence.HIGH,
                    reason=s.get("rationale", "Weekly AI SEO scan suggestion"),
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
                        "source": "scheduled_weekly_scan",
                    },
                )
                self.engine.pending_actions.append(action)
                try:
                    from app import db as _db
                    await _db.save_action(action)
                except Exception:
                    pass
                queued += 1

            logger.info(f"[Scheduler] Queued {queued} AI SEO suggestions for approval.")
        except Exception as e:
            logger.error(f"[Scheduler] On-page SEO suggestion job failed: {e}")

    async def _daily_report(self):
        logger.info("[Scheduler] Generating daily report...")
        try:
            snapshot = self.engine.get_last_snapshot()
            if not snapshot:
                logger.info("[Scheduler] No snapshot available for daily report.")
                return

            logger.info(
                f"[Scheduler] Daily Report — "
                f"Spend=${snapshot.total_spend:.2f}, "
                f"Revenue=${snapshot.total_revenue:.2f}, "
                f"ROAS={snapshot.blended_roas:.2f}, "
                f"Campaigns={snapshot.num_active_campaigns}/{snapshot.num_campaigns}"
            )

            if settings.SLACK_WEBHOOK_URL:
                from app.utils.notifications import send_slack_notification
                await send_slack_notification(snapshot)
        except Exception as e:
            logger.error(f"[Scheduler] Daily report failed: {e}")
