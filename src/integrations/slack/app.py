"""Slack app integration using Bolt framework."""

import structlog
from slack_bolt.async_app import AsyncApp

from src.config import settings
from src.models.recommendation import RecommendationBatch

logger = structlog.get_logger(__name__)

# Initialize Slack app
slack_app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)


async def request_approval(batch: RecommendationBatch) -> None:
    """Send approval request to Slack channel.

    Args:
        batch: Batch of recommendations to approve
    """
    logger.info(
        "sending_approval_request",
        run_id=str(batch.run_id),
        agent_type=batch.agent_type.value,
        count=batch.total_count,
    )

    try:
        # Build Slack blocks
        blocks = _build_approval_blocks(batch)

        # Send message
        response = await slack_app.client.chat_postMessage(
            channel=settings.slack_approval_channel_id,
            text=f"New recommendations from {batch.agent_type.value} agent",
            blocks=blocks,
        )

        # Store message timestamp for tracking
        batch.slack_message_ts = response["ts"]
        batch.slack_channel_id = response["channel"]

        logger.info("approval_request_sent", message_ts=response["ts"])

    except Exception as e:
        logger.error("approval_request_failed", error=str(e))
        raise


async def send_notification(
    channel: str,
    message: str,
    blocks: list[dict] | None = None,
) -> None:
    """Send notification message to Slack.

    Args:
        channel: Channel ID or name
        message: Text message
        blocks: Optional Block Kit blocks
    """
    try:
        await slack_app.client.chat_postMessage(
            channel=channel,
            text=message,
            blocks=blocks,
        )
        logger.info("notification_sent", channel=channel)

    except Exception as e:
        logger.error("notification_failed", error=str(e))
        raise


def _build_approval_blocks(batch: RecommendationBatch) -> list[dict]:
    """Build Slack Block Kit blocks for approval message.

    Args:
        batch: Recommendation batch

    Returns:
        List of Block Kit blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🤖 {batch.agent_type.value.replace('_', ' ').title()} Agent Recommendations",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:* {batch.summary}\n*Total Recommendations:* {batch.total_count}\n*Run ID:* `{batch.run_id}`",
            },
        },
        {"type": "divider"},
    ]

    # Add recommendation details (first 10 only to avoid message size limits)
    for i, rec in enumerate(batch.recommendations[:10]):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{i+1}. {rec.title}*\n{rec.description}\n_Risk: {rec.risk_level}_",
                },
            }
        )

    if batch.total_count > 10:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_...and {batch.total_count - 10} more recommendations_",
                },
            }
        )

    # Add action buttons
    blocks.extend(
        [
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve All"},
                        "style": "primary",
                        "value": str(batch.run_id),
                        "action_id": "approve_all",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject All"},
                        "style": "danger",
                        "value": str(batch.run_id),
                        "action_id": "reject_all",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⏰ Defer (24h)"},
                        "value": str(batch.run_id),
                        "action_id": "defer",
                    },
                ],
            },
        ]
    )

    return blocks
