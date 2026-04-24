"""Unit tests for sync group propagation."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.core.base_agent import BaseAgent
from src.models.base import AgentType
from src.models.recommendation import Recommendation
from src.models.taxonomy import (
    CampaignTaxonomy,
    CampaignType,
    ManagementStrategy,
    DetectionMethod,
    SyncGroupContext,
)
from datetime import datetime


class TestAgent(BaseAgent):
    """Test agent implementation for testing base agent functionality."""

    PROPAGATABLE_ACTIONS = {"pause_ad_group", "delegate_keyword_review"}

    async def gather_data(self, context):
        return {}

    async def analyze(self, data):
        return "Test analysis"

    async def generate_recommendations(self, data, analysis):
        return []

    async def _apply_single_recommendation(self, recommendation):
        pass

    async def _create_summary(self, recommendations):
        return "Test summary"


@pytest.fixture
def sample_taxonomy():
    """Create sample campaign taxonomy."""
    return CampaignTaxonomy(
        campaign_id="123",
        campaign_name="NonBrand_AI-Code_US",
        customer_id="456",
        campaign_type=CampaignType.NON_BRAND,
        vertical="AI-Code",
        geo="US",
        sync_group="NonBrand_AI-Code",
        management_strategy=ManagementStrategy.SYNCED,
        is_template=True,
        detection_method=DetectionMethod.AUTO,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sync_group_context(sample_taxonomy):
    """Create sample sync group context."""
    # Create campaigns for US, UK, DE
    campaigns = [
        sample_taxonomy,  # US
        sample_taxonomy.model_copy(update={
            "campaign_id": "124",
            "campaign_name": "NonBrand_AI-Code_UK",
            "geo": "UK",
            "is_template": False,
        }),
        sample_taxonomy.model_copy(update={
            "campaign_id": "125",
            "campaign_name": "NonBrand_AI-Code_DE",
            "geo": "DE",
            "is_template": False,
        }),
    ]

    return SyncGroupContext(
        sync_group="NonBrand_AI-Code",
        campaign_type=CampaignType.NON_BRAND,
        vertical="AI-Code",
        management_strategy=ManagementStrategy.SYNCED,
        campaigns=campaigns,
        template_campaign=campaigns[0],
    )


@pytest.fixture
def sample_recommendation():
    """Create sample recommendation."""
    return Recommendation(
        agent_type=AgentType.CAMPAIGN_HEALTH,
        run_id=uuid4(),
        title="Pause ad group: broad_generic_terms",
        description="Spent $200 with zero conversions",
        rationale="Ad group has high spend without conversions",
        impact_estimate="Save $200/month",
        risk_level="low",
        action_type="pause_ad_group",
        action_params={
            "campaign_id": "123",
            "ad_group_id": "789",
            "ad_group_name": "broad_generic_terms",
        },
        metadata={
            "sync_group": "NonBrand_AI-Code",
            "management_strategy": "synced",
            "geo": "US",
        },
    )


@pytest.mark.asyncio
async def test_propagate_to_sync_group_creates_clones(
    sample_recommendation,
    sync_group_context,
):
    """Test that propagate_to_sync_group creates clones for each campaign."""
    agent = TestAgent(agent_type=AgentType.CAMPAIGN_HEALTH)

    # Mock SyncGroupResolver
    with patch("src.core.base_agent.SyncGroupResolver") as mock_resolver_class:
        mock_resolver = AsyncMock()
        mock_resolver_class.return_value = mock_resolver

        # Mock resolved entities for UK and DE
        mock_resolver.resolve_entities_for_sync_group.return_value = [
            {
                "campaign_id": "124",
                "ad_group_id": "790",
                "ad_group_name": "broad_generic_terms",
                "geo": "UK",
            },
            {
                "campaign_id": "125",
                "ad_group_id": "791",
                "ad_group_name": "broad_generic_terms",
                "geo": "DE",
            },
        ]

        propagated = await agent.propagate_to_sync_group(
            rec=sample_recommendation,
            sync_group_context=sync_group_context,
        )

        # Should create 2 clones (UK, DE) - US is skipped as source
        assert len(propagated) == 2

        # Verify clones have correct campaign IDs
        assert propagated[0].action_params["campaign_id"] == "124"
        assert propagated[1].action_params["campaign_id"] == "125"


@pytest.mark.asyncio
async def test_propagate_preserves_metadata(
    sample_recommendation,
    sync_group_context,
):
    """Test that propagation preserves and enhances metadata."""
    agent = TestAgent(agent_type=AgentType.CAMPAIGN_HEALTH)

    with patch("src.core.base_agent.SyncGroupResolver") as mock_resolver_class:
        mock_resolver = AsyncMock()
        mock_resolver_class.return_value = mock_resolver

        mock_resolver.resolve_entities_for_sync_group.return_value = [
            {
                "campaign_id": "124",
                "ad_group_id": "790",
                "geo": "UK",
            },
        ]

        propagated = await agent.propagate_to_sync_group(
            rec=sample_recommendation,
            sync_group_context=sync_group_context,
        )

        # Verify metadata
        clone = propagated[0]
        assert clone.metadata["propagated_from"] == str(sample_recommendation.id)
        assert clone.metadata["geo"] == "UK"
        assert clone.metadata["sync_group"] == "NonBrand_AI-Code"


@pytest.mark.asyncio
async def test_propagate_skips_non_propagatable_actions(
    sync_group_context,
):
    """Test that non-propagatable actions are not propagated."""
    agent = TestAgent(agent_type=AgentType.CAMPAIGN_HEALTH)

    # Create recommendation with non-propagatable action
    rec = Recommendation(
        agent_type=AgentType.CAMPAIGN_HEALTH,
        run_id=uuid4(),
        title="Test",
        description="Test",
        rationale="Test",
        impact_estimate="Test",
        risk_level="low",
        action_type="adjust_bid",  # Not in PROPAGATABLE_ACTIONS
        action_params={"campaign_id": "123"},
    )

    propagated = await agent.propagate_to_sync_group(
        rec=rec,
        sync_group_context=sync_group_context,
    )

    # Should return empty list
    assert len(propagated) == 0


@pytest.mark.asyncio
async def test_propagate_generates_unique_ids(
    sample_recommendation,
    sync_group_context,
):
    """Test that propagated recommendations get unique IDs."""
    agent = TestAgent(agent_type=AgentType.CAMPAIGN_HEALTH)

    with patch("src.core.base_agent.SyncGroupResolver") as mock_resolver_class:
        mock_resolver = AsyncMock()
        mock_resolver_class.return_value = mock_resolver

        mock_resolver.resolve_entities_for_sync_group.return_value = [
            {"campaign_id": "124", "ad_group_id": "790", "geo": "UK"},
            {"campaign_id": "125", "ad_group_id": "791", "geo": "DE"},
        ]

        propagated = await agent.propagate_to_sync_group(
            rec=sample_recommendation,
            sync_group_context=sync_group_context,
        )

        # All IDs should be unique
        ids = [rec.id for rec in propagated]
        assert len(ids) == len(set(ids))  # No duplicates

        # IDs should be different from original
        assert sample_recommendation.id not in ids


def test_propagatable_actions_defined():
    """Test that PROPAGATABLE_ACTIONS is defined on BaseAgent."""
    agent = TestAgent(agent_type=AgentType.CAMPAIGN_HEALTH)

    assert hasattr(agent, "PROPAGATABLE_ACTIONS")
    assert isinstance(agent.PROPAGATABLE_ACTIONS, set)
    assert "pause_ad_group" in agent.PROPAGATABLE_ACTIONS
