"""
AI SEO Suggester (Gemini)
Generates concrete SEO fix content from page audit findings.
"""
import json
import logging
from typing import Dict, List, Optional, Any

import google.generativeai as genai

from app.config.settings import settings

logger = logging.getLogger("roas_engine.seo.ai_suggester")

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are an expert SEO copywriter and technical SEO specialist for e-commerce stores.
You analyze page audit data and generate concrete SEO improvements, including JSON-LD schema markup.

Rules:
- SEO title: 50-60 characters, includes primary keyword, brand at the end if room
- Meta description: 140-160 characters, action-oriented, includes a benefit
- H1: Clear, keyword-rich, distinct from the title
- Alt text: Descriptive, under 125 characters, no "image of" / "picture of"
- JSON-LD schema: ONLY produce when the page is missing structured data. Pick the most
  relevant schema type for the URL: Product (for /products/...), CollectionPage (for
  /collections/...), WebPage (for /pages/...), Organization or WebSite (for homepage).
  Include @context, @type, name, description, url. For products include offers + image
  if known. NEVER invent prices, ratings, or stock status — leave those fields out
  if not provided in the audit.
- All output must be in English unless the page content is in another language
- Match the brand tone seen in current content
- Never invent facts about the product — work only with what's in the audit

Return STRICT JSON matching the requested schema. No markdown, no commentary."""


def _configure():
    """Configure Gemini API. Idempotent."""
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    else:
        # On Cloud Run, will use ADC for Vertex AI fallback
        logger.warning("GEMINI_API_KEY not set; SEO suggestions will fail")


def _build_prompt(audit: Dict[str, Any], current_content: Optional[Dict[str, Any]] = None) -> str:
    """
    Build the user prompt from a page audit + optional current content.
    audit: page audit dict (url, score, issues, current title/desc/h1/etc)
    current_content: optional fuller content (body_html, product_type, etc.)
    """
    issues = audit.get("issues", [])
    current = {
        "url": audit.get("url"),
        "current_title": audit.get("title"),
        "current_meta_description": audit.get("meta_description"),
        "current_h1": (audit.get("h1_tags") or [None])[0] if audit.get("h1_tags") else None,
        "title_length": audit.get("title_length"),
        "meta_description_length": audit.get("meta_description_length"),
        "word_count": audit.get("word_count"),
        "images_total": audit.get("images_total"),
        "images_missing_alt": audit.get("images_missing_alt"),
        "issues": issues,
    }

    if current_content:
        current["product_title"] = current_content.get("title")
        current["product_type"] = current_content.get("product_type")
        current["vendor"] = current_content.get("vendor")
        current["body_excerpt"] = (current_content.get("body_html") or "")[:1500]

    schema = {
        "seo_title": "string (50-60 chars) or null if no fix needed",
        "meta_description": "string (140-160 chars) or null",
        "h1": "string or null",
        "schema_jsonld": (
            "JSON-LD object as a JSON value (not stringified) — provide ONLY if the "
            "page audit shows has_structured_data is false. Otherwise null."
        ),
        "alt_text_suggestions": [
            {"image_index": "int", "alt_text": "string"}
        ],
        "rationale": "1-2 sentence explanation of the changes",
    }

    return f"""Analyze this page audit and generate SEO fixes.

PAGE AUDIT:
{json.dumps(current, indent=2, default=str)}

OUTPUT SCHEMA (return JSON matching exactly):
{json.dumps(schema, indent=2)}

Generate fixes ONLY for fields that need improvement. Use null for fields that are already good.
"""


async def suggest_fixes(
    audit: Dict[str, Any],
    current_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate SEO fix suggestions for a page audit.
    Returns a dict with suggested fields + rationale.
    """
    _configure()
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    prompt = _build_prompt(audit, current_content)

    try:
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.4,
            },
        )
        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        result = json.loads(text)
        result["url"] = audit.get("url")
        result["model"] = MODEL_NAME
        return result
    except Exception as e:
        logger.error(f"Gemini suggestion failed for {audit.get('url')}: {e}")
        return {"error": str(e), "url": audit.get("url")}


async def suggest_for_pages(
    audits: List[Dict[str, Any]],
    max_pages: int = 10,
    shopify_connector=None,
) -> List[Dict[str, Any]]:
    """
    Generate suggestions for the worst-scoring pages (up to max_pages).
    Optionally enriches each page with Shopify product/page data.
    """
    # Sort by score asc — worst first
    sorted_audits = sorted(audits, key=lambda a: a.get("score", 100))[:max_pages]

    suggestions = []
    for audit in sorted_audits:
        current_content = None
        if shopify_connector and audit.get("url"):
            try:
                resource = await shopify_connector.find_resource_by_url(audit["url"])
                if resource:
                    current_content = resource["data"]
                    audit["_shopify"] = {
                        "type": resource["type"],
                        "id": resource["id"],
                    }
            except Exception as e:
                logger.warning(f"Shopify lookup failed for {audit['url']}: {e}")

        suggestion = await suggest_fixes(audit, current_content)
        # Pass through the shopify resource info so the executor can apply
        if "_shopify" in audit:
            suggestion["shopify_resource"] = audit["_shopify"]
        suggestions.append(suggestion)

    return suggestions
