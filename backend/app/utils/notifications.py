"""
Notification utilities — Slack and email.
"""
import logging
import json
import urllib.request
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger("roas_engine.notifications")


async def send_slack_notification(snapshot) -> bool:
    """Send a performance summary to Slack via webhook."""
    if not settings.SLACK_WEBHOOK_URL:
        return False

    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 ROAS Engine — Daily Report",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Spend*\n${snapshot.total_spend:,.2f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Revenue*\n${snapshot.total_revenue:,.2f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Blended ROAS*\n{snapshot.blended_roas:.2f}x",
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Active Campaigns*\n"
                            f"{snapshot.num_active_campaigns}/{snapshot.num_campaigns}"
                        ),
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Actions Taken:* {snapshot.actions_applied}\n"
                        f"*Timestamp:* {snapshot.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
                    ),
                },
            },
        ]

        payload = json.dumps({"blocks": blocks}).encode("utf-8")
        req = urllib.request.Request(
            settings.SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")
        return False


async def send_alert(message: str, level: str = "warning") -> bool:
    """Send a text alert via Slack."""
    if not settings.SLACK_WEBHOOK_URL:
        return False

    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
    }
    emoji = emoji_map.get(level, "🔔")

    try:
        payload = json.dumps(
            {"text": f"{emoji} *ROAS Engine Alert:* {message}"}
        ).encode("utf-8")
        req = urllib.request.Request(
            settings.SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Slack alert failed: {e}")
        return False
