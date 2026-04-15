"""Campaign taxonomy models for sync group management."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CampaignType(str, Enum):
    """Campaign classification types."""

    BRAND = "brand"
    NON_BRAND = "non_brand"
    COMPETITOR = "competitor"
    DYNAMIC = "dynamic"
    SHOPPING = "shopping"


class ManagementStrategy(str, Enum):
    """How campaigns in a sync group should be managed."""

    SYNCED = "synced"  # Multi-geo variants, shared keywords/ad copy
    INDIVIDUAL = "individual"  # Evaluated independently


class DetectionMethod(str, Enum):
    """How the taxonomy was determined."""

    AUTO = "auto"  # Detected from naming conventions
    MANUAL = "manual"  # User-specified
    HYBRID = "hybrid"  # Auto + manual override


class CampaignTaxonomy(BaseModel):
    """Taxonomy classification for a campaign."""

    campaign_id: str
    campaign_name: str
    customer_id: str
    campaign_type: CampaignType
    vertical: str  # e.g., "AI-Code", "LLM-Integration"
    geo: str  # e.g., "US", "UK", "DE"
    sync_group: str  # e.g., "NonBrand_AI-Code"
    management_strategy: ManagementStrategy
    is_template: bool = False  # Template campaign drives analysis
    detection_method: DetectionMethod
    detection_confidence: float | None = None
    campaign_status: str | None = None
    agent_exclusions: list[str] = Field(default_factory=list)  # AgentType values to skip
    external_manager: str | None = None  # Who manages excluded scope
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None
    notes: str | None = None


class SyncGroupContext(BaseModel):
    """Context for a sync group with all its campaigns."""

    sync_group: str
    campaign_type: CampaignType
    vertical: str
    management_strategy: ManagementStrategy
    campaigns: list[CampaignTaxonomy]
    template_campaign: CampaignTaxonomy | None = None  # Preferably US

    @property
    def excluded_agents(self) -> set[str]:
        """Union of agent_exclusions across all campaigns in sync group.

        If ANY campaign in the group excludes an agent, the whole group does.
        This is conservative but prevents accidental operations.
        """
        result = set()
        for campaign in self.campaigns:
            result.update(campaign.agent_exclusions)
        return result

    @property
    def external_manager(self) -> str | None:
        """Return external manager if any campaign has one."""
        for campaign in self.campaigns:
            if campaign.external_manager:
                return campaign.external_manager
        return None

    def is_agent_excluded(self, agent_type: str) -> bool:
        """Check if an agent should skip this sync group.

        Args:
            agent_type: AgentType value (e.g., "keyword", "bid_modifier")

        Returns:
            True if the agent should skip this sync group
        """
        return agent_type in self.excluded_agents

    @property
    def campaign_ids(self) -> list[str]:
        """List of all campaign IDs in this sync group."""
        return [c.campaign_id for c in self.campaigns]

    @property
    def geos(self) -> list[str]:
        """List of all geos in this sync group."""
        return sorted(set(c.geo for c in self.campaigns))
