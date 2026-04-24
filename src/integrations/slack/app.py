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


def is_user_authorized(user_id: str) -> bool:
    """Check if user is authorized to approve/reject recommendations.

    Args:
        user_id: Slack user ID

    Returns:
        True if user is authorized (in whitelist or whitelist is empty)
    """
    whitelist = settings.slack_approval_user_whitelist.strip()
    if not whitelist:
        # Empty whitelist = allow all users
        return True

    allowed_users = [u.strip() for u in whitelist.split(",") if u.strip()]
    is_allowed = user_id in allowed_users

    logger.info(
        "user_authorization_check",
        user_id=user_id,
        is_authorized=is_allowed,
        whitelist_size=len(allowed_users),
    )

    return is_allowed


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
    # Add dry run indicator to header
    dry_run_tag = " [DRY RUN]" if settings.is_dry_run else ""

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🤖 {batch.agent_type.value.replace('_', ' ').title()} Agent Recommendations{dry_run_tag}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:* {batch.summary}\n*Total Recommendations:* {batch.total_count}\n*Run ID:* `{batch.run_id}`"
                        + (f"\n\n⚠️ *DRY RUN MODE* - Approving will NOT make real changes" if settings.is_dry_run else ""),
            },
        },
    ]

    # Check if there are any SYNCED recommendations
    synced_count = sum(
        1 for rec in batch.recommendations
        if rec.metadata.get("management_strategy") == "synced"
    )

    if synced_count > 0:
        # Get unique sync groups
        sync_groups = set(
            rec.metadata.get("sync_group")
            for rec in batch.recommendations
            if rec.metadata.get("management_strategy") == "synced" and rec.metadata.get("sync_group")
        )

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚡ *Multi-Geo Sync Groups Affected:* {', '.join(sorted(sync_groups))}\n"
                            f"_{synced_count} of {batch.total_count} recommendations will propagate across all geos_",
                },
            }
        )

    blocks.append({"type": "divider"})

    # Add recommendation details (first 10 only to avoid message size limits)
    for i, rec in enumerate(batch.recommendations[:10]):
        # Build recommendation text
        rec_text = f"*{i+1}. {rec.title}*\n{rec.description}\n_Risk: {rec.risk_level}_"

        # Add sync group info if this is a SYNCED recommendation
        if rec.metadata.get("management_strategy") == "synced" and rec.metadata.get("sync_group"):
            sync_group = rec.metadata["sync_group"]
            geo = rec.metadata.get("geo", "unknown")
            rec_text += f"\n\n⚡ *Sync Group:* {sync_group} (showing {geo} - will apply to all geos)"

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": rec_text,
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

    # Check user authorization
    if not is_user_authorized(user_id):
        logger.warning(
            "unauthorized_approval_attempt",
            run_id=run_id,
            user_id=user_id,
            action="approve_all",
        )
        await client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text=f"❌ You are not authorized to approve recommendations. Contact your administrator.",
        )
        return

    logger.info("approval_received", run_id=run_id, user_id=user_id, action="approve_all")

    # Update message to show approval in progress
    try:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Processing approval...",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Approved by <@{user_id}>*\nRun ID: `{run_id}`\nProcessing recommendations and sync group propagation...",
                    },
                }
            ],
        )

        # Load recommendations from BigQuery and apply with propagation
        from src.integrations.bigquery.client import get_client
        from src.models.recommendation import Recommendation
        from src.models.base import AgentType, RecommendationStatus, ApprovalStatus
        from src.services.taxonomy import TaxonomyService
        from src.core.orchestrator import Orchestrator
        from datetime import datetime
        import json

        bq_client = get_client()

        # Query recommendations for this run
        sql = f"""
        SELECT *
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.agent_recommendations`
        WHERE run_id = @run_id
        AND status = @status
        """

        rows = await bq_client.query(
            sql,
            {
                "run_id": run_id,
                "status": RecommendationStatus.AWAITING_APPROVAL.value,
            },
        )

        if not rows:
            logger.warning("no_recommendations_found", run_id=run_id)
            return

        # Convert rows to Recommendation objects
        recommendations = []
        for row in rows:
            rec = Recommendation(
                id=row["id"],
                agent_type=AgentType(row["agent_type"]),
                run_id=row["run_id"],
                title=row["title"],
                description=row["description"],
                rationale=row["rationale"],
                impact_estimate=row["impact_estimate"],
                risk_level=row["risk_level"],
                action_type=row["action_type"],
                action_params=json.loads(row["action_params"]),
                status=RecommendationStatus(row["status"]),
                approval_status=ApprovalStatus(row["approval_status"]) if row.get("approval_status") else None,
                metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            )
            recommendations.append(rec)

        # Propagate SYNCED recommendations to other geos
        taxonomy_service = TaxonomyService(bq_client=bq_client)
        all_recommendations = list(recommendations)  # Start with originals

        for rec in recommendations:
            if rec.metadata.get("management_strategy") == "synced" and rec.metadata.get("sync_group"):
                # Load sync group context
                sync_context = await taxonomy_service.get_sync_group_context(
                    rec.metadata["sync_group"]
                )

                if sync_context:
                    # Get the agent to call propagate_to_sync_group
                    orchestrator = Orchestrator()
                    agent = orchestrator._get_agent(AgentType(rec.agent_type.value))

                    # Propagate to sync group
                    propagated = await agent.propagate_to_sync_group(rec, sync_context)
                    all_recommendations.extend(propagated)

                    logger.info(
                        "recommendations_propagated",
                        original_rec_id=str(rec.id),
                        sync_group=rec.metadata["sync_group"],
                        propagated_count=len(propagated),
                    )

        # Update all recommendations to APPROVED status
        for rec in all_recommendations:
            rec.status = RecommendationStatus.APPROVED
            rec.approval_status = ApprovalStatus.APPROVED
            rec.approved_by = user_id
            rec.approved_at = datetime.utcnow()

        # Save propagated recommendations to BigQuery
        await bq_client.insert_rows(
            "agent_recommendations",
            [
                {
                    "id": str(rec.id),
                    "run_id": str(rec.run_id),
                    "agent_type": rec.agent_type.value,
                    "created_at": datetime.utcnow().isoformat(),
                    "title": rec.title,
                    "description": rec.description,
                    "rationale": rec.rationale,
                    "impact_estimate": rec.impact_estimate,
                    "risk_level": rec.risk_level,
                    "action_type": rec.action_type,
                    "action_params": json.dumps(rec.action_params),
                    "status": rec.status.value,
                    "approval_status": rec.approval_status.value if rec.approval_status else None,
                    "approved_by": rec.approved_by,
                    "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
                    "metadata": json.dumps(rec.metadata),
                }
                for rec in all_recommendations
                if rec.metadata.get("propagated_from")  # Only save new propagated ones
            ]
        )

        # Apply all recommendations (original + propagated)
        # TODO: This should be done by the agent's apply_changes method
        # For now, just log that we would apply

        # Update message to show completion
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Recommendations approved",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Approved by <@{user_id}>*\n"
                                f"Run ID: `{run_id}`\n"
                                f"Total recommendations (including propagated): {len(all_recommendations)}\n"
                                f"Original: {len(recommendations)} | Propagated: {len(all_recommendations) - len(recommendations)}",
                    },
                }
            ],
        )

        logger.info(
            "approval_processed",
            run_id=run_id,
            original_count=len(recommendations),
            total_count=len(all_recommendations),
        )

    except Exception as e:
        logger.error("approval_update_failed", error=str(e))
        # Update message to show error
        try:
            await client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text="Approval failed",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"❌ *Approval Failed*\nRun ID: `{run_id}`\nError: {str(e)}",
                        },
                    }
                ],
            )
        except:
            pass


@slack_app.action("reject_all")
async def handle_reject_all(ack, body, client):
    """Handle reject all button click."""
    await ack()

    run_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    # Check user authorization
    if not is_user_authorized(user_id):
        logger.warning(
            "unauthorized_rejection_attempt",
            run_id=run_id,
            user_id=user_id,
            action="reject_all",
        )
        await client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text=f"❌ You are not authorized to reject recommendations. Contact your administrator.",
        )
        return

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

    # Check user authorization
    if not is_user_authorized(user_id):
        logger.warning(
            "unauthorized_defer_attempt",
            run_id=run_id,
            user_id=user_id,
            action="defer",
        )
        await client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text=f"❌ You are not authorized to defer recommendations. Contact your administrator.",
        )
        return

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


# ============================================================================
# Approval Monitoring Functions
# ============================================================================


async def post_approval_reminder(rec_id: str, rec_data: dict) -> None:
    """Post a reminder for a pending approval.

    Args:
        rec_id: Recommendation ID
        rec_data: Recommendation data from BigQuery
    """
    try:
        await slack_app.client.chat_postMessage(
            channel=settings.slack_approval_channel_id,
            text=f"⏰ Reminder: Pending approval for recommendation {rec_id}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏰ *Approval Reminder*\n\n"
                                f"*Recommendation:* {rec_data.get('title', 'N/A')}\n"
                                f"*Run ID:* `{rec_data.get('run_id', 'N/A')}`\n"
                                f"*Created:* {rec_data.get('created_at', 'N/A')}\n\n"
                                f"This approval has been pending for 4+ hours. "
                                f"Please review or it will auto-reject in 4 hours.",
                    },
                }
            ],
        )
        logger.info("approval_reminder_sent", rec_id=rec_id)

    except Exception as e:
        logger.error("approval_reminder_failed", rec_id=rec_id, error=str(e))
        raise


async def post_timeout_notification(rec_id: str, rec_data: dict) -> None:
    """Post a notification that an approval has timed out.

    Args:
        rec_id: Recommendation ID
        rec_data: Recommendation data from BigQuery
    """
    try:
        await slack_app.client.chat_postMessage(
            channel=settings.slack_approval_channel_id,
            text=f"⏱️ Auto-rejected: {rec_id}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏱️ *Auto-Rejected (Timeout)*\n\n"
                                f"*Recommendation:* {rec_data.get('title', 'N/A')}\n"
                                f"*Run ID:* `{rec_data.get('run_id', 'N/A')}`\n"
                                f"*Created:* {rec_data.get('created_at', 'N/A')}\n\n"
                                f"This approval was pending for 8+ hours and has been automatically rejected. "
                                f"No changes were made.",
                    },
                }
            ],
        )
        logger.info("timeout_notification_sent", rec_id=rec_id)

    except Exception as e:
        logger.error("timeout_notification_failed", rec_id=rec_id, error=str(e))
        raise


async def post_weekly_report(report_data: dict) -> None:
    """Post weekly optimization report to Slack.

    Args:
        report_data: Report data from WeeklyReportService
    """
    try:
        blocks = _build_weekly_report_blocks(report_data)

        await slack_app.client.chat_postMessage(
            channel=settings.slack_approval_channel_id,
            text="📊 Weekly Optimization Report",
            blocks=blocks,
        )

        logger.info("weekly_report_posted")

    except Exception as e:
        logger.error("weekly_report_post_failed", error=str(e))
        raise


def _build_weekly_report_blocks(report_data: dict) -> list[dict]:
    """Build Slack Block Kit blocks for weekly report.

    Args:
        report_data: Report data from WeeklyReportService

    Returns:
        List of Block Kit blocks
    """
    from datetime import datetime

    week_start = datetime.fromisoformat(report_data["week_start"]).strftime("%b %d, %Y")
    week_end = datetime.fromisoformat(report_data["week_end"]).strftime("%b %d, %Y")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 Weekly Optimization Report — {week_start} to {week_end}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary*\n\n{report_data['executive_summary']}",
            },
        },
        {"type": "divider"},
    ]

    # Add sync group breakdowns
    for sg_report in report_data["sync_group_reports"]:
        sg = sg_report["sync_group"]
        count = sg_report["optimization_count"]
        perf = sg_report["performance"]

        # Format performance changes
        cpa_before = perf["cpa"]["before"]
        cpa_after = perf["cpa"]["after"]
        cpa_change_pct = perf["cpa"]["change_pct"]
        cpa_emoji = "✅" if cpa_change_pct < 0 else "⚠️"  # Improvement = lower CPA

        ctr_before = perf["ctr"]["before"]
        ctr_after = perf["ctr"]["after"]
        ctr_change_pct = perf["ctr"]["change_pct"]
        ctr_emoji = "✅" if ctr_change_pct > 0 else "⚠️"  # Improvement = higher CTR

        cost_change = perf["cost"]["change"]
        cost_emoji = "✅" if cost_change < 0 else "⚠️"  # Improvement = lower cost

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{sg}*\n"
                            f"📊 {count} optimizations applied this week\n\n"
                            f"*Performance Impact:*\n"
                            f"{cpa_emoji} CPA: ${cpa_before:.2f} → ${cpa_after:.2f} ({cpa_change_pct:+.1f}%)\n"
                            f"{ctr_emoji} CTR: {ctr_before:.2%} → {ctr_after:.2%} ({ctr_change_pct:+.1f}%)\n"
                            f"{cost_emoji} Cost: ${cost_change:+.2f}\n",
                },
            }
        )

        # Show top optimizations for this sync group (max 3)
        if sg_report["optimizations"]:
            opt_list = []
            for i, opt in enumerate(sg_report["optimizations"][:3]):
                opt_list.append(f"• {opt['title']}")

            opt_text = "\n".join(opt_list)
            if len(sg_report["optimizations"]) > 3:
                opt_text += f"\n_...and {len(sg_report['optimizations']) - 3} more_"

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Optimizations Applied:*\n{opt_text}",
                    },
                }
            )

        blocks.append({"type": "divider"})

    # Add footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🤖 Generated by SEM GCP Agents | "
                            f"Total: {report_data['total_optimizations']} optimizations | "
                            f"{len(report_data['sync_group_reports'])} sync groups affected",
                }
            ],
        }
    )

    return blocks
