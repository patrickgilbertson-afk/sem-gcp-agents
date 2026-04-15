"""Parameterized SQL queries for BigQuery."""

# Campaign Health Queries

CAMPAIGN_HEALTH_METRICS = """
SELECT
    c.campaign_id,
    c.campaign_name,
    ag.ad_group_id,
    ag.ad_group_name,

    -- Current period metrics (last 30 days)
    SUM(s.impressions) as impressions,
    SUM(s.clicks) as clicks,
    SUM(s.cost_micros) / 1e6 as cost,
    SUM(s.conversions) as conversions,
    SUM(s.conversions_value) as conversion_value,

    -- Calculated metrics
    SAFE_DIVIDE(SUM(s.clicks), SUM(s.impressions)) as ctr,
    SAFE_DIVIDE(SUM(s.cost_micros) / 1e6, SUM(s.clicks)) as avg_cpc,
    SAFE_DIVIDE(SUM(s.conversions), SUM(s.clicks)) as conversion_rate,
    SAFE_DIVIDE(SUM(s.cost_micros) / 1e6, SUM(s.conversions)) as cost_per_conversion,
    SAFE_DIVIDE(SUM(s.conversions_value), SUM(s.cost_micros) / 1e6) as roas,

    -- Quality metrics
    AVG(kw.quality_score) as avg_quality_score,
    AVG(s.search_impression_share) as impression_share,
    AVG(s.search_rank_lost_impression_share) as impression_share_lost_to_rank,
    AVG(s.search_budget_lost_impression_share) as impression_share_lost_to_budget,

    -- Status
    c.status as campaign_status,
    ag.status as ad_group_status

FROM `{project_id}.{dataset}.campaign_{date_suffix}` c
JOIN `{project_id}.{dataset}.ad_group_{date_suffix}` ag
    ON c.campaign_id = ag.campaign_id
JOIN `{project_id}.{dataset}.ad_group_stats_{date_suffix}` s
    ON ag.ad_group_id = s.ad_group_id
LEFT JOIN `{project_id}.{dataset}.keyword_{date_suffix}` kw
    ON ag.ad_group_id = kw.ad_group_id

WHERE s.date BETWEEN @start_date AND @end_date
    AND c.customer_id = @customer_id

GROUP BY 1, 2, 3, 4, campaign_status, ad_group_status
HAVING SUM(s.impressions) > 100  -- Minimum traffic threshold
ORDER BY cost DESC
"""

# Keyword Queries

SEARCH_TERM_REPORT = """
SELECT
    st.search_term,
    st.campaign_id,
    st.ad_group_id,
    c.campaign_name,
    ag.ad_group_name,

    SUM(st.impressions) as impressions,
    SUM(st.clicks) as clicks,
    SUM(st.cost_micros) / 1e6 as cost,
    SUM(st.conversions) as conversions,
    SUM(st.conversions_value) as conversion_value,

    SAFE_DIVIDE(SUM(st.clicks), SUM(st.impressions)) as ctr,
    SAFE_DIVIDE(SUM(st.conversions), SUM(st.clicks)) as conversion_rate,
    SAFE_DIVIDE(SUM(st.cost_micros) / 1e6, SUM(st.conversions)) as cost_per_conversion,

    -- Matched keyword info
    kw.keyword_text as matched_keyword,
    kw.keyword_id as matched_keyword_id

FROM `{project_id}.{dataset}.search_term_view_{date_suffix}` st
JOIN `{project_id}.{dataset}.campaign_{date_suffix}` c
    ON st.campaign_id = c.campaign_id
JOIN `{project_id}.{dataset}.ad_group_{date_suffix}` ag
    ON st.ad_group_id = ag.ad_group_id
LEFT JOIN `{project_id}.{dataset}.keyword_{date_suffix}` kw
    ON st.ad_group_id = kw.ad_group_id

WHERE st.date BETWEEN @start_date AND @end_date
    AND c.customer_id = @customer_id

GROUP BY 1, 2, 3, 4, 5, matched_keyword, matched_keyword_id
HAVING SUM(st.impressions) > 10
ORDER BY cost DESC
LIMIT 10000
"""

KEYWORD_PERFORMANCE = """
SELECT
    kw.keyword_id,
    kw.keyword_text,
    kw.match_type,
    kw.status,
    kw.campaign_id,
    kw.ad_group_id,

    SUM(s.impressions) as impressions,
    SUM(s.clicks) as clicks,
    SUM(s.cost_micros) / 1e6 as cost,
    SUM(s.conversions) as conversions,
    SUM(s.conversions_value) as conversion_value,

    AVG(kw.quality_score) as quality_score,
    SAFE_DIVIDE(SUM(s.clicks), SUM(s.impressions)) as ctr,
    SAFE_DIVIDE(SUM(s.conversions), SUM(s.clicks)) as conversion_rate

FROM `{project_id}.{dataset}.keyword_{date_suffix}` kw
JOIN `{project_id}.{dataset}.keyword_stats_{date_suffix}` s
    ON kw.keyword_id = s.keyword_id

WHERE s.date BETWEEN @start_date AND @end_date
    AND kw.customer_id = @customer_id
    AND kw.status IN ('ENABLED', 'PAUSED')

GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY cost DESC
"""

# Ad Copy Queries

RSA_PERFORMANCE = """
SELECT
    ad.ad_id,
    ad.campaign_id,
    ad.ad_group_id,
    ad.type as ad_type,

    -- RSA assets
    ARRAY_AGG(STRUCT(
        ah.asset_field_type,
        ah.headline_text,
        ah.description_text
    )) as assets,

    -- Performance
    SUM(s.impressions) as impressions,
    SUM(s.clicks) as clicks,
    SUM(s.cost_micros) / 1e6 as cost,
    SUM(s.conversions) as conversions,
    SAFE_DIVIDE(SUM(s.clicks), SUM(s.impressions)) as ctr

FROM `{project_id}.{dataset}.ad_{date_suffix}` ad
JOIN `{project_id}.{dataset}.ad_stats_{date_suffix}` s
    ON ad.ad_id = s.ad_id
LEFT JOIN `{project_id}.{dataset}.ad_asset_headline_{date_suffix}` ah
    ON ad.ad_id = ah.ad_id

WHERE s.date BETWEEN @start_date AND @end_date
    AND ad.customer_id = @customer_id
    AND ad.type = 'RESPONSIVE_SEARCH_AD'

GROUP BY 1, 2, 3, 4
ORDER BY cost DESC
"""

# Bid Modifier Queries

BID_MODIFIER_PERFORMANCE = """
SELECT
    bm.campaign_id,
    bm.criterion_id,
    bm.bid_modifier_source,
    bm.bid_modifier,

    -- Segment performance
    SUM(s.impressions) as impressions,
    SUM(s.clicks) as clicks,
    SUM(s.cost_micros) / 1e6 as cost,
    SUM(s.conversions) as conversions,
    SAFE_DIVIDE(SUM(s.conversions), SUM(s.clicks)) as conversion_rate,
    SAFE_DIVIDE(SUM(s.cost_micros) / 1e6, SUM(s.conversions)) as cost_per_conversion

FROM `{project_id}.{dataset}.campaign_criterion_{date_suffix}` bm
JOIN `{project_id}.{dataset}.campaign_criterion_stats_{date_suffix}` s
    ON bm.criterion_id = s.criterion_id

WHERE s.date BETWEEN @start_date AND @end_date
    AND bm.customer_id = @customer_id
    AND bm.status = 'ENABLED'

GROUP BY 1, 2, 3, 4
HAVING SUM(s.clicks) > 100  -- Minimum clicks for statistical significance
ORDER BY cost DESC
"""
