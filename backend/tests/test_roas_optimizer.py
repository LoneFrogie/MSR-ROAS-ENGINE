"""
Unit tests for ROASOptimizer — scoring and action generation.
"""
import pytest
from unittest.mock import patch

from app.optimizers.roas_optimizer import ROASOptimizer
from app.models.schemas import (
    UnifiedCampaign, Platform, CampaignStatus, ActionType, CampaignScore
)
from tests.mock_data import (
    generate_all_campaigns, scenario_healthy_account,
    scenario_emergency, scenario_all_winners,
    scenario_budget_imbalance, scenario_insufficient_data,
)


@pytest.fixture
def optimizer():
    return ROASOptimizer()


@pytest.fixture
def current_campaigns():
    google, meta = generate_all_campaigns("current")
    return google + meta


@pytest.fixture
def historical_campaigns():
    google, meta = generate_all_campaigns("historical")
    return google + meta


# ── Scoring tests ──────────────────────────────────────────────────────────────

def test_analyze_campaigns_returns_scores(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns)
    assert len(scores) > 0
    assert all(hasattr(s, "composite_score") for s in scores)


def test_scores_sorted_descending(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns)
    composites = [s.composite_score for s in scores]
    assert composites == sorted(composites, reverse=True)


def test_all_composite_scores_in_range(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns)
    for s in scores:
        assert 0.0 <= s.composite_score <= 1.0, (
            f"{s.campaign.name} composite={s.composite_score}"
        )


def test_roas_score_zero_for_zero_roas(optimizer):
    assert optimizer._score_roas(0.0) == 0.0


def test_roas_score_max_for_high_roas(optimizer):
    assert optimizer._score_roas(100.0) == 1.0


def test_roas_score_partial(optimizer):
    # target=4.0, so 1.5x = 6.0 → score = 4/6 ≈ 0.667
    score = optimizer._score_roas(4.0)
    assert 0.5 < score < 1.0


def test_volume_score_zero_for_zero_conversions(optimizer):
    assert optimizer._score_volume(0) == 0.0


def test_volume_score_max_for_100_plus(optimizer):
    assert optimizer._score_volume(100) == 1.0


def test_efficiency_score_zero_no_conversions(optimizer):
    campaign = UnifiedCampaign(
        platform=Platform.GOOGLE_ADS,
        platform_campaign_id="test_001",
        name="Zero Conv",
        status=CampaignStatus.ACTIVE,
        daily_budget=100,
        spend=500,
        revenue=0,
        conversions=0,
        clicks=200,
        impressions=5000,
    )
    score = optimizer._score_efficiency(campaign)
    assert score == 0.0


def test_trend_score_zero_no_history(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns, historical_campaigns=None)
    for s in scores:
        assert s.trend_score == 0.0


def test_trend_score_with_history(optimizer, current_campaigns, historical_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns, historical_campaigns)
    # Some scores should be non-zero with history
    trend_scores = [s.trend_score for s in scores]
    assert any(t != 0.0 for t in trend_scores)


# ── Action generation tests ────────────────────────────────────────────────────

def test_generate_actions_returns_list(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns)
    actions = optimizer.generate_actions(scores)
    assert isinstance(actions, list)


def test_all_actions_above_confidence_threshold(optimizer, current_campaigns):
    scores = optimizer.analyze_campaigns(current_campaigns)
    actions = optimizer.generate_actions(scores)
    for action in actions:
        assert action.confidence >= optimizer.confidence_threshold, (
            f"Action {action.action_type} has confidence {action.confidence}"
        )


def test_insufficient_data_mostly_no_actions(optimizer):
    google, meta = scenario_insufficient_data()
    all_camps = google + meta
    scores = optimizer.analyze_campaigns(all_camps)
    actions = optimizer.generate_actions(scores)
    # Most campaigns have < 10 conversions, so budget actions should be skipped
    budget_actions = [
        a for a in actions
        if a.action_type in (ActionType.INCREASE_BUDGET, ActionType.DECREASE_BUDGET)
    ]
    assert len(budget_actions) < len(all_camps)


def test_emergency_campaigns_get_pause_actions(optimizer):
    google, meta = scenario_emergency()
    all_camps = google + meta
    scores = optimizer.analyze_campaigns(all_camps)
    actions = optimizer.generate_actions(scores)
    pause_actions = [a for a in actions if a.action_type == ActionType.PAUSE_CAMPAIGN]
    assert len(pause_actions) >= 1


def test_healthy_campaigns_get_increase_actions(optimizer):
    google, meta = scenario_healthy_account()
    all_camps = google + meta
    scores = optimizer.analyze_campaigns(all_camps)
    actions = optimizer.generate_actions(scores)
    increase_actions = [
        a for a in actions if a.action_type == ActionType.INCREASE_BUDGET
    ]
    assert len(increase_actions) >= 1


def test_optimal_budget_increase_capped_at_max_change(optimizer):
    campaign = UnifiedCampaign(
        platform=Platform.GOOGLE_ADS,
        platform_campaign_id="cap_test",
        name="Cap Test Campaign",
        status=CampaignStatus.ACTIVE,
        daily_budget=500,
        spend=3500,
        revenue=20000,
        conversions=100,
        clicks=500,
        impressions=10000,
    )
    scores = optimizer.analyze_campaigns([campaign])
    assert len(scores) == 1
    score = scores[0]
    new_budget = optimizer.calculate_optimal_budget(campaign, score)
    max_allowed = campaign.daily_budget * (1 + optimizer.max_budget_change)
    assert new_budget <= max_allowed + 0.01


def test_optimal_budget_respects_single_campaign_max(optimizer):
    from app.config.settings import settings
    campaign = UnifiedCampaign(
        platform=Platform.GOOGLE_ADS,
        platform_campaign_id="max_test",
        name="Max Budget Campaign",
        status=CampaignStatus.ACTIVE,
        daily_budget=1900,
        spend=26600,
        revenue=200000,
        conversions=200,
        clicks=1000,
        impressions=20000,
    )
    scores = optimizer.analyze_campaigns([campaign])
    score = scores[0]
    new_budget = optimizer.calculate_optimal_budget(campaign, score)
    assert new_budget <= settings.MAX_SINGLE_CAMPAIGN_BUDGET + 0.01


def test_killed_campaigns_excluded(optimizer):
    campaign = UnifiedCampaign(
        platform=Platform.GOOGLE_ADS,
        platform_campaign_id="killed_001",
        name="Killed Campaign",
        status=CampaignStatus.KILLED,
        daily_budget=100,
        spend=1000,
        revenue=5000,
        conversions=50,
        clicks=200,
        impressions=5000,
    )
    scores = optimizer.analyze_campaigns([campaign])
    assert len(scores) == 0


def test_mode_weights_sum_to_one(optimizer):
    from app.config.settings import OptimizationMode
    for mode in OptimizationMode:
        with patch.object(optimizer, "mode", mode):
            weights = optimizer._get_mode_weights()
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{mode} weights sum to {total}"
