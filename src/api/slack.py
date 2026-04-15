"""Slack integration API endpoints."""

import structlog
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from src.integrations.slack.app import slack_app

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/events")
async def slack_events(request: Request):
    """Handle Slack events (slash commands, interactions)."""
    try:
        # Slack sends events as form data
        form_data = await request.form()
        body = dict(form_data)

        logger.info("slack_event_received", event_type=body.get("type"))

        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            return JSONResponse(content={"challenge": body.get("challenge")})

        # Process event with Slack Bolt
        # TODO: Implement Slack Bolt handler
        return JSONResponse(content={"status": "ok"})

    except Exception as e:
        logger.error("slack_event_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interactions")
async def slack_interactions(request: Request):
    """Handle Slack interactive components (button clicks, modals)."""
    try:
        form_data = await request.form()
        body = dict(form_data)

        logger.info("slack_interaction_received")

        # TODO: Process interaction
        return JSONResponse(content={"status": "ok"})

    except Exception as e:
        logger.error("slack_interaction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
