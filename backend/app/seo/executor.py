"""
SEO Fix Executor
Pushes approved SEO fixes to the underlying CMS (Shopify).
"""
import logging
from typing import Dict, Any

from app.connectors.shopify import ShopifyConnector
from app.models.schemas import OptimizationAction

logger = logging.getLogger("roas_engine.seo.executor")


async def execute_seo_fix(action: OptimizationAction) -> Dict[str, Any]:
    """
    Apply an approved SEO_FIX action to Shopify.

    Expected action.details structure:
    {
        "shopify_resource": {"type": "product"|"page", "id": int},
        "fixes": {
            "seo_title": "...",          # optional
            "meta_description": "...",   # optional
            "h1": "...",                 # optional (will be merged into body_html)
            "body_html": "..."           # optional (full body replacement)
        }
    }
    """
    details = action.details or {}
    resource = details.get("shopify_resource")
    fixes = details.get("fixes") or {}

    if not resource or not resource.get("id"):
        raise ValueError("Action is missing shopify_resource.id")

    shopify = ShopifyConnector()
    resource_type = resource.get("type")
    resource_id = int(resource["id"])

    seo_title = fixes.get("seo_title")
    meta_description = fixes.get("meta_description")
    body_html = fixes.get("body_html")
    schema_jsonld = fixes.get("schema_jsonld")

    # If schema is approved, embed it as a <script type="application/ld+json"> block
    # appended to the body_html (or current product/page body).
    if schema_jsonld and resource_type in ("product", "page"):
        try:
            existing_body = ""
            if resource_type == "product":
                prod = await shopify.get_product(resource_id)
                existing_body = prod.get("body_html") or ""
            elif resource_type == "page":
                # Fetch existing page body
                r = await shopify._request("GET", f"/pages/{resource_id}.json")
                existing_body = r.json().get("page", {}).get("body_html") or ""

            # Strip any previous ROAS-injected schema block to avoid duplicates
            import re as _re
            existing_body = _re.sub(
                r'<script type="application/ld\+json" data-roas-engine="1">.*?</script>',
                '', existing_body, flags=_re.DOTALL,
            )
            schema_block = (
                f'\n<script type="application/ld+json" data-roas-engine="1">\n'
                f'{schema_jsonld}\n</script>\n'
            )
            body_html = (body_html or existing_body) + schema_block
        except Exception as e:
            logger.warning(f"Failed to merge schema into body: {e}")

    if resource_type == "shop":
        # Homepage SEO via shop-level metafields.
        # IMPORTANT: Shopify does NOT expose homepage H1 / body content as a metafield —
        # those live in the theme template. We can ONLY auto-apply title + meta description here.
        applied = []
        skipped = []

        if seo_title is not None or meta_description is not None:
            result = await shopify.update_shop_seo(
                seo_title=seo_title,
                seo_description=meta_description,
            )
            for u in result.get("updates", []):
                applied.append(u["field"])
        else:
            result = {"resource": "shop", "updates": []}

        h1_value = fixes.get("h1")
        if h1_value:
            skipped.append(f"h1 (homepage H1 must be edited in your theme)")
        if body_html:
            skipped.append("body_html (homepage body must be edited in your theme)")

        if applied and not skipped:
            msg = f"Applied to Shopify homepage: {', '.join(applied)}"
        elif applied and skipped:
            msg = f"Applied to Shopify homepage: {', '.join(applied)}. Manual: {', '.join(skipped)}"
        else:
            msg = (
                f"Manual apply required: {', '.join(skipped)}. "
                "Edit in Shopify Admin → Online Store → Themes → Customize."
            )
        return {"message": msg, "shopify_response": result}

    if resource_type == "product":
        result = await shopify.update_product_seo(
            product_id=resource_id,
            seo_title=seo_title,
            seo_description=meta_description,
            body_html=body_html,
        )
    elif resource_type == "page":
        result = await shopify.update_page_seo(
            page_id=resource_id,
            seo_title=seo_title,
            seo_description=meta_description,
            body_html=body_html,
        )
    else:
        raise ValueError(f"Unsupported Shopify resource type: {resource_type}")

    fields_updated = ", ".join(u["field"] for u in result.get("updates", []))
    return {
        "message": f"Applied to Shopify {resource_type} {resource_id}: {fields_updated}",
        "shopify_response": result,
    }
