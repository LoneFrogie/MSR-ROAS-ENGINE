"""
Data Models and Pydantic Schemas
Unified schemas for campaign, ad group, and optimization data across platforms.
"""
from enum import Enum
from uuid import uuid4
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Platform(str, Enum):
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    GOOGLE_SEARCH_CONSOLE = "gsc"
    SEO = "seo"


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    KILLED = "killed"


class ActionType(str, Enum):
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    ENABLE_CAMPAIGN = "enable_campaign"
    INCREASE_BID = "increase_bid"
    DECREASE_BID = "decrease_bid"
    ADJUST_GEO_BID = "adjust_geo_bid"
    UPDATE_TARGETING = "update_targeting"
    UPDATE_AD_COPY = "update_ad_copy"
    UPDATE_KEYWORDS = "update_keywords"
    PAUSE_KEYWORD = "pause_keyword"
    ENABLE_KEYWORD = "enable_keyword"
    CREATE_AUDIENCE = "create_audience"
    REMOVE_AUDIENCE = "remove_audience"
    SEO_FIX = "seo_fix"
    REALLOCATE_BUDGET = "reallocate_budget"
    EMERGENCY_STOP = "emergency_stop"
    ADJUST_BID_MODIFIER = "adjust_bid_modifier"
    EXCLUDE_GEO = "exclude_geo"


class DecisionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UnifiedCampaign(BaseModel):
    id: Optional[str] = None
    platform: Platform
    platform_campaign_id: str
    name: str
    status: CampaignStatus
    daily_budget: float
    spend: float
    revenue: float
    roas: float = 0.0
    conversions: int
    clicks: int
    impressions: int
    ctr: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    conversion_rate: float = 0.0
    date_range_start: date = Field(default_factory=date.today)
    date_range_end: date = Field(default_factory=date.today)
    last_synced: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}

    def model_post_init(self, __context: Any) -> None:
        # Auto-compute id if not set
        if self.id is None:
            self.id = f"{self.platform.value}/{self.platform_campaign_id}"
        # Auto-compute roas if not provided
        if self.roas == 0.0 and self.spend > 0:
            self.roas = self.revenue / self.spend
        # Auto-compute derived metrics
        if self.clicks > 0 and self.impressions > 0:
            self.ctr = self.clicks / self.impressions
        if self.clicks > 0:
            self.cpc = self.spend / self.clicks
        if self.conversions > 0:
            self.cpa = self.spend / self.conversions
            self.conversion_rate = self.conversions / self.clicks if self.clicks > 0 else 0.0

    class Config:
        use_enum_values = False


class UnifiedAdGroup(BaseModel):
    id: Optional[str] = None
    campaign_id: Optional[str] = None
    platform_campaign_id: Optional[str] = None
    platform: Platform
    platform_adgroup_id: str
    name: str
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    conversions: int = 0
    clicks: int = 0
    impressions: int = 0
    bid_amount: Optional[float] = None
    targeting: Dict[str, Any] = {}

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = f"{self.platform.value}/{self.platform_adgroup_id}"
        if self.campaign_id is None and self.platform_campaign_id:
            self.campaign_id = self.platform_campaign_id
        if self.spend > 0 and self.revenue > 0:
            self.roas = self.revenue / self.spend

    class Config:
        use_enum_values = False


class UnifiedAd(BaseModel):
    id: str
    adgroup_id: str
    platform: Platform
    platform_ad_id: str
    headline: Optional[str] = None
    description: Optional[str] = None
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    conversions: int = 0
    clicks: int = 0
    impressions: int = 0

    class Config:
        use_enum_values = False


class SEOPageMetrics(BaseModel):
    url: str
    page_title: Optional[str] = None
    meta_description: Optional[str] = None
    avg_position: float = 0.0
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    top_queries: List[str] = []
    issues: List[str] = []
    optimization_suggestions: List[str] = []

    class Config:
        use_enum_values = False


class SEOSiteHealth(BaseModel):
    site_url: str = ""
    domain: str = ""
    total_pages_indexed: int = 0
    avg_position: float = 0.0
    total_clicks: int = 0
    total_impressions: int = 0
    avg_ctr: float = 0.0
    top_queries: List[str] = []
    ranking_pages_top3: int = 0
    ranking_pages_top10: int = 0
    ranking_pages_top20: int = 0
    top_performing_pages: List[SEOPageMetrics] = []
    underperforming_pages: List[SEOPageMetrics] = []
    technical_issues: List[Dict[str, Any]] = []
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    last_audit: Optional[datetime] = None


class GeoPerformance(BaseModel):
    region: str
    country: str
    platform: Platform
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    conversions: int = 0
    impressions: int = 0
    recommended_bid_modifier: float = 1.0

    class Config:
        use_enum_values = False


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"


class OptimizationAction(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    platform: Platform
    campaign_id: Optional[str] = None
    adgroup_id: Optional[str] = None
    action_type: ActionType
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    reason: str = ""
    confidence: float = 0.0
    confidence_level: Optional[DecisionConfidence] = None
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    executed: bool = False
    executed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    applied: bool = False
    result: Optional[str] = None
    details: Dict[str, Any] = {}

    class Config:
        use_enum_values = False


class BudgetAllocation(BaseModel):
    total_budget: float
    allocations: Dict[str, float]
    expected_roas: float
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = False


class CampaignScore(BaseModel):
    campaign: UnifiedCampaign
    roas_score: float = Field(ge=0, le=1)
    efficiency_score: float = Field(ge=0, le=1)
    volume_score: float = Field(ge=0, le=1)
    trend_score: float = Field(ge=-1, le=1)
    composite_score: float = Field(ge=0, le=1)
    recommended_action: ActionType
    confidence: float = Field(ge=0, le=1)

    class Config:
        use_enum_values = False


class PerformanceSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_spend: float = 0.0
    total_revenue: float = 0.0
    blended_roas: float = 0.0
    total_conversions: int = 0
    num_campaigns: int = 0
    num_active_campaigns: int = 0
    platform_breakdown: Dict[str, Dict[str, float]] = {}
    top_campaigns: List[UnifiedCampaign] = []
    actions_taken: List[OptimizationAction] = []
    actions_applied: int = 0
    alerts: List[str] = []
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = False


class WeeklyReport(BaseModel):
    period_start: date
    period_end: date
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str
    total_spend: float
    total_revenue: float
    blended_roas: float
    roas_trend: float
    spend_trend: float
    revenue_trend: float
    platform_performance: Dict[str, Dict[str, float]]
    top_actions: List[OptimizationAction]
    recommendations: List[str]
    seo_summary: Optional[SEOSiteHealth] = None
    geo_insights: List[GeoPerformance] = []


class NotificationPayload(BaseModel):
    title: str
    body: str
    severity: str = "info"
    action_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
