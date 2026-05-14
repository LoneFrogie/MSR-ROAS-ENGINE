"""
Autonomous Decision Engine
Coordinates all optimizers and executes actions with 3 approval modes.
"""
from typing import List, Dict, Optional
from datetime import datetime

from app.models.schemas import (
    UnifiedCampaign, CampaignScore, OptimizationAction,
    ActionType, ActionStatus, DecisionConfidence, PerformanceSnapshot,
    CampaignStatus,
)
from app.config.settings import settings, runtime_settings, ApprovalMode
from app.learning import LearningEngine
from app import db

import logging

logger = logging.getLogger("roas_engine.decision_engine")


class AutonomousDecisionEngine:

    def __init__(self):
        self.google_ads = None
        self.meta_ads = None
        self.meta_social = None
        self.gsc = None
        self.action_history: List[OptimizationAction] = []
        self.pending_actions: List[OptimizationAction] = []
        self.last_snapshot: Optional[PerformanceSnapshot] = None
        self.current_campaigns: List[UnifiedCampaign] = []
        self.learning = LearningEngine()

    # ─── Approval Mode Logic ─────────────────────────────────────────

    async def _persist_pending(self, action: OptimizationAction) -> None:
        try:
            await db.save_action(action)
        except Exception:
            pass

    async def evaluate_actions(
        self, actions: List[OptimizationAction]
    ) -> List[OptimizationAction]:
        """
        Route actions based on approval mode:
        - FULL_AUTO: auto-approve above confidence threshold
        - SEMI_AUTO: auto-approve high confidence (>=0.85), queue the rest
        - FULL_MANUAL: queue everything (incl. emergency stops)
        Pending actions are persisted to Firestore so they survive restarts.
        """
        mode = ApprovalMode(runtime_settings.get("APPROVAL_MODE"))
        threshold = float(runtime_settings.get("CONFIDENCE_THRESHOLD"))

        approved = []
        for action in actions:
            # Apply learned confidence calibration
            action.confidence = self.learning.adjust_confidence(
                action.action_type, action.confidence
            )

            # Filter by confidence threshold first
            if action.confidence < threshold:
                action.status = ActionStatus.REJECTED
                action.rejected_at = datetime.now()
                action.result = f"Below confidence threshold ({action.confidence:.2f} < {threshold:.2f})"
                continue

            if mode == ApprovalMode.FULL_AUTO:
                # Auto-approve everything above threshold (incl. emergency stops)
                action.status = ActionStatus.EXECUTED
                action.executed = True
                action.approved_at = datetime.now()
                action.applied = True
                approved.append(action)

            elif mode == ApprovalMode.SEMI_AUTO:
                # High confidence (>= 0.85) auto-executes
                if action.confidence >= 0.85:
                    action.status = ActionStatus.EXECUTED
                    action.executed = True
                    action.approved_at = datetime.now()
                    action.applied = True
                    approved.append(action)
                else:
                    # Medium confidence goes to pending queue
                    action.status = ActionStatus.PENDING
                    self.pending_actions.append(action)
                    await self._persist_pending(action)

            elif mode == ApprovalMode.FULL_MANUAL:
                # Everything (incl. emergency stops) goes to pending queue
                action.status = ActionStatus.PENDING
                self.pending_actions.append(action)
                await self._persist_pending(action)

        return approved

    # ─── Pending Action Management ───────────────────────────────────

    def get_pending_actions(self) -> List[OptimizationAction]:
        return [a for a in self.pending_actions if a.status == ActionStatus.PENDING]

    async def approve_action(self, action_id: str) -> Optional[OptimizationAction]:
        for action in self.pending_actions:
            if action.id == action_id and action.status == ActionStatus.PENDING:
                action.status = ActionStatus.APPROVED
                action.approved_at = datetime.now()
                action.applied = True

                # Execute SEO_FIX via Shopify
                if action.action_type == ActionType.SEO_FIX:
                    details = action.details or {}
                    has_resource = bool((details.get("shopify_resource") or {}).get("id"))

                    if has_resource:
                        try:
                            from app.seo.executor import execute_seo_fix
                            result = await execute_seo_fix(action)
                            action.result = result.get("message", "Applied to Shopify")
                            action.executed_at = datetime.now()
                            action.status = ActionStatus.EXECUTED
                        except Exception as e:
                            logger.error(f"SEO fix execution failed: {e}")
                            action.result = f"Execution failed: {str(e)}"
                            action.status = ActionStatus.REJECTED
                    else:
                        action.result = (
                            "Approved — apply manually: Shopify Admin → "
                            "Online Store → Preferences (or relevant page settings)"
                        )

                # Execute campaign actions on the source platform
                else:
                    try:
                        platform_result = await self._execute_campaign_action(action)
                        if platform_result is not None:
                            action.result = platform_result
                            action.executed_at = datetime.now()
                            action.status = ActionStatus.EXECUTED
                    except Exception as e:
                        logger.error(f"Campaign action execution failed: {e}")
                        action.result = f"Execution failed: {str(e)}"
                        action.status = ActionStatus.REJECTED

                self.pending_actions.remove(action)
                self.action_history.append(action)
                await db.save_action(action)
                return action
        return None

    async def _execute_campaign_action(self, action: OptimizationAction) -> Optional[str]:
        """Push an approved campaign action (pause / budget change / bid) to the platform."""
        from app.models.schemas import Platform

        if not action.campaign_id:
            return None

        connector = None
        if action.platform == Platform.GOOGLE_ADS:
            connector = self.google_ads
        elif action.platform == Platform.META_ADS:
            connector = self.meta_ads
        if connector is None:
            return f"Connector for {action.platform} not initialized — skipped"

        if action.action_type in (ActionType.PAUSE_CAMPAIGN, ActionType.EMERGENCY_STOP):
            ok = await connector.pause_campaign(action.campaign_id)
            return "Paused on platform" if ok else "Pause failed on platform"

        if action.action_type == ActionType.RESUME_CAMPAIGN or action.action_type == ActionType.ENABLE_CAMPAIGN:
            ok = await connector.enable_campaign(action.campaign_id)
            return "Enabled on platform" if ok else "Enable failed on platform"

        if action.action_type in (ActionType.INCREASE_BUDGET, ActionType.DECREASE_BUDGET):
            try:
                new_budget = float(action.new_value)
            except (TypeError, ValueError):
                return "Budget value missing — skipped"
            ok = await connector.update_campaign_budget(action.campaign_id, new_budget)
            return f"Budget set to ${new_budget:.2f}" if ok else "Budget update failed"

        # Other action types not yet wired up — just mark approved
        return f"Approved (no platform executor for {action.action_type.value})"

    async def reject_action(self, action_id: str, reason: str = "") -> Optional[OptimizationAction]:
        for action in self.pending_actions:
            if action.id == action_id and action.status == ActionStatus.PENDING:
                action.status = ActionStatus.REJECTED
                action.rejected_at = datetime.now()
                if reason:
                    action.result = f"Rejected: {reason}"
                self.pending_actions.remove(action)
                self.action_history.append(action)
                await db.save_action(action)
                return action
        return None

    async def approve_all_pending(self) -> int:
        count = 0
        pending = [a for a in self.pending_actions if a.status == ActionStatus.PENDING]
        for action in pending:
            action.status = ActionStatus.APPROVED
            action.approved_at = datetime.now()
            action.applied = True
            self.pending_actions.remove(action)
            self.action_history.append(action)
            await db.save_action(action)
            count += 1
        return count

    # ─── Budget Filtering ────────────────────────────────────────────

    def _is_anomaly(self, action: OptimizationAction) -> bool:
        if action.old_value is None or action.new_value is None:
            return False
        try:
            old = float(action.old_value)
            new = float(action.new_value)
        except (ValueError, TypeError):
            return False
        if new > old:
            return False
        threshold = float(runtime_settings.get("ANOMALY_SPEND_THRESHOLD_PCT"))
        pct_change = abs(new - old) / old
        return pct_change > (threshold / 100)

    def filter_by_budget_availability(
        self,
        actions: List[OptimizationAction],
        available_budget: float,
    ) -> List[OptimizationAction]:
        emergency = [a for a in actions if a.action_type == ActionType.EMERGENCY_STOP]
        increases = [a for a in actions if a.action_type == ActionType.INCREASE_BUDGET]
        decreases = [a for a in actions if a.action_type == ActionType.DECREASE_BUDGET]
        pauses = [a for a in actions if a.action_type == ActionType.PAUSE_CAMPAIGN]

        approved = emergency + pauses
        total_increase = sum(
            max(0, a.new_value - a.old_value) for a in increases
            if a.old_value and a.new_value
        )

        if total_increase > available_budget:
            increases.sort(key=lambda a: a.confidence, reverse=True)
            budget_remaining = available_budget
            for action in increases:
                if action.old_value and action.new_value:
                    increase_amt = action.new_value - action.old_value
                    if increase_amt <= budget_remaining:
                        approved.append(action)
                        budget_remaining -= increase_amt
        else:
            approved.extend(increases)

        approved.extend(decreases)
        return approved

    # ─── Core Optimization Cycle ─────────────────────────────────────

    async def run_optimization_cycle(self) -> PerformanceSnapshot:
        from datetime import timedelta, date
        from app.optimizers.roas_optimizer import ROASOptimizer
        from app.optimizers.budget_allocator import CrossPlatformBudgetAllocator

        lookback_days = int(runtime_settings.get("LOOKBACK_DAYS"))
        all_campaigns = []
        lookback_date = date.today() - timedelta(days=lookback_days)

        if self.google_ads:
            logger.info(f"[Cycle] Fetching Google Ads campaigns ({lookback_date} to {date.today()})...")
            try:
                google_camps = await self.google_ads.get_campaigns(lookback_date, date.today())
                logger.info(f"[Cycle] Google Ads returned {len(google_camps)} campaigns")
                all_campaigns.extend(google_camps)
            except Exception as e:
                logger.error(f"[Cycle] Google Ads fetch failed: {e}")

        if self.meta_ads:
            logger.info(f"[Cycle] Fetching Meta Ads campaigns...")
            try:
                meta_camps = await self.meta_ads.get_campaigns(lookback_date, date.today())
                logger.info(f"[Cycle] Meta Ads returned {len(meta_camps)} campaigns")
                all_campaigns.extend(meta_camps)
            except Exception as e:
                logger.error(f"[Cycle] Meta Ads fetch failed: {e}")

        historical_campaigns = []
        hist_date = date.today() - timedelta(days=lookback_days * 2)

        if self.google_ads:
            try:
                logger.info(f"[Cycle] Fetching Google Ads historical ({hist_date} to {lookback_date})...")
                hist_google = await self.google_ads.get_campaigns(hist_date, lookback_date)
                logger.info(f"[Cycle] Google Ads historical: {len(hist_google)} campaigns")
                historical_campaigns.extend(hist_google)
            except Exception as e:
                logger.warning(f"[Cycle] Google Ads historical fetch failed (non-fatal): {e}")

        if self.meta_ads:
            try:
                logger.info(f"[Cycle] Fetching Meta historical...")
                hist_meta = await self.meta_ads.get_campaigns(hist_date, lookback_date)
                logger.info(f"[Cycle] Meta historical: {len(hist_meta)} campaigns")
                historical_campaigns.extend(hist_meta)
            except Exception as e:
                logger.warning(f"[Cycle] Meta historical fetch failed (non-fatal): {e}")

        logger.info(f"[Cycle] Total campaigns: {len(all_campaigns)} current, {len(historical_campaigns)} historical")

        optimizer = ROASOptimizer()
        learned_weights = self.learning.get_learned_weights()
        scores = optimizer.analyze_campaigns(
            all_campaigns, historical_campaigns,
            weight_overrides=learned_weights,
        )
        actions = optimizer.generate_actions(scores)

        allocator = CrossPlatformBudgetAllocator()
        allocation = allocator.calculate_allocation(all_campaigns)
        realloc_actions = allocator.generate_reallocation_actions(allocation, all_campaigns)
        actions.extend(realloc_actions)

        approved_actions = await self.evaluate_actions(actions)

        total_spend = sum(c.spend for c in all_campaigns)
        total_revenue = sum(c.revenue for c in all_campaigns)
        blended_roas = total_revenue / total_spend if total_spend > 0 else 0

        platform_breakdown = {}
        for camp in all_campaigns:
            plat = camp.platform.value
            if plat not in platform_breakdown:
                platform_breakdown[plat] = {
                    "spend": 0, "total_spend": 0,
                    "revenue": 0, "total_revenue": 0, "roas": 0
                }
            platform_breakdown[plat]["spend"] += camp.spend
            platform_breakdown[plat]["total_spend"] += camp.spend
            platform_breakdown[plat]["revenue"] += camp.revenue
            platform_breakdown[plat]["total_revenue"] += camp.revenue

        for plat in platform_breakdown:
            spend = platform_breakdown[plat]["spend"]
            rev = platform_breakdown[plat]["revenue"]
            platform_breakdown[plat]["roas"] = rev / spend if spend > 0 else 0

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            total_spend=total_spend,
            total_revenue=total_revenue,
            blended_roas=blended_roas,
            total_conversions=sum(c.conversions for c in all_campaigns),
            num_campaigns=len(all_campaigns),
            num_active_campaigns=len([c for c in all_campaigns if c.status.value == "active"]),
            platform_breakdown=platform_breakdown,
            actions_taken=approved_actions,
            actions_applied=len([a for a in approved_actions if a.applied]),
        )

        self.action_history.extend(approved_actions)
        self.last_snapshot = snapshot
        self.current_campaigns = all_campaigns

        # Persist to Firestore and run self-improvement
        try:
            snapshot_id = await db.save_snapshot(snapshot, all_campaigns)
            for action in approved_actions:
                await db.save_action(action)
            learning_result = await self.learning.run_improvement_cycle(snapshot_id)
            logger.info(f"Learning: {learning_result}")
        except Exception as e:
            logger.warning(f"Persistence/learning error (non-fatal): {e}")

        return snapshot

    # ─── Accessors ───────────────────────────────────────────────────

    def get_action_history(self) -> List[OptimizationAction]:
        return self.action_history

    def get_last_snapshot(self) -> Optional[PerformanceSnapshot]:
        return self.last_snapshot

    def get_platform_summary(self) -> Dict[str, Dict]:
        if not self.last_snapshot:
            return {}
        return self.last_snapshot.platform_breakdown

    async def _sync_all_platforms(self) -> None:
        from datetime import timedelta, date
        self.current_campaigns = []
        lookback_days = int(runtime_settings.get("LOOKBACK_DAYS"))
        lookback_date = date.today() - timedelta(days=lookback_days)

        if self.google_ads:
            try:
                camps = await self.google_ads.get_campaigns(lookback_date, date.today())
                self.current_campaigns.extend(camps)
            except Exception:
                pass

        if self.meta_ads:
            try:
                camps = await self.meta_ads.get_campaigns(lookback_date, date.today())
                self.current_campaigns.extend(camps)
            except Exception:
                pass

    def _check_for_anomalies(self) -> List[OptimizationAction]:
        anomalies = []
        lookback_days = int(runtime_settings.get("LOOKBACK_DAYS"))
        emergency_roas = float(runtime_settings.get("EMERGENCY_STOP_ROAS_BELOW"))
        # Minimum spend required to consider a campaign for emergency-stop.
        # Avoids paused/inactive campaigns being flagged with ROAS=0.
        min_spend = float(runtime_settings.get("EMERGENCY_STOP_MIN_SPEND"))

        for campaign in self.current_campaigns:
            # Skip non-active campaigns — they have no live spend
            if campaign.status != CampaignStatus.ACTIVE:
                continue
            # Skip campaigns with no meaningful spend in the window
            if campaign.spend < min_spend:
                continue

            expected_spend = campaign.daily_budget * lookback_days
            if campaign.spend > expected_spend * 1.5 and expected_spend > 0:
                anomalies.append(OptimizationAction(
                    platform=campaign.platform,
                    campaign_id=campaign.platform_campaign_id,
                    action_type=ActionType.PAUSE_CAMPAIGN,
                    reason=(
                        f"SPENDING ANOMALY: Spent {campaign.spend:.2f} "
                        f"vs expected {expected_spend:.2f}"
                    ),
                    confidence=0.95,
                    confidence_level=DecisionConfidence.HIGH,
                ))
            if campaign.roas < emergency_roas:
                anomalies.append(OptimizationAction(
                    platform=campaign.platform,
                    campaign_id=campaign.platform_campaign_id,
                    action_type=ActionType.EMERGENCY_STOP,
                    reason=(
                        f"ROAS EMERGENCY: ROAS {campaign.roas:.2f} "
                        f"below threshold {emergency_roas}"
                    ),
                    confidence=1.0,
                    confidence_level=DecisionConfidence.HIGH,
                ))
        return anomalies
