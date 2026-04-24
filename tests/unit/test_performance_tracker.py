"""Unit tests for performance tracker service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.services.performance_tracker import PerformanceTracker


@pytest.fixture
def mock_bq_client():
    """Mock BigQuery client."""
    client = AsyncMock()
    client.query = AsyncMock()
    client.insert_rows = AsyncMock()
    return client


@pytest.fixture
def performance_tracker(mock_bq_client):
    """Create performance tracker with mocked dependencies."""
    return PerformanceTracker(bq_client=mock_bq_client)


@pytest.mark.asyncio
async def test_record_baseline_campaign_level(performance_tracker, mock_bq_client):
    """Test recording baseline metrics at campaign level."""
    # Mock metrics query result
    mock_bq_client.query.return_value = [
        {
            "impressions": 1000,
            "clicks": 50,
            "cost": 100.0,
            "conversions": 5,
            "conversion_value": 500.0,
        }
    ]

    await performance_tracker.record_baseline(
        recommendation_id="rec-123",
        campaign_id="camp-456",
    )

    # Verify insert_rows was called with baseline metrics
    mock_bq_client.insert_rows.assert_called_once()
    call_args = mock_bq_client.insert_rows.call_args
    rows = call_args[0][1]  # Second argument is the rows list

    # Should have 7 metrics (impressions, clicks, cost, conversions, ctr, cpc, cpa)
    assert len(rows) == 7

    # Verify each metric has recommendation_id and before_value
    for row in rows:
        assert row["recommendation_id"] == "rec-123"
        assert "before_value" in row
        assert "baseline_recorded_at" in row


@pytest.mark.asyncio
async def test_record_baseline_ad_group_level(performance_tracker, mock_bq_client):
    """Test recording baseline metrics at ad group level."""
    mock_bq_client.query.return_value = [
        {
            "impressions": 500,
            "clicks": 25,
            "cost": 50.0,
            "conversions": 2,
            "conversion_value": 200.0,
        }
    ]

    await performance_tracker.record_baseline(
        recommendation_id="rec-123",
        campaign_id="camp-456",
        ad_group_id="ag-789",
    )

    # Verify ad group query was used
    mock_bq_client.query.assert_called_once()
    call_args = mock_bq_client.query.call_args
    sql = call_args[0][0]  # First argument is SQL
    params = call_args[0][1]  # Second argument is params

    assert "ad_group_stats" in sql
    assert params["ad_group_id"] == "ag-789"


@pytest.mark.asyncio
async def test_record_baseline_no_data(performance_tracker, mock_bq_client):
    """Test baseline recording when no data is found."""
    mock_bq_client.query.return_value = []  # No data

    # Should not raise, just log warning
    await performance_tracker.record_baseline(
        recommendation_id="rec-123",
        campaign_id="camp-456",
    )

    # insert_rows should not be called
    mock_bq_client.insert_rows.assert_not_called()


@pytest.mark.asyncio
async def test_record_outcome(performance_tracker, mock_bq_client):
    """Test recording outcome metrics after application."""
    # Mock current metrics query
    mock_bq_client.query.side_effect = [
        # First call: current metrics
        [
            {
                "impressions": 1200,
                "clicks": 60,
                "cost": 110.0,
                "conversions": 7,
                "conversion_value": 700.0,
            }
        ],
        # Subsequent calls: baseline queries for each metric
        [{"before_value": 1000}],  # impressions
        [{"before_value": 50}],  # clicks
        [{"before_value": 100.0}],  # cost
        [{"before_value": 5}],  # conversions
        [{"before_value": 0.05}],  # ctr
        [{"before_value": 2.0}],  # cpc
        [{"before_value": 20.0}],  # cpa
    ]

    await performance_tracker.record_outcome(
        recommendation_id="rec-123",
        campaign_id="camp-456",
        days_after=7,
    )

    # Verify multiple queries were made (metrics + baselines)
    assert mock_bq_client.query.call_count >= 2


@pytest.mark.asyncio
async def test_record_outcome_no_baseline(performance_tracker, mock_bq_client):
    """Test outcome recording when baseline doesn't exist."""
    # Mock current metrics query
    mock_bq_client.query.side_effect = [
        # First call: current metrics
        [
            {
                "impressions": 1200,
                "clicks": 60,
                "cost": 110.0,
                "conversions": 7,
                "conversion_value": 700.0,
            }
        ],
        # Subsequent calls: no baseline found
        [],  # impressions baseline
        [],  # clicks baseline
        # ...etc
    ]

    # Should not raise, just skip metrics without baseline
    await performance_tracker.record_outcome(
        recommendation_id="rec-123",
        campaign_id="camp-456",
    )


@pytest.mark.asyncio
async def test_derived_metrics_calculation(performance_tracker, mock_bq_client):
    """Test that derived metrics (CTR, CPC, CPA) are calculated correctly."""
    mock_bq_client.query.return_value = [
        {
            "impressions": 1000,
            "clicks": 50,  # CTR = 0.05 (5%)
            "cost": 100.0,  # CPC = $2.00
            "conversions": 5,  # CPA = $20.00
            "conversion_value": 500.0,
        }
    ]

    await performance_tracker.record_baseline(
        recommendation_id="rec-123",
        campaign_id="camp-456",
    )

    # Get the inserted rows
    rows = mock_bq_client.insert_rows.call_args[0][1]

    # Find CTR, CPC, CPA metrics
    ctr_row = next(r for r in rows if r["metric_name"] == "ctr")
    cpc_row = next(r for r in rows if r["metric_name"] == "cpc")
    cpa_row = next(r for r in rows if r["metric_name"] == "cpa")

    assert ctr_row["before_value"] == pytest.approx(0.05)  # 50/1000
    assert cpc_row["before_value"] == pytest.approx(2.0)  # 100/50
    assert cpa_row["before_value"] == pytest.approx(20.0)  # 100/5


@pytest.mark.asyncio
async def test_error_handling(performance_tracker, mock_bq_client):
    """Test error handling during baseline recording."""
    # Mock query failure
    mock_bq_client.query.side_effect = Exception("BigQuery error")

    # Should not raise, just log error (best-effort)
    await performance_tracker.record_baseline(
        recommendation_id="rec-123",
        campaign_id="camp-456",
    )

    # insert_rows should not be called
    mock_bq_client.insert_rows.assert_not_called()
