"""Campaign health data models."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class CampaignMetrics(BaseModel):
    """Performance metrics for a campaign or ad group."""

    impressions: int
    clicks: int
    cost: float
    conversions: float
    conversion_value: float

    # Calculated
    ctr: float  # Click-through rate
    avg_cpc: float  # Average cost per click
    conversion_rate: float  # Conversions / clicks
    cost_per_conversion: float | None = None
    roas: float | None = None  # Return on ad spend

    # Quality metrics
    avg_quality_score: float | None = None
    impression_share: float | None = None
    search_impression_share_lost_to_rank: float | None = None
    search_impression_share_lost_to_budget: float | None = None


class CampaignHealthData(BaseModel):
    """Campaign health analysis data."""

    campaign_id: str
    campaign_name: str
    ad_group_id: str | None = None
    ad_group_name: str | None = None

    # Time period
    date_start: date
    date_end: date

    # Current metrics
    current_metrics: CampaignMetrics

    # Historical comparison (30-day period before current)
    previous_metrics: CampaignMetrics | None = None

    # Flags and anomalies
    is_paused: bool = False
    is_under_budget: bool = False
    has_quality_score_issues: bool = False
    has_zero_conversions: bool = False
    has_low_ctr: bool = False
    has_high_impression_share_loss: bool = False

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def health_flags(self) -> list[str]:
        """Get list of active health flags."""
        flags = []
        if self.has_quality_score_issues:
            flags.append("quality_score_issues")
        if self.has_zero_conversions:
            flags.append("zero_conversions")
        if self.has_low_ctr:
            flags.append("low_ctr")
        if self.has_high_impression_share_loss:
            flags.append("high_impression_share_loss")
        if self.is_under_budget:
            flags.append("under_budget")
        return flags
