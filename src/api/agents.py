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
