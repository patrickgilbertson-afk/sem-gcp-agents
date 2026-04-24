"""Unit tests for analytics queries."""

import pytest
from unittest.mock import AsyncMock, patch

from src.integrations.bigquery.analytics_queries import (
    GA4_CAMPAIGN_EVENTS,
    GA4_CONVERSION_BY_GOAL,
    get_ga4_campaign_metrics,
    get_ga4_conversions_by_goal,
)


def test_ga4_campaign_events_query():
    """Test GA4 campaign events query generation."""
    sql = GA4_CAMPAIGN_EVENTS(
        start_date="2024-04-01",
        end_date="2024-04-07",
    )

    assert "events_*" in sql
    assert "@start_date" in sql
    assert "@end_date" in sql
    assert "traffic_source.campaign" in sql
    assert "engagement_rate" in sql


def test_ga4_campaign_events_with_filter():
    """Test GA4 query with campaign filter."""
    sql = GA4_CAMPAIGN_EVENTS(
        start_date="2024-04-01",
        end_date="2024-04-07",
        campaign_filter="NonBrand",
    )

    assert "NonBrand" in sql
    assert "traffic_source.campaign LIKE" in sql


def test_ga4_conversion_by_goal_query():
    """Test GA4 conversion by goal query generation."""
    sql = GA4_CONVERSION_BY_GOAL(
        start_date="2024-04-01",
        end_date="2024-04-07",
    )

    assert "events_*" in sql
    assert "event_name" in sql
    assert "conversion_count" in sql
    assert "converting_users" in sql


def test_ga4_conversion_by_goal_with_filter():
    """Test GA4 conversion query with goal filter."""
    sql = GA4_CONVERSION_BY_GOAL(
        start_date="2024-04-01",
        end_date="2024-04-07",
        conversion_goal="sqc_org_create",
    )

    assert "sqc_org_create" in sql
    assert "event_name =" in sql


@pytest.mark.asyncio
async def test_get_ga4_campaign_metrics():
    """Test fetching GA4 campaign metrics."""
    mock_client = AsyncMock()
    mock_client.query = AsyncMock(return_value=[
        {
            "campaign_name": "NonBrand_AI-Code_US",
            "users": 1000,
            "sessions": 1500,
            "page_views": 5000,
            "conversions": 50,
            "engaged_visitors": 300,
            "engagement_rate": 0.75,
            "engaged_visitor_rate": 0.30,
            "conversion_rate_ga4": 0.033,
            "avg_engagement_time_sec": 120.5,
        }
    ])

    with patch("src.integrations.bigquery.analytics_queries.settings") as mock_settings:
        mock_settings.ga4_dataset = "analytics_123456"

        results = await get_ga4_campaign_metrics(
            bq_client=mock_client,
            start_date="2024-04-01",
            end_date="2024-04-07",
        )

        assert len(results) == 1
        assert results[0]["campaign_name"] == "NonBrand_AI-Code_US"
        assert results[0]["users"] == 1000


@pytest.mark.asyncio
async def test_get_ga4_metrics_no_dataset_configured():
    """Test GA4 metrics fetch when dataset not configured."""
    mock_client = AsyncMock()

    with patch("src.integrations.bigquery.analytics_queries.settings") as mock_settings:
        mock_settings.ga4_dataset = ""  # Not configured

        results = await get_ga4_campaign_metrics(
            bq_client=mock_client,
            start_date="2024-04-01",
            end_date="2024-04-07",
        )

        # Should return empty list without querying
        assert results == []
        mock_client.query.assert_not_called()


@pytest.mark.asyncio
async def test_get_ga4_metrics_query_error():
    """Test GA4 metrics fetch handles query errors gracefully."""
    mock_client = AsyncMock()
    mock_client.query = AsyncMock(side_effect=Exception("BigQuery error"))

    with patch("src.integrations.bigquery.analytics_queries.settings") as mock_settings:
        mock_settings.ga4_dataset = "analytics_123456"

        results = await get_ga4_campaign_metrics(
            bq_client=mock_client,
            start_date="2024-04-01",
            end_date="2024-04-07",
        )

        # Should fail gracefully and return empty list
        assert results == []


@pytest.mark.asyncio
async def test_get_ga4_conversions_by_goal():
    """Test fetching GA4 conversions by goal."""
    mock_client = AsyncMock()
    mock_client.query = AsyncMock(return_value=[
        {
            "campaign_name": "NonBrand_AI-Code_US",
            "event_name": "sc_org_create",
            "conversion_count": 25,
            "converting_users": 20,
            "conversion_value": 2500.0,
        }
    ])

    with patch("src.integrations.bigquery.analytics_queries.settings") as mock_settings:
        mock_settings.ga4_dataset = "analytics_123456"

        results = await get_ga4_conversions_by_goal(
            bq_client=mock_client,
            start_date="2024-04-01",
            end_date="2024-04-07",
            conversion_goal="sc_org_create",
        )

        assert len(results) == 1
        assert results[0]["event_name"] == "sc_org_create"
        assert results[0]["conversion_count"] == 25


@pytest.mark.asyncio
async def test_get_ga4_conversions_no_dataset():
    """Test GA4 conversions fetch when dataset not configured."""
    mock_client = AsyncMock()

    with patch("src.integrations.bigquery.analytics_queries.settings") as mock_settings:
        mock_settings.ga4_dataset = ""

        results = await get_ga4_conversions_by_goal(
            bq_client=mock_client,
            start_date="2024-04-01",
            end_date="2024-04-07",
        )

        assert results == []
        mock_client.query.assert_not_called()


def test_query_contains_expected_conversion_events():
    """Test that conversion query includes expected event types."""
    sql = GA4_CONVERSION_BY_GOAL(
        start_date="2024-04-01",
        end_date="2024-04-07",
    )

    # Should include these conversion events (actual GA4 event names)
    assert "sc_org_create" in sql  # SQC Org Create (PRIMARY)
    assert "sc_new_signup" in sql  # New signups
    assert "sc_trial_upgrade" in sql  # Trial upgrades
    assert "submittedForm" in sql  # Form submissions
    assert "sq_download" in sql  # Downloads
    assert "engaged_visitor_2025" in sql  # High-value engagement
    assert "form_submit" in sql  # Alternative form completion
    assert "sc_signup_clicks" in sql  # Signup clicks
