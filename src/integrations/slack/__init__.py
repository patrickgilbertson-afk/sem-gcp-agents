"""Slack integration for approvals and notifications."""

from src.integrations.slack.app import request_approval, send_notification

__all__ = ["request_approval", "send_notification"]
