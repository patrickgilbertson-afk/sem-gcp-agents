"""Unit tests for weekly report service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.services.weekly_report import WeeklyReportService


@pytest.fixture
def mock_bq_client():
    """Mock BigQuery client."""
    client = AsyncMock()
    client.query = AsyncMock()
    return client


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="Test executive summary. Overall CPA improved by 8%.")
    return llm


@pytest.fixture
def weekly_report_service(mock_bq_client, mock_llm):
    """Create weekly report service with mocked dependencies."""
    with patch("src.services.weekly_report.AnthropicClient", return_value=mock_llm):
        service = WeeklyReportService(bq_client=mock_bq_client)
        return service


@pytest.fixture
def sample_recommendations():
    """Sample recommendation data from BigQuery."""
    return [
        {
            "id": "rec-1",
            "run_id": "run-123",
            "agent_type": "campaign_health",
            "title": "Pause ad group: broad_generic_terms",
            "description": "Spent $200 with zero conversions",
            "action_type": "pause_ad_group",
            "status": "applied",
            "approval_status": "approved",
            "created_at": "2024-04-20T10:00:00",
            "approved_at": "2024-04-20T11:00:00",
            "applied_at": "2024-04-20T11:05:00",
            "metadata": json.dumps({
                "sync_group": "NonBrand_AI-Code",
                "management_strategy": "synced",
                "geo": "US",
            }),
        },
        {
            "id": "rec-2",
            "run_id": "run-123",
            "agent_type": "campaign_health",
            "title": "Review keywords in: ai_coding_tools",
            "description": "Average quality score: 4.2",
            "action_type": "delegate_keyword_review",
            "status": "applied",
            "approval_status": "approved",
            "created_at": "2024-04-21T10:00:00",
            "approved_at": "2024-04-21T11:00:00",
            "applied_at": "2024-04-21T11:05:00",
            "metadata": json.dumps({
                "sync_group": "NonBrand_AI-Code",
                "management_strategy": "synced",
                "geo": "UK",
            }),
        },
    ]


@pytest.fixture
def sample_performance_data():
    """Sample performance metrics from BigQuery."""
    return [
        {
            "recommendation_id": "rec-1",
            "metric_name": "cost",
            "before_value": 200.0,
            "after_value": 0.0,
            "change_value": -200.0,
            "change_percent": -100.0,
        },
        {
            "recommendation_id": "rec-1",
            "metric_name": "conversions",
            "before_value": 0.0,
            "after_value": 0.0,
            "change_value": 0.0,
            "change_percent": 0.0,
        },
        {
            "recommendation_id": "rec-1",
            "metric_name": "cpa",
            "before_value": 0.0,
            "after_value": 0.0,
            "change_value": 0.0,
            "change_percent": 0.0,
        },
    ]


@pytest.mark.asyncio
async def test_generate_report_basic(
    weekly_report_service,
    mock_bq_client,
    sample_recommendations,
    sample_performance_data,
):
    """Test basic report generation."""
    # Mock BigQuery queries
    mock_bq_client.query.side_effect = [
        sample_recommendations,  # Recommendations query
        sample_performance_data,  # Performance query
    ]

    report = await weekly_report_service.generate_report(days_back=7)

    assert report["total_optimizations"] == 2
    assert len(report["sync_group_reports"]) > 0
    assert "executive_summary" in report


@pytest.mark.asyncio
async def test_generate_report_no_recommendations(weekly_report_service, mock_bq_client):
    """Test report generation when no recommendations exist."""
    mock_bq_client.query.return_value = []  # No recommendations

    report = await weekly_report_service.generate_report(days_back=7)

    assert report["total_optimizations"] == 0
    assert report["sync_group_reports"] == []
    assert report["executive_summary"] == "No optimizations were applied this week."


@pytest.mark.asyncio
async def test_sync_group_grouping(
    weekly_report_service,
    mock_bq_client,
    sample_recommendations,
    sample_performance_data,
):
    """Test that recommendations are correctly grouped by sync group."""
    mock_bq_client.query.side_effect = [
        sample_recommendations,
        sample_performance_data,
    ]

    report = await weekly_report_service.generate_report(days_back=7)

    # Should have one sync group report for "NonBrand_AI-Code"
    assert len(report["sync_group_reports"]) == 1
    sync_group_report = report["sync_group_reports"][0]

    assert sync_group_report["sync_group"] == "NonBrand_AI-Code"
    assert sync_group_report["optimization_count"] == 2


@pytest.mark.asyncio
async def test_performance_aggregation(
    weekly_report_service,
    mock_bq_client,
    sample_recommendations,
):
    """Test performance metric aggregation."""
    # Create performance data with meaningful metrics
    performance_data = [
        # rec-1
        {"recommendation_id": "rec-1", "metric_name": "cost", "before_value": 100.0, "after_value": 80.0, "change_value": -20.0, "change_percent": -20.0},
        {"recommendation_id": "rec-1", "metric_name": "conversions", "before_value": 5.0, "after_value": 6.0, "change_value": 1.0, "change_percent": 20.0},
        {"recommendation_id": "rec-1", "metric_name": "clicks", "before_value": 100.0, "after_value": 110.0, "change_value": 10.0, "change_percent": 10.0},
        {"recommendation_id": "rec-1", "metric_name": "impressions", "before_value": 1000.0, "after_value": 1100.0, "change_value": 100.0, "change_percent": 10.0},
        # rec-2
        {"recommendation_id": "rec-2", "metric_name": "cost", "before_value": 200.0, "after_value": 180.0, "change_value": -20.0, "change_percent": -10.0},
        {"recommendation_id": "rec-2", "metric_name": "conversions", "before_value": 10.0, "after_value": 12.0, "change_value": 2.0, "change_percent": 20.0},
        {"recommendation_id": "rec-2", "metric_name": "clicks", "before_value": 200.0, "after_value": 220.0, "change_value": 20.0, "change_percent": 10.0},
        {"recommendation_id": "rec-2", "metric_name": "impressions", "before_value": 2000.0, "after_value": 2200.0, "change_value": 200.0, "change_percent": 10.0},
    ]

    mock_bq_client.query.side_effect = [
        sample_recommendations,
        performance_data,
    ]

    report = await weekly_report_service.generate_report(days_back=7)

    sync_group_report = report["sync_group_reports"][0]
    perf = sync_group_report["performance"]

    # Check aggregated CPA calculation
    # Total cost before: 100 + 200 = 300
    # Total cost after: 80 + 180 = 260
    # Total conversions before: 5 + 10 = 15
    # Total conversions after: 6 + 12 = 18
    # CPA before: 300/15 = 20.0
    # CPA after: 260/18 = 14.44
    # Change: (14.44 - 20) / 20 * 100 = -27.78%

    assert perf["cpa"]["before"] == pytest.approx(20.0, rel=0.01)
    assert perf["cpa"]["after"] == pytest.approx(14.44, rel=0.01)
    assert perf["cpa"]["change_pct"] < 0  # Should be improvement


@pytest.mark.asyncio
async def test_executive_summary_generation(
    weekly_report_service,
    mock_bq_client,
    mock_llm,
    sample_recommendations,
    sample_performance_data,
):
    """Test executive summary generation with LLM."""
    mock_bq_client.query.side_effect = [
        sample_recommendations,
        sample_performance_data,
    ]

    report = await weekly_report_service.generate_report(days_back=7)

    # Verify LLM was called to generate summary
    mock_llm.generate.assert_called_once()

    # Verify summary is in report
    assert report["executive_summary"] == "Test executive summary. Overall CPA improved by 8%."


@pytest.mark.asyncio
async def test_build_summary_prompt(weekly_report_service):
    """Test summary prompt building."""
    sync_group_reports = [
        {
            "sync_group": "NonBrand_AI-Code",
            "optimization_count": 5,
            "performance": {
                "cpa": {"before": 50.0, "after": 40.0, "change_pct": -20.0},
                "ctr": {"before": 0.02, "after": 0.025, "change_pct": 25.0},
            },
        },
        {
            "sync_group": "Brand_Core",
            "optimization_count": 3,
            "performance": {
                "cpa": {"before": 30.0, "after": 28.0, "change_pct": -6.7},
                "ctr": {"before": 0.15, "after": 0.16, "change_pct": 6.7},
            },
        },
    ]

    prompt = weekly_report_service._build_summary_prompt(sync_group_reports, 8)

    assert "8" in prompt  # Total optimizations
    assert "NonBrand_AI-Code" in prompt
    assert "Brand_Core" in prompt
    assert "-20.0%" in prompt  # CPA change
    assert "2-3 sentences" in prompt
