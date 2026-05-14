"""
SEO Analyzer
Cross-references organic search data with paid keywords to find opportunities.
Generates autonomous actions: bid reductions, keyword pauses, content briefs.
"""
import logging
from typing import List, Dict, Optional
from datetime import date, datetime, timedelta

from app.models.schemas import (
    OptimizationAction, ActionType, DecisionConfidence, Platform
)
from app.config.settings import settings

logger = logging.getLogger("roas_engine.seo_analyzer")


class SEOAnalyzer:

    def __init__(self):
        self.brand_domain = settings.BRAND_DOMAIN
        self.target_roas = settings.TARGET_ROAS
        self.organic_bid_reduce_pct = 0.40  # reduce bid 40% when organic ranks top 3
        self.organic_pause_position = 1.5   # pause paid if organic #1-1.5
        self.content_gap_min_spend = 50.0   # min paid spend to flag as content gap

    def find_keyword_opportunities(
        self,
        organic_queries: List[Dict],
        paid_search_terms: List[Dict],
    ) -> List[Dict]:
        """
        Find paid keywords where we rank organically in top 3 — candidates to
        reduce CPC bid since organic traffic is already captured.
        """
        # Build a dict: query -> organic position
        organic_map = {}
        for row in organic_queries:
            query = row.get("query", "").lower().strip()
            pos = row.get("position", 100)
            if query and pos < organic_map.get(query, 999):
                organic_map[query] = pos

        opportunities = []
        for term in paid_search_terms:
            search_term = term.get("search_term", "").lower().strip()
            organic_pos = organic_map.get(search_term)
            if organic_pos and organic_pos <= 3:
                roas = term["revenue"] / term["spend"] if term.get("spend", 0) > 0 else 0
                opportunities.append({
                    "search_term": search_term,
                    "organic_position": organic_pos,
                    "paid_spend": term.get("spend", 0),
                    "paid_revenue": term.get("revenue", 0),
                    "paid_roas": roas,
                    "recommendation": "reduce_bid" if roas < self.target_roas else "monitor",
                    "reason": (
                        f"Organic rank #{organic_pos:.0f} — paid spend may be redundant"
                    ),
                })
        opportunities.sort(key=lambda x: x["paid_spend"], reverse=True)
        return opportunities

    def find_content_gaps(
        self,
        organic_queries: List[Dict],
        paid_search_terms: List[Dict],
        min_paid_spend: float = 50.0,
    ) -> List[Dict]:
        """
        Find paid keywords that have no organic ranking — content creation
        opportunities to reduce long-term paid dependency.
        """
        organic_set = {
            row.get("query", "").lower().strip()
            for row in organic_queries
        }

        gaps = []
        for term in paid_search_terms:
            search_term = term.get("search_term", "").lower().strip()
            spend = term.get("spend", 0)
            if spend < min_paid_spend:
                continue
            if search_term not in organic_set:
                roas = term["revenue"] / spend if spend > 0 else 0
                gaps.append({
                    "search_term": search_term,
                    "paid_spend": spend,
                    "paid_revenue": term.get("revenue", 0),
                    "paid_roas": roas,
                    "recommendation": "create_content",
                    "reason": "No organic ranking — create targeted content page",
                })
        gaps.sort(key=lambda x: x["paid_spend"], reverse=True)
        return gaps[:50]

    def detect_keyword_cannibalization(
        self, query_page_matrix: List[Dict], min_impressions: int = 100
    ) -> List[Dict]:
        """
        Find queries where multiple pages compete, diluting relevance signals.
        """
        # Group by query
        query_to_pages: Dict[str, List[Dict]] = {}
        for row in query_page_matrix:
            query = row.get("query", "").lower().strip()
            if row.get("impressions", 0) < min_impressions:
                continue
            if query not in query_to_pages:
                query_to_pages[query] = []
            query_to_pages[query].append(row)

        cannibalization = []
        for query, pages in query_to_pages.items():
            if len(pages) < 2:
                continue
            pages.sort(key=lambda x: x.get("clicks", 0), reverse=True)
            cannibalization.append({
                "query": query,
                "competing_pages": [p.get("page", "") for p in pages],
                "primary_page": pages[0].get("page", ""),
                "total_impressions": sum(p.get("impressions", 0) for p in pages),
                "total_clicks": sum(p.get("clicks", 0) for p in pages),
                "recommendation": "consolidate_content",
                "reason": f"{len(pages)} pages competing for same query",
            })
        cannibalization.sort(
            key=lambda x: x["total_impressions"], reverse=True
        )
        return cannibalization[:30]

    def find_quick_wins(
        self,
        organic_queries: List[Dict],
        min_impressions: int = 500,
        position_range: tuple = (4, 20),
    ) -> List[Dict]:
        """
        Find queries ranking #4-20 with high impressions — small SEO improvements
        could push them to page 1 and reduce paid dependency.
        """
        quick_wins = []
        for row in organic_queries:
            pos = row.get("position", 0)
            impressions = row.get("impressions", 0)
            if (
                position_range[0] <= pos <= position_range[1]
                and impressions >= min_impressions
            ):
                ctr_potential = 0.15 if pos <= 5 else 0.05
                click_potential = int(impressions * ctr_potential)
                current_clicks = row.get("clicks", 0)
                lift = click_potential - current_clicks

                quick_wins.append({
                    "query": row.get("query", ""),
                    "current_position": pos,
                    "impressions": impressions,
                    "current_clicks": current_clicks,
                    "estimated_click_lift": max(0, lift),
                    "recommendation": "optimize_content",
                    "reason": (
                        f"Position {pos:.1f} — optimize title/meta for top-3 potential"
                    ),
                })
        quick_wins.sort(
            key=lambda x: x["estimated_click_lift"], reverse=True
        )
        return quick_wins[:50]

    # ─── Autonomous Action Generation ────────────────────────────────

    def generate_seo_actions(
        self,
        organic_queries: List[Dict],
        paid_search_terms: List[Dict],
        query_page_matrix: List[Dict],
    ) -> List[OptimizationAction]:
        """
        Master method: generates executable OptimizationActions from all
        SEO analysis modules. These flow through the decision engine just
        like ROAS optimizer actions.
        """
        actions = []
        actions.extend(self._generate_bid_reduction_actions(organic_queries, paid_search_terms))
        actions.extend(self._generate_cannibalization_actions(query_page_matrix))
        actions.extend(self._generate_content_gap_actions(organic_queries, paid_search_terms))
        actions.extend(self._generate_quick_win_actions(organic_queries))
        return actions

    def _generate_bid_reduction_actions(
        self,
        organic_queries: List[Dict],
        paid_search_terms: List[Dict],
    ) -> List[OptimizationAction]:
        """
        Auto-reduce bids or pause paid keywords where organic already ranks top 3.
        - Organic #1-1.5 → pause the paid keyword entirely (organic dominates)
        - Organic #2-3   → reduce bid by 40% (still keep paid as safety net)
        """
        organic_map = {}
        for row in organic_queries:
            query = row.get("query", "").lower().strip()
            pos = row.get("position", 100)
            if query and pos < organic_map.get(query, {}).get("position", 999):
                organic_map[query] = {
                    "position": pos,
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "page": row.get("page", ""),
                }

        actions = []
        for term in paid_search_terms:
            search_term = term.get("search_term", "").lower().strip()
            organic = organic_map.get(search_term)
            if not organic or organic["position"] > 3:
                continue

            paid_spend = term.get("spend", 0)
            paid_revenue = term.get("revenue", 0)
            paid_roas = paid_revenue / paid_spend if paid_spend > 0 else 0
            campaign = term.get("campaign", "Unknown")

            if organic["position"] <= self.organic_pause_position:
                # Organic dominates — pause the paid keyword
                confidence = min(0.95, 0.80 + (organic["clicks"] / 1000) * 0.15)
                actions.append(OptimizationAction(
                    platform=Platform.GOOGLE_ADS,
                    campaign_id=campaign,
                    action_type=ActionType.PAUSE_KEYWORD,
                    old_value=paid_spend,
                    new_value=0.0,
                    confidence=confidence,
                    confidence_level=DecisionConfidence.HIGH if confidence >= 0.85 else DecisionConfidence.MEDIUM,
                    reason=(
                        f"SEO Auto-Pause: '{search_term}' ranks #{organic['position']:.1f} organically "
                        f"({organic['clicks']} clicks/period). Paid spend ${paid_spend:.0f} is redundant. "
                        f"Estimated savings: ${paid_spend:.0f}/period."
                    ),
                    details={
                        "type": "seo_bid_reduction",
                        "search_term": search_term,
                        "organic_position": organic["position"],
                        "organic_clicks": organic["clicks"],
                        "organic_page": organic["page"],
                        "paid_spend": paid_spend,
                        "paid_revenue": paid_revenue,
                        "paid_roas": paid_roas,
                        "estimated_savings": paid_spend,
                    },
                ))
            else:
                # Organic top 3 but not dominant — reduce bid by 40%
                reduced_spend = paid_spend * (1 - self.organic_bid_reduce_pct)
                confidence = min(0.90, 0.70 + (organic["clicks"] / 1000) * 0.20)
                actions.append(OptimizationAction(
                    platform=Platform.GOOGLE_ADS,
                    campaign_id=campaign,
                    action_type=ActionType.DECREASE_BID,
                    old_value=paid_spend,
                    new_value=round(reduced_spend, 2),
                    confidence=confidence,
                    confidence_level=DecisionConfidence.MEDIUM,
                    reason=(
                        f"SEO Bid Reduce: '{search_term}' ranks #{organic['position']:.1f} organically. "
                        f"Reducing paid bid {self.organic_bid_reduce_pct*100:.0f}% "
                        f"(${paid_spend:.0f} → ${reduced_spend:.0f}). "
                        f"Organic captures {organic['clicks']} clicks already."
                    ),
                    details={
                        "type": "seo_bid_reduction",
                        "search_term": search_term,
                        "organic_position": organic["position"],
                        "organic_clicks": organic["clicks"],
                        "organic_page": organic["page"],
                        "paid_spend": paid_spend,
                        "paid_revenue": paid_revenue,
                        "paid_roas": paid_roas,
                        "estimated_savings": paid_spend - reduced_spend,
                    },
                ))

        actions.sort(key=lambda a: a.details.get("paid_spend", 0), reverse=True)
        return actions

    def _generate_cannibalization_actions(
        self, query_page_matrix: List[Dict], min_impressions: int = 100
    ) -> List[OptimizationAction]:
        """
        Flag keyword cannibalization as SEO_FIX actions with consolidation instructions.
        """
        cannibalization = self.detect_keyword_cannibalization(query_page_matrix, min_impressions)
        actions = []

        for item in cannibalization:
            query = item["query"]
            pages = item["competing_pages"]
            primary = item["primary_page"]
            total_imp = item["total_impressions"]

            # Higher confidence for more severe cannibalization
            confidence = min(0.90, 0.65 + len(pages) * 0.10 + (total_imp / 20000) * 0.15)

            actions.append(OptimizationAction(
                platform=Platform.SEO,
                action_type=ActionType.SEO_FIX,
                old_value=len(pages),
                new_value=1,
                confidence=confidence,
                confidence_level=DecisionConfidence.MEDIUM,
                reason=(
                    f"Cannibalization: '{query}' has {len(pages)} competing pages "
                    f"({total_imp:,} impressions). Consolidate to {primary}. "
                    f"Add canonical tags on secondary pages."
                ),
                details={
                    "type": "cannibalization_fix",
                    "query": query,
                    "primary_page": primary,
                    "secondary_pages": [p for p in pages if p != primary],
                    "total_impressions": total_imp,
                    "total_clicks": item["total_clicks"],
                    "fix_steps": [
                        f"1. Set canonical on secondary pages pointing to {primary}",
                        f"2. Add internal links from secondary → primary",
                        f"3. Differentiate secondary page intent or merge content",
                        f"4. Monitor rankings for 2-4 weeks post-fix",
                    ],
                },
            ))
        return actions

    def _generate_content_gap_actions(
        self,
        organic_queries: List[Dict],
        paid_search_terms: List[Dict],
    ) -> List[OptimizationAction]:
        """
        Generate content creation actions for keywords with paid spend but no organic presence.
        """
        gaps = self.find_content_gaps(organic_queries, paid_search_terms, self.content_gap_min_spend)
        actions = []

        for gap in gaps:
            search_term = gap["search_term"]
            paid_spend = gap["paid_spend"]
            paid_revenue = gap["paid_revenue"]
            paid_roas = gap["paid_roas"]

            # Higher confidence for higher-spend gaps
            confidence = min(0.85, 0.55 + (paid_spend / 500) * 0.30)

            # Estimate annual savings if content captures 50% of paid traffic
            annual_savings_est = paid_spend * 26 * 0.50  # 26 bi-weekly periods, 50% capture

            actions.append(OptimizationAction(
                platform=Platform.SEO,
                action_type=ActionType.SEO_FIX,
                old_value=0,  # zero organic presence
                new_value=paid_spend,  # target: replace this paid spend
                confidence=confidence,
                confidence_level=DecisionConfidence.MEDIUM if confidence >= 0.65 else DecisionConfidence.LOW,
                reason=(
                    f"Content Gap: '{search_term}' — spending ${paid_spend:.0f}/period with zero organic ranking. "
                    f"Create targeted content page. Estimated annual savings: ${annual_savings_est:,.0f}."
                ),
                details={
                    "type": "content_gap",
                    "search_term": search_term,
                    "paid_spend": paid_spend,
                    "paid_revenue": paid_revenue,
                    "paid_roas": paid_roas,
                    "estimated_annual_savings": annual_savings_est,
                    "content_brief": {
                        "target_keyword": search_term,
                        "intent": "commercial" if paid_roas > 2 else "informational",
                        "suggested_format": "product_page" if paid_roas > 3 else "blog_guide",
                        "target_word_count": 1500 if paid_roas > 3 else 2000,
                        "priority": "high" if paid_spend > 100 else "medium",
                    },
                },
            ))
        return actions

    def _generate_quick_win_actions(
        self, organic_queries: List[Dict]
    ) -> List[OptimizationAction]:
        """
        Generate optimization actions for keywords ranking #4-20 with high potential.
        """
        quick_wins = self.find_quick_wins(organic_queries)
        actions = []

        for win in quick_wins:
            query = win["query"]
            position = win["current_position"]
            impressions = win["impressions"]
            click_lift = win["estimated_click_lift"]

            if click_lift <= 0:
                continue

            confidence = min(0.80, 0.50 + (click_lift / 500) * 0.30)

            actions.append(OptimizationAction(
                platform=Platform.SEO,
                action_type=ActionType.SEO_FIX,
                old_value=position,
                new_value=3.0,  # target: top 3
                confidence=confidence,
                confidence_level=DecisionConfidence.MEDIUM if confidence >= 0.65 else DecisionConfidence.LOW,
                reason=(
                    f"Quick Win: '{query}' at position {position:.1f} with {impressions:,} impressions. "
                    f"Optimize title/meta/content for +{click_lift} estimated clicks."
                ),
                details={
                    "type": "quick_win",
                    "query": query,
                    "current_position": position,
                    "target_position": 3.0,
                    "impressions": impressions,
                    "current_clicks": win["current_clicks"],
                    "estimated_click_lift": click_lift,
                    "optimization_steps": [
                        f"1. Update page title to include '{query}' prominently",
                        f"2. Optimize meta description with compelling CTA",
                        f"3. Add 2-3 internal links from high-authority pages",
                        f"4. Expand content depth — aim for 1500+ words",
                        f"5. Add FAQ schema markup for featured snippet potential",
                    ],
                },
            ))
        return actions
