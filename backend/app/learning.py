"""
Self-Improvement Engine
Tracks action outcomes, calibrates confidence scores, and evolves scoring weights.
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime

from app.config.settings import settings, runtime_settings
from app import db

logger = logging.getLogger("roas_engine.learning")

# Default balanced weights (must match roas_optimizer.py)
INITIAL_WEIGHTS = {
    "roas": 0.35,
    "efficiency": 0.25,
    "volume": 0.20,
    "trend": 0.20,
}

# Weight bounds
MIN_WEIGHT = 0.10
MAX_WEIGHT = 0.50


class LearningEngine:

    def __init__(self):
        # Cached calibration ratios: {action_type: ratio}
        self._calibration_cache: Dict[str, float] = {}
        # Cached learned weights
        self._learned_weights: Optional[Dict[str, float]] = None

    async def load_from_db(self):
        """Load cached state from DB on startup."""
        # Load latest weights
        w = await db.get_latest_weights()
        if w:
            self._learned_weights = {
                "roas": w["roas_weight"],
                "efficiency": w["efficiency_weight"],
                "volume": w["volume_weight"],
                "trend": w["trend_weight"],
            }
            logger.info(f"Loaded learned weights: {self._learned_weights}")

        # Load calibration ratios
        stats = await db.get_calibration_stats()
        for s in stats:
            if s["sample_size"] >= 5:
                predicted = max(s["predicted_avg"], 0.01)
                actual = s["actual_success_rate"]
                ratio = max(0.5, min(1.5, actual / predicted))
                self._calibration_cache[s["action_type"]] = ratio
        if self._calibration_cache:
            logger.info(f"Loaded calibration cache: {self._calibration_cache}")

    def adjust_confidence(self, action_type: str, raw_confidence: float) -> float:
        """Apply calibration ratio to a raw confidence score."""
        at = action_type.value if hasattr(action_type, 'value') else str(action_type)
        ratio = self._calibration_cache.get(at, 1.0)
        adjusted = max(0.3, min(1.0, raw_confidence * ratio))
        return adjusted

    def get_learned_weights(self) -> Optional[Dict[str, float]]:
        """Return learned weights if available, else None."""
        return self._learned_weights

    async def run_improvement_cycle(self, current_snapshot_id: int) -> Dict:
        """
        Main learning loop. Called after each optimization cycle.
        1. Evaluate outcomes of past actions
        2. Update confidence calibration
        3. Evolve scoring weights if enough data
        """
        lookback = runtime_settings.get("LEARNING_LOOKBACK_CYCLES")
        min_samples = runtime_settings.get("LEARNING_MIN_SAMPLES")

        # Step 1: Evaluate outcomes of actions from N cycles ago
        actions_to_eval = await db.get_actions_for_evaluation(cycles_ago=lookback)
        evaluated = 0

        for action in actions_to_eval:
            campaign_id = action.get("campaign_id")
            if not campaign_id:
                continue

            # Find ROAS at the time of the action
            action_time = action.get("created_at", "")
            old_snapshot_id = await db.get_snapshot_id_near_time(action_time)
            if not old_snapshot_id:
                continue

            roas_before = await db.get_campaign_roas_at_snapshot(campaign_id, old_snapshot_id)
            roas_after = await db.get_campaign_roas_at_snapshot(campaign_id, current_snapshot_id)

            if roas_before is None or roas_after is None:
                continue

            outcome = self._evaluate_outcome(
                action_type=action.get("action_type", ""),
                roas_before=roas_before,
                roas_after=roas_after,
            )

            await db.save_calibration(
                action_id=action["id"],
                action_type=action.get("action_type", ""),
                predicted_confidence=action.get("confidence", 0),
                campaign_id=campaign_id,
                roas_before=roas_before,
                roas_after=roas_after,
                outcome_positive=outcome,
                cycles_elapsed=lookback,
            )
            evaluated += 1

        # Step 2: Update calibration cache
        total_evals = await db.get_total_evaluations()
        if total_evals >= min_samples:
            await self._update_calibration()
            await self._update_weights()

        logger.info(
            f"Learning cycle: evaluated {evaluated} actions, "
            f"total evaluations: {total_evals}, "
            f"weights active: {self._learned_weights is not None}"
        )

        return {
            "evaluated_this_cycle": evaluated,
            "total_evaluations": total_evals,
            "weights_active": self._learned_weights is not None,
        }

    def _evaluate_outcome(self, action_type: str, roas_before: float, roas_after: float) -> bool:
        """Determine if an action produced a positive outcome."""
        target = runtime_settings.get("TARGET_ROAS")
        min_roas = runtime_settings.get("MIN_ROAS_THRESHOLD")

        if action_type == "increase_budget":
            # Positive if ROAS stayed near target OR improved
            return roas_after >= target * 0.9 or roas_after >= roas_before * 0.95

        if action_type == "decrease_budget":
            # Positive if ROAS improved
            return roas_after > roas_before

        if action_type in ("pause_campaign", "pause_keyword", "emergency_stop"):
            # Positive if the campaign was below threshold (correct to pause)
            return roas_before < min_roas

        if action_type in ("decrease_bid", "adjust_bid_modifier"):
            # Positive if ROAS improved or stayed stable
            return roas_after >= roas_before * 0.95

        # Default: positive if ROAS didn't decrease
        return roas_after >= roas_before

    async def _update_calibration(self):
        """Refresh the calibration cache from DB stats."""
        stats = await db.get_calibration_stats()
        new_cache = {}
        for s in stats:
            if s["sample_size"] >= 5:
                predicted = max(s["predicted_avg"], 0.01)
                actual = s["actual_success_rate"]
                ratio = max(0.5, min(1.5, actual / predicted))
                new_cache[s["action_type"]] = ratio
        self._calibration_cache = new_cache
        logger.info(f"Updated calibration: {new_cache}")

    async def _update_weights(self):
        """Evolve scoring weights based on which dimensions predict successful actions."""
        lr = runtime_settings.get("LEARNING_RATE")

        # Get current weights as baseline
        current = self._learned_weights or INITIAL_WEIGHTS.copy()

        # Get calibration data with action details for weight evolution
        rows = await db.get_calibration_details_for_learning(limit=500)

        if len(rows) < 10:
            return

        # Track success rate for each dominant dimension
        dim_success = {"roas": [], "efficiency": [], "volume": [], "trend": []}

        for row in rows:
            details = row.get("details", {})
            if isinstance(details, str):
                import json
                try:
                    details = json.loads(details)
                except Exception:
                    continue

            scores = {
                "roas": details.get("roas_score", 0),
                "efficiency": details.get("efficiency_score", 0),
                "volume": details.get("volume_score", 0),
                "trend": details.get("trend_score", 0),
            }

            if not any(scores.values()):
                continue

            # Find the dominant dimension
            dominant = max(scores, key=scores.get)
            outcome = bool(row["outcome_positive"])
            dim_success[dominant].append(outcome)

        # Calculate effectiveness per dimension
        effectiveness = {}
        for dim, outcomes in dim_success.items():
            if outcomes:
                effectiveness[dim] = sum(outcomes) / len(outcomes)
            else:
                effectiveness[dim] = 0.5  # neutral if no data

        # EMA update
        new_weights = {}
        for dim in ["roas", "efficiency", "volume", "trend"]:
            old_w = current.get(dim, INITIAL_WEIGHTS[dim])
            eff = effectiveness.get(dim, 0.5)
            new_w = old_w * (1 - lr) + eff * lr
            new_w = max(MIN_WEIGHT, min(MAX_WEIGHT, new_w))
            new_weights[dim] = new_w

        # Normalize to sum=1.0
        total = sum(new_weights.values())
        for dim in new_weights:
            new_weights[dim] = round(new_weights[dim] / total, 4)

        # Save
        await db.save_weights(
            roas_w=new_weights["roas"],
            eff_w=new_weights["efficiency"],
            vol_w=new_weights["volume"],
            trend_w=new_weights["trend"],
            source="learned",
        )
        self._learned_weights = new_weights
        logger.info(f"Updated weights: {new_weights} (effectiveness: {effectiveness})")

    async def get_stats(self) -> Dict:
        """Return learning statistics for the API."""
        calibration_stats = await db.get_calibration_stats()
        total_evals = await db.get_total_evaluations()
        latest_weights = await db.get_latest_weights()
        weight_count = await db.get_weight_count()

        # Build calibration table with ratios
        calibration = []
        for s in calibration_stats:
            predicted = max(s["predicted_avg"], 0.01)
            actual = s["actual_success_rate"]
            ratio = max(0.5, min(1.5, actual / predicted))
            calibration.append({
                "action_type": s["action_type"],
                "sample_size": s["sample_size"],
                "predicted_avg": round(predicted, 3),
                "actual_success_rate": round(actual, 3),
                "calibration_ratio": round(ratio, 3),
                "avg_roas_delta": round(s["avg_roas_delta"] or 0, 4),
            })

        # Action effectiveness
        effectiveness = []
        for s in calibration_stats:
            effectiveness.append({
                "action_type": s["action_type"],
                "total": s["sample_size"],
                "positive": round(s["actual_success_rate"] * s["sample_size"]),
                "negative": s["sample_size"] - round(s["actual_success_rate"] * s["sample_size"]),
                "effectiveness_pct": round(s["actual_success_rate"] * 100, 1),
            })
        effectiveness.sort(key=lambda x: x["effectiveness_pct"], reverse=True)

        # Current weights vs initial
        current_weights = self._learned_weights or INITIAL_WEIGHTS
        weight_comparison = {}
        for dim in ["roas", "efficiency", "volume", "trend"]:
            initial = INITIAL_WEIGHTS[dim]
            current = current_weights.get(dim, initial)
            weight_comparison[dim] = {
                "initial": initial,
                "current": round(current, 4),
                "delta": round(current - initial, 4),
                "direction": "up" if current > initial + 0.005 else "down" if current < initial - 0.005 else "stable",
            }

        return {
            "calibration": calibration,
            "action_effectiveness": effectiveness,
            "weights": weight_comparison,
            "total_evaluations": total_evals,
            "learning_active": total_evals >= runtime_settings.get("LEARNING_MIN_SAMPLES"),
            "cycles_with_learning": weight_count,
            "last_weight_update": latest_weights["timestamp"] if latest_weights else None,
        }

    async def get_history(self, limit: int = 50) -> List[Dict]:
        """Return weight evolution timeline."""
        return await db.get_weight_history(limit)
