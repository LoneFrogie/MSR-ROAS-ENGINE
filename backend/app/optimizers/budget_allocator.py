"""
Cross-Platform Budget Allocator
Distributes total daily budget across Google Ads and Meta campaigns.
"""
from typing import List, Dict
from datetime import datetime

from app.models.schemas import (
    UnifiedCampaign, Platform, OptimizationAction, ActionType,
    BudgetAllocation, DecisionConfidence
)
from app.config.settings import settings


class CrossPlatformBudgetAllocator:

    def __init__(self):
        self.total_budget = settings.MAX_TOTAL_DAILY_BUDGET
        self.min_platform_pct = 0.20
        self.max_platform_pct = 0.80
        self.min_change_threshold = 2.0

    def calculate_allocation(
        self, campaigns: List[UnifiedCampaign]
    ) -> BudgetAllocation:
        google_campaigns = [c for c in campaigns if c.platform == Platform.GOOGLE_ADS]
        meta_campaigns = [c for c in campaigns if c.platform == Platform.META_ADS]

        google_metrics = self._calculate_platform_metrics(google_campaigns)
        meta_metrics = self._calculate_platform_metrics(meta_campaigns)

        total_roas = google_metrics["roas"] + meta_metrics["roas"]

        if total_roas > 0:
            google_pct = google_metrics["roas"] / total_roas
            meta_pct = meta_metrics["roas"] / total_roas
        else:
            google_pct = 0.5
            meta_pct = 0.5

        google_pct = max(self.min_platform_pct, min(self.max_platform_pct, google_pct))
        meta_pct = 1.0 - google_pct

        google_budget = self.total_budget * google_pct
        meta_budget = self.total_budget * meta_pct

        allocations = {}
        allocations.update(self._allocate_platform_budget(google_campaigns, google_budget))
        allocations.update(self._allocate_platform_budget(meta_campaigns, meta_budget))

        total_spend = sum(allocations.values())
        expected_roas = (
            google_metrics["roas"] * (google_budget / total_spend) +
            meta_metrics["roas"] * (meta_budget / total_spend)
        ) if total_spend > 0 else 2.0

        reasoning = (
            f"Budget reallocation: {google_pct*100:.1f}% to Google Ads "
            f"(ROAS: {google_metrics['roas']:.2f}), "
            f"{meta_pct*100:.1f}% to Meta (ROAS: {meta_metrics['roas']:.2f}). "
            f"Expected blended ROAS: {expected_roas:.2f}"
        )

        return BudgetAllocation(
            total_budget=self.total_budget,
            allocations=allocations,
            expected_roas=expected_roas,
            reasoning=reasoning,
        )

    def _calculate_platform_metrics(self, campaigns: List[UnifiedCampaign]) -> Dict:
        if not campaigns:
            return {"roas": 0.0, "spend": 0.0, "revenue": 0.0}
        total_spend = sum(c.spend for c in campaigns)
        total_revenue = sum(c.revenue for c in campaigns)
        roas = (total_revenue / total_spend) if total_spend > 0 else 0
        return {"roas": roas, "spend": total_spend, "revenue": total_revenue}

    def _allocate_platform_budget(
        self, campaigns: List[UnifiedCampaign], platform_budget: float
    ) -> Dict[str, float]:
        if not campaigns:
            return {}

        weights = {}
        for campaign in campaigns:
            vol_factor = min(1.0, campaign.conversions / 50)
            weight = max(0.1, campaign.roas) * vol_factor
            weights[campaign.id] = weight

        total_weight = sum(weights.values())
        allocations = {}

        if total_weight == 0:
            per_campaign = platform_budget / len(campaigns)
            for campaign in campaigns:
                allocations[f"{campaign.platform.value}/{campaign.id}"] = per_campaign
        else:
            for campaign in campaigns:
                budget = (weights[campaign.id] / total_weight) * platform_budget
                budget = min(budget, settings.MAX_SINGLE_CAMPAIGN_BUDGET)
                allocations[f"{campaign.platform.value}/{campaign.id}"] = round(budget, 2)

        return allocations

    def generate_reallocation_actions(
        self,
        allocation: BudgetAllocation,
        campaigns: List[UnifiedCampaign],
    ) -> List[OptimizationAction]:
        actions = []

        for campaign in campaigns:
            key = f"{campaign.platform.value}/{campaign.id}"
            raw_new_budget = allocation.allocations.get(key, campaign.daily_budget)

            # Enforce max daily change cap
            max_change = campaign.daily_budget * settings.MAX_DAILY_BUDGET_CHANGE_PCT
            if raw_new_budget > campaign.daily_budget:
                new_budget = min(raw_new_budget, campaign.daily_budget + max_change)
            else:
                new_budget = max(raw_new_budget, campaign.daily_budget - max_change)

            # Skip tiny changes
            if abs(new_budget - campaign.daily_budget) < self.min_change_threshold:
                continue

            action_type = (
                ActionType.INCREASE_BUDGET
                if new_budget > campaign.daily_budget
                else ActionType.DECREASE_BUDGET
            )

            confidence = min(
                1.0,
                0.5 + (allocation.expected_roas / settings.TARGET_ROAS) * 0.3
            )

            actions.append(OptimizationAction(
                platform=campaign.platform,
                campaign_id=campaign.platform_campaign_id,
                action_type=action_type,
                old_value=campaign.daily_budget,
                new_value=new_budget,
                reason=f"Platform reallocation: {campaign.name}",
                confidence=confidence,
                confidence_level=(
                    DecisionConfidence.HIGH if confidence > 0.8
                    else DecisionConfidence.MEDIUM if confidence > 0.5
                    else DecisionConfidence.LOW
                ),
            ))

        return actions
