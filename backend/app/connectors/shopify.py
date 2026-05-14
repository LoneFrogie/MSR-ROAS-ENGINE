"""
Shopify Admin API Connector
Fetches and updates SEO fields on products and pages.
Auth via OAuth client_credentials grant (auto-refresh on 401) or static token.
"""
import logging
from typing import List, Dict, Optional, Any

import httpx

from app.config.settings import settings

logger = logging.getLogger("roas_engine.shopify")

API_VERSION = "2024-10"


class ShopifyConnector:
    """
    Shopify Admin API client.
    Prefers OAuth client_credentials (auto-refreshing tokens) when client_id/secret set,
    falls back to static SHOPIFY_ACCESS_TOKEN otherwise.
    """

    def __init__(
        self,
        shop_domain: Optional[str] = None,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.shop_domain = shop_domain or settings.SHOPIFY_SHOP_DOMAIN or settings.SHOPIFY_STORE_URL
        self.access_token = access_token or settings.SHOPIFY_ACCESS_TOKEN or settings.SHOPIFY_ADMIN_API_TOKEN
        self.client_id = client_id or settings.SHOPIFY_CLIENT_ID
        self.client_secret = client_secret or settings.SHOPIFY_CLIENT_SECRET
        self._token_refreshed_once = False

        if not self.shop_domain:
            raise ValueError("SHOPIFY_SHOP_DOMAIN (or SHOPIFY_STORE_URL) is required")
        if not self.access_token and not (self.client_id and self.client_secret):
            raise ValueError("Provide SHOPIFY_ACCESS_TOKEN OR SHOPIFY_CLIENT_ID+SHOPIFY_CLIENT_SECRET")

        self.base_url = f"https://{self.shop_domain}/admin/api/{API_VERSION}"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def _refresh_token(self) -> bool:
        """Refresh access_token via client_credentials grant. Returns True on success."""
        if not (self.client_id and self.client_secret):
            return False
        url = f"https://{self.shop_domain}/admin/oauth/access_token"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.post(url, json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                })
                r.raise_for_status()
                token = r.json().get("access_token")
                if token:
                    self.access_token = token
                    logger.info("Shopify token refreshed")
                    return True
            except Exception as e:
                logger.error(f"Shopify token refresh failed: {e}")
        return False

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make a request, refreshing token once on 401."""
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.request(method, url, headers=self.headers, **kwargs)
            if r.status_code == 401 and not self._token_refreshed_once:
                self._token_refreshed_once = True
                if await self._refresh_token():
                    r = await client.request(method, url, headers=self.headers, **kwargs)
            r.raise_for_status()
            return r

    # ─── Products ─────────────────────────────────────────────────

    async def list_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        r = await self._request(
            "GET", "/products.json",
            params={"limit": limit, "fields": "id,title,handle,body_html,vendor,product_type,tags"},
        )
        return r.json().get("products", [])

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        r = await self._request("GET", f"/products/{product_id}.json")
        return r.json().get("product", {})

    async def update_product_seo(
        self,
        product_id: int,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
        body_html: Optional[str] = None,
    ) -> Dict[str, Any]:
        results = []
        if seo_title is not None:
            await self._request(
                "POST", f"/products/{product_id}/metafields.json",
                json={"metafield": {
                    "namespace": "global", "key": "title_tag",
                    "value": seo_title, "type": "single_line_text_field",
                }},
            )
            results.append({"field": "seo_title", "status": "updated"})

        if seo_description is not None:
            await self._request(
                "POST", f"/products/{product_id}/metafields.json",
                json={"metafield": {
                    "namespace": "global", "key": "description_tag",
                    "value": seo_description, "type": "multi_line_text_field",
                }},
            )
            results.append({"field": "seo_description", "status": "updated"})

        if body_html is not None:
            await self._request(
                "PUT", f"/products/{product_id}.json",
                json={"product": {"id": product_id, "body_html": body_html}},
            )
            results.append({"field": "body_html", "status": "updated"})

        logger.info(f"Updated product {product_id}: {results}")
        return {"product_id": product_id, "updates": results}

    # ─── Pages ────────────────────────────────────────────────────

    async def list_pages(self, limit: int = 50) -> List[Dict[str, Any]]:
        r = await self._request("GET", "/pages.json", params={"limit": limit})
        return r.json().get("pages", [])

    async def update_page_seo(
        self,
        page_id: int,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
        body_html: Optional[str] = None,
    ) -> Dict[str, Any]:
        results = []
        if seo_title is not None:
            await self._request(
                "POST", f"/pages/{page_id}/metafields.json",
                json={"metafield": {
                    "namespace": "global", "key": "title_tag",
                    "value": seo_title, "type": "single_line_text_field",
                }},
            )
            results.append({"field": "seo_title", "status": "updated"})

        if seo_description is not None:
            await self._request(
                "POST", f"/pages/{page_id}/metafields.json",
                json={"metafield": {
                    "namespace": "global", "key": "description_tag",
                    "value": seo_description, "type": "multi_line_text_field",
                }},
            )
            results.append({"field": "seo_description", "status": "updated"})

        if body_html is not None:
            await self._request(
                "PUT", f"/pages/{page_id}.json",
                json={"page": {"id": page_id, "body_html": body_html}},
            )
            results.append({"field": "body_html", "status": "updated"})

        logger.info(f"Updated page {page_id}: {results}")
        return {"page_id": page_id, "updates": results}

    # ─── Shop-level (homepage) ────────────────────────────────────

    async def get_shop(self) -> Dict[str, Any]:
        r = await self._request("GET", "/shop.json")
        return r.json().get("shop", {})

    async def update_shop_seo(
        self,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update homepage SEO via shop-level metafields under namespace `global`:
          - title_tag       → homepage <title>
          - description_tag → homepage meta description
        """
        results = []
        if seo_title is not None:
            await self._request(
                "POST", "/metafields.json",
                json={"metafield": {
                    "namespace": "global",
                    "key": "title_tag",
                    "value": seo_title,
                    "type": "single_line_text_field",
                    "owner_resource": "shop",
                }},
            )
            results.append({"field": "seo_title", "status": "updated"})

        if seo_description is not None:
            await self._request(
                "POST", "/metafields.json",
                json={"metafield": {
                    "namespace": "global",
                    "key": "description_tag",
                    "value": seo_description,
                    "type": "multi_line_text_field",
                    "owner_resource": "shop",
                }},
            )
            results.append({"field": "seo_description", "status": "updated"})

        logger.info(f"Updated shop-level SEO: {results}")
        return {"resource": "shop", "updates": results}

    # ─── Resolver ─────────────────────────────────────────────────

    async def find_resource_by_url(self, page_url: str) -> Optional[Dict[str, Any]]:
        """
        Given a public URL, return:
          {'type': 'shop'|'product'|'page', 'id': any, 'data': {...}}

        Uses Shopify's `handle` query filter instead of paging — works for stores
        of any size.
        """
        from urllib.parse import urlparse
        path = urlparse(page_url).path.strip("/")

        # Homepage → shop-level resource
        if path == "" or path == "/":
            try:
                shop = await self.get_shop()
                return {"type": "shop", "id": shop.get("id"), "data": shop}
            except Exception as e:
                logger.warning(f"Could not fetch shop info: {e}")
                return None

        parts = path.split("/")

        # Product
        if len(parts) >= 2 and parts[0] == "products":
            handle = parts[1]
            try:
                r = await self._request("GET", "/products.json", params={"handle": handle, "limit": 1})
                products = r.json().get("products", [])
                if products:
                    p = products[0]
                    return {"type": "product", "id": p["id"], "data": p}
            except Exception as e:
                logger.warning(f"Product lookup failed for {handle}: {e}")

        # Page
        if len(parts) >= 2 and parts[0] == "pages":
            handle = parts[1]
            try:
                r = await self._request("GET", "/pages.json", params={"handle": handle, "limit": 1})
                pages = r.json().get("pages", [])
                if pages:
                    p = pages[0]
                    return {"type": "page", "id": p["id"], "data": p}
            except Exception as e:
                logger.warning(f"Page lookup failed for {handle}: {e}")

        return None
