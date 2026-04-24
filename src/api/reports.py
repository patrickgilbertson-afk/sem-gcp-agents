"""Reporting API endpoints."""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.weekly_report import WeeklyReportService

logger = structlog.get_logger(__name__)
router = APIRouter()


class WeeklyReportResponse(BaseModel):
    """Response from weekly report generation."""

    week_start: str
    week_end: str
    total_optimizations: int
    sync_groups_affected: int
    executive_summary: str
    message: str


@router.post("/weekly", response_model=WeeklyReportResponse)
async def generate_weekly_report():
    """Generate and post weekly optimization report.

    This endpoint is called by Cloud Scheduler every Thursday at 11 AM CST.
    Generates a summary of all optimizations from the past 7 days,
    broken down by sync group, and posts to Slack.
    """
    logger.info("weekly_report_triggered")

    try:
        # Generate report
        report_service = WeeklyReportService()
        report_data = await report_service.generate_report(days_back=7)

        # Post to Slack
        from src.integrations.slack.app import post_weekly_report
        await post_weekly_report(report_data)

        return WeeklyReportResponse(
            week_start=report_data["week_start"],
            week_end=report_data["week_end"],
            total_optimizations=report_data["total_optimizations"],
            sync_groups_affected=len(report_data["sync_group_reports"]),
            executive_summary=report_data["executive_summary"],
            message=f"Weekly report generated and posted to Slack. {report_data['total_optimizations']} optimizations across {len(report_data['sync_group_reports'])} sync groups.",
        )

    except Exception as e:
        logger.error("weekly_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
