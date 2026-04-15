"""Tests for data models."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.models.base import AgentType, RecommendationStatus
from src.models.recommendation import Recommendation, RecommendationBatch


def test_recommendation_creation():
    """Test creating a recommendation."""
    rec = Recommendation(
        agent_type=AgentType.CAMPAIGN_HEALTH,
        run_id=uuid4(),
        title="Test recommendation",
        description="Test description",
        rationale="Test rationale",
        action_type="pause_ad_group",
        action_params={"ad_group_id": "123"},
    )

    assert rec.id
    assert rec.agent_type == AgentType.CAMPAIGN_HEALTH
    assert rec.status == RecommendationStatus.PENDING
    assert rec.action_type == "pause_ad_group"


def test_recommendation_batch():
    """Test creating a recommendation batch."""
    run_id = uuid4()
    recommendations = [
        Recommendation(
            agent_type=AgentType.KEYWORD,
            run_id=run_id,
            title=f"Recommendation {i}",
            description="Description",
            rationale="Rationale",
            action_type="add_negative_keyword",
            action_params={},
        )
        for i in range(3)
    ]

    batch = RecommendationBatch(
        run_id=run_id,
        agent_type=AgentType.KEYWORD,
        recommendations=recommendations,
        summary="Test batch",
    )

    assert batch.total_count == 3
    assert batch.agent_type == AgentType.KEYWORD
    assert len(batch.by_action_type) == 1
    assert batch.by_action_type["add_negative_keyword"] == 3
