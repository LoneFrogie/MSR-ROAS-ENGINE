"""
Firestore Persistence Layer
Async wrapper around google-cloud-firestore for persisting actions, snapshots, and learning data.
"""
import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

from google.cloud.firestore import AsyncClient

logger = logging.getLogger("roas_engine.db")

FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "roas-engine")

# Lazy-initialized Firestore client
_db: Optional[AsyncClient] = None


def _get_db() -> AsyncClient:
    """Get or create the Firestore async client."""
    global _db
    if _db is None:
        _db = AsyncClient(database=FIRESTORE_DATABASE)
    return _db


async def init_db():
    """Initialize Firestore client. No schema needed — Firestore is schemaless."""
    _get_db()
    logger.info("Firestore client initialized")


# ─── Actions ────────────────────────────────────────────────────────

async def save_action(action) -> None:
    """Persist an OptimizationAction (insert or update)."""
    db = _get_db()
    doc = {
        "platform": action.platform.value if hasattr(action.platform, 'value') else str(action.platform),
        "campaign_id": action.campaign_id,
        "adgroup_id": action.adgroup_id,
        "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
        "old_value": str(action.old_value) if action.old_value is not None else None,
        "new_value": str(action.new_value) if action.new_value is not None else None,
        "reason": action.reason,
        "confidence": action.confidence,
        "confidence_level": action.confidence_level.value if action.confidence_level and hasattr(action.confidence_level, 'value') else str(action.confidence_level) if action.confidence_level else None,
        "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
        "created_at": action.created_at.isoformat() if action.created_at else datetime.now().isoformat(),
        "executed_at": action.executed_at.isoformat() if action.executed_at else None,
        "approved_at": action.approved_at.isoformat() if action.approved_at else None,
        "rejected_at": action.rejected_at.isoformat() if action.rejected_at else None,
        "applied": action.applied or False,
        "result": action.result,
        "details": action.details or {},
    }
    await db.collection("actions").document(action.id).set(doc)


async def get_pending_actions(limit: int = 500) -> List[Dict]:
    """Retrieve all PENDING actions (for rehydrating queue on startup)."""
    db = _get_db()
    # No order_by here to avoid needing a composite Firestore index;
    # sorting in Python is fine for the small pending queue.
    query = db.collection("actions").where("status", "==", "pending").limit(limit)
    results = []
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        results.append(d)
    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results


async def get_actions(limit: int = 200, status_filter: str = None) -> List[Dict]:
    """Retrieve actions, newest first."""
    db = _get_db()
    query = db.collection("actions").order_by("created_at", direction="DESCENDING")
    if status_filter:
        query = query.where("status", "==", status_filter)
    query = query.limit(limit)
    docs = query.stream()
    results = []
    async for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        results.append(d)
    return results


# ─── Snapshots ──────────────────────────────────────────────────────

async def save_snapshot(snapshot, campaigns=None) -> str:
    """Persist a PerformanceSnapshot and associated campaign data. Returns snapshot doc id."""
    db = _get_db()
    now = datetime.now()
    doc = {
        "timestamp": snapshot.timestamp.isoformat() if snapshot.timestamp else now.isoformat(),
        "created_at": now.isoformat(),
        "total_spend": snapshot.total_spend,
        "total_revenue": snapshot.total_revenue,
        "blended_roas": snapshot.blended_roas,
        "total_conversions": snapshot.total_conversions,
        "num_campaigns": snapshot.num_campaigns,
        "num_active_campaigns": snapshot.num_active_campaigns,
        "platform_breakdown": snapshot.platform_breakdown or {},
        "actions_applied": snapshot.actions_applied,
        "alerts": snapshot.alerts or [],
    }
    _, snap_ref = await db.collection("snapshots").add(doc)
    snapshot_id = snap_ref.id

    if campaigns:
        batch = db.batch()
        for c in campaigns:
            camp_ref = db.collection("campaign_snapshots").document()
            batch.set(camp_ref, {
                "snapshot_id": snapshot_id,
                "campaign_id": c.id or c.platform_campaign_id,
                "platform": c.platform.value if hasattr(c.platform, 'value') else str(c.platform),
                "name": c.name,
                "spend": c.spend,
                "revenue": c.revenue,
                "roas": c.roas,
                "conversions": c.conversions,
                "daily_budget": c.daily_budget,
                "created_at": now.isoformat(),
            })
        await batch.commit()

    logger.info(f"Saved snapshot {snapshot_id} with {len(campaigns or [])} campaigns")
    return snapshot_id


async def get_snapshots(limit: int = 50) -> List[Dict]:
    """Retrieve snapshots ordered by timestamp desc."""
    db = _get_db()
    query = db.collection("snapshots").order_by("timestamp", direction="DESCENDING").limit(limit)
    results = []
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        results.append(d)
    return results


async def get_latest_snapshot() -> Optional[Dict]:
    """Get the most recent snapshot."""
    snapshots = await get_snapshots(limit=1)
    return snapshots[0] if snapshots else None


async def get_campaign_history(campaign_id: str, limit: int = 50) -> List[Dict]:
    """Get historical snapshots for a specific campaign."""
    db = _get_db()
    query = (
        db.collection("campaign_snapshots")
        .where("campaign_id", "==", campaign_id)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )
    results = []
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        results.append(d)
    return results


async def get_campaign_roas_at_snapshot(campaign_id: str, snapshot_id: str) -> Optional[float]:
    """Get a campaign's ROAS at a specific snapshot."""
    db = _get_db()
    query = (
        db.collection("campaign_snapshots")
        .where("campaign_id", "==", campaign_id)
        .where("snapshot_id", "==", snapshot_id)
        .limit(1)
    )
    async for doc in query.stream():
        return doc.to_dict().get("roas")
    return None


async def get_campaign_latest_roas(campaign_id: str) -> Optional[float]:
    """Get a campaign's most recent ROAS."""
    db = _get_db()
    query = (
        db.collection("campaign_snapshots")
        .where("campaign_id", "==", campaign_id)
        .order_by("created_at", direction="DESCENDING")
        .limit(1)
    )
    async for doc in query.stream():
        return doc.to_dict().get("roas")
    return None


async def get_snapshot_id_near_time(timestamp_iso: str) -> Optional[str]:
    """Find the snapshot closest to a given timestamp."""
    db = _get_db()
    # Get one snapshot before and one after, pick the closest
    before_query = (
        db.collection("snapshots")
        .where("timestamp", "<=", timestamp_iso)
        .order_by("timestamp", direction="DESCENDING")
        .limit(1)
    )
    after_query = (
        db.collection("snapshots")
        .where("timestamp", ">=", timestamp_iso)
        .order_by("timestamp")
        .limit(1)
    )

    candidates = []
    async for doc in before_query.stream():
        d = doc.to_dict()
        candidates.append((doc.id, abs(_parse_ts(d["timestamp"]) - _parse_ts(timestamp_iso))))
    async for doc in after_query.stream():
        d = doc.to_dict()
        candidates.append((doc.id, abs(_parse_ts(d["timestamp"]) - _parse_ts(timestamp_iso))))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


def _parse_ts(ts_str: str) -> float:
    """Parse ISO timestamp to epoch seconds for comparison."""
    try:
        return datetime.fromisoformat(ts_str).timestamp()
    except Exception:
        return 0.0


# ─── Confidence Calibration ─────────────────────────────────────────

async def save_calibration(action_id: str, action_type: str, predicted_confidence: float,
                           campaign_id: str, roas_before: float, roas_after: float,
                           outcome_positive: bool, cycles_elapsed: int) -> None:
    """Record an outcome evaluation."""
    db = _get_db()
    await db.collection("calibrations").add({
        "action_id": action_id,
        "action_type": action_type,
        "predicted_confidence": predicted_confidence,
        "campaign_id": campaign_id,
        "roas_before": roas_before,
        "roas_after": roas_after,
        "roas_delta": roas_after - roas_before,
        "outcome_positive": outcome_positive,
        "evaluated_at": datetime.now().isoformat(),
        "cycles_elapsed": cycles_elapsed,
    })


async def get_calibration_stats() -> List[Dict]:
    """Get per-action-type calibration statistics."""
    db = _get_db()
    # Firestore has no GROUP BY — aggregate in Python
    docs = db.collection("calibrations").stream()
    by_type: Dict[str, List[Dict]] = {}
    async for doc in docs:
        d = doc.to_dict()
        at = d.get("action_type", "unknown")
        by_type.setdefault(at, []).append(d)

    results = []
    for action_type, entries in by_type.items():
        n = len(entries)
        predicted_avg = sum(e.get("predicted_confidence", 0) for e in entries) / n
        positive_count = sum(1 for e in entries if e.get("outcome_positive"))
        actual_rate = positive_count / n
        avg_delta = sum(e.get("roas_delta", 0) for e in entries) / n
        results.append({
            "action_type": action_type,
            "sample_size": n,
            "predicted_avg": predicted_avg,
            "actual_success_rate": actual_rate,
            "avg_roas_delta": avg_delta,
        })
    results.sort(key=lambda x: x["sample_size"], reverse=True)
    return results


async def get_total_evaluations() -> int:
    """Count total evaluated outcomes."""
    db = _get_db()
    count = 0
    async for _ in db.collection("calibrations").select([]).stream():
        count += 1
    return count


async def get_actions_for_evaluation(cycles_ago: int = 3) -> List[Dict]:
    """
    Get executed actions from N snapshots ago that haven't been evaluated yet.
    """
    db = _get_db()

    # Get snapshots ordered by time
    snapshots = await get_snapshots(limit=cycles_ago + 1)
    if len(snapshots) <= cycles_ago:
        return []

    old_snapshot = snapshots[cycles_ago]
    old_timestamp = old_snapshot["timestamp"]

    # Upper bound is the next snapshot's timestamp
    upper_bound = snapshots[cycles_ago - 1]["timestamp"] if cycles_ago > 0 else datetime.now().isoformat()

    # Get executed/approved actions in that time range
    query = (
        db.collection("actions")
        .where("status", "in", ["executed", "approved"])
        .where("created_at", ">=", old_timestamp)
        .where("created_at", "<", upper_bound)
    )
    actions = []
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        if d.get("campaign_id"):
            actions.append(d)

    if not actions:
        return actions

    # Filter out already-evaluated actions
    evaluated_ids = set()
    async for doc in db.collection("calibrations").select(["action_id"]).stream():
        evaluated_ids.add(doc.to_dict().get("action_id"))

    return [a for a in actions if a["id"] not in evaluated_ids]


# ─── Learning Weights ───────────────────────────────────────────────

async def save_weights(roas_w: float, eff_w: float, vol_w: float, trend_w: float,
                       source: str = "learned") -> None:
    """Save a new set of learned weights."""
    db = _get_db()
    await db.collection("learning_weights").add({
        "timestamp": datetime.now().isoformat(),
        "roas_weight": roas_w,
        "efficiency_weight": eff_w,
        "volume_weight": vol_w,
        "trend_weight": trend_w,
        "source": source,
    })


async def get_latest_weights() -> Optional[Dict]:
    """Get the most recent learned weights."""
    db = _get_db()
    query = db.collection("learning_weights").order_by("timestamp", direction="DESCENDING").limit(1)
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        return d
    return None


async def get_weight_history(limit: int = 50) -> List[Dict]:
    """Get weight evolution timeline."""
    db = _get_db()
    query = db.collection("learning_weights").order_by("timestamp", direction="DESCENDING").limit(limit)
    results = []
    async for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        results.append(d)
    return results


async def get_weight_count() -> int:
    """Count total weight entries."""
    db = _get_db()
    count = 0
    async for _ in db.collection("learning_weights").select([]).stream():
        count += 1
    return count


# ─── Scored Social Posts ─────────────────────────────────────────────

async def save_scored_post(post: Dict) -> None:
    """Persist a single scored post (keyed by post_id)."""
    db = _get_db()
    post_id = post.get("post_id")
    if not post_id:
        return
    # Strip non-serialisable bits if any; ensure datetimes are isoformat strings
    safe = {k: v for k, v in post.items()}
    if "scored_at" not in safe:
        safe["scored_at"] = datetime.now().isoformat()
    await db.collection("scored_posts").document(str(post_id)).set(safe)


async def get_scored_posts(
    limit: int = 200,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """
    Return previously-scored posts, optionally filtered by created_time range.
    Tries Firestore inequality filter on created_time first (fast), falls back to
    Python-side filter if that requires a missing index.
    """
    db = _get_db()
    # Use Firestore-side range filter when possible (much faster than full scan)
    try:
        if start_date and end_date:
            query = (db.collection("scored_posts")
                       .where("created_time", ">=", start_date)
                       .where("created_time", "<=", end_date + "T23:59:59")
                       .limit(limit))
        elif start_date:
            query = db.collection("scored_posts").where("created_time", ">=", start_date).limit(limit)
        elif end_date:
            query = db.collection("scored_posts").where("created_time", "<=", end_date + "T23:59:59").limit(limit)
        else:
            query = db.collection("scored_posts").limit(limit)

        results = []
        async for doc in query.stream():
            results.append(doc.to_dict())
        results.sort(key=lambda r: (r.get("created_time") or ""), reverse=True)
        return results
    except Exception as e:
        # Fallback: full scan + Python filter (Firestore index not yet built)
        logger.warning(f"Indexed query failed, falling back to scan: {e}")
        query = db.collection("scored_posts").limit(limit * 3)
        results = []
        async for doc in query.stream():
            d = doc.to_dict()
            if start_date or end_date:
                ct = (d.get("created_time") or "")[:10]
                if start_date and ct < start_date:
                    continue
                if end_date and ct > end_date:
                    continue
            results.append(d)
        results.sort(key=lambda r: (r.get("created_time") or ""), reverse=True)
        return results[:limit]


async def get_scored_post_ids() -> set:
    """Return a set of all scored post_ids (for skip-already-scored logic)."""
    db = _get_db()
    ids = set()
    async for doc in db.collection("scored_posts").select([]).stream():
        ids.add(doc.id)
    return ids


async def get_calibration_details_for_learning(limit: int = 500) -> List[Dict]:
    """
    Get calibration entries joined with their action details for weight evolution.
    Returns calibration rows with action details embedded.
    """
    db = _get_db()

    # Get recent calibrations
    query = db.collection("calibrations").order_by("evaluated_at", direction="DESCENDING").limit(limit)
    calibrations = []
    async for doc in query.stream():
        calibrations.append(doc.to_dict())

    if not calibrations:
        return []

    # Batch-fetch the referenced actions
    action_ids = list({c["action_id"] for c in calibrations if c.get("action_id")})
    action_details = {}
    # Fetch in chunks of 30 (Firestore 'in' query limit)
    for i in range(0, len(action_ids), 30):
        chunk = action_ids[i:i+30]
        for aid in chunk:
            doc = await db.collection("actions").document(aid).get()
            if doc.exists:
                action_details[aid] = doc.to_dict().get("details", {})

    # Merge
    results = []
    for c in calibrations:
        aid = c.get("action_id")
        details = action_details.get(aid, {})
        if details:
            results.append({
                "outcome_positive": c.get("outcome_positive"),
                "details": details,
            })
    return results
