"""Core recommendation data models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.base import AgentType, ApprovalStatus, RecommendationStatus


class Recommendation(BaseModel):
    """A single recommendation from an agent."""

    id: UUID = Field(default_factory=uuid4)
    agent_type: AgentType
    run_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Recommendation details
    title: str
    description: str
    rationale: str  # LLM explanation
    impact_estimate: str | None = None  # Expected outcome
    risk_level: str = "low"  # low, medium, high

    # Action to execute
    action_type: str  # e.g., "pause_ad_group", "add_negative_keyword"
    action_params: dict[str, Any]

    # Status tracking
    status: RecommendationStatus = RecommendationStatus.PENDING
    approval_status: ApprovalStatus | None = None
    approved_by: str | None = None  # Slack user ID
    approved_at: datetime | None = None

    # Execution results
    applied_at: datetime | None = None
    applied_result: dict[str, Any] | None = None
    error_message: str | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat(), UUID: str}


class RecommendationBatch(BaseModel):
    """A batch of recommendations for approval."""

    run_id: UUID
    agent_type: AgentType
    recommendations: list[Recommendation]
    summary: str  # High-level summary for Slack message
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Slack integration
    slack_message_ts: str | None = None  # Thread timestamp for tracking
    slack_channel_id: str | None = None

    @property
    def total_count(self) -> int:
        """Total number of recommendations."""
        return len(self.recommendations)

    @property
    def by_action_type(self) -> dict[str, int]:
        """Count recommendations by action type."""
        counts: dict[str, int] = {}
        for rec in self.recommendations:
            counts[rec.action_type] = counts.get(rec.action_type, 0) + 1
        return counts
