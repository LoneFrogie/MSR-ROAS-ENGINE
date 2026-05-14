"""
Meta Social Connector
Fetches Facebook Page + Instagram organic insights:
  - Page/Profile follower counts and growth
  - Post / Reel engagement metrics
  - Recent posts for AI scoring
"""
import asyncio
import logging
from typing import List, Dict, Optional, Any

import httpx

from app.config.settings import settings

logger = logging.getLogger("roas_engine.meta_social")

GRAPH_VERSION = "v22.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class MetaSocialConnector:

    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.page_id = settings.META_PAGE_ID
        self.ig_business_id = settings.META_INSTAGRAM_BUSINESS_ID
        self._page_token: Optional[str] = None

    async def _get_page_token(self) -> str:
        """Page insights require a Page Access Token. Derive it from the User token once."""
        if self._page_token:
            return self._page_token
        if not self.page_id:
            return self.access_token  # fall back to user token

        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(
                f"{GRAPH_BASE}/{self.page_id}",
                params={"fields": "access_token", "access_token": self.access_token},
            )
            r.raise_for_status()
            self._page_token = r.json().get("access_token") or self.access_token
            return self._page_token

    # ─── Page (Facebook) ────────────────────────────────────────────

    async def get_page_overview(self) -> Dict[str, Any]:
        """Followers + 28d reach/engagement via Graph API v22 metrics."""
        if not self.page_id:
            return {}
        from datetime import datetime, timedelta

        token = await self._get_page_token()
        end = datetime.utcnow().date()
        start = end - timedelta(days=28)

        async with httpx.AsyncClient(timeout=20.0) as c:
            # Basic page fields
            r = await c.get(
                f"{GRAPH_BASE}/{self.page_id}",
                params={
                    "fields": "name,fan_count,followers_count,about,link,category",
                    "access_token": token,
                },
            )
            r.raise_for_status()
            page = r.json()

            # v22 daily-page metrics (period=day with since/until)
            insights = {}
            metrics = (
                "page_impressions_unique,"
                "page_post_engagements,"
                "page_actions_post_reactions_total,"
                "page_video_views"
            )
            try:
                ri = await c.get(
                    f"{GRAPH_BASE}/{self.page_id}/insights",
                    params={
                        "metric": metrics,
                        "period": "day",
                        "since": start.isoformat(),
                        "until": end.isoformat(),
                        "access_token": token,
                    },
                )
                if ri.status_code != 200:
                    # Fallback to a smaller, safer metric set
                    ri = await c.get(
                        f"{GRAPH_BASE}/{self.page_id}/insights",
                        params={
                            "metric": "page_impressions_unique,page_post_engagements",
                            "period": "day",
                            "since": start.isoformat(),
                            "until": end.isoformat(),
                            "access_token": token,
                        },
                    )
                if ri.status_code == 200:
                    for m in ri.json().get("data", []):
                        name = m["name"]
                        total = 0
                        for value in m.get("values", []):
                            v = value.get("value", 0)
                            if isinstance(v, dict):
                                total += sum(int(x or 0) for x in v.values())
                            else:
                                total += int(v or 0)
                        insights[name] = total
            except Exception as e:
                logger.warning(f"FB page insights failed: {e}")

        return {
            "platform": "facebook",
            "page_id": self.page_id,
            "name": page.get("name"),
            "followers": page.get("followers_count", 0) or page.get("fan_count", 0),
            "fan_count": page.get("fan_count", 0),
            "category": page.get("category"),
            "url": page.get("link"),
            "impressions_28d": insights.get("page_impressions_unique", 0),
            "engagements_28d": insights.get("page_post_engagements", 0),
            "reactions_28d": insights.get("page_actions_post_reactions_total", 0),
            "video_views_28d": insights.get("page_video_views", 0),
        }

    # ─── Instagram ──────────────────────────────────────────────────

    async def get_instagram_overview(self) -> Dict[str, Any]:
        """
        Followers + 28d engagement aggregated from recent posts.
        IG Business is reached via the Page; needs Page Access Token.
        """
        if not self.ig_business_id:
            return {}
        from datetime import datetime, timedelta, timezone

        token = await self._get_page_token()
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(
                f"{GRAPH_BASE}/{self.ig_business_id}",
                params={
                    "fields": "username,name,followers_count,follows_count,media_count,profile_picture_url",
                    "access_token": token,
                },
            )
            r.raise_for_status()
            ig = r.json()

        # Aggregate engagement from posts in the last 28 days
        ig_posts = []
        try:
            ig_posts = await self.list_recent_instagram_posts(limit=50)
        except Exception as e:
            logger.warning(f"IG posts list failed: {e}")

        cutoff = datetime.now(timezone.utc) - timedelta(days=28)
        likes_28d = comments_28d = posts_28d = video_views_28d = 0
        for p in ig_posts:
            try:
                ts = datetime.fromisoformat((p.get("created_time") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff:
                continue
            posts_28d += 1
            likes_28d += p.get("likes", 0) or 0
            comments_28d += p.get("comments", 0) or 0
            video_views_28d += p.get("video_views", 0) or 0

        return {
            "platform": "instagram",
            "ig_id": self.ig_business_id,
            "username": ig.get("username"),
            "name": ig.get("name"),
            "followers": ig.get("followers_count", 0),
            "following": ig.get("follows_count", 0),
            "media_count": ig.get("media_count", 0),
            "profile_picture_url": ig.get("profile_picture_url"),
            "posts_28d": posts_28d,
            "likes_28d": likes_28d,
            "comments_28d": comments_28d,
            "engagement_28d": likes_28d + comments_28d,
            "video_views_28d": video_views_28d,
        }

    # ─── Recent Posts (for AI scoring) ──────────────────────────────

    async def get_post_metrics(self, platform: str, post_id: str) -> Dict[str, Any]:
        """
        Fetch fresh metrics for a single FB or IG post by ID.
        Returns dict with reach, impressions, views, likes, comments, shares, saves
        (whichever the platform exposes). Returns empty dict on failure.
        """
        if not post_id or not platform:
            return {}
        try:
            token = await self._get_page_token()
        except Exception as e:
            logger.warning(f"Page token unavailable for metric refresh: {e}")
            return {}

        async with httpx.AsyncClient(timeout=30.0) as c:
            if platform == "instagram":
                # 1) basic counts
                basic = {}
                try:
                    rr = await c.get(
                        f"{GRAPH_BASE}/{post_id}",
                        params={
                            "fields": "media_type,like_count,comments_count",
                            "access_token": token,
                        },
                    )
                    if rr.status_code == 200:
                        d = rr.json()
                        basic = {
                            "media_type": d.get("media_type"),
                            "likes": d.get("like_count", 0) or 0,
                            "comments": d.get("comments_count", 0) or 0,
                        }
                except Exception:
                    pass
                # 2) insights
                media_type = basic.get("media_type")
                metric = ("reach,saved,shares,total_interactions,views,likes,comments"
                          if media_type in ("VIDEO", "REELS")
                          else "reach,saved,shares,total_interactions,likes,comments")
                try:
                    rr = await c.get(
                        f"{GRAPH_BASE}/{post_id}/insights",
                        params={"metric": metric, "access_token": token},
                    )
                    if rr.status_code != 200:
                        return {
                            "likes": basic.get("likes", 0),
                            "comments": basic.get("comments", 0),
                        }
                    ins = {}
                    for item in rr.json().get("data", []) or []:
                        vals = item.get("values") or []
                        if vals:
                            ins[item.get("name")] = vals[0].get("value", 0)
                    reach = ins.get("reach", 0) or 0
                    likes = ins.get("likes") or basic.get("likes", 0)
                    comments = ins.get("comments") or basic.get("comments", 0)
                    saves = ins.get("saved", 0) or 0
                    shares = ins.get("shares", 0) or 0
                    views = ins.get("views", 0) or 0
                    total_inter = ins.get("total_interactions") or (likes + comments + saves + shares)
                    return {
                        "reach": reach,
                        "impressions": reach,  # IG only exposes reach on v22
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "saves": saves,
                        "engagements": total_inter,
                        "engagement_rate": (total_inter / reach) if reach else 0,
                    }
                except Exception as e:
                    logger.debug(f"IG insights {post_id} failed: {e}")
                    return {"likes": basic.get("likes", 0), "comments": basic.get("comments", 0)}

            elif platform == "facebook":
                # 1) summary counts + insights in one shot
                try:
                    rr = await c.get(
                        f"{GRAPH_BASE}/{post_id}",
                        params={
                            "fields": (
                                "reactions.summary(total_count).limit(0),"
                                "comments.summary(total_count).limit(0),"
                                "shares,"
                                "insights.metric(post_impressions_unique,post_clicks,post_video_views)"
                            ),
                            "access_token": token,
                        },
                    )
                    if rr.status_code != 200:
                        return {}
                    d = rr.json()
                    rxn = (d.get("reactions") or {}).get("summary", {}).get("total_count", 0) or 0
                    com = (d.get("comments") or {}).get("summary", {}).get("total_count", 0) or 0
                    shr = (d.get("shares") or {}).get("count", 0) or 0
                    ins = {}
                    for item in (d.get("insights") or {}).get("data", []) or []:
                        vals = item.get("values") or []
                        if vals:
                            ins[item.get("name")] = vals[0].get("value", 0)
                    # v22 valid: post_impressions_unique (=reach), post_clicks, post_video_views
                    reach = ins.get("post_impressions_unique", 0) or 0
                    clicks_real = ins.get("post_clicks", 0) or 0
                    views = ins.get("post_video_views", 0) or 0
                    engaged = rxn + com + shr + clicks_real
                    return {
                        "reach": reach,
                        "impressions": reach,  # FB v22 no longer exposes total impressions
                        "views": views,
                        "likes": rxn,
                        "comments": com,
                        "shares": shr,
                        "saves": 0,  # FB doesn't expose saves
                        "clicks": clicks_real,
                        "engagements": engaged,
                        "engagement_rate": (engaged / reach) if reach else 0,
                    }
                except Exception as e:
                    logger.debug(f"FB insights {post_id} failed: {e}")
                    return {}
        return {}

    async def list_recent_facebook_posts(self, limit: int = 25) -> List[Dict[str, Any]]:
        if not self.page_id:
            return []
        token = await self._get_page_token()
        posts = []
        async with httpx.AsyncClient(timeout=30.0) as c:
            # Try with insights subquery (gives reach, impressions, views).
            # Falls back to summary-only if insights perm is unavailable.
            r = await c.get(
                f"{GRAPH_BASE}/{self.page_id}/feed",
                params={
                    "fields": (
                        "id,message,created_time,permalink_url,"
                        "attachments{media_type,media,title,description},"
                        "reactions.summary(total_count).limit(0),"
                        "comments.summary(total_count).limit(0),"
                        "shares,"
                        "insights.metric(post_impressions_unique,post_clicks,post_video_views)"
                    ),
                    "limit": limit,
                    "access_token": token,
                },
            )
            if r.status_code != 200:
                # Strip insights and try again
                r = await c.get(
                    f"{GRAPH_BASE}/{self.page_id}/feed",
                    params={
                        "fields": (
                            "id,message,created_time,permalink_url,"
                            "attachments{media_type,media,title,description},"
                            "reactions.summary(total_count).limit(0),"
                            "comments.summary(total_count).limit(0),"
                            "shares"
                        ),
                        "limit": limit,
                        "access_token": token,
                    },
                )
            if r.status_code != 200:
                # Fall back to posts endpoint
                r = await c.get(
                    f"{GRAPH_BASE}/{self.page_id}/posts",
                    params={
                        "fields": "id,message,created_time,permalink_url,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares",
                        "limit": limit,
                        "access_token": token,
                    },
                )
            r.raise_for_status()
            for p in r.json().get("data", []):
                attachments = (p.get("attachments") or {}).get("data", []) or []
                first = attachments[0] if attachments else {}
                rxn = (p.get("reactions") or {}).get("summary", {}).get("total_count", 0)
                com = (p.get("comments") or {}).get("summary", {}).get("total_count", 0)
                shr = (p.get("shares") or {}).get("count", 0)
                engagements = (rxn or 0) + (com or 0) + (shr or 0)
                # Parse insights subquery (when available)
                ins = {}
                for item in (p.get("insights") or {}).get("data", []) or []:
                    name = item.get("name")
                    values = item.get("values") or []
                    if values:
                        ins[name] = values[0].get("value", 0)
                # FB v22 deprecated post_impressions + post_engaged_users; we use what's valid:
                reach = ins.get("post_impressions_unique", 0) or 0
                impressions = reach  # FB no longer exposes total impressions on posts
                clicks_real = ins.get("post_clicks", 0) or 0
                engaged_users = engagements + clicks_real
                video_views = ins.get("post_video_views", 0) or 0
                posts.append({
                    "platform": "facebook",
                    "id": p.get("id"),
                    "message": p.get("message", ""),
                    "created_time": p.get("created_time"),
                    "permalink_url": p.get("permalink_url"),
                    "media_type": first.get("media_type", "TEXT"),
                    "title": first.get("title"),
                    "description": first.get("description"),
                    "media_url": (first.get("media") or {}).get("source") or (first.get("media") or {}).get("image", {}).get("src"),
                    "likes": rxn,        # FB "reactions" is the equivalent of likes
                    "reactions": rxn,
                    "comments": com,
                    "shares": shr,
                    "engaged_users": engaged_users,
                    "impressions": impressions,
                    "reach": reach,
                    "video_views": video_views,
                    "clicks": 0,
                })
        return posts

    async def list_recent_instagram_posts(self, limit: int = 25) -> List[Dict[str, Any]]:
        if not self.ig_business_id:
            return []
        token = await self._get_page_token()  # IG Business reached via page token
        posts = []
        async with httpx.AsyncClient(timeout=30.0) as c:
            # First pass: basic media fields. Insights are fetched per-post below
            # because nested insights subquery on /media is unreliable on v22.
            r = await c.get(
                f"{GRAPH_BASE}/{self.ig_business_id}/media",
                params={
                    "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count",
                    "limit": limit,
                    "access_token": token,
                },
            )
            r.raise_for_status()
            media_list = r.json().get("data", [])

            # Fetch insights for each post concurrently
            async def _fetch_ins(media_id, media_type):
                # IG insights metric set depends on media_type
                if media_type in ("VIDEO", "REELS"):
                    metric = "reach,saved,shares,total_interactions,views,likes,comments"
                else:
                    metric = "reach,saved,shares,total_interactions,likes,comments"
                try:
                    rr = await c.get(
                        f"{GRAPH_BASE}/{media_id}/insights",
                        params={"metric": metric, "access_token": token},
                    )
                    if rr.status_code != 200:
                        return {}
                    out = {}
                    for item in rr.json().get("data", []) or []:
                        vals = item.get("values") or []
                        if vals:
                            out[item.get("name")] = vals[0].get("value", 0)
                    return out
                except Exception as e:
                    logger.debug(f"IG insights for {media_id} failed: {e}")
                    return {}

            import asyncio
            ins_results = await asyncio.gather(*[
                _fetch_ins(p.get("id"), p.get("media_type")) for p in media_list
            ])

            for p, ins in zip(media_list, ins_results):
                likes = ins.get("likes") or p.get("like_count", 0) or 0
                comments = ins.get("comments") or p.get("comments_count", 0) or 0
                reach = ins.get("reach") or 0
                saves = ins.get("saved") or 0
                shares = ins.get("shares") or 0
                video_views = ins.get("views") or 0
                total_inter = ins.get("total_interactions") or (likes + comments + saves + shares)
                posts.append({
                    "platform": "instagram",
                    "id": p.get("id"),
                    "message": p.get("caption", ""),
                    "created_time": p.get("timestamp"),
                    "permalink_url": p.get("permalink"),
                    "media_type": p.get("media_type"),  # IMAGE, VIDEO, REEL, CAROUSEL_ALBUM
                    "media_url": p.get("media_url"),
                    "thumbnail_url": p.get("thumbnail_url"),
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "saves": saves,
                    "engaged_users": total_inter,
                    "engagement": total_inter,
                    "impressions": reach,  # IG only exposes 'reach' on v22; use as impressions proxy
                    "reach": reach,
                    "video_views": video_views,
                })
        return posts
