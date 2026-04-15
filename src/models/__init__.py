"""Pydantic models for the SEM GCP Agents framework."""

from src.models.base import AgentType, ApprovalStatus, RecommendationStatus
from src.models.campaign import CampaignHealthData, CampaignMetrics
from src.models.keyword import KeywordData, KeywordRecommendation, SearchTermData
from src.models.recommendation import Recommendation, RecommendationBatch
from src.models.taxonomy import (
    CampaignTaxonomy,
    CampaignType,
    DetectionMethod,
    ManagementStrategy,
    SyncGroupContext,
)

__all__ = [
    "AgentType",
    "ApprovalStatus",
    "RecommendationStatus",
    "CampaignHealthData",
    "CampaignMetrics",
    "KeywordData",
    "KeywordRecommendation",
    "SearchTermData",
    "Recommendation",
    "RecommendationBatch",
    "CampaignTaxonomy",
    "CampaignType",
    "DetectionMethod",
    "ManagementStrategy",
    "SyncGroupContext",
]
