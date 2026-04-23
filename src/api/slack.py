"""Slack integration API endpoints."""

import structlog
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from src.integrations.slack.app import slack_app

logger = structlog.get_logger(__name__)
router = APIRouter()

# Create Slack handler
slack_handler = AsyncSlackRequestHandler(slack_app)


@router.post("/events")
async def slack_events(request: Request):
    """Handle Slack events (slash commands, interactions)."""
    try:
        logger.info("slack_event_endpoint_called")
        return await slack_handler.handle(request)
    except Exception as e:
        logger.error("slack_event_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interactions")
async def slack_interactions(request: Request):
    """Handle Slack interactive components (button clicks, modals)."""
    try:
        logger.info("slack_interaction_endpoint_called")
        return await slack_handler.handle(request)
    except Exception as e:
        logger.error("slack_interaction_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
