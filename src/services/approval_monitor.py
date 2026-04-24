"""Service for monitoring and enforcing approval timeouts."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient
from src.models.base import ApprovalStatus, RecommendationStatus

logger = structlog.get_logger(__name__)


class ApprovalMonitorService:
    """Service for checking stale approvals and enforcing timeouts."""

    def __init__(self, bq_client: BigQueryClient | None = None):
        """Initialize approval monitor.

        Args:
            bq_client: BigQuery client for querying recommendations
        """
        self.bq_client = bq_client or BigQueryClient()
        self.logger = logger.bind(component="approval_monitor")

    async def check_stale_approvals(self) -> dict[str, Any]:
        """Check for stale approvals and send reminders or auto-reject.

        Returns:
            Summary of actions taken
        """
        self.logger.info("checking_stale_approvals")

        now = datetime.utcnow()
        escalation_threshold = now - timedelta(hours=settings.approval_escalation_hours)
        timeout_threshold = now - timedelta(hours=settings.approval_timeout_hours)

        summary = {
            "reminders_sent": 0,
            "auto_rejected": 0,
            "errors": [],
        }

        try:
            # Query for awaiting approval recommendations
            sql = f"""
                SELECT
                    id,
                    run_id,
                    agent_type,
                    title,
                    description,
                    created_at,
                    metadata
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.agent_recommendations`
                WHERE status = @status
                AND created_at < @escalation_threshold
                ORDER BY created_at ASC
            """

            rows = await self.bq_client.query(
                sql,
                {
                    "status": RecommendationStatus.AWAITING_APPROVAL.value,
                    "escalation_threshold": escalation_threshold,
                },
            )

            for row in rows:
                rec_id = row["id"]
                created_at = datetime.fromisoformat(row["created_at"].rstrip("Z"))

                # Check if past timeout threshold
                if created_at < timeout_threshold:
                    # Auto-reject
                    await self._auto_reject_recommendation(rec_id, row)
                    summary["auto_rejected"] += 1
                else:
                    # Send reminder
                    await self._send_reminder(rec_id, row)
                    summary["reminders_sent"] += 1

            self.logger.info(
                "stale_approvals_checked",
                reminders_sent=summary["reminders_sent"],
                auto_rejected=summary["auto_rejected"],
            )

        except Exception as e:
            self.logger.error("check_stale_approvals_failed", error=str(e))
            summary["errors"].append(str(e))

        return summary

    async def _send_reminder(self, rec_id: str, rec_data: dict[str, Any]) -> None:
        """Send a Slack reminder for a pending approval.

        Args:
            rec_id: Recommendation ID
            rec_data: Recommendation data from BigQuery
        """
        try:
            # Import here to avoid circular dependency
            from src.integrations.slack.app import post_approval_reminder

            await post_approval_reminder(rec_id, rec_data)

            self.logger.info("reminder_sent", recommendation_id=rec_id)

        except Exception as e:
            self.logger.error(
                "reminder_failed",
                recommendation_id=rec_id,
                error=str(e),
            )
            raise

    async def _auto_reject_recommendation(
        self, rec_id: str, rec_data: dict[str, Any]
    ) -> None:
        """Auto-reject a recommendation that has timed out.

        Args:
            rec_id: Recommendation ID
            rec_data: Recommendation data from BigQuery
        """
        try:
            # Update recommendation status in BigQuery
            sql = f"""
                UPDATE `{settings.gcp_project_id}.{settings.bq_dataset_agents}.agent_recommendations`
                SET
                    status = @new_status,
                    approval_status = @approval_status,
                    approved_by = 'system_timeout',
                    approved_at = CURRENT_TIMESTAMP()
                WHERE id = @rec_id
            """

            await self.bq_client.query(
                sql,
                {
                    "rec_id": rec_id,
                    "new_status": RecommendationStatus.REJECTED.value,
                    "approval_status": ApprovalStatus.TIMEOUT.value,
                },
            )

            # Post notification to Slack
            from src.integrations.slack.app import post_timeout_notification

            await post_timeout_notification(rec_id, rec_data)

            self.logger.info("recommendation_auto_rejected", recommendation_id=rec_id)

        except Exception as e:
            self.logger.error(
                "auto_reject_failed",
                recommendation_id=rec_id,
                error=str(e),
            )
            raise
