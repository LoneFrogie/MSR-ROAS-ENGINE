"""
Google Search Console Connector
Fetches organic search performance data.
"""
import logging
import json
from datetime import date, timedelta
from typing import List, Dict, Optional

from app.models.schemas import SEOSiteHealth
from app.config.settings import settings

logger = logging.getLogger("roas_engine.gsc")


class GoogleSearchConsoleConnector:

    def __init__(self):
        self.site_url = settings.GSC_SITE_URL
        self.service = None

    def _get_service(self):
        if self.service:
            return self.service
        from googleapiclient.discovery import build

        # Prefer OAuth user credentials (refresh token) — works with Domain properties
        # without needing to add a service account as a user.
        if (settings.GSC_OAUTH_CLIENT_ID and settings.GSC_OAUTH_CLIENT_SECRET
                and settings.GSC_OAUTH_REFRESH_TOKEN):
            from google.oauth2.credentials import Credentials as OAuthCreds
            creds = OAuthCreds(
                token=None,
                refresh_token=settings.GSC_OAUTH_REFRESH_TOKEN,
                client_id=settings.GSC_OAUTH_CLIENT_ID,
                client_secret=settings.GSC_OAUTH_CLIENT_SECRET,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
        else:
            # Fallback: service account credentials (won't work with Domain properties
            # unless explicitly added as user — kept for backwards compatibility)
            from google.oauth2.service_account import Credentials
            creds_data = json.loads(settings.GSC_CREDENTIALS_JSON)
            creds = Credentials.from_service_account_info(
                creds_data,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )

        self.service = build("searchconsole", "v1", credentials=creds)
        return self.service

    async def get_search_analytics(
        self,
        start_date: date,
        end_date: date,
        dimensions: Optional[List[str]] = None,
        row_limit: int = 1000,
    ) -> List[Dict]:
        if dimensions is None:
            dimensions = ["query"]

        service = self._get_service()
        body = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "dataState": "all",
        }

        response = service.searchanalytics().query(
            siteUrl=self.site_url, body=body
        ).execute()

        rows = response.get("rows", [])
        results = []
        for row in rows:
            keys = row.get("keys", [])
            result = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            }
            for i, dim in enumerate(dimensions):
                if i < len(keys):
                    result[dim] = keys[i]
            results.append(result)
        return results

    async def get_top_queries(
        self, start_date: date, end_date: date, limit: int = 500
    ) -> List[Dict]:
        return await self.get_search_analytics(
            start_date, end_date,
            dimensions=["query"],
            row_limit=limit,
        )

    async def get_page_performance(
        self, start_date: date, end_date: date, limit: int = 500
    ) -> List[Dict]:
        return await self.get_search_analytics(
            start_date, end_date,
            dimensions=["page"],
            row_limit=limit,
        )

    async def get_query_page_matrix(
        self, start_date: date, end_date: date, limit: int = 2000
    ) -> List[Dict]:
        return await self.get_search_analytics(
            start_date, end_date,
            dimensions=["query", "page"],
            row_limit=limit,
        )

    async def get_site_health(
        self, start_date: date, end_date: date
    ) -> SEOSiteHealth:
        rows = await self.get_search_analytics(
            start_date, end_date,
            dimensions=["query"],
            row_limit=5000,
        )

        total_clicks = sum(r["clicks"] for r in rows)
        total_impressions = sum(r["impressions"] for r in rows)
        avg_position = (
            sum(r["position"] for r in rows) / len(rows) if rows else 0
        )
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0

        top_1_3 = [r for r in rows if r["position"] <= 3]
        top_4_10 = [r for r in rows if 4 <= r["position"] <= 10]
        top_11_20 = [r for r in rows if 11 <= r["position"] <= 20]

        return SEOSiteHealth(
            site_url=self.site_url,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            avg_position=avg_position,
            avg_ctr=avg_ctr,
            top_queries=[r["query"] for r in sorted(
                rows, key=lambda x: x["clicks"], reverse=True
            )[:20]],
            ranking_pages_top3=len(top_1_3),
            ranking_pages_top10=len(top_1_3) + len(top_4_10),
            ranking_pages_top20=len(top_1_3) + len(top_4_10) + len(top_11_20),
            date_range_start=start_date,
            date_range_end=end_date,
        )
