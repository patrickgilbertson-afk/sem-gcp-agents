"""Agent management API endpoints."""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.models.base import AgentType

logger = structlog.get_logger(__name__)
router = APIRouter()


class AgentStatusResponse(BaseModel):
    """Agent status information."""

    agent_type: AgentType
    status: str
    last_run: str | None = None
    next_scheduled: str | None = None


class KillSwitchRequest(BaseModel):
    """Kill switch control."""

    enabled: bool
    reason: str | None = None


@router.get("/status")
async def get_all_agent_status():
    """Get status of all agents."""
    # TODO: Query BigQuery for agent status
    statuses = []
    for agent_type in AgentType:
        if agent_type != AgentType.ORCHESTRATOR:
            statuses.append(
                AgentStatusResponse(
                    agent_type=agent_type,
                    status="active" if not settings.kill_switch_enabled else "paused",
                    last_run=None,
                    next_scheduled=None,
                )
            )
    return {"agents": statuses, "kill_switch": settings.kill_switch_enabled}


@router.post("/kill-switch")
async def toggle_kill_switch(request: KillSwitchRequest):
    """Toggle the kill switch.

    When enabled, all agents run in dry-run mode only.
    """
    logger.warning(
        "kill_switch_toggled",
        enabled=request.enabled,
        reason=request.reason,
    )

    # Note: In production, this should update a BigQuery table or Secret Manager
    # For now, we just log it
    settings.kill_switch_enabled = request.enabled

    return {
        "kill_switch": request.enabled,
        "message": f"Kill switch {'enabled' if request.enabled else 'disabled'}",
    }


@router.post("/test-slack-approval")
async def test_slack_approval():
    """Send a test approval request to Slack channel.

    This is for testing the Slack integration and approval workflow.
    """
    from datetime import datetime
    from uuid import uuid4
    from src.models.recommendation import Recommendation, RecommendationBatch
    from src.integrations.slack.app import request_approval

    logger.info("sending_test_approval_request")

    try:
        # Create sample recommendations
        run_id = uuid4()

        recommendations = [
            Recommendation(
                id=uuid4(),
                agent_type=AgentType.CAMPAIGN_HEALTH,
                run_id=run_id,
                created_at=datetime.utcnow(),
                title="🧪 TEST: Pause underperforming ad group",
                description="This is a TEST recommendation. Ad group 'Test Group 1' has 0 conversions in 30 days with $500 spend",
                rationale="No conversions despite significant spend. This is a test of the approval workflow.",
                impact_estimate="Save $500/month (TEST)",
                risk_level="low",
                action_type="pause_ad_group",
                action_params={
                    "campaign_id": "12345",
                    "ad_group_id": "67890",
                    "campaign_name": "Test Campaign",
                    "ad_group_name": "Test Group 1"
                }
            ),
            Recommendation(
                id=uuid4(),
                agent_type=AgentType.CAMPAIGN_HEALTH,
                run_id=run_id,
                created_at=datetime.utcnow(),
                title="🧪 TEST: Review keywords for low CTR",
                description="This is a TEST recommendation. Ad group 'Test Group 2' has CTR of 0.5% (below 2% threshold)",
                rationale="Low CTR suggests poor keyword-ad relevance. This is a test.",
                impact_estimate="Potential 2x CTR improvement (TEST)",
                risk_level="medium",
                action_type="delegate_keyword_review",
                action_params={
                    "campaign_id": "12345",
                    "ad_group_id": "67891",
                    "campaign_name": "Test Campaign",
                    "ad_group_name": "Test Group 2"
                }
            ),
            Recommendation(
                id=uuid4(),
                agent_type=AgentType.CAMPAIGN_HEALTH,
                run_id=run_id,
                created_at=datetime.utcnow(),
                title="🧪 TEST: Increase budget for high-performing campaign",
                description="This is a TEST recommendation. Campaign 'Winner Campaign' has ROAS of 8.5x with maxed budget",
                rationale="Campaign is constrained by budget. This is a test of the approval workflow.",
                impact_estimate="Estimated +$2,000/month revenue (TEST)",
                risk_level="low",
                action_type="increase_budget",
                action_params={
                    "campaign_id": "54321",
                    "campaign_name": "Winner Campaign",
                    "current_budget": 100,
                    "recommended_budget": 150,
                    "current_roas": 8.5
                }
            ),
        ]

        # Create batch
        batch = RecommendationBatch(
            run_id=run_id,
            agent_type=AgentType.CAMPAIGN_HEALTH,
            recommendations=recommendations,
            summary=f"🧪 TEST MESSAGE: Found {len(recommendations)} optimization opportunities. This is a test of the Slack approval workflow."
        )

        # Send to Slack
        await request_approval(batch)

        logger.info("test_approval_sent", run_id=str(run_id))

        return {
            "status": "success",
            "message": "Test approval request sent to Slack",
            "run_id": str(run_id),
            "channel": settings.slack_approval_channel_id,
            "recommendation_count": len(recommendations)
        }

    except Exception as e:
        logger.error("test_approval_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to send test approval: {str(e)}")
