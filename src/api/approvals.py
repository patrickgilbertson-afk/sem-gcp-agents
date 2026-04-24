"""Approval monitoring API endpoints."""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.approval_monitor import ApprovalMonitorService

logger = structlog.get_logger(__name__)
router = APIRouter()


class CheckStaleResponse(BaseModel):
    """Response from stale approval check."""

    reminders_sent: int
    auto_rejected: int
    errors: list[str]
    message: str


@router.post("/check-stale", response_model=CheckStaleResponse)
async def check_stale_approvals():
    """Check for stale approvals and send reminders or auto-reject.

    This endpoint is called by Cloud Scheduler every 30 minutes.
    - At 4 hours: sends Slack reminder
    - At 8 hours: auto-rejects and notifies
    """
    logger.info("check_stale_approvals_triggered")

    try:
        monitor = ApprovalMonitorService()
        summary = await monitor.check_stale_approvals()

        return CheckStaleResponse(
            reminders_sent=summary["reminders_sent"],
            auto_rejected=summary["auto_rejected"],
            errors=summary["errors"],
            message=f"Processed stale approvals: {summary['reminders_sent']} reminders, {summary['auto_rejected']} auto-rejected",
        )

    except Exception as e:
        logger.error("check_stale_approvals_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
