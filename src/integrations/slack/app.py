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


# ============================================================================
# Button Action Handlers
# ============================================================================


@slack_app.action("approve_all")
async def handle_approve_all(ack, body, client):
    """Handle approve all button click."""
    await ack()

    run_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    logger.info("approval_received", run_id=run_id, user_id=user_id, action="approve_all")

    # Update message to show approval
    try:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Recommendations approved",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Approved by <@{user_id}>*\nRun ID: `{run_id}`\nAll recommendations will be applied.",
                    },
                }
            ],
        )

        # TODO: Trigger recommendation application via Pub/Sub
        # This will publish to approval-responses topic
        # The orchestrator will pick it up and apply changes

        logger.info("approval_processed", run_id=run_id)

    except Exception as e:
        logger.error("approval_update_failed", error=str(e))


@slack_app.action("reject_all")
async def handle_reject_all(ack, body, client):
    """Handle reject all button click."""
    await ack()

    run_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    logger.info("rejection_received", run_id=run_id, user_id=user_id, action="reject_all")

    # Update message to show rejection
    try:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Recommendations rejected",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Rejected by <@{user_id}>*\nRun ID: `{run_id}`\nNo changes will be made.",
                    },
                }
            ],
        )

        logger.info("rejection_processed", run_id=run_id)

    except Exception as e:
        logger.error("rejection_update_failed", error=str(e))


@slack_app.action("defer")
async def handle_defer(ack, body, client):
    """Handle defer button click."""
    await ack()

    run_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    logger.info("deferral_received", run_id=run_id, user_id=user_id, action="defer")

    # Update message to show deferral
    try:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Recommendations deferred",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏰ *Deferred by <@{user_id}>*\nRun ID: `{run_id}`\nYou'll be reminded in 24 hours.",
                    },
                }
            ],
        )

        # TODO: Schedule reminder via Pub/Sub or Cloud Scheduler

        logger.info("deferral_processed", run_id=run_id)

    except Exception as e:
        logger.error("deferral_update_failed", error=str(e))
