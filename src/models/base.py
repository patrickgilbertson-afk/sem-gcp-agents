"""Base enums and types for the agent framework."""

from enum import Enum


class AgentType(str, Enum):
    """Types of SEM agents."""

    CAMPAIGN_HEALTH = "campaign_health"
    KEYWORD = "keyword"
    AD_COPY = "ad_copy"
    BID_MODIFIER = "bid_modifier"
    ORCHESTRATOR = "orchestrator"


class RecommendationStatus(str, Enum):
    """Status of a recommendation in the pipeline."""

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"
    DEFERRED = "deferred"


class ApprovalStatus(str, Enum):
    """User approval decision from Slack."""

    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    TIMEOUT = "timeout"


class EventType(str, Enum):
    """Types of audit log events."""

    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"
    RUN_FAILED = "run_failed"
    GATHER_DATA = "gather_data"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    APPLY_CHANGES = "apply_changes"
    DELEGATION = "delegation"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    ERROR = "error"
