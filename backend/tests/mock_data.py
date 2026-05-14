"""
Mock data generators for testing — no live API calls.
Uses seed=42 for reproducibility.
"""
import random
from typing import List, Tuple
from datetime import date, timedelta

from app.models.schemas import (
    UnifiedCampaign, Platform, CampaignStatus
)


random.seed(42)

# ── Campaign templates ─────────────────────────────────────────────────────────

GOOGLE_CAMPAIGN_TEMPLATES = [
    {"name": "Brand - Search",       "budget": 500,  "roas_range": (5.0, 8.0),  "conv": (80, 150)},
    {"name": "Generic - Search",     "budget": 800,  "roas_range": (3.0, 5.5),  "conv": (40, 100)},
    {"name": "Shopping - All",       "budget": 1200, "roas_range": (4.0, 7.0),  "conv": (60, 130)},
    {"name": "Retargeting - RLSA",   "budget": 400,  "roas_range": (6.0, 10.0), "conv": (50, 90)},
    {"name": "Competitor - Search",  "budget": 300,  "roas_range": (1.2, 3.0),  "conv": (10, 40)},
    {"name": "Display - Prospecting","budget": 600,  "roas_range": (0.5, 2.0),  "conv": (5, 25)},
    {"name": "YouTube - Brand",      "budget": 350,  "roas_range": (1.8, 4.0),  "conv": (15, 50)},
    {"name": "Performance Max",      "budget": 1000, "roas_range": (3.5, 6.0),  "conv": (70, 140)},
    {"name": "DSA - All Pages",      "budget": 250,  "roas_range": (2.0, 4.5),  "conv": (20, 60)},
    {"name": "RLSA - Cart Abandon",  "budget": 450,  "roas_range": (7.0, 12.0), "conv": (90, 180)},
    {"name": "Low ROAS Campaign",    "budget": 200,  "roas_range": (0.3, 0.9),  "conv": (2, 10)},
    {"name": "New Product Launch",   "budget": 700,  "roas_range": (1.5, 3.5),  "conv": (20, 55)},
]

META_CAMPAIGN_TEMPLATES = [
    {"name": "Prospecting - TOF",       "budget": 600,  "roas_range": (2.5, 5.0),  "conv": (30, 80)},
    {"name": "Retargeting - MOF",       "budget": 450,  "roas_range": (4.0, 8.0),  "conv": (50, 100)},
    {"name": "Lookalike - Purchasers",  "budget": 700,  "roas_range": (3.5, 6.5),  "conv": (45, 95)},
    {"name": "Dynamic Product Ads",     "budget": 900,  "roas_range": (5.0, 9.0),  "conv": (80, 160)},
    {"name": "Catalog - Retargeting",   "budget": 500,  "roas_range": (6.0, 11.0), "conv": (70, 130)},
    {"name": "Broad - Video Views",     "budget": 300,  "roas_range": (0.8, 2.5),  "conv": (5, 20)},
    {"name": "Interest - Skincare",     "budget": 400,  "roas_range": (1.5, 4.0),  "conv": (15, 50)},
    {"name": "Lookalike - High LTV",    "budget": 550,  "roas_range": (4.5, 7.5),  "conv": (60, 110)},
    {"name": "Brand Awareness",         "budget": 200,  "roas_range": (0.4, 1.2),  "conv": (2, 12)},
    {"name": "Conversion - BOFU",       "budget": 800,  "roas_range": (5.5, 10.0), "conv": (90, 170)},
]

GEO_COUNTRIES = [
    {"code": "MY",  "roas_range": (3.5, 6.5), "spend_pct": 0.25},
    {"code": "SG",  "roas_range": (4.0, 8.0), "spend_pct": 0.20},
    {"code": "US",  "roas_range": (5.0, 9.0), "spend_pct": 0.15},
    {"code": "GB",  "roas_range": (4.5, 7.0), "spend_pct": 0.10},
    {"code": "AU",  "roas_range": (3.0, 6.0), "spend_pct": 0.08},
    {"code": "ID",  "roas_range": (1.5, 3.5), "spend_pct": 0.07},
    {"code": "TH",  "roas_range": (1.2, 2.5), "spend_pct": 0.05},
    {"code": "PH",  "roas_range": (0.8, 2.0), "spend_pct": 0.04},
    {"code": "IN",  "roas_range": (0.5, 1.5), "spend_pct": 0.03},
    {"code": "VN",  "roas_range": (0.3, 1.0), "spend_pct": 0.02},
    {"code": "HK",  "roas_range": (5.5, 10.0),"spend_pct": 0.01},
    {"code": "JP",  "roas_range": (2.0, 4.5), "spend_pct": 0.00},
]

SEO_PAGES = [
    {"query": "best skincare products",     "position": 1.2,  "impressions": 8000,  "clicks": 900},
    {"query": "moisturizer for dry skin",   "position": 2.5,  "impressions": 5000,  "clicks": 450},
    {"query": "anti aging serum",           "position": 5.1,  "impressions": 4500,  "clicks": 180},
    {"query": "vitamin c serum review",     "position": 8.3,  "impressions": 3200,  "clicks": 96},
    {"query": "natural skincare routine",   "position": 12.4, "impressions": 2800,  "clicks": 42},
    {"query": "buy sunscreen online",       "position": 15.7, "impressions": 2100,  "clicks": 21},
    {"query": "retinol cream benefits",     "position": 18.0, "impressions": 1800,  "clicks": 9},
    {"query": "hyaluronic acid serum",      "position": 3.2,  "impressions": 6200,  "clicks": 620},
    {"query": "brand.com reviews",          "position": 1.0,  "impressions": 3000,  "clicks": 870},
    {"query": "niacinamide serum",          "position": 6.8,  "impressions": 2500,  "clicks": 75},
    {"query": "exfoliating toner",          "position": 11.5, "impressions": 1500,  "clicks": 22},
    {"query": "face oil dry skin",          "position": 9.0,  "impressions": 1900,  "clicks": 57},
]


def _make_campaign(
    template: dict,
    platform: Platform,
    platform_id: str,
    lookback_days: int = 14,
    status: CampaignStatus = CampaignStatus.ACTIVE,
) -> UnifiedCampaign:
    roas = random.uniform(*template["roas_range"])
    conversions = random.randint(*template["conv"])
    spend = template["budget"] * lookback_days * random.uniform(0.85, 1.0)
    revenue = spend * roas
    clicks = int(conversions * random.uniform(25, 60))
    impressions = int(clicks * random.uniform(8, 20))

    return UnifiedCampaign(
        platform=platform,
        platform_campaign_id=platform_id,
        name=template["name"],
        status=status,
        daily_budget=float(template["budget"]),
        spend=round(spend, 2),
        revenue=round(revenue, 2),
        conversions=conversions,
        clicks=clicks,
        impressions=impressions,
    )


def generate_all_campaigns(
    period: str = "current",
    lookback_days: int = 14,
) -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """
    Generate full set of Google + Meta campaigns.
    Returns (google_campaigns, meta_campaigns).
    """
    seed_offset = 0 if period == "current" else 100
    random.seed(42 + seed_offset)

    google = []
    for i, tmpl in enumerate(GOOGLE_CAMPAIGN_TEMPLATES):
        camp = _make_campaign(
            tmpl, Platform.GOOGLE_ADS, f"g_{i+1:04d}", lookback_days
        )
        google.append(camp)

    meta = []
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES):
        camp = _make_campaign(
            tmpl, Platform.META_ADS, f"m_{i+1:04d}", lookback_days
        )
        meta.append(camp)

    return google, meta


# ── Named scenarios ────────────────────────────────────────────────────────────

def scenario_healthy_account() -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """All campaigns above target ROAS. Expect budget increases."""
    random.seed(1)
    google, meta = [], []
    for i, tmpl in enumerate(GOOGLE_CAMPAIGN_TEMPLATES[:6]):
        t = dict(tmpl)
        t["roas_range"] = (4.5, 7.0)
        t["conv"] = (50, 120)
        google.append(_make_campaign(t, Platform.GOOGLE_ADS, f"g_{i+1:04d}"))
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES[:5]):
        t = dict(tmpl)
        t["roas_range"] = (4.5, 7.0)
        t["conv"] = (50, 110)
        meta.append(_make_campaign(t, Platform.META_ADS, f"m_{i+1:04d}"))
    return google, meta


def scenario_emergency() -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """Several campaigns below EMERGENCY_STOP_ROAS_BELOW=0.5."""
    random.seed(2)
    google, meta = [], []
    emergency_templates = [
        {"name": "Emergency Camp 1", "budget": 500, "roas_range": (0.1, 0.4), "conv": (1, 5)},
        {"name": "Emergency Camp 2", "budget": 400, "roas_range": (0.2, 0.4), "conv": (1, 3)},
        {"name": "Normal Camp 1",    "budget": 600, "roas_range": (4.0, 6.0), "conv": (60, 100)},
    ]
    for i, tmpl in enumerate(emergency_templates):
        google.append(_make_campaign(tmpl, Platform.GOOGLE_ADS, f"g_{i+1:04d}"))
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES[:3]):
        t = dict(tmpl)
        if i < 2:
            t["roas_range"] = (0.1, 0.4)
            t["conv"] = (1, 5)
        meta.append(_make_campaign(t, Platform.META_ADS, f"m_{i+1:04d}"))
    return google, meta


def scenario_all_winners() -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """All campaigns with high ROAS and high volume."""
    random.seed(3)
    google, meta = [], []
    for i, tmpl in enumerate(GOOGLE_CAMPAIGN_TEMPLATES[:8]):
        t = dict(tmpl)
        t["roas_range"] = (6.0, 10.0)
        t["conv"] = (100, 200)
        google.append(_make_campaign(t, Platform.GOOGLE_ADS, f"g_{i+1:04d}"))
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES[:6]):
        t = dict(tmpl)
        t["roas_range"] = (6.0, 10.0)
        t["conv"] = (100, 200)
        meta.append(_make_campaign(t, Platform.META_ADS, f"m_{i+1:04d}"))
    return google, meta


def scenario_budget_imbalance() -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """Google has much higher ROAS than Meta — expect reallocation to Google."""
    random.seed(4)
    google, meta = [], []
    for i, tmpl in enumerate(GOOGLE_CAMPAIGN_TEMPLATES[:5]):
        t = dict(tmpl)
        t["roas_range"] = (6.0, 9.0)
        t["conv"] = (80, 150)
        google.append(_make_campaign(t, Platform.GOOGLE_ADS, f"g_{i+1:04d}"))
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES[:5]):
        t = dict(tmpl)
        t["roas_range"] = (0.8, 1.4)
        t["conv"] = (5, 20)
        meta.append(_make_campaign(t, Platform.META_ADS, f"m_{i+1:04d}"))
    return google, meta


def scenario_insufficient_data() -> Tuple[List[UnifiedCampaign], List[UnifiedCampaign]]:
    """All campaigns below min_conversions threshold — most actions should be skipped."""
    random.seed(5)
    google, meta = [], []
    for i, tmpl in enumerate(GOOGLE_CAMPAIGN_TEMPLATES[:4]):
        t = dict(tmpl)
        t["conv"] = (1, 5)  # below MIN_CONVERSIONS_FOR_DECISION=10
        google.append(_make_campaign(t, Platform.GOOGLE_ADS, f"g_{i+1:04d}"))
    for i, tmpl in enumerate(META_CAMPAIGN_TEMPLATES[:3]):
        t = dict(tmpl)
        t["conv"] = (1, 5)
        meta.append(_make_campaign(t, Platform.META_ADS, f"m_{i+1:04d}"))
    return google, meta
