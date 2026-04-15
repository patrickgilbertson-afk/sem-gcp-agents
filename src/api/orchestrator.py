"""Orchestrator API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.orchestrator import Orchestrator
from src.models.base import AgentType

logger = structlog.get_logger(__name__)
router = APIRouter()


class RunRequest(BaseModel):
    """Request to run orchestrator or specific agent."""

    agent_type: AgentType | None = None
    context: dict | None = None


class RunResponse(BaseModel):
    """Response from agent run."""

    run_id: UUID
    agent_type: AgentType
    status: str
    recommendation_count: int
    message: str


@router.post("/run", response_model=RunResponse)
async def run_orchestrator(request: RunRequest):
    """Trigger orchestrator or specific agent run.

    This endpoint is called by Cloud Scheduler or manually.
    """
    logger.info(
        "orchestrator_triggered",
        agent_type=request.agent_type,
        has_context=request.context is not None,
    )

    try:
        orchestrator = Orchestrator()

        if request.agent_type:
            # Run specific agent
            batch = await orchestrator.run_agent(request.agent_type, request.context)
        else:
            # Run orchestrator (decides which agents to run)
            batch = await orchestrator.run(request.context)

        return RunResponse(
            run_id=batch.run_id,
            agent_type=batch.agent_type,
            status="completed",
            recommendation_count=batch.total_count,
            message=f"Generated {batch.total_count} recommendations",
        )

    except Exception as e:
        logger.error("orchestrator_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{run_id}")
async def get_run_status(run_id: UUID):
    """Get status of a specific run."""
    # TODO: Query BigQuery for run status
    return {"run_id": str(run_id), "status": "not_implemented"}
