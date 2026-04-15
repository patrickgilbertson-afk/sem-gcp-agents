# Gemini SQL Prompt Library

A collection of effective prompts for using Gemini to generate BigQuery SQL queries for the SEM GCP Agents system.

## Table of Contents
- [Prompt Engineering Principles](#prompt-engineering-principles)
- [Schema Context Templates](#schema-context-templates)
- [Agent Query Prompts](#agent-query-prompts)
- [Performance Analysis Prompts](#performance-analysis-prompts)
- [Quality Score Analysis Prompts](#quality-score-analysis-prompts)
- [Sync Group Analysis Prompts](#sync-group-analysis-prompts)
- [Audit & Monitoring Prompts](#audit--monitoring-prompts)
- [Optimization Tips](#optimization-tips)

---

## Prompt Engineering Principles

### Structure for Effective SQL Generation

```
[ROLE] You are an expert BigQuery SQL developer for Google Ads analytics.

[CONTEXT] I'm working with the following BigQuery datasets:
- google_ads_raw: Contains Google Ads Data Transfer tables (campaigns, keywords, ads, search terms)
- sem_agents: Contains agent configuration, recommendations, and audit logs

[SCHEMA] Here are the relevant table schemas:
[Include specific table schemas needed for the query]

[TASK] Write a SQL query to [specific objective]

[REQUIREMENTS]
- Use standard SQL (not legacy)
- Optimize for performance (use partitioning/clustering where available)
- Include comments explaining complex logic
- Handle NULL values appropriately
- Use meaningful column aliases

[CONSTRAINTS]
- Data date range: [specify]
- Filter criteria: [specify]
- Aggregation level: [campaign/ad_group/keyword]

[OUTPUT FORMAT]
Provide the complete SQL query with:
1. A brief explanation of what it does
2. The query itself
3. Sample expected output structure
```

---

## Schema Context Templates

### Template 1: Google Ads Performance Data

```markdown
SCHEMA CONTEXT:

Table: google_ads_raw.p_ads_Campaign_{CUSTOMER_ID}
Fields:
- campaign_id (STRING): Unique campaign identifier
- campaign_name (STRING): Campaign name
- campaign_status (STRING): ENABLED, PAUSED, REMOVED
- date (DATE): Performance date
- impressions (INT64): Number of impressions
- clicks (INT64): Number of clicks
- cost_micros (INT64): Cost in micros (divide by 1,000,000 for dollars)
- conversions (FLOAT64): Number of conversions
- conversions_value (FLOAT64): Total conversion value
- average_cpc (INT64): Avg CPC in micros
- ctr (FLOAT64): Click-through rate (0.05 = 5%)

Partitioning: By date
Clustering: By campaign_id
```

### Template 2: Keyword Performance & Quality Score

```markdown
SCHEMA CONTEXT:

Table: google_ads_raw.p_ads_KeywordView_{CUSTOMER_ID}
Fields:
- keyword_id (STRING): Unique keyword identifier
- ad_group_id (STRING): Parent ad group ID
- campaign_id (STRING): Parent campaign ID
- keyword_text (STRING): The keyword text
- match_type (STRING): EXACT, PHRASE, BROAD
- quality_score (INT64): 1-10 or NULL
- quality_score_expected_ctr (STRING): BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE
- quality_score_ad_relevance (STRING): BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE
- quality_score_landing_page (STRING): BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE
- date (DATE): Performance date
- impressions (INT64)
- clicks (INT64)
- cost_micros (INT64)
- conversions (FLOAT64)

Partitioning: By date
Clustering: By campaign_id, ad_group_id
```

### Template 3: Search Term Report

```markdown
SCHEMA CONTEXT:

Table: google_ads_raw.p_ads_SearchTermView_{CUSTOMER_ID}
Fields:
- search_term (STRING): User's actual search query
- keyword_id (STRING): Matched keyword ID
- keyword_text (STRING): Matched keyword text
- match_type (STRING): How keyword matched (EXACT, PHRASE, BROAD)
- campaign_id (STRING)
- ad_group_id (STRING)
- date (DATE)
- impressions (INT64)
- clicks (INT64)
- cost_micros (INT64)
- conversions (FLOAT64)
- ctr (FLOAT64)

Use Case: Identify negative keyword opportunities and keyword expansion ideas
```

### Template 4: Agent Tables

```markdown
SCHEMA CONTEXT:

Table: sem_agents.agent_recommendations
Fields:
- recommendation_id (STRING)
- agent_type (STRING): campaign_health, keyword, ad_copy, bid_modifier
- run_id (STRING)
- entity_type (STRING): campaign, ad_group, keyword, ad
- entity_id (STRING): Google Ads resource name
- entity_name (STRING)
- recommendation_type (STRING): pause_ad_group, add_negative_keyword, etc.
- recommendation_data (JSON): Action-specific data
- confidence_score (FLOAT64): 0.0 to 1.0
- reasoning (TEXT): LLM explanation
- created_at (TIMESTAMP)
- approval_status (STRING): pending, approved, rejected, expired, applied, failed
- executed_at (TIMESTAMP)
- sync_group_id (STRING)

Table: sem_agents.campaign_taxonomy
Fields:
- campaign_id (STRING)
- campaign_name (STRING)
- campaign_type (STRING): brand, nonbrand, competitor
- intent_category (STRING): ai_code, ai_chat, alternatives, etc.
- geo (STRING): US, UK, DE, FR
- sync_group_id (STRING)
- sync_group_role (STRING): template, replica, individual
- management_strategy (STRING): synced, individual
```

---

## Agent Query Prompts

### 1. Campaign Health Agent - Underperforming Campaigns

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: I need to identify underperforming campaigns for the Campaign Health Agent to analyze.

SCHEMA: [Include Template 1: Google Ads Performance Data]

TASK: Write a SQL query to identify campaigns that meet ANY of these criteria over the last 30 days:
1. Average Quality Score < 5
2. Zero conversions
3. CTR < 2%
4. Cost per conversion > $100
5. Impression share < 50%

REQUIREMENTS:
- Aggregate data by campaign_id and campaign_name
- Include last 30 days of data
- Calculate key metrics: total impressions, clicks, conversions, cost, CTR, CPC
- Flag which criteria triggered the alert (use a flagging column)
- Order by severity (campaigns meeting multiple criteria first)
- Exclude campaigns with < 1000 impressions (not enough data)

OUTPUT: Return campaign_id, campaign_name, metrics, and alert_reasons (array of triggered criteria)
```

**Expected Gemini Output Pattern:**
```sql
-- Identify underperforming campaigns for Campaign Health Agent
-- Checks multiple health criteria over 30-day window

WITH campaign_metrics AS (
  SELECT
    campaign_id,
    campaign_name,
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    SUM(conversions) AS total_conversions,
    SUM(cost_micros) / 1e6 AS total_cost_usd,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(cost_micros) / 1e6, SUM(conversions)) AS cost_per_conversion,
    AVG(quality_score) AS avg_quality_score
  FROM `google_ads_raw.p_ads_Campaign_1234567890`
  WHERE
    date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
    AND campaign_status = 'ENABLED'
  GROUP BY campaign_id, campaign_name
  HAVING total_impressions >= 1000  -- Minimum data threshold
),

flagged_campaigns AS (
  SELECT
    *,
    ARRAY_CONCAT_AGG([
      IF(avg_quality_score < 5, 'Low Quality Score', NULL),
      IF(total_conversions = 0, 'Zero Conversions', NULL),
      IF(ctr < 0.02, 'Low CTR', NULL),
      IF(cost_per_conversion > 100, 'High CPA', NULL)
    ]) AS alert_reasons,
    -- Count how many criteria triggered
    (CAST(avg_quality_score < 5 AS INT64) +
     CAST(total_conversions = 0 AS INT64) +
     CAST(ctr < 0.02 AS INT64) +
     CAST(cost_per_conversion > 100 AS INT64)) AS severity_score
  FROM campaign_metrics
)

SELECT
  campaign_id,
  campaign_name,
  total_impressions,
  total_clicks,
  total_conversions,
  ROUND(total_cost_usd, 2) AS total_cost_usd,
  ROUND(ctr * 100, 2) AS ctr_percent,
  ROUND(cost_per_conversion, 2) AS cost_per_conversion,
  ROUND(avg_quality_score, 1) AS avg_quality_score,
  alert_reasons,
  severity_score
FROM flagged_campaigns
WHERE severity_score > 0  -- Only campaigns with issues
ORDER BY severity_score DESC, total_cost_usd DESC;
```

---

### 2. Keyword Agent - Negative Keyword Opportunities

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: The Keyword Agent needs to identify search terms that should be added as negative keywords.

SCHEMA: [Include Template 3: Search Term Report]

TASK: Analyze the search term report to find negative keyword candidates.

CRITERIA FOR NEGATIVE KEYWORDS:
1. Search term has 0 conversions AND cost > $50 (30 days)
2. OR: CTR < 1% AND impressions > 100
3. OR: Contains irrelevant words like "free", "cheap", "job", "salary", "course"
4. Exclude search terms that exactly match existing keywords (those are intentional)

REQUIREMENTS:
- Last 30 days of data
- Group by search_term
- Calculate: total impressions, clicks, cost, conversions, CTR
- Include the keyword it matched to
- Suggest match type for negative keyword (phrase or exact)
- Order by cost (highest first)

OUTPUT: search_term, matched_keyword, metrics, suggested_negative_match_type, reason
```

**Expected Output:**
```sql
-- Identify negative keyword opportunities from search term report
-- Finds wasteful search terms with poor performance

WITH search_term_performance AS (
  SELECT
    search_term,
    keyword_text AS matched_keyword,
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    SUM(conversions) AS total_conversions,
    SUM(cost_micros) / 1e6 AS total_cost_usd,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr
  FROM `google_ads_raw.p_ads_SearchTermView_1234567890`
  WHERE
    date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
  GROUP BY search_term, matched_keyword
),

flagged_terms AS (
  SELECT
    *,
    CASE
      -- High cost, no conversions
      WHEN total_conversions = 0 AND total_cost_usd > 50 THEN 'High cost, zero conversions'
      -- Low engagement
      WHEN ctr < 0.01 AND total_impressions > 100 THEN 'Low CTR with volume'
      -- Irrelevant intent indicators
      WHEN REGEXP_CONTAINS(LOWER(search_term), r'\b(free|cheap|job|salary|course|download|crack|torrent)\b')
        THEN 'Irrelevant intent keyword detected'
      ELSE NULL
    END AS negative_reason,
    -- Suggest match type based on specificity
    CASE
      WHEN search_term = matched_keyword THEN 'EXACT'  -- Exact match to keyword
      WHEN ARRAY_LENGTH(SPLIT(search_term, ' ')) <= 2 THEN 'PHRASE'  -- Short query
      ELSE 'PHRASE'  -- Default to phrase match for safety
    END AS suggested_match_type
  FROM search_term_performance
  WHERE
    -- Exclude exact matches to existing keywords (those are intentional)
    search_term != matched_keyword
)

SELECT
  search_term,
  matched_keyword,
  total_impressions,
  total_clicks,
  total_conversions,
  ROUND(total_cost_usd, 2) AS total_cost_usd,
  ROUND(ctr * 100, 2) AS ctr_percent,
  suggested_match_type,
  negative_reason
FROM flagged_terms
WHERE negative_reason IS NOT NULL
ORDER BY total_cost_usd DESC
LIMIT 100;  -- Top 100 opportunities
```

---

### 3. Quality Score Agent - QS Drop Detection

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: The Quality Score Agent monitors keyword QS trends to detect degradation.

SCHEMA:
Table: sem_agents.quality_score_history
- snapshot_date (DATE)
- campaign_id, ad_group_id, keyword_id (STRING)
- keyword_text (STRING)
- quality_score (INT64): 1-10
- quality_score_expected_ctr (STRING): BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE
- quality_score_ad_relevance (STRING)
- quality_score_landing_page (STRING)
- sync_group_id (STRING)

TASK: Detect keywords where Quality Score dropped ≥2 points in the last 7 days.

REQUIREMENTS:
1. Compare today's snapshot vs 7 days ago
2. Calculate QS delta
3. Identify which sub-component degraded (Expected CTR, Ad Relevance, or LP Experience)
4. For sync groups, aggregate by keyword_text across all geos
5. Flag keywords where QS drop ≥ 2 points
6. Include campaign/ad group context

OUTPUT: keyword details, QS change, degraded component, sync_group_id if applicable
```

**Expected Output:**
```sql
-- Detect Quality Score drops over 7-day window
-- Identifies which sub-component degraded for targeted remediation

WITH latest_snapshot AS (
  SELECT
    campaign_id,
    ad_group_id,
    keyword_id,
    keyword_text,
    quality_score,
    quality_score_expected_ctr,
    quality_score_ad_relevance,
    quality_score_landing_page,
    sync_group_id,
    snapshot_date
  FROM `sem_agents.quality_score_history`
  WHERE snapshot_date = CURRENT_DATE()
),

prior_snapshot AS (
  SELECT
    campaign_id,
    ad_group_id,
    keyword_id,
    keyword_text,
    quality_score AS prior_quality_score,
    quality_score_expected_ctr AS prior_expected_ctr,
    quality_score_ad_relevance AS prior_ad_relevance,
    quality_score_landing_page AS prior_landing_page,
    snapshot_date AS prior_date
  FROM `sem_agents.quality_score_history`
  WHERE snapshot_date = DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
),

qs_delta AS (
  SELECT
    l.campaign_id,
    l.ad_group_id,
    l.keyword_id,
    l.keyword_text,
    l.sync_group_id,
    p.prior_quality_score,
    l.quality_score AS current_quality_score,
    l.quality_score - p.prior_quality_score AS qs_delta,

    -- Detect which component degraded
    CASE
      WHEN p.prior_expected_ctr = 'ABOVE_AVERAGE' AND l.quality_score_expected_ctr IN ('AVERAGE', 'BELOW_AVERAGE')
        THEN 'Expected CTR degraded'
      WHEN p.prior_expected_ctr = 'AVERAGE' AND l.quality_score_expected_ctr = 'BELOW_AVERAGE'
        THEN 'Expected CTR degraded'
      ELSE NULL
    END AS expected_ctr_issue,

    CASE
      WHEN p.prior_ad_relevance = 'ABOVE_AVERAGE' AND l.quality_score_ad_relevance IN ('AVERAGE', 'BELOW_AVERAGE')
        THEN 'Ad Relevance degraded'
      WHEN p.prior_ad_relevance = 'AVERAGE' AND l.quality_score_ad_relevance = 'BELOW_AVERAGE'
        THEN 'Ad Relevance degraded'
      ELSE NULL
    END AS ad_relevance_issue,

    CASE
      WHEN p.prior_landing_page = 'ABOVE_AVERAGE' AND l.quality_score_landing_page IN ('AVERAGE', 'BELOW_AVERAGE')
        THEN 'LP Experience degraded'
      WHEN p.prior_landing_page = 'AVERAGE' AND l.quality_score_landing_page = 'BELOW_AVERAGE'
        THEN 'LP Experience degraded'
      ELSE NULL
    END AS landing_page_issue,

    l.quality_score_expected_ctr AS current_expected_ctr,
    l.quality_score_ad_relevance AS current_ad_relevance,
    l.quality_score_landing_page AS current_landing_page

  FROM latest_snapshot l
  INNER JOIN prior_snapshot p
    ON l.keyword_id = p.keyword_id
  WHERE
    l.quality_score IS NOT NULL
    AND p.prior_quality_score IS NOT NULL
)

SELECT
  campaign_id,
  ad_group_id,
  keyword_id,
  keyword_text,
  sync_group_id,
  prior_quality_score,
  current_quality_score,
  qs_delta,

  -- Aggregate degraded components into array
  ARRAY_CONCAT_AGG([
    expected_ctr_issue,
    ad_relevance_issue,
    landing_page_issue
  ]) AS degraded_components,

  current_expected_ctr,
  current_ad_relevance,
  current_landing_page

FROM qs_delta
WHERE qs_delta <= -2  -- QS dropped by 2 or more points
ORDER BY qs_delta ASC, sync_group_id;  -- Worst drops first, grouped by sync
```

---

### 4. Sync Group Aggregation Query

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: For campaigns in sync groups (multi-geo variants), we need to aggregate performance by keyword text across all geos to make unified decisions.

SCHEMA:
[Include Template 2: Keyword Performance AND Template 4: campaign_taxonomy]

TASK: Aggregate keyword performance for sync group "nonbrand_ai_code_v1" across all geo variants.

REQUIREMENTS:
1. Join keyword performance with campaign_taxonomy
2. Filter to specific sync_group_id
3. Aggregate by keyword_text and match_type (same keyword may exist in US, UK, DE campaigns)
4. Calculate total metrics across all geos
5. Calculate per-geo breakdown as nested fields
6. Identify the template campaign (sync_group_role = 'template')
7. Last 30 days of data

OUTPUT: keyword_text, match_type, aggregated metrics, geo breakdown, template_campaign_id
```

**Expected Output:**
```sql
-- Aggregate keyword performance across sync group geos
-- Enables unified analysis for keywords shared across US/UK/DE/FR variants

WITH sync_group_keywords AS (
  SELECT
    kw.keyword_text,
    kw.match_type,
    kw.keyword_id,
    kw.campaign_id,
    tax.geo,
    tax.sync_group_id,
    tax.sync_group_role,

    SUM(kw.impressions) AS impressions,
    SUM(kw.clicks) AS clicks,
    SUM(kw.conversions) AS conversions,
    SUM(kw.cost_micros) / 1e6 AS cost_usd,
    AVG(kw.quality_score) AS avg_quality_score

  FROM `google_ads_raw.p_ads_KeywordView_1234567890` kw
  INNER JOIN `sem_agents.campaign_taxonomy` tax
    ON kw.campaign_id = tax.campaign_id
  WHERE
    tax.sync_group_id = 'nonbrand_ai_code_v1'
    AND kw.date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
  GROUP BY
    kw.keyword_text,
    kw.match_type,
    kw.keyword_id,
    kw.campaign_id,
    tax.geo,
    tax.sync_group_id,
    tax.sync_group_role
),

geo_breakdown AS (
  SELECT
    keyword_text,
    match_type,

    -- Identify template campaign
    MAX(IF(sync_group_role = 'template', campaign_id, NULL)) AS template_campaign_id,

    -- Aggregate across all geos
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    SUM(conversions) AS total_conversions,
    SUM(cost_usd) AS total_cost_usd,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS overall_ctr,
    SAFE_DIVIDE(SUM(cost_usd), SUM(conversions)) AS overall_cpa,
    AVG(avg_quality_score) AS avg_quality_score,

    -- Per-geo breakdown as structs
    ARRAY_AGG(
      STRUCT(
        geo,
        campaign_id,
        impressions,
        clicks,
        conversions,
        cost_usd,
        SAFE_DIVIDE(clicks, impressions) AS ctr,
        avg_quality_score
      )
      ORDER BY impressions DESC
    ) AS geo_performance

  FROM sync_group_keywords
  GROUP BY keyword_text, match_type
)

SELECT
  keyword_text,
  match_type,
  template_campaign_id,
  total_impressions,
  total_clicks,
  total_conversions,
  ROUND(total_cost_usd, 2) AS total_cost_usd,
  ROUND(overall_ctr * 100, 2) AS overall_ctr_percent,
  ROUND(overall_cpa, 2) AS overall_cpa,
  ROUND(avg_quality_score, 1) AS avg_quality_score,
  geo_performance
FROM geo_breakdown
WHERE total_impressions >= 100  -- Minimum volume threshold
ORDER BY total_cost_usd DESC;
```

---

## Performance Analysis Prompts

### 5. Top Performers vs Bottom Performers Comparison

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: Create a comparative analysis of top 10 vs bottom 10 performing ad groups.

SCHEMA: [Include Google Ads AdGroup performance table schema]

TASK: Compare top 10 vs bottom 10 ad groups by conversion rate over last 30 days.

REQUIREMENTS:
- Calculate conversion rate for each ad group
- Identify top 10 and bottom 10 by conversion rate
- Only include ad groups with ≥1000 impressions
- Show side-by-side metrics: impressions, clicks, CTR, conversions, CVR, cost, CPA
- Include campaign name for context
- Calculate the performance gap (how many X better top performers are)

OUTPUT: Two result sets (top_performers, bottom_performers) with comparison metrics
```

---

### 6. Hour-of-Day Performance Analysis

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: Analyze performance by hour of day to inform bid modifier recommendations.

SCHEMA:
Table: google_ads_raw.p_ads_AdGroupHourly_1234567890
- ad_group_id, campaign_id (STRING)
- hour_of_day (INT64): 0-23
- day_of_week (STRING): MONDAY, TUESDAY, etc.
- date (DATE)
- impressions, clicks, conversions, cost_micros (standard metrics)

TASK: For a specific campaign, analyze which hours of day have the best/worst conversion rates.

REQUIREMENTS:
- Last 30 days
- Group by hour_of_day
- Calculate: avg impressions, clicks, conversions, CVR, CPA per hour
- Identify peak hours (CVR > campaign average)
- Identify low hours (CVR < 50% of campaign average)
- Suggest bid modifier adjustments (±30% max)

OUTPUT: hour_of_day, metrics, performance_tier (peak/normal/low), suggested_bid_modifier
```

---

### 7. Geographic Performance Deep Dive

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: Analyze campaign performance by geographic location to identify high-value regions.

SCHEMA:
Table: google_ads_raw.p_ads_GeoStats_1234567890
- campaign_id (STRING)
- country_code (STRING): US, UK, DE, etc.
- region_name (STRING): California, London, etc.
- city_name (STRING)
- date (DATE)
- [standard performance metrics]

TASK: Identify top and bottom performing US states for location bid modifier optimization.

REQUIREMENTS:
- Filter to United States only
- Last 60 days of data
- Group by region_name (state)
- Calculate: total conversions, CVR, CPA, ROAS
- Compare each state to national average
- Flag states for bid modifier increase (ROAS > 120% of avg) or decrease (ROAS < 80% of avg)
- Minimum 50 conversions per state to qualify

OUTPUT: state, metrics, performance_vs_avg, recommended_action
```

---

## Audit & Monitoring Prompts

### 8. Agent Performance Dashboard Query

```
You are an expert BigQuery SQL developer for our internal agent monitoring system.

CONTEXT: Create a daily dashboard query showing agent health metrics.

SCHEMA: [Include Template 4: agent_recommendations, agent_runs, agent_audit_log]

TASK: Generate a daily agent performance summary.

REQUIREMENTS:
Last 7 days aggregated by day and agent_type:
- Total runs
- Total recommendations generated
- Approval rate (approved / total)
- Application success rate (applied / approved)
- Average LLM tokens used
- Error count
- Average execution time

OUTPUT: Daily time series by agent_type with health metrics
```

**Expected Output:**
```sql
-- Agent Performance Dashboard (7-day rolling)
-- Tracks health, approval rates, and operational metrics

WITH daily_runs AS (
  SELECT
    DATE(started_at) AS run_date,
    agent_type,
    COUNT(DISTINCT run_id) AS total_runs,
    SUM(total_recommendations) AS total_recommendations,
    SUM(approved_count) AS approved_count,
    SUM(applied_count) AS applied_count,
    COUNTIF(status = 'failed') AS failed_runs,
    AVG(TIMESTAMP_DIFF(completed_at, started_at, SECOND)) AS avg_execution_time_sec
  FROM `sem_agents.agent_runs`
  WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY run_date, agent_type
),

llm_usage AS (
  SELECT
    DATE(timestamp) AS usage_date,
    agent_type,
    SUM(total_tokens) AS total_tokens,
    AVG(total_tokens) AS avg_tokens_per_call,
    SUM(cost_usd) AS total_llm_cost
  FROM `sem_agents.llm_usage_log`
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY usage_date, agent_type
),

errors AS (
  SELECT
    DATE(timestamp) AS error_date,
    agent_type,
    COUNT(*) AS error_count
  FROM `sem_agents.agent_audit_log`
  WHERE
    timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    AND success = FALSE
  GROUP BY error_date, agent_type
)

SELECT
  r.run_date,
  r.agent_type,
  r.total_runs,
  r.total_recommendations,

  -- Approval metrics
  SAFE_DIVIDE(r.approved_count, r.total_recommendations) AS approval_rate,
  SAFE_DIVIDE(r.applied_count, r.approved_count) AS application_success_rate,

  -- Performance metrics
  ROUND(r.avg_execution_time_sec, 1) AS avg_execution_time_sec,
  r.failed_runs,
  COALESCE(e.error_count, 0) AS error_count,

  -- LLM usage
  COALESCE(l.total_tokens, 0) AS total_llm_tokens,
  ROUND(COALESCE(l.avg_tokens_per_call, 0), 0) AS avg_tokens_per_call,
  ROUND(COALESCE(l.total_llm_cost, 0), 2) AS llm_cost_usd,

  -- Health score (0-100)
  CAST(
    (SAFE_DIVIDE(r.approved_count, r.total_recommendations) * 40) +  -- 40% weight on approval
    (SAFE_DIVIDE(r.applied_count, r.approved_count) * 40) +          -- 40% weight on execution
    ((1 - SAFE_DIVIDE(r.failed_runs, r.total_runs)) * 20)            -- 20% weight on reliability
    AS INT64
  ) AS health_score

FROM daily_runs r
LEFT JOIN llm_usage l
  ON r.run_date = l.usage_date AND r.agent_type = l.agent_type
LEFT JOIN errors e
  ON r.run_date = e.error_date AND r.agent_type = e.agent_type
ORDER BY r.run_date DESC, r.agent_type;
```

---

### 9. Anomaly Detection Query

```
You are an expert BigQuery SQL developer specializing in anomaly detection for ad campaigns.

CONTEXT: Detect sudden changes in campaign performance that might indicate issues.

SCHEMA: [Campaign performance table with daily metrics]

TASK: Identify campaigns with anomalous performance changes in the last 7 days vs prior 30 days.

ANOMALY CRITERIA:
- Cost increased >50% week-over-week
- Conversion rate dropped >30%
- CTR dropped >25%
- Average CPC increased >40%

REQUIREMENTS:
- Calculate baseline metrics (days 31-7 ago)
- Calculate recent metrics (last 7 days)
- Compute percentage change
- Flag anomalies with type (cost_spike, cvr_drop, ctr_drop, cpc_spike)
- Minimum 10,000 impressions in baseline period

OUTPUT: campaign details, baseline vs recent metrics, anomaly_type, severity
```

---

### 10. Budget Pacing Analysis

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: Monitor daily budget pacing to ensure even spend distribution.

SCHEMA: Campaign daily performance with budget info

TASK: For each campaign, analyze budget pacing for current month.

REQUIREMENTS:
- Calculate days elapsed in current month
- Calculate days remaining
- Total spend so far this month
- Average daily spend
- Monthly budget (from campaign settings)
- Projected month-end spend (current pace)
- Pacing status: under-pacing (<90% of budget), on-track (90-110%), over-pacing (>110%)
- Recommended daily budget adjustment

OUTPUT: campaign, budget metrics, pacing_status, recommended_adjustment
```

---

## Optimization Tips

### Best Practices for SQL Generation with Gemini

1. **Always provide explicit schemas**: Don't rely on Gemini to guess table structures
2. **Specify the SQL dialect**: "Use BigQuery Standard SQL (not legacy)"
3. **Include data volume context**: "Table contains ~500M rows" helps with optimization
4. **Request comments**: "Add comments explaining complex logic"
5. **Ask for sample output**: Helps validate the query structure
6. **Specify partitioning/clustering usage**: "Use the date partition for filtering"

### Common Pitfalls to Avoid

```markdown
❌ DON'T: "Write a query to analyze campaigns"
✅ DO: "Write a BigQuery SQL query to identify campaigns with CTR < 2% in the last 30 days, using table google_ads_raw.p_ads_Campaign_123"

❌ DON'T: Use SELECT * on large tables
✅ DO: Explicitly list needed columns and use WHERE date >= '...' to leverage partitioning

❌ DON'T: Assume column names
✅ DO: Provide exact schema including data types

❌ DON'T: Forget NULL handling
✅ DO: "Use SAFE_DIVIDE for division and COALESCE for NULL defaults"
```

### Performance Optimization Prompts

```
ADDITIONAL INSTRUCTION to append to any query prompt:

"Optimize this query for performance by:
1. Leveraging date partitioning with explicit WHERE date >= ... filters
2. Using clustering keys (campaign_id, ad_group_id) in WHERE and JOIN clauses
3. Minimizing data scanned with column selection (no SELECT *)
4. Using approximate aggregation (APPROX_COUNT_DISTINCT) where exact counts not needed
5. Adding a LIMIT clause if this is for exploratory analysis
6. Using CTEs instead of subqueries for readability
7. Avoiding DISTINCT where GROUP BY can be used instead

Also explain the expected data scanned (GB) and execution time estimate."
```

---

## Advanced Prompt: Multi-Table Join Template

```
You are an expert BigQuery SQL developer for Google Ads analytics.

CONTEXT: I need to join multiple Google Ads tables to create a comprehensive keyword performance report.

SCHEMAS:
1. google_ads_raw.p_ads_KeywordView_1234567890 (keyword performance + QS)
2. google_ads_raw.p_ads_SearchTermView_1234567890 (search term report)
3. google_ads_raw.p_ads_AdGroup_1234567890 (ad group details)
4. google_ads_raw.p_ads_Campaign_1234567890 (campaign details)
5. sem_agents.campaign_taxonomy (sync groups + classification)

[Include all relevant schemas]

TASK: Create a unified keyword analysis report joining all these tables.

REQUIREMENTS:
- Last 30 days of data
- Join keyword → ad group → campaign → taxonomy
- Include search term analysis (aggregated by keyword)
- Calculate keyword-level metrics: impressions, clicks, conversions, QS
- Include campaign classification (brand/nonbrand/competitor)
- Include sync group context
- Filter to only active campaigns and ad groups
- Optimize joins to minimize data scanned

OUTPUT: Comprehensive keyword report with all context needed for analysis

SPECIAL INSTRUCTIONS:
- Use LEFT JOINs appropriately (some keywords may not have search term data)
- Partition filters on date column in WHERE clause (not in JOIN)
- Use clustering keys in JOIN conditions
- Comment each join to explain the relationship
```

---

## Gemini Model Selection Guide

### When to use Gemini Flash vs Pro for SQL generation

**Gemini Flash (Faster, Cheaper)**
- ✅ Simple SELECT queries with basic aggregation
- ✅ Single-table queries
- ✅ Well-defined prompts with complete schemas
- ✅ Standard analytics patterns (GROUP BY, ORDER BY, filtering)

**Gemini Pro (More Complex Reasoning)**
- ✅ Complex multi-table joins (4+ tables)
- ✅ Advanced window functions and analytics
- ✅ Optimization suggestions and query tuning
- ✅ Anomaly detection logic
- ✅ Schema inference from examples

---

## Example: Full Agent Implementation with Gemini

### Campaign Health Agent - Complete SQL Generation Workflow

```python
# File: src/agents/campaign_health/agent.py

from src.core.llm_client import GeminiClient

class CampaignHealthAgent(BaseAgent):
    def __init__(self):
        self.llm = GeminiClient(model="gemini-1.5-flash")

    def gather_data(self) -> pd.DataFrame:
        """Use Gemini to generate the SQL query dynamically"""

        # Schema context (loaded from metadata or config)
        schema_context = """
        Table: google_ads_raw.p_ads_Campaign_1234567890
        Fields: campaign_id, campaign_name, date, impressions, clicks,
                conversions, cost_micros, ctr, quality_score
        Partitioning: By date
        """

        # Prompt for SQL generation
        prompt = f"""
        You are an expert BigQuery SQL developer.

        SCHEMA: {schema_context}

        TASK: Generate a SQL query to identify underperforming campaigns for health monitoring.

        CRITERIA:
        - Last 30 days of data
        - Flag campaigns with: QS < 5, zero conversions, CTR < 2%, or cost > $5000 with CVR < 1%
        - Minimum 1000 impressions
        - Return: campaign_id, campaign_name, all key metrics, array of alert_reasons

        OUTPUT: Only the SQL query, no explanation.
        """

        # Generate SQL with Gemini
        sql_query = self.llm.generate(prompt, temperature=0.1)  # Low temp for consistency

        # Execute query
        from src.integrations.bigquery.client import BigQueryClient
        bq_client = BigQueryClient()
        results = bq_client.query(sql_query)

        return results
```

---

## Prompt Library Summary

| Query Type | Complexity | Recommended Model | Avg Tokens |
|------------|------------|------------------|------------|
| Campaign Health Check | Medium | Flash | 1500 |
| Negative Keyword Discovery | Medium-High | Flash | 2000 |
| Quality Score Analysis | High | Pro | 2500 |
| Sync Group Aggregation | High | Pro | 3000 |
| Agent Dashboard | Medium | Flash | 1800 |
| Anomaly Detection | High | Pro | 2800 |
| Multi-Table Joins | Very High | Pro | 3500 |

---

**Document Version**: 1.0
**Last Updated**: 2026-04-15
**Compatible with**: Google Gemini 1.5 Flash, Gemini 1.5 Pro
