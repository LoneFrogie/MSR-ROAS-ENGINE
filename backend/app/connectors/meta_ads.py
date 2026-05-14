"""
Meta Ads Connector
Fetches campaign data and executes changes via Meta Marketing API.

The facebook-business SDK is synchronous; methods wrap calls in asyncio.to_thread()
to avoid blocking the event loop.
"""
import asyncio
import logging
from datetime import date
from typing import List, Dict, Optional

from app.models.schemas import (
    UnifiedCampaign, Platform, CampaignStatus
)
from app.config.settings import settings

logger = logging.getLogger("roas_engine.meta_ads")


class MetaAdsConnector:

    def __init__(self):
        # Strip any pre-existing "act_" prefix so we always prepend exactly once
        raw = settings.META_AD_ACCOUNT_ID or ""
        self.ad_account_id = raw[4:] if raw.startswith("act_") else raw
        self.access_token = settings.META_ACCESS_TOKEN
        self._initialized = False

    def _init_api(self):
        if self._initialized:
            return
        from facebook_business.api import FacebookAdsApi
        FacebookAdsApi.init(
            app_id=settings.META_APP_ID,
            app_secret=settings.META_APP_SECRET,
            access_token=self.access_token,
        )
        self._initialized = True

    async def get_campaigns(self, start_date: date, end_date: date) -> List[UnifiedCampaign]:
        return await asyncio.to_thread(self._get_campaigns_sync, start_date, end_date)

    def _get_campaigns_sync(
        self, start_date: date, end_date: date
    ) -> List[UnifiedCampaign]:
        """
        Fetch all campaigns + their insights in TWO API calls (instead of N+1):
        1. List campaigns (metadata)
        2. Account-level insights with level=campaign (returns all insights in one call)
        """
        self._init_api()
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.campaign import Campaign

        account = AdAccount(f"act_{self.ad_account_id}")
        time_range = {
            "since": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
        }

        # 1) List campaigns (metadata only)
        fields = [
            Campaign.Field.id,
            Campaign.Field.name,
            Campaign.Field.status,
            Campaign.Field.daily_budget,
            Campaign.Field.lifetime_budget,
        ]
        raw_campaigns = list(account.get_campaigns(
            fields=fields,
            params={
                "effective_status": ["ACTIVE", "PAUSED"],
                "limit": 500,
            }
        ))
        logger.info(f"Meta: fetched {len(raw_campaigns)} campaign metadata records")

        # 2) Bulk insights at campaign level (single paginated query)
        insight_fields = [
            "campaign_id",
            "spend",
            "action_values",
            "actions",
            "clicks",
            "impressions",
        ]
        insights_iter = account.get_insights(
            fields=insight_fields,
            params={
                "level": "campaign",
                "time_range": time_range,
                "limit": 500,
            }
        )
        insights_by_campaign = {}
        for ins in insights_iter:
            cid = str(ins.get("campaign_id"))
            insights_by_campaign[cid] = ins
        logger.info(f"Meta: bulk insights for {len(insights_by_campaign)} campaigns")

        status_map = {
            "ACTIVE": CampaignStatus.ACTIVE,
            "PAUSED": CampaignStatus.PAUSED,
            "ARCHIVED": CampaignStatus.KILLED,
            "DELETED": CampaignStatus.KILLED,
        }

        campaigns = []
        for raw in raw_campaigns:
            cid = str(raw["id"])
            ins = insights_by_campaign.get(cid)

            spend = 0.0
            revenue = 0.0
            conversions = 0
            clicks = 0
            impressions = 0

            if ins:
                spend = float(ins.get("spend", 0))
                for av in ins.get("action_values", []) or []:
                    if av.get("action_type") == "offsite_conversion.fb_pixel_purchase":
                        revenue = float(av.get("value", 0))
                        break
                for act in ins.get("actions", []) or []:
                    if act.get("action_type") == "offsite_conversion.fb_pixel_purchase":
                        conversions = int(float(act.get("value", 0)))
                        break
                clicks = int(ins.get("clicks", 0))
                impressions = int(ins.get("impressions", 0))

            status = status_map.get(raw.get("status", "PAUSED"), CampaignStatus.PAUSED)
            daily_budget = float(raw.get("daily_budget", 0)) / 100  # cents to dollars

            campaigns.append(UnifiedCampaign(
                platform=Platform.META_ADS,
                platform_campaign_id=cid,
                name=raw["name"],
                status=status,
                daily_budget=daily_budget,
                spend=spend,
                revenue=revenue,
                conversions=conversions,
                clicks=clicks,
                impressions=impressions,
            ))
        return campaigns

    async def get_geo_performance(self, start_date: date, end_date: date) -> List[Dict]:
        return await asyncio.to_thread(self._get_geo_performance_sync, start_date, end_date)

    def _get_geo_performance_sync(
        self, start_date: date, end_date: date
    ) -> List[Dict]:
        self._init_api()
        from facebook_business.adobjects.adaccount import AdAccount

        account = AdAccount(f"act_{self.ad_account_id}")
        time_range = {
            "since": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
        }

        insights = account.get_insights(
            fields=["spend", "action_values", "actions", "clicks", "impressions"],
            params={
                "time_range": time_range,
                "breakdowns": ["country"],
                "level": "account",
                "limit": 200,
            }
        )

        geo_data = []
        for ins in insights:
            spend = float(ins.get("spend", 0))
            revenue = 0.0
            for av in ins.get("action_values", []):
                if av.get("action_type") == "offsite_conversion.fb_pixel_purchase":
                    revenue = float(av.get("value", 0))
                    break
            conversions = 0
            for act in ins.get("actions", []):
                if act.get("action_type") == "offsite_conversion.fb_pixel_purchase":
                    conversions = int(float(act.get("value", 0)))
                    break
            geo_data.append({
                "country": ins.get("country", "UNKNOWN"),
                "spend": spend,
                "revenue": revenue,
                "conversions": conversions,
                "clicks": int(ins.get("clicks", 0)),
                "platform": "meta",
            })
        return geo_data

    async def update_campaign_budget(self, campaign_id: str, new_daily_budget: float) -> bool:
        return await asyncio.to_thread(self._update_campaign_budget_sync, campaign_id, new_daily_budget)

    def _update_campaign_budget_sync(
        self, campaign_id: str, new_daily_budget: float
    ) -> bool:
        try:
            self._init_api()
            from facebook_business.adobjects.campaign import Campaign

            campaign = Campaign(campaign_id)
            campaign.update(
                params={
                    "daily_budget": int(new_daily_budget * 100),  # to cents
                }
            )
            logger.info(f"Updated Meta campaign {campaign_id} budget to ${new_daily_budget:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update Meta campaign budget {campaign_id}: {e}")
            return False

    async def pause_campaign(self, campaign_id: str) -> bool:
        return await asyncio.to_thread(self._pause_campaign_sync, campaign_id)

    def _pause_campaign_sync(self, campaign_id: str) -> bool:
        try:
            self._init_api()
            from facebook_business.adobjects.campaign import Campaign

            campaign = Campaign(campaign_id)
            campaign.update(params={"status": "PAUSED"})
            logger.info(f"Paused Meta campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause Meta campaign {campaign_id}: {e}")
            return False

    async def enable_campaign(self, campaign_id: str) -> bool:
        return await asyncio.to_thread(self._enable_campaign_sync, campaign_id)

    def _enable_campaign_sync(self, campaign_id: str) -> bool:
        try:
            self._init_api()
            from facebook_business.adobjects.campaign import Campaign

            campaign = Campaign(campaign_id)
            campaign.update(params={"status": "ACTIVE"})
            logger.info(f"Enabled Meta campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable Meta campaign {campaign_id}: {e}")
            return False
