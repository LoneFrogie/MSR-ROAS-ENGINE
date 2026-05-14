"""
Unit tests for CrossPlatformBudgetAllocator.
"""
import pytest

from app.optimizers.budget_allocator import CrossPlatformBudgetAllocator
from app.models.schemas import Platform, ActionType
from app.config.settings import settings
from tests.mock_data import (
    generate_all_campaigns, scenario_budget_imbalance,
    scenario_healthy_account,
)


@pytest.fixture
def allocator():
    return CrossPlatformBudgetAllocator()


@pytest.fixture
def all_campaigns():
    google, meta = generate_all_campaigns()
    return google + meta


# ── Allocation tests ───────────────────────────────────────────────────────────

def test_calculate_allocation_returns_budget_allocation(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    assert allocation is not None
    assert allocation.total_budget == settings.MAX_TOTAL_DAILY_BUDGET


def test_allocation_covers_all_campaigns(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    for campaign in all_campaigns:
        key = f"{campaign.platform.value}/{campaign.id}"
        assert key in allocation.allocations, f"Missing key: {key}"


def test_allocation_values_positive(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    for key, budget in allocation.allocations.items():
        assert budget > 0, f"{key} has non-positive budget {budget}"


def test_allocation_respects_single_campaign_max(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    for key, budget in allocation.allocations.items():
        assert budget <= settings.MAX_SINGLE_CAMPAIGN_BUDGET + 0.01, (
            f"{key} budget {budget} exceeds max {settings.MAX_SINGLE_CAMPAIGN_BUDGET}"
        )


def test_high_roas_platform_gets_more_budget(allocator):
    """Google has higher ROAS → should receive ≥ 50% of budget."""
    google, meta = scenario_budget_imbalance()
    all_camps = google + meta
    allocation = allocator.calculate_allocation(all_camps)

    google_budget = sum(
        v for k, v in allocation.allocations.items()
        if k.startswith("google_ads/")
    )
    meta_budget = sum(
        v for k, v in allocation.allocations.items()
        if k.startswith("meta_ads/")
    )
    assert google_budget > meta_budget, (
        f"Expected Google > Meta: {google_budget:.2f} vs {meta_budget:.2f}"
    )


def test_min_platform_allocation_respected(allocator):
    """Even a platform with 0 ROAS should get at least min_platform_pct."""
    google, _ = generate_all_campaigns()
    # Meta campaigns with zero spend/revenue
    from app.models.schemas import UnifiedCampaign, CampaignStatus
    meta_zero = [
        UnifiedCampaign(
            platform=Platform.META_ADS,
            platform_campaign_id=f"m_zero_{i}",
            name=f"Zero Meta {i}",
            status=CampaignStatus.ACTIVE,
            daily_budget=100,
            spend=0,
            revenue=0,
            conversions=0,
            clicks=0,
            impressions=0,
        )
        for i in range(3)
    ]
    all_camps = google + meta_zero
    allocation = allocator.calculate_allocation(all_camps)

    meta_budget = sum(
        v for k, v in allocation.allocations.items()
        if k.startswith("meta_ads/")
    )
    min_meta = settings.MAX_TOTAL_DAILY_BUDGET * allocator.min_platform_pct
    # Meta should get at least min_platform_pct of total
    assert meta_budget >= min_meta - 1.0, (
        f"Meta budget {meta_budget:.2f} below min {min_meta:.2f}"
    )


def test_allocation_reasoning_string(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    assert "Budget reallocation" in allocation.reasoning


# ── Reallocation action tests ──────────────────────────────────────────────────

def test_generate_reallocation_actions_returns_list(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    actions = allocator.generate_reallocation_actions(allocation, all_campaigns)
    assert isinstance(actions, list)


def test_reallocation_actions_respect_max_daily_change(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    actions = allocator.generate_reallocation_actions(allocation, all_campaigns)
    for action in actions:
        if action.old_value and action.new_value:
            pct_change = abs(action.new_value - action.old_value) / action.old_value
            assert pct_change <= settings.MAX_DAILY_BUDGET_CHANGE_PCT + 0.001, (
                f"Action for {action.campaign_id} change {pct_change:.3f} "
                f"exceeds max {settings.MAX_DAILY_BUDGET_CHANGE_PCT}"
            )


def test_reallocation_action_types_correct(allocator, all_campaigns):
    allocation = allocator.calculate_allocation(all_campaigns)
    actions = allocator.generate_reallocation_actions(allocation, all_campaigns)
    for action in actions:
        if action.old_value and action.new_value:
            if action.new_value > action.old_value:
                assert action.action_type == ActionType.INCREASE_BUDGET
            else:
                assert action.action_type == ActionType.DECREASE_BUDGET


def test_small_changes_filtered_out(allocator):
    """Changes < $2 should be skipped."""
    from app.models.schemas import UnifiedCampaign, CampaignStatus
    campaign = UnifiedCampaign(
        platform=Platform.GOOGLE_ADS,
        platform_campaign_id="tiny_change",
        name="Tiny Change Campaign",
        status=CampaignStatus.ACTIVE,
        daily_budget=100.00,
        spend=1400,
        revenue=5600,
        conversions=20,
        clicks=100,
        impressions=2000,
    )
    allocation = allocator.calculate_allocation([campaign])
    # Manually set the allocation to current budget (no change)
    key = f"{campaign.platform.value}/{campaign.id}"
    allocation.allocations[key] = campaign.daily_budget + 1.0  # $1 change
    actions = allocator.generate_reallocation_actions(allocation, [campaign])
    assert len(actions) == 0, "Small change should be filtered"


def test_empty_campaigns_list(allocator):
    allocation = allocator.calculate_allocation([])
    assert allocation.total_budget == settings.MAX_TOTAL_DAILY_BUDGET
    assert allocation.allocations == {}
