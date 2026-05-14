"""
Google Ads Connector
Fetches campaign data and executes budget/bid changes via Google Ads API.

The Google Ads SDK is synchronous (blocking). Async methods wrap calls in
asyncio.to_thread() so we don't block the event loop on long queries.
"""
import asyncio
import logging
from datetime import date
from typing import List, Optional, Dict

from app.models.schemas import (
    UnifiedCampaign, UnifiedAdGroup, Platform, CampaignStatus
)
from app.config.settings import settings

logger = logging.getLogger("roas_engine.google_ads")


class GoogleAdsConnector:

    def __init__(self):
        self.customer_id = settings.GOOGLE_ADS_CUSTOMER_ID
        self.client = None
        self._initialized = False

    def _get_client(self):
        if self._initialized:
            return self.client

        from google.ads.googleads.client import GoogleAdsClient
        import json, tempfile, os, time

        credentials = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID or settings.GOOGLE_ADS_CUSTOMER_ID,
            "use_proto_plus": True,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(credentials, f)
            tmp_path = f.name

        # Retry up to 3 times on transient SSL/network errors
        last_err = None
        for attempt in range(3):
            try:
                self.client = GoogleAdsClient.load_from_storage(tmp_path)
                self._initialized = True
                os.unlink(tmp_path)
                return self.client
            except Exception as e:
                last_err = e
                err_str = str(e)
                # Retry on transient network errors
                if any(k in err_str for k in ("SSL", "EOF", "Connection", "timeout", "TimeoutError")):
                    logger.warning(f"Google Ads client init attempt {attempt+1}/3 failed: {e}")
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        logger.error(f"Failed to initialize Google Ads client after retries: {last_err}")
        raise last_err

    async def get_campaigns(self, start_date: date, end_date: date) -> List[UnifiedCampaign]:
        return await asyncio.to_thread(self._get_campaigns_sync, start_date, end_date)

    def _get_campaigns_sync(
        self, start_date: date, end_date: date
    ) -> List[UnifiedCampaign]:
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign_budget.amount_micros,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.conversions,
                metrics.clicks,
                metrics.impressions,
                metrics.ctr
            FROM campaign
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
        """

        campaigns = []
        response = ga_service.search_stream(
            customer_id=self.customer_id, query=query
        )
        for batch in response:
            for row in batch.results:
                spend = row.metrics.cost_micros / 1_000_000
                revenue = row.metrics.conversions_value
                conversions = int(row.metrics.conversions)
                clicks = int(row.metrics.clicks)
                daily_budget = row.campaign_budget.amount_micros / 1_000_000

                status_map = {
                    "ENABLED": CampaignStatus.ACTIVE,
                    "PAUSED": CampaignStatus.PAUSED,
                    "REMOVED": CampaignStatus.KILLED,
                }
                status = status_map.get(row.campaign.status.name, CampaignStatus.PAUSED)

                campaigns.append(UnifiedCampaign(
                    platform=Platform.GOOGLE_ADS,
                    platform_campaign_id=str(row.campaign.id),
                    name=row.campaign.name,
                    status=status,
                    daily_budget=daily_budget,
                    spend=spend,
                    revenue=revenue,
                    conversions=conversions,
                    clicks=clicks,
                    impressions=int(row.metrics.impressions),
                ))
        return campaigns

    async def get_ad_groups(self, campaign_id: str, start_date: date, end_date: date) -> List[UnifiedAdGroup]:
        return await asyncio.to_thread(self._get_ad_groups_sync, campaign_id, start_date, end_date)

    def _get_ad_groups_sync(
        self, campaign_id: str, start_date: date, end_date: date
    ) -> List[UnifiedAdGroup]:
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                ad_group.id,
                ad_group.name,
                ad_group.status,
                ad_group.cpc_bid_micros,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.conversions,
                metrics.clicks,
                metrics.impressions
            FROM ad_group
            WHERE campaign.id = {campaign_id}
                AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND ad_group.status != 'REMOVED'
        """

        ad_groups = []
        response = ga_service.search_stream(
            customer_id=self.customer_id, query=query
        )
        for batch in response:
            for row in batch.results:
                spend = row.metrics.cost_micros / 1_000_000
                revenue = row.metrics.conversions_value
                conversions = int(row.metrics.conversions)
                clicks = int(row.metrics.clicks)

                ad_groups.append(UnifiedAdGroup(
                    platform=Platform.GOOGLE_ADS,
                    platform_adgroup_id=str(row.ad_group.id),
                    platform_campaign_id=campaign_id,
                    name=row.ad_group.name,
                    spend=spend,
                    revenue=revenue,
                    conversions=conversions,
                    clicks=clicks,
                    impressions=int(row.metrics.impressions),
                    bid_amount=row.ad_group.cpc_bid_micros / 1_000_000,
                ))
        return ad_groups

    async def get_keyword_performance(self, start_date: date, end_date: date) -> List[Dict]:
        return await asyncio.to_thread(self._get_keyword_performance_sync, start_date, end_date)

    def _get_keyword_performance_sync(
        self, start_date: date, end_date: date
    ) -> List[Dict]:
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                campaign.name,
                ad_group.name,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.conversions,
                metrics.clicks,
                metrics.average_cpc
            FROM keyword_view
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND ad_group_criterion.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT 500
        """

        keywords = []
        response = ga_service.search_stream(
            customer_id=self.customer_id, query=query
        )
        for batch in response:
            for row in batch.results:
                keywords.append({
                    "keyword": row.ad_group_criterion.keyword.text,
                    "match_type": row.ad_group_criterion.keyword.match_type.name,
                    "campaign": row.campaign.name,
                    "ad_group": row.ad_group.name,
                    "spend": row.metrics.cost_micros / 1_000_000,
                    "revenue": row.metrics.conversions_value,
                    "conversions": int(row.metrics.conversions),
                    "clicks": int(row.metrics.clicks),
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                })
        return keywords

    async def get_search_terms_report(self, start_date: date, end_date: date) -> List[Dict]:
        return await asyncio.to_thread(self._get_search_terms_report_sync, start_date, end_date)

    def _get_search_terms_report_sync(
        self, start_date: date, end_date: date
    ) -> List[Dict]:
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                search_term_view.search_term,
                campaign.name,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.conversions,
                metrics.clicks,
                metrics.impressions
            FROM search_term_view
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY metrics.cost_micros DESC
            LIMIT 1000
        """

        terms = []
        response = ga_service.search_stream(
            customer_id=self.customer_id, query=query
        )
        for batch in response:
            for row in batch.results:
                terms.append({
                    "search_term": row.search_term_view.search_term,
                    "campaign": row.campaign.name,
                    "spend": row.metrics.cost_micros / 1_000_000,
                    "revenue": row.metrics.conversions_value,
                    "conversions": int(row.metrics.conversions),
                    "clicks": int(row.metrics.clicks),
                    "impressions": int(row.metrics.impressions),
                })
        return terms

    async def get_geo_performance(self, start_date: date, end_date: date) -> List[Dict]:
        return await asyncio.to_thread(self._get_geo_performance_sync, start_date, end_date)

    def _get_geo_performance_sync(
        self, start_date: date, end_date: date
    ) -> List[Dict]:
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                geographic_view.country_criterion_id,
                campaign.id,
                campaign.name,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.conversions,
                metrics.clicks
            FROM geographic_view
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY metrics.cost_micros DESC
        """

        geo_data = []
        response = ga_service.search_stream(
            customer_id=self.customer_id, query=query
        )
        for batch in response:
            for row in batch.results:
                geo_data.append({
                    "country_criterion_id": row.geographic_view.country_criterion_id,
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name,
                    "spend": row.metrics.cost_micros / 1_000_000,
                    "revenue": row.metrics.conversions_value,
                    "conversions": int(row.metrics.conversions),
                    "clicks": int(row.metrics.clicks),
                })
        return geo_data

    async def update_campaign_budget(self, campaign_id: str, new_daily_budget: float) -> bool:
        return await asyncio.to_thread(self._update_campaign_budget_sync, campaign_id, new_daily_budget)

    def _update_campaign_budget_sync(
        self, campaign_id: str, new_daily_budget: float
    ) -> bool:
        try:
            client = self._get_client()
            campaign_service = client.get_service("CampaignService")
            campaign_budget_service = client.get_service("CampaignBudgetService")

            # Get the budget resource name first
            ga_service = client.get_service("GoogleAdsService")
            query = f"""
                SELECT campaign.campaign_budget
                FROM campaign
                WHERE campaign.id = {campaign_id}
            """
            response = list(ga_service.search(
                customer_id=self.customer_id, query=query
            ))
            if not response:
                return False

            budget_resource = response[0].campaign.campaign_budget
            budget_op = client.get_type("CampaignBudgetOperation")
            budget = budget_op.update
            budget.resource_name = budget_resource
            budget.amount_micros = int(new_daily_budget * 1_000_000)

            from google.protobuf import field_mask_pb2
            budget_op.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["amount_micros"])
            )

            campaign_budget_service.mutate_campaign_budgets(
                customer_id=self.customer_id,
                operations=[budget_op]
            )
            logger.info(f"Updated campaign {campaign_id} budget to ${new_daily_budget:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update budget for campaign {campaign_id}: {e}")
            return False

    async def pause_campaign(self, campaign_id: str) -> bool:
        return await asyncio.to_thread(self._pause_campaign_sync, campaign_id)

    def _pause_campaign_sync(self, campaign_id: str) -> bool:
        try:
            client = self._get_client()
            campaign_service = client.get_service("CampaignService")

            campaign_op = client.get_type("CampaignOperation")
            campaign = campaign_op.update
            campaign.resource_name = campaign_service.campaign_path(
                self.customer_id, campaign_id
            )
            campaign.status = client.enums.CampaignStatusEnum.PAUSED

            from google.protobuf import field_mask_pb2
            campaign_op.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["status"])
            )

            campaign_service.mutate_campaigns(
                customer_id=self.customer_id, operations=[campaign_op]
            )
            logger.info(f"Paused campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause campaign {campaign_id}: {e}")
            return False

    async def enable_campaign(self, campaign_id: str) -> bool:
        return await asyncio.to_thread(self._enable_campaign_sync, campaign_id)

    def _enable_campaign_sync(self, campaign_id: str) -> bool:
        try:
            client = self._get_client()
            campaign_service = client.get_service("CampaignService")

            campaign_op = client.get_type("CampaignOperation")
            campaign = campaign_op.update
            campaign.resource_name = campaign_service.campaign_path(
                self.customer_id, campaign_id
            )
            campaign.status = client.enums.CampaignStatusEnum.ENABLED

            from google.protobuf import field_mask_pb2
            campaign_op.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["status"])
            )

            campaign_service.mutate_campaigns(
                customer_id=self.customer_id, operations=[campaign_op]
            )
            logger.info(f"Enabled campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable campaign {campaign_id}: {e}")
            return False

    async def update_bid(self, adgroup_id: str, campaign_id: str, new_bid: float) -> bool:
        return await asyncio.to_thread(self._update_bid_sync, adgroup_id, campaign_id, new_bid)

    def _update_bid_sync(
        self, adgroup_id: str, campaign_id: str, new_bid: float
    ) -> bool:
        try:
            client = self._get_client()
            adgroup_service = client.get_service("AdGroupService")

            adgroup_op = client.get_type("AdGroupOperation")
            adgroup = adgroup_op.update
            adgroup.resource_name = adgroup_service.ad_group_path(
                self.customer_id, campaign_id, adgroup_id
            )
            adgroup.cpc_bid_micros = int(new_bid * 1_000_000)

            from google.protobuf import field_mask_pb2
            adgroup_op.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["cpc_bid_micros"])
            )

            adgroup_service.mutate_ad_groups(
                customer_id=self.customer_id, operations=[adgroup_op]
            )
            logger.info(f"Updated adgroup {adgroup_id} bid to ${new_bid:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update bid for adgroup {adgroup_id}: {e}")
            return False
