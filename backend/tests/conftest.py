"""
Test configuration — sets environment variables so settings load without real credentials.
"""
import os
import pytest

# Set all required env vars before importing settings
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GOOGLE_ADS_DEVELOPER_TOKEN", "test_dev_token")
os.environ.setdefault("GOOGLE_ADS_CLIENT_ID", "test_client_id")
os.environ.setdefault("GOOGLE_ADS_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("GOOGLE_ADS_REFRESH_TOKEN", "test_refresh_token")
os.environ.setdefault("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
os.environ.setdefault("META_APP_ID", "test_meta_app_id")
os.environ.setdefault("META_APP_SECRET", "test_meta_app_secret")
os.environ.setdefault("META_ACCESS_TOKEN", "test_meta_token")
os.environ.setdefault("META_AD_ACCOUNT_ID", "test_ad_account")
os.environ.setdefault("GSC_CREDENTIALS_JSON", "{}")
os.environ.setdefault("GSC_SITE_URL", "https://brand.com")
os.environ.setdefault("BRAND_DOMAIN", "brand.com")
os.environ.setdefault("TARGET_ROAS", "4.0")
os.environ.setdefault("MIN_ROAS_THRESHOLD", "1.5")
os.environ.setdefault("MAX_DAILY_BUDGET_CHANGE_PCT", "0.20")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "0.75")
os.environ.setdefault("OPTIMIZATION_MODE", "balanced")
