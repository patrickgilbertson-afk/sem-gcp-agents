"""Unit tests for guardrail service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.guardrails import GuardrailService, GuardrailViolation
from src.models.base import AgentType
from src.models.recommendation import Recommendation


@pytest.fixture
def mock_bq_client():
    """Mock BigQuery client."""
    client = AsyncMock()
    client.query = AsyncMock(return_value=[])
    return client


@pytest.fixture
def guardrail_service(mock_bq_client):
    """Create guardrail service with mocked dependencies."""
    return GuardrailService(bq_client=mock_bq_client)


@pytest.fixture
def sample_recommendations():
    """Create sample recommendations for testing."""
    return [
        Recommendation(
            agent_type=AgentType.CAMPAIGN_HEALTH,
            run_id="test-run-123",
            title="Test rec 1",
            description="Test",
            rationale="Test",
            impact_estimate="$100",
            risk_level="low",
            action_type="pause_ad_group",
            action_params={"campaign_id": "123", "ad_group_id": "456"},
        )
        for _ in range(5)
    ]


@pytest.mark.asyncio
async def test_validate_within_limits(guardrail_service, sample_recommendations):
    """Test validation passes when within all limits."""
    with patch("src.core.guardrails.settings") as mock_settings:
        mock_settings.kill_switch_enabled = False
        mock_settings.is_dry_run = False
        mock_settings.max_operations_per_run = 10000

        is_safe, violations = await guardrail_service.validate_before_apply(
            recommendations=sample_recommendations,
            agent_type=AgentType.CAMPAIGN_HEALTH,
        )

        assert is_safe is True
        assert len(violations) == 0


@pytest.mark.asyncio
async def test_validate_kill_switch_enabled(guardrail_service, sample_recommendations):
    """Test validation blocks when kill switch is enabled."""
    with patch("src.core.guardrails.settings") as mock_settings:
        mock_settings.kill_switch_enabled = True
        mock_settings.is_dry_run = False

        is_safe, violations = await guardrail_service.validate_before_apply(
            recommendations=sample_recommendations,
            agent_type=AgentType.CAMPAIGN_HEALTH,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].rule == "kill_switch"


@pytest.mark.asyncio
async def test_validate_dry_run_mode(guardrail_service, sample_recommendations):
    """Test validation blocks when dry run mode is enabled."""
    with patch("src.core.guardrails.settings") as mock_settings:
        mock_settings.kill_switch_enabled = False
        mock_settings.is_dry_run = True

        is_safe, violations = await guardrail_service.validate_before_apply(
            recommendations=sample_recommendations,
            agent_type=AgentType.CAMPAIGN_HEALTH,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].rule == "dry_run_mode"


@pytest.mark.asyncio
async def test_validate_exceeds_operation_limit(guardrail_service):
    """Test validation blocks when operation count exceeds limit."""
    # Create 101 recommendations (exceeds default limit of 100 for this test)
    many_recs = [
        Recommendation(
            agent_type=AgentType.CAMPAIGN_HEALTH,
            run_id="test-run-123",
            title=f"Test rec {i}",
            description="Test",
            rationale="Test",
            impact_estimate="$100",
            risk_level="low",
            action_type="pause_ad_group",
            action_params={"campaign_id": "123"},
        )
        for i in range(101)
    ]

    with patch("src.core.guardrails.settings") as mock_settings:
        mock_settings.kill_switch_enabled = False
        mock_settings.is_dry_run = False
        mock_settings.max_operations_per_run = 100

        is_safe, violations = await guardrail_service.validate_before_apply(
            recommendations=many_recs,
            agent_type=AgentType.CAMPAIGN_HEALTH,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].rule == "max_operations"


@pytest.mark.asyncio
async def test_validate_exceeds_spend_limit(guardrail_service):
    """Test validation blocks when spend impact exceeds limit."""
    # Create recommendations with high spend impact
    high_spend_recs = [
        Recommendation(
            agent_type=AgentType.CAMPAIGN_HEALTH,
            run_id="test-run-123",
            title="Test rec",
            description="Test",
            rationale="Test",
            impact_estimate="$100",
            risk_level="low",
            action_type="pause_ad_group",
            action_params={
                "campaign_id": "123",
                "spend_impact_estimate": 200,  # $200 impact
            },
        )
        for _ in range(5)
    ]

    with patch("src.core.guardrails.settings") as mock_settings:
        mock_settings.kill_switch_enabled = False
        mock_settings.is_dry_run = False
        mock_settings.max_operations_per_run = 10000
        mock_settings.max_daily_spend_increase_pct = 10.0  # 10% max

        # Total impact = $1000, daily spend = $5000 -> 20% impact (exceeds 10%)
        is_safe, violations = await guardrail_service.validate_before_apply(
            recommendations=high_spend_recs,
            agent_type=AgentType.CAMPAIGN_HEALTH,
            daily_spend=5000.0,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].rule == "max_daily_spend_increase"


@pytest.mark.asyncio
async def test_load_config_overrides(guardrail_service, mock_bq_client):
    """Test loading agent-specific config overrides from BigQuery."""
    # Mock config rows
    mock_bq_client.query.return_value = [
        {"config_key": "max_operations_per_run", "config_value": "5000"},
        {"config_key": "max_daily_spend_increase_pct", "config_value": "20.0"},
    ]

    config = await guardrail_service._load_config("campaign_health")

    assert config["max_operations_per_run"] == 5000
    assert config["max_daily_spend_increase_pct"] == 20.0


@pytest.mark.asyncio
async def test_load_config_fallback_on_error(guardrail_service, mock_bq_client):
    """Test config loading falls back gracefully on error."""
    # Mock query failure
    mock_bq_client.query.side_effect = Exception("BigQuery error")

    config = await guardrail_service._load_config("campaign_health")

    # Should return empty dict (falls back to settings defaults)
    assert config == {}


def test_guardrail_violation_to_dict():
    """Test GuardrailViolation serialization."""
    violation = GuardrailViolation(
        rule="test_rule",
        message="Test message",
        context={"foo": "bar"},
    )

    result = violation.to_dict()

    assert result["rule"] == "test_rule"
    assert result["message"] == "Test message"
    assert result["context"] == {"foo": "bar"}
