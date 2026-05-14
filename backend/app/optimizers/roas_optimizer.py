"""
ROAS Optimizer — Core scoring and action generation logic.
"""
import logging
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from app.models.schemas import (
    UnifiedCampaign, UnifiedAdGroup, OptimizationAction,
    ActionType, DecisionConfidence, Platform, CampaignStatus,
    BudgetAllocation, CampaignScore
)
from app.config.settings import settings, OptimizationMode

logger = logging.getLogger("roas_engine.optimizer")


class ROASOptimizer:

    def __init__(self):
        self.target_roas = settings.TARGET_ROAS
        self.min_roas = settings.MIN_ROAS_THRESHOLD
        self.max_budget_change = settings.MAX_DAILY_BUDGET_CHANGE_PCT
        self.max_bid_change = settings.MAX_BID_CHANGE_PCT
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD
        self.min_conversions = settings.MIN_CONVERSIONS_FOR_DECISION
        self.mode = settings.OPTIMIZATION_MODE

    def analyze_campaigns(
        self,
        current_campaigns: List[UnifiedCampaign],
        historical_campaigns: Optional[List[UnifiedCampaign]] = None,
        weight_overrides: Optional[Dict[str, float]] = None,
    ) -> List[CampaignScore]:
        scores = []
        for campaign in current_campaigns:
            if campaign.status == CampaignStatus.KILLED:
                continue

            roas_score = self._score_roas(campaign.roas)
            efficiency_score = self._score_efficiency(campaign)
            volume_score = self._score_volume(campaign.conversions)
            trend_score = self._score_trend(campaign, historical_campaigns)

            weights = weight_overrides if weight_overrides else self._get_mode_weights()
            composite = (
                weights["roas"] * roas_score +
                weights["efficiency"] * efficiency_score +
                weights["volume"] * volume_score +
                weights["trend"] * max(0, trend_score)  # only positive trend helps
            )
            composite = max(0.0, min(1.0, composite))

            action, confidence = self._determine_action(
                campaign, composite, roas_score, trend_score
            )

            scores.append(CampaignScore(
                campaign=campaign,
                roas_score=roas_score,
                efficiency_score=efficiency_score,
                volume_score=volume_score,
                trend_score=trend_score,
                composite_score=composite,
                recommended_action=action,
                confidence=confidence,
            ))

        scores.sort(key=lambda s: s.composite_score, reverse=True)
        return scores

    def generate_actions(
        self, scores: List[CampaignScore]
    ) -> List[OptimizationAction]:
        actions = []
        for score in scores:
            campaign = score.campaign
            if score.confidence < self.confidence_threshold:
                continue
            if campaign.conversions < self.min_conversions:
                if score.recommended_action not in (
                    ActionType.PAUSE_CAMPAIGN, ActionType.EMERGENCY_STOP
                ):
                    continue

            confidence_level = self._get_confidence_level(score.confidence)
            action = self._build_action(score, confidence_level)
            if action:
                actions.append(action)
        return actions

    def calculate_optimal_budget(
        self, campaign: UnifiedCampaign, score: CampaignScore
    ) -> float:
        current = campaign.daily_budget
        if score.recommended_action == ActionType.INCREASE_BUDGET:
            roas_multiplier = min(campaign.roas / self.target_roas, 2.0)
            increase_pct = min(
                self.max_budget_change * roas_multiplier * score.confidence,
                self.max_budget_change
            )
            new_budget = current * (1 + increase_pct)
        elif score.recommended_action == ActionType.DECREASE_BUDGET:
            roas_gap = max(1 - (campaign.roas / self.target_roas), 0)
            decrease_pct = min(
                self.max_budget_change * roas_gap * score.confidence,
                self.max_budget_change
            )
            new_budget = current * (1 - decrease_pct)
        else:
            return current

        new_budget = min(new_budget, settings.MAX_SINGLE_CAMPAIGN_BUDGET)
        new_budget = max(new_budget, 5.0)
        return round(new_budget, 2)

    def calculate_optimal_bid(
        self, adgroup: UnifiedAdGroup, target_cpa: float
    ) -> float:
        if adgroup.clicks == 0 or adgroup.conversions == 0:
            return adgroup.bid_amount or 1.0

        conv_rate = adgroup.conversions / adgroup.clicks
        optimal_bid = target_cpa * conv_rate

        if adgroup.bid_amount:
            max_change = adgroup.bid_amount * self.max_bid_change
            optimal_bid = max(
                adgroup.bid_amount - max_change,
                min(optimal_bid, adgroup.bid_amount + max_change)
            )
        return round(max(optimal_bid, 0.10), 2)

    def _score_roas(self, roas: float) -> float:
        if roas <= 0:
            return 0.0
        if roas >= self.target_roas * 1.5:
            return 1.0
        return min(roas / (self.target_roas * 1.5), 1.0)

    def _score_efficiency(self, campaign: UnifiedCampaign) -> float:
        if campaign.conversions == 0 or campaign.clicks == 0:
            return 0.0
        conv_rate = campaign.conversions / campaign.clicks
        conv_score = min(conv_rate / 0.05, 1.0)
        cpa_target = (
            campaign.revenue / campaign.conversions / self.target_roas
            if campaign.conversions > 0 else 50
        )
        cpa_score = (
            min(cpa_target / max(campaign.cpa, 0.01), 1.0)
            if campaign.cpa > 0 else 0
        )
        return (conv_score * 0.5 + cpa_score * 0.5)

    def _score_volume(self, conversions: int) -> float:
        if conversions <= 0:
            return 0.0
        return min(np.log1p(conversions) / np.log1p(100), 1.0)

    def _score_trend(
        self,
        current: UnifiedCampaign,
        historical: Optional[List[UnifiedCampaign]],
    ) -> float:
        if not historical:
            return 0.0
        hist = [
            h for h in historical
            if h.platform_campaign_id == current.platform_campaign_id
        ]
        if not hist:
            return 0.0
        prev = hist[0]
        if prev.roas == 0:
            return 0.5 if current.roas > 0 else 0.0
        roas_change = (current.roas - prev.roas) / prev.roas
        return max(-1.0, min(1.0, roas_change))

    def _get_mode_weights(self) -> Dict[str, float]:
        if self.mode == OptimizationMode.AGGRESSIVE:
            return {"roas": 0.45, "efficiency": 0.15, "volume": 0.25, "trend": 0.15}
        elif self.mode == OptimizationMode.CONSERVATIVE:
            return {"roas": 0.30, "efficiency": 0.30, "volume": 0.15, "trend": 0.25}
        else:
            return {"roas": 0.35, "efficiency": 0.25, "volume": 0.20, "trend": 0.20}

    def _determine_action(
        self,
        campaign: UnifiedCampaign,
        composite: float,
        roas_score: float,
        trend_score: float,
    ) -> Tuple[ActionType, float]:
        if campaign.roas < settings.EMERGENCY_STOP_ROAS_BELOW and campaign.spend > 50:
            return ActionType.PAUSE_CAMPAIGN, 0.95

        if campaign.roas >= self.target_roas and composite >= 0.6:
            confidence = min(0.75 + (composite - 0.6) * 1.33, 0.95)
            return ActionType.INCREASE_BUDGET, confidence

        if campaign.roas >= self.target_roas and trend_score < -0.2:
            return ActionType.DECREASE_BUDGET, 0.65

        if campaign.roas < self.min_roas and campaign.conversions >= self.min_conversions:
            confidence = min(0.7 + (self.min_roas - campaign.roas) * 0.3, 0.90)
            return ActionType.DECREASE_BUDGET, confidence

        if campaign.roas < self.min_roas * 0.5 and campaign.spend > 100:
            return ActionType.PAUSE_CAMPAIGN, 0.85

        return ActionType.DECREASE_BUDGET, 0.3

    def _get_confidence_level(self, confidence: float) -> DecisionConfidence:
        if confidence >= 0.85:
            return DecisionConfidence.HIGH
        elif confidence >= 0.65:
            return DecisionConfidence.MEDIUM
        return DecisionConfidence.LOW

    def _build_action(
        self, score: CampaignScore, confidence_level: DecisionConfidence
    ) -> Optional[OptimizationAction]:
        campaign = score.campaign
        if score.recommended_action in (
            ActionType.INCREASE_BUDGET, ActionType.DECREASE_BUDGET
        ):
            new_budget = self.calculate_optimal_budget(campaign, score)
            if abs(new_budget - campaign.daily_budget) < 1.0:
                return None
            return OptimizationAction(
                platform=campaign.platform,
                campaign_id=campaign.platform_campaign_id,
                action_type=score.recommended_action,
                confidence=score.confidence,
                confidence_level=confidence_level,
                reason=(
                    f"Campaign '{campaign.name}' ROAS={campaign.roas:.2f} "
                    f"(target={self.target_roas:.2f}). "
                    f"Composite={score.composite_score:.2f}."
                ),
                old_value=campaign.daily_budget,
                new_value=new_budget,
                details={
                    "roas_score": score.roas_score,
                    "efficiency_score": score.efficiency_score,
                    "volume_score": score.volume_score,
                    "trend_score": score.trend_score,
                },
            )
        elif score.recommended_action == ActionType.PAUSE_CAMPAIGN:
            return OptimizationAction(
                platform=campaign.platform,
                campaign_id=campaign.platform_campaign_id,
                action_type=ActionType.PAUSE_CAMPAIGN,
                confidence=score.confidence,
                confidence_level=confidence_level,
                reason=(
                    f"Campaign '{campaign.name}' ROAS={campaign.roas:.2f} critically low. "
                    f"Spend=${campaign.spend:.2f}, conversions={campaign.conversions}. Auto-pausing."
                ),
                old_value="active",
                new_value="paused",
            )
        return None
