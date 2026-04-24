"""BigQuery queries for Google Analytics 4 data integration."""

from typing import Any

from src.config import settings


def GA4_CAMPAIGN_EVENTS(
    start_date: str,
    end_date: str,
    campaign_filter: str | None = None,
) -> str:
    """Query GA4 events joined with Google Ads campaign data.

    Joins GA4 events table with Google Ads campaigns via UTM parameters
    (source/medium/campaign). Pulls session-level and event-level metrics.

    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        campaign_filter: Optional campaign name filter

    Returns:
        SQL query string
    """
    campaign_clause = ""
    if campaign_filter:
        campaign_clause = f"AND traffic_source.medium = 'cpc' AND traffic_source.campaign LIKE '%{campaign_filter}%'"

    return f"""
    WITH ga4_sessions AS (
        SELECT
            traffic_source.source,
            traffic_source.medium,
            traffic_source.campaign,
            user_pseudo_id,
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
            COUNT(DISTINCT event_name) AS unique_events,
            COUNTIF(event_name = 'session_start') AS sessions,
            COUNTIF(event_name = 'page_view') AS page_views,
            -- Key conversions (actual event names from your GA4 setup)
            COUNTIF(event_name IN (
                'sc_org_create',        -- SQC Org Create (PRIMARY)
                'sc_new_signup',        -- New signups
                'sc_trial_upgrade',     -- Trial upgrades
                'submittedForm',        -- Form submissions
                'sq_download',          -- Downloads
                'form_submit'           -- Alternative form completion
            )) AS conversions,
            AVG((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec')) / 1000.0 AS avg_engagement_time_sec,
            COUNTIF(
                (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') > 0
            ) AS engaged_sessions,
            -- Engaged visitors (custom high-value engagement metric)
            COUNTIF(event_name = 'engaged_visitor_2025') AS engaged_visitors
        FROM `{settings.gcp_project_id}.{settings.ga4_dataset}.events_*`
        WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE(@start_date))
        AND FORMAT_DATE('%Y%m%d', DATE(@end_date))
        AND traffic_source.source = 'google'
        {campaign_clause}
        GROUP BY
            traffic_source.source,
            traffic_source.medium,
            traffic_source.campaign,
            user_pseudo_id,
            session_id
    )
    SELECT
        campaign AS campaign_name,
        COUNT(DISTINCT user_pseudo_id) AS users,
        SUM(sessions) AS sessions,
        SUM(page_views) AS page_views,
        SUM(conversions) AS conversions,
        SUM(engaged_visitors) AS engaged_visitors,
        AVG(avg_engagement_time_sec) AS avg_engagement_time_sec,
        SAFE_DIVIDE(SUM(engaged_sessions), SUM(sessions)) AS engagement_rate,
        SAFE_DIVIDE(SUM(conversions), SUM(sessions)) AS conversion_rate_ga4,
        SAFE_DIVIDE(SUM(engaged_visitors), COUNT(DISTINCT user_pseudo_id)) AS engaged_visitor_rate
    FROM ga4_sessions
    WHERE campaign IS NOT NULL
    GROUP BY campaign
    ORDER BY sessions DESC
    """


def GA4_CONVERSION_BY_GOAL(
    start_date: str,
    end_date: str,
    conversion_goal: str | None = None,
) -> str:
    """Query GA4 conversions aggregated by campaign and event name.

    This powers conversion-goal-aware optimization (e.g., filter for
    event_name = 'sqc_org_create').

    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        conversion_goal: Optional conversion event name filter

    Returns:
        SQL query string
    """
    event_filter = ""
    if conversion_goal:
        event_filter = f"AND event_name = '{conversion_goal}'"

    return f"""
    SELECT
        traffic_source.campaign AS campaign_name,
        event_name,
        COUNT(*) AS conversion_count,
        COUNT(DISTINCT user_pseudo_id) AS converting_users,
        SUM((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value')) AS conversion_value
    FROM `{settings.gcp_project_id}.{settings.ga4_dataset}.events_*`
    WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE(@start_date))
    AND FORMAT_DATE('%Y%m%d', DATE(@end_date))
    AND traffic_source.source = 'google'
    AND traffic_source.medium = 'cpc'
    AND event_name IN (
        -- Key conversion events (marked as key events in GA4)
        'sc_org_create',        -- SQC Org Create (PRIMARY - 484/day)
        'sc_new_signup',        -- New signups (859/day)
        'sc_trial_upgrade',     -- Trial upgrades (57/day)
        'submittedForm',        -- Form submissions (222/day)
        'sq_download',          -- Downloads (173/day)
        'engaged_visitor_2025', -- High-value engagement (13,044/day)
        -- Supporting events
        'form_submit',          -- Alternative form completion (16,475/day)
        'sc_signup_clicks'      -- Signup click tracking (586/day)
    )
    {event_filter}
    GROUP BY
        traffic_source.campaign,
        event_name
    ORDER BY
        conversion_count DESC
    """


async def get_ga4_campaign_metrics(
    bq_client: Any,
    start_date: str,
    end_date: str,
    campaign_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch GA4 campaign metrics.

    Args:
        bq_client: BigQuery client
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        campaign_filter: Optional campaign name filter

    Returns:
        List of campaign metrics from GA4
    """
    # Check if GA4 dataset is configured
    if not settings.ga4_dataset:
        return []

    sql = GA4_CAMPAIGN_EVENTS(start_date, end_date, campaign_filter)

    try:
        rows = await bq_client.query(
            sql,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return rows
    except Exception:
        # GA4 integration is optional - fail gracefully
        return []


async def get_ga4_conversions_by_goal(
    bq_client: Any,
    start_date: str,
    end_date: str,
    conversion_goal: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch GA4 conversion data by goal.

    Args:
        bq_client: BigQuery client
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        conversion_goal: Optional conversion event name filter

    Returns:
        List of conversion data by campaign and event
    """
    # Check if GA4 dataset is configured
    if not settings.ga4_dataset:
        return []

    sql = GA4_CONVERSION_BY_GOAL(start_date, end_date, conversion_goal)

    try:
        rows = await bq_client.query(
            sql,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return rows
    except Exception:
        # GA4 integration is optional - fail gracefully
        return []
