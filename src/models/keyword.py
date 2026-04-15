"""Keyword management data models."""

from enum import Enum

from pydantic import BaseModel


class MatchType(str, Enum):
    """Keyword match types."""

    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


class KeywordStatus(str, Enum):
    """Keyword status."""

    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class SearchTermData(BaseModel):
    """Search term report data."""

    search_term: str
    campaign_id: str
    ad_group_id: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    conversion_value: float

    # Calculated
    ctr: float
    conversion_rate: float
    cost_per_conversion: float | None = None

    # Matching
    matched_keyword: str | None = None
    matched_keyword_id: str | None = None


class KeywordData(BaseModel):
    """Keyword performance data."""

    keyword_id: str
    keyword_text: str
    match_type: MatchType
    status: KeywordStatus

    campaign_id: str
    ad_group_id: str

    # Performance
    impressions: int
    clicks: int
    cost: float
    conversions: float
    conversion_value: float

    # Quality
    quality_score: int | None = None
    ctr: float
    conversion_rate: float


class KeywordRecommendation(BaseModel):
    """Keyword-specific recommendation details."""

    keyword_text: str
    match_type: MatchType
    action: str  # "add_negative", "add_positive", "pause", "enable"
    campaign_id: str
    ad_group_id: str | None = None
    rationale: str
    supporting_data: dict[str, float | int | str]
