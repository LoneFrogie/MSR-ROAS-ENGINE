"""
ROAS Engine - Central Configuration
"""
import logging
from pydantic_settings import BaseSettings
from typing import Optional, Any, Dict
from enum import Enum

logger = logging.getLogger("roas_engine.settings")


class OptimizationMode(str, Enum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"


class ApprovalMode(str, Enum):
    FULL_MANUAL = "full_manual"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


class Settings(BaseSettings):
    APP_NAME: str = "ROAS Optimization Engine"
    APP_VERSION: str = "1.0.0"
    DEMO_MODE: bool = True
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/roas_engine"
    REDIS_URL: str = "redis://localhost:6379/0"

    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_CUSTOMER_ID: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: Optional[str] = None

    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_ACCESS_TOKEN: str = ""
    META_AD_ACCOUNT_ID: str = ""
    META_PIXEL_ID: Optional[str] = None
    META_PAGE_ID: str = ""
    META_INSTAGRAM_BUSINESS_ID: str = ""

    GSC_CREDENTIALS_JSON: str = ""
    GSC_SITE_URL: str = ""
    # OAuth (preferred — works with Domain properties when service account can't be added as user)
    GSC_OAUTH_CLIENT_ID: str = ""
    GSC_OAUTH_CLIENT_SECRET: str = ""
    GSC_OAUTH_REFRESH_TOKEN: str = ""

    # Shopify CMS (for SEO fix execution)
    SHOPIFY_SHOP_DOMAIN: str = ""  # e.g. mystore.myshopify.com
    SHOPIFY_ACCESS_TOKEN: str = ""
    # Aliases matching virtual_board project naming
    SHOPIFY_STORE_URL: str = ""
    SHOPIFY_ADMIN_API_TOKEN: str = ""
    # OAuth client_credentials for auto-refreshing tokens
    SHOPIFY_CLIENT_ID: str = ""
    SHOPIFY_CLIENT_SECRET: str = ""

    # Gemini (AI SEO suggestions)
    GEMINI_API_KEY: str = ""

    BRAND_DOMAIN: str = "brand.com"
    BRAND_SITEMAP_URL: str = "https://brand.com/sitemap.xml"

    OPTIMIZATION_MODE: OptimizationMode = OptimizationMode.BALANCED
    TARGET_ROAS: float = 4.0
    MIN_ROAS_THRESHOLD: float = 1.5
    MAX_DAILY_BUDGET_CHANGE_PCT: float = 0.20
    MAX_BID_CHANGE_PCT: float = 0.15
    LOOKBACK_DAYS: int = 14
    CONFIDENCE_THRESHOLD: float = 0.75
    MIN_CONVERSIONS_FOR_DECISION: int = 10
    BUDGET_REALLOCATION_FREQUENCY_HOURS: int = 6

    MAX_TOTAL_DAILY_BUDGET: float = 10000.0
    MAX_SINGLE_CAMPAIGN_BUDGET: float = 2000.0
    PAUSE_ON_ANOMALY: bool = True
    ANOMALY_SPEND_THRESHOLD_PCT: float = 2.0
    EMERGENCY_STOP_ROAS_BELOW: float = 0.5
    EMERGENCY_STOP_MIN_SPEND: float = 50.0  # Don't pause campaigns with spend below this

    DATA_SYNC_INTERVAL_MINUTES: int = 30
    OPTIMIZATION_CYCLE_MINUTES: int = 60
    SEO_AUDIT_INTERVAL_HOURS: int = 24
    ONPAGE_SCAN_INTERVAL_HOURS: int = 168  # weekly on-page crawl + AI suggest
    AI_SUGGESTIONS_PER_RUN: int = 5
    REPORT_GENERATION_HOUR: int = 8

    APPROVAL_MODE: ApprovalMode = ApprovalMode.FULL_MANUAL

    GCP_PROJECT_ID: Optional[str] = None  # auto-detected on Cloud Run
    LEARNING_LOOKBACK_CYCLES: int = 3
    LEARNING_RATE: float = 0.1
    LEARNING_MIN_SAMPLES: int = 20

    SLACK_WEBHOOK_URL: Optional[str] = None
    EMAIL_NOTIFICATIONS: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


# ─── Runtime Settings (user-adjustable at runtime) ───────────────────

# Keys that users can change via the dashboard
CONFIGURABLE_KEYS = {
    "TARGET_ROAS": {"type": float, "min": 0.1, "max": 50.0},
    "MIN_ROAS_THRESHOLD": {"type": float, "min": 0.1, "max": 20.0},
    "OPTIMIZATION_MODE": {"type": str, "enum": [m.value for m in OptimizationMode]},
    "CONFIDENCE_THRESHOLD": {"type": float, "min": 0.1, "max": 1.0},
    "MAX_DAILY_BUDGET_CHANGE_PCT": {"type": float, "min": 0.01, "max": 1.0},
    "MAX_BID_CHANGE_PCT": {"type": float, "min": 0.01, "max": 1.0},
    "MAX_TOTAL_DAILY_BUDGET": {"type": float, "min": 100, "max": 1000000},
    "MAX_SINGLE_CAMPAIGN_BUDGET": {"type": float, "min": 10, "max": 100000},
    "LOOKBACK_DAYS": {"type": int, "min": 1, "max": 90},
    "OPTIMIZATION_CYCLE_MINUTES": {"type": int, "min": 5, "max": 1440},
    "APPROVAL_MODE": {"type": str, "enum": [m.value for m in ApprovalMode]},
    "EMERGENCY_STOP_ROAS_BELOW": {"type": float, "min": 0.0, "max": 5.0},
    "EMERGENCY_STOP_MIN_SPEND": {"type": float, "min": 0.0, "max": 10000.0},
    "PAUSE_ON_ANOMALY": {"type": bool},
    "SEO_AUDIT_INTERVAL_HOURS": {"type": int, "min": 1, "max": 168},
    "ONPAGE_SCAN_INTERVAL_HOURS": {"type": int, "min": 1, "max": 720},
    "AI_SUGGESTIONS_PER_RUN": {"type": int, "min": 1, "max": 50},
    "LEARNING_LOOKBACK_CYCLES": {"type": int, "min": 1, "max": 20},
    "LEARNING_RATE": {"type": float, "min": 0.01, "max": 0.5},
    "LEARNING_MIN_SAMPLES": {"type": int, "min": 5, "max": 200},
}


class RuntimeSettings:
    """
    Wraps the immutable Pydantic Settings with a runtime override layer.
    Reads override first, falls back to base settings.
    """

    def __init__(self):
        self._overrides: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        return getattr(settings, key)

    def set(self, key: str, value: Any) -> None:
        if key not in CONFIGURABLE_KEYS:
            raise ValueError(f"Setting '{key}' is not configurable at runtime")

        spec = CONFIGURABLE_KEYS[key]

        # Type coercion
        if spec["type"] == float:
            value = float(value)
        elif spec["type"] == int:
            value = int(value)
        elif spec["type"] == bool:
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            value = bool(value)

        # Enum validation
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"'{value}' not in allowed values: {spec['enum']}")

        # Range validation
        if "min" in spec and value < spec["min"]:
            raise ValueError(f"'{key}' must be >= {spec['min']}")
        if "max" in spec and value > spec["max"]:
            raise ValueError(f"'{key}' must be <= {spec['max']}")

        self._overrides[key] = value
        logger.info(f"Runtime config updated: {key} = {value}")

    def get_all(self) -> Dict[str, Any]:
        """Return all configurable settings with current values."""
        result = {}
        for key in CONFIGURABLE_KEYS:
            result[key.lower()] = self.get(key)
        return result

    def reset(self, key: str = None) -> None:
        if key:
            self._overrides.pop(key, None)
        else:
            self._overrides.clear()


runtime_settings = RuntimeSettings()
