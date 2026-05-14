"""
GEO Optimizer
Analyzes cross-platform geographic performance and generates bid modifier actions.
"""
import logging
from typing import List, Dict, Optional

from app.models.schemas import (
    OptimizationAction, ActionType, Platform, DecisionConfidence
)
from app.config.settings import settings

logger = logging.getLogger("roas_engine.geo_optimizer")


class GeoOptimizer:

    def __init__(self):
        self.target_roas = settings.TARGET_ROAS
        self.min_roas = settings.MIN_ROAS_THRESHOLD
        self.min_spend_threshold = 50.0  # Min spend to evaluate a country

    def analyze_geo_performance(
        self,
        google_geo: List[Dict],
        meta_geo: List[Dict],
    ) -> Dict[str, Dict]:
        """
        Aggregate geographic data across both platforms by country.
        Returns: {country_code: {spend, revenue, roas, conversions, ...}}
        """
        combined: Dict[str, Dict] = {}

        for row in google_geo:
            country = row.get("country", row.get("country_criterion_id", "UNKNOWN"))
            if country not in combined:
                combined[country] = {
                    "country": country,
                    "spend": 0,
                    "revenue": 0,
                    "conversions": 0,
                    "clicks": 0,
                    "platforms": [],
                }
            combined[country]["spend"] += row.get("spend", 0)
            combined[country]["revenue"] += row.get("revenue", 0)
            combined[country]["conversions"] += row.get("conversions", 0)
            combined[country]["clicks"] += row.get("clicks", 0)
            if "google" not in combined[country]["platforms"]:
                combined[country]["platforms"].append("google")

        for row in meta_geo:
            country = row.get("country", "UNKNOWN")
            if country not in combined:
                combined[country] = {
                    "country": country,
                    "spend": 0,
                    "revenue": 0,
                    "conversions": 0,
                    "clicks": 0,
                    "platforms": [],
                }
            combined[country]["spend"] += row.get("spend", 0)
            combined[country]["revenue"] += row.get("revenue", 0)
            combined[country]["conversions"] += row.get("conversions", 0)
            combined[country]["clicks"] += row.get("clicks", 0)
            if "meta" not in combined[country]["platforms"]:
                combined[country]["platforms"].append("meta")

        # Compute ROAS per country
        for country, data in combined.items():
            spend = data["spend"]
            revenue = data["revenue"]
            data["roas"] = revenue / spend if spend > 0 else 0

        return combined

    def generate_bid_modifier_actions(
        self, geo_summary: Dict[str, Dict]
    ) -> List[OptimizationAction]:
        """
        Generate bid modifier recommendations based on country-level ROAS.
        - High ROAS (> 1.5x target): increase bids
        - Low ROAS (< min_roas): decrease bids
        - Very low ROAS (< 0.5): exclude country
        """
        if not geo_summary:
            return []

        total_spend = sum(d["spend"] for d in geo_summary.values())
        avg_roas = (
            sum(d["revenue"] for d in geo_summary.values()) / total_spend
            if total_spend > 0 else self.target_roas
        )

        actions = []
        for country, data in geo_summary.items():
            spend = data["spend"]
            if spend < self.min_spend_threshold:
                continue

            roas = data["roas"]

            if roas >= self.target_roas * 1.5:
                # Scale up: increase bids
                modifier = min(1.0 + (roas / avg_roas - 1) * 0.3, 1.30)
                actions.append(OptimizationAction(
                    platform=Platform.GOOGLE_ADS,
                    campaign_id="ALL",
                    action_type=ActionType.ADJUST_BID_MODIFIER,
                    old_value=1.0,
                    new_value=round(modifier, 2),
                    confidence=0.80,
                    confidence_level=DecisionConfidence.HIGH,
                    reason=(
                        f"GEO: {country} ROAS={roas:.2f} ({roas/avg_roas:.1f}x avg). "
                        f"Increase bid modifier to {modifier:.2f}"
                    ),
                    details={"country": country, "spend": spend, "roas": roas},
                ))

            elif roas < 0.5:
                # Exclude country
                actions.append(OptimizationAction(
                    platform=Platform.GOOGLE_ADS,
                    campaign_id="ALL",
                    action_type=ActionType.EXCLUDE_GEO,
                    old_value=1.0,
                    new_value=0.0,
                    confidence=0.90,
                    confidence_level=DecisionConfidence.HIGH,
                    reason=(
                        f"GEO: {country} ROAS={roas:.2f} critically low. "
                        f"Recommend geo exclusion."
                    ),
                    details={"country": country, "spend": spend, "roas": roas},
                ))

            elif roas < self.min_roas:
                # Reduce bids
                modifier = max(0.7, 1.0 - (self.min_roas - roas) * 0.2)
                actions.append(OptimizationAction(
                    platform=Platform.GOOGLE_ADS,
                    campaign_id="ALL",
                    action_type=ActionType.ADJUST_BID_MODIFIER,
                    old_value=1.0,
                    new_value=round(modifier, 2),
                    confidence=0.75,
                    confidence_level=DecisionConfidence.MEDIUM,
                    reason=(
                        f"GEO: {country} ROAS={roas:.2f} below min {self.min_roas}. "
                        f"Reduce bid modifier to {modifier:.2f}"
                    ),
                    details={"country": country, "spend": spend, "roas": roas},
                ))

        return actions
