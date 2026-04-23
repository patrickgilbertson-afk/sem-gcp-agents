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
        # Get raw body
        body_bytes = await request.body()

        # Parse JSON body
        import json
        body = json.loads(body_bytes.decode("utf-8"))

        logger.info("slack_event_received", event_type=body.get("type"))

        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            return JSONResponse(content={"challenge": body.get("challenge")})

        # Process event with Slack Bolt
        from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
        handler = AsyncSlackRequestHandler(slack_app)

        return await handler.handle(request)

    except Exception as e:
        logger.error("slack_event_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interactions")
async def slack_interactions(request: Request):
    """Handle Slack interactive components (button clicks, modals)."""
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()

        # Slack sends interactions as form-encoded payload
        form_data = await request.form()

        if "payload" in form_data:
            import json
            payload = json.loads(form_data["payload"])

            logger.info(
                "slack_interaction_received",
                type=payload.get("type"),
                action_id=payload.get("actions", [{}])[0].get("action_id") if payload.get("actions") else None
            )

            # Process with Slack Bolt
            from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
            handler = AsyncSlackRequestHandler(slack_app)

            # Let Bolt handle the interaction
            return await handler.handle(request)

        return JSONResponse(content={"status": "ok"})

    except Exception as e:
        logger.error("slack_interaction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
