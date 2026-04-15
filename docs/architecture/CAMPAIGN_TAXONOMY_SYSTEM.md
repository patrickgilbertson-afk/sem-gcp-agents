# Campaign Taxonomy & Sync Group System

## Overview

The Campaign Taxonomy & Sync Group System enables intelligent campaign grouping and sync-aware agent operations. This system addresses the core architectural challenge: the Google Ads account has campaigns with fundamentally different management patterns.

## Problem Statement

The account has 6 verticals with two distinct management patterns:

1. **Synced campaigns** (NonBrand_AI-Code, NonBrand_Code, NonBrand_Languages, NonBrand_Security, Brand): Each vertical has multiple geo variants (US, UK, DE, etc.) sharing **identical** keywords and ad copy. Changes must propagate to ALL geo campaigns in the vertical.

2. **Individual campaigns** (Competitor): Each competitor has a unique global campaign evaluated independently.

Without campaign taxonomy, agents would:
- Add a negative keyword to NonBrand_AI-Code_US but miss UK/DE/FR variants
- Analyze keyword performance in isolation per campaign (low data volume)
- Generate redundant recommendations for each geo variant
- Risk sync drift where geos diverge over time

## Solution Architecture

### 1. Campaign Taxonomy Table

**Purpose**: Dimension table mapping campaigns to sync groups and management strategies.

**Key Fields**:
- `sync_group`: Groups campaigns sharing keywords/ad copy (e.g., `nonbrand_ai_code`)
- `management_strategy`: `synced` (propagate changes) or `individual` (evaluate independently)
- `is_template`: Primary campaign in sync group (drives analysis, preferably US geo)
- `detection_method`: `auto` (parsed from name) or `manual` (user override)
- `detection_confidence`: 0.0-1.0 for auto-detection quality

**Size**: Small dimension table (~50-200 rows, <1 GB)

**Auto-Detection**: Regex patterns parse campaign names:
- `NonBrand_AI-Code_US` → type=nonbrand, vertical=ai_code, geo=US, sync_group=nonbrand_ai_code
- `Brand_EMEA` → type=brand, vertical=brand, geo=EMEA, sync_group=brand
- `Competitor_GitHub` → type=competitor, vertical=competitor_github, geo=Global, sync_group=competitor_github

### 2. Sync Group Context

**Data Structure** (Pydantic model):
```python
class SyncGroupContext(BaseModel):
    sync_group: str  # e.g., "nonbrand_ai_code"
    campaign_type: CampaignType  # nonbrand, brand, competitor
    vertical: str  # ai_code, code, languages, etc.
    management_strategy: ManagementStrategy  # synced or individual
    campaigns: list[CampaignTaxonomy]  # All campaigns in sync group
    template_campaign_id: str | None  # Campaign driving analysis

    @property
    def campaign_ids(self) -> list[str]:
        """All campaign IDs in sync group for propagation"""
```

### 3. Agent Operation Modes

#### Synced Mode (NonBrand, Brand)
- **gather_data**: Aggregate metrics across ALL geos in sync group
- **analyze**: LLM sees aggregated data, understands it represents multiple markets
- **generate_recommendations**: Set `target_campaign_ids` to ALL campaigns in sync group
- **apply_changes**: Loop over `target_campaign_ids`, apply change to each campaign

**Example**: Add negative keyword "free" to NonBrand_AI-Code
→ Applied to US, UK, DE, FR, JP campaigns in single batch operation

#### Individual Mode (Competitor)
- **gather_data**: Query single campaign
- **analyze**: LLM sees single campaign data
- **generate_recommendations**: Set `target_campaign_ids` to single campaign
- **apply_changes**: Apply to single campaign

**Example**: Add negative keyword to Competitor_GitHub
→ Only affects that campaign, NOT Competitor_AWS or Competitor_Azure

### 4. Quality Score & Landing Page Specialization

#### Quality Score Agent
**Taxonomy-aware features**:
- Aggregate QS by keyword text across sync group (spot patterns)
- Geo variance analysis: "keyword X has QS 7 in US but 3 in DE → geo-specific LP issue"
- Delegates to specialist agents based on sub-component degradation

**Example QS Analysis**:
```
Keyword: "python code editor"
Sync Group: nonbrand_code
QS by geo:
  US: 8 (Expected CTR: ABOVE_AVERAGE, Ad Relevance: AVERAGE, LP: ABOVE_AVERAGE)
  UK: 8 (similar to US)
  DE: 4 (Expected CTR: BELOW_AVERAGE, Ad Relevance: AVERAGE, LP: AVERAGE)

Diagnosis: DE market has low Expected CTR despite same ad copy.
Root cause: Likely German-language search intent mismatch.
Recommendation: Delegate to Keyword Agent for DE-specific keyword/match-type review.
```

#### Landing Page Agent
**Taxonomy-aware features**:
- URL deduplication: same URL used in US/UK/DE → check once, tag all sync groups
- Aggregate keyword associations across geos
- Content relevance analysis per unique URL
- 7-day audit cache to avoid redundant PageSpeed API calls

**Example LP Analysis**:
```
URL: example.com/python-editor
Sync groups using this URL: [nonbrand_code, nonbrand_ai_code]
Campaigns: NonBrand_Code_US, NonBrand_Code_UK, NonBrand_AI-Code_US, ...
Keywords (12 total): "python editor", "python code editor", "code editor python", ...

PageSpeed Score: 42 (CRITICAL - affects QS)
Content Relevance: 8.5/10 (good keyword coverage)
Improvement suggestions:
  1. CRITICAL: Optimize largest contentful paint (4.2s → target <2.5s)
  2. HIGH: Reduce cumulative layout shift (0.18 → target <0.1)
  3. MEDIUM: Add section covering "debugging" theme (keyword gap)
```

## Data Flow

### Campaign Health Agent (Per-Campaign with Sync Context)
```
1. gather_data()
   - JOIN campaign_taxonomy on campaign_id
   - Load sibling campaigns in same sync_group

2. analyze()
   - Prompt includes: "Campaign NonBrand_AI-Code_US is 1 of 5 geo variants.
     Siblings: UK (CTR 2.1%), DE (CTR 1.8%), FR (CTR 1.5%), JP (CTR 0.9%)
     If this campaign significantly underperforms siblings, flag it."

3. generate_recommendations()
   - Tag with sync_group for context
   - No propagation (health is per-campaign)
```

### Keyword Agent (Sync-Group-Aware)
```
1. gather_data()
   - Check management_strategy from context
   - IF synced:
       Use SEARCH_TERM_REPORT_SYNC_GROUP (aggregated across geos)
       Load all campaigns in sync group
   - ELSE:
       Use standard SEARCH_TERM_REPORT (single campaign)

2. analyze()
   - Prompt includes: "Data is aggregated across 5 geo campaigns.
     Recommendations apply to all geos unless geo-specific."

3. generate_recommendations()
   - Set target_campaign_ids to ALL campaign_ids in sync group

4. apply_changes()
   - Loop over target_campaign_ids
   - Batch into single Google Ads mutate call
   - Audit log shows: "Added negative keyword 'free' to 5 campaigns in nonbrand_ai_code"
```

### Quality Score Agent (Sync-Group-Aggregated)
```
1. gather_data()
   - Query quality_score_history for sync group
   - Aggregate by keyword_text across geos
   - Detect drops (QS decreased >2 points in 7 days)
   - Geo variance analysis (same keyword different QS by geo)

2. analyze()
   - Diagnose which sub-component drove QS drop:
       * Expected CTR → keyword/match-type issue
       * Ad Relevance → ad copy issue
       * LP Experience → landing page issue

3. generate_recommendations()
   - Create delegation recommendations:
       * delegate_keyword_review (to Keyword Agent)
       * delegate_ad_copy_refresh (to Ad Copy Agent)
       * delegate_landing_page_audit (to Landing Page Agent)
   - Also create alert_qs_drop for Slack notification

4. apply_changes()
   - Log QS snapshots to quality_score_history
   - Delegate to specialist agents via Pub/Sub
   - Post diagnostic summaries to Slack
```

### Landing Page Agent (URL-Deduplicated)
```
1. gather_data()
   - Extract all unique final URLs from Google Ads keyword data
   - Map URLs to keywords, ad groups, sync groups
   - Deduplicate: if example.com/python used by US+UK+DE → check once
   - Run PageSpeed Insights API (cached 7 days)
   - Fetch page HTML for LLM content analysis

2. analyze() - Two phases:
   Phase 1: Content Relevance
     - Claude receives: page content + keywords mapped to this URL
     - Prompt: "Score relevance 1-10. Identify content gaps."

   Phase 2: Improvement Recommendations
     - Claude receives: PageSpeed data + content analysis + keyword performance
     - Prompt: "Generate specific LP improvement recommendations"

3. generate_recommendations()
   - lp_speed_critical (score <50)
   - lp_not_accessible (404, 500, redirects)
   - lp_content_mismatch (relevance <5)
   - lp_improvement (specific content/UX suggestions)

4. apply_changes()
   - Store audit results in landing_page_audits
   - Post detailed reports to Slack
   - For URL reassignment recs, generate Google Ads URL update operations
```

## BigQuery Query Patterns

### Standard Queries (with Taxonomy JOIN)
All existing queries get taxonomy context:
```sql
SELECT
  c.campaign_id,
  c.campaign_name,
  c.impressions,
  c.clicks,
  t.campaign_type,
  t.vertical,
  t.geo,
  t.sync_group,
  t.management_strategy,
  t.is_template
FROM `{project}.sem_ads_raw.p_Campaign_{date}` c
LEFT JOIN sem_agents.campaign_taxonomy t
  ON c.campaign_id = t.campaign_id
WHERE t.campaign_status IN ('ENABLED', 'PAUSED')
  AND DATE(_PARTITIONTIME) = @date
```

### Sync-Group-Aggregated Queries
For Keyword/Ad Copy/QS agents operating on synced campaigns:
```sql
-- SEARCH_TERM_REPORT_SYNC_GROUP
SELECT
  t.sync_group,
  st.search_term,
  SUM(st.impressions) as total_impressions,
  SUM(st.clicks) as total_clicks,
  SUM(st.cost_micros) as total_cost_micros,
  SUM(st.conversions) as total_conversions,
  COUNT(DISTINCT st.campaign_id) as campaign_count
FROM `{project}.sem_ads_raw.p_SearchTermView_{date}` st
JOIN sem_agents.campaign_taxonomy t
  ON st.campaign_id = t.campaign_id
WHERE t.sync_group = @sync_group
  AND t.campaign_status = 'ENABLED'
  AND DATE(_PARTITIONTIME) BETWEEN @start_date AND @end_date
GROUP BY 1, 2
HAVING total_impressions >= 10
ORDER BY total_cost_micros DESC
```

### Quality Score Queries
```sql
-- QS_TREND (detect drops)
SELECT
  keyword_text,
  sync_group,
  geo,
  quality_score as current_qs,
  LAG(quality_score, 7) OVER (
    PARTITION BY keyword_id
    ORDER BY snapshot_date
  ) as qs_7d_ago,
  quality_score - LAG(quality_score, 7) OVER (
    PARTITION BY keyword_id
    ORDER BY snapshot_date
  ) as qs_change
FROM sem_agents.quality_score_history
WHERE snapshot_date >= CURRENT_DATE() - 7
  AND sync_group = @sync_group
  AND quality_score IS NOT NULL
HAVING qs_change < -2
ORDER BY qs_change;

-- QS_GEO_VARIANCE (spot geo-specific issues)
SELECT
  sync_group,
  keyword_text,
  MAX(quality_score) - MIN(quality_score) as qs_variance,
  ARRAY_AGG(
    STRUCT(geo, quality_score, expected_ctr, ad_relevance, landing_page_experience)
    ORDER BY geo
  ) as geo_breakdown
FROM sem_agents.quality_score_history
WHERE snapshot_date = CURRENT_DATE()
  AND sync_group = @sync_group
GROUP BY 1, 2
HAVING qs_variance >= 3
ORDER BY qs_variance DESC;
```

### Landing Page Queries
```sql
-- LP_URLS_BY_SYNC_GROUP (with deduplication)
SELECT
  url,
  url_hash,
  ARRAY_AGG(DISTINCT sync_group) as sync_groups,
  ARRAY_AGG(DISTINCT campaign_id) as campaign_ids,
  COUNT(DISTINCT keyword_id) as keyword_count
FROM (
  SELECT
    k.final_url as url,
    TO_BASE64(SHA256(k.final_url)) as url_hash,
    t.sync_group,
    k.campaign_id,
    k.keyword_id
  FROM `{project}.sem_ads_raw.p_Keyword_{date}` k
  JOIN sem_agents.campaign_taxonomy t
    ON k.campaign_id = t.campaign_id
  WHERE k.status = 'ENABLED'
    AND t.campaign_status = 'ENABLED'
)
GROUP BY 1, 2
ORDER BY keyword_count DESC;

-- LP_AUDIT_CACHE_CHECK (skip recently audited URLs)
SELECT
  url,
  url_hash,
  MAX(audit_date) as last_audit_date,
  CURRENT_DATE() - MAX(audit_date) as days_since_audit
FROM sem_agents.landing_page_audits
WHERE url_hash IN UNNEST(@url_hashes)
GROUP BY 1, 2
HAVING days_since_audit < 7;
```

## Orchestrator Routing

### New Routing Methods
```python
async def run_by_sync_group(self, sync_group: str, agent_type: AgentType):
    """Run agent for specific sync group"""

async def run_by_vertical(self, vertical: str, agent_type: AgentType):
    """Run agent for all sync groups in vertical"""

async def run_by_campaign_type(self, campaign_type: str, agent_type: AgentType):
    """Run agent for all sync groups of campaign type"""
```

### Modified Scheduled Run Flow
```python
async def run(self):
    # 1. Load full taxonomy
    taxonomy = await self.taxonomy_service.get_all()

    # 2. Group by sync_group
    sync_groups = self._group_by_sync_group(taxonomy)

    # 3. For each SYNCED sync group:
    for sg_context in sync_groups.synced:
        # Campaign Health → per-campaign with sync context
        for campaign in sg_context.campaigns:
            await self.run_campaign_health(campaign, sg_context)

        # Keyword → once per sync group (aggregated)
        await self.run_keyword(sg_context)

        # Quality Score → once per sync group (aggregated)
        await self.run_quality_score(sg_context)

        # Landing Page → once per sync group (deduplicated URLs)
        await self.run_landing_page(sg_context)

        # Ad Copy → once per sync group (aggregated)
        await self.run_ad_copy(sg_context)

        # Bid Modifier → per-campaign (geo-specific)
        for campaign in sg_context.campaigns:
            await self.run_bid_modifier(campaign, sg_context)

    # 4. For each INDIVIDUAL campaign (Competitor):
    for campaign in sync_groups.individual:
        await self.run_all_agents(campaign)
```

## Agent Scheduling

| Agent | Schedule | Trigger | Scope |
|-------|----------|---------|-------|
| Campaign Health | Daily 7 AM | Scheduled | Per-campaign with sync context |
| Keyword | Daily 8 AM | Scheduled | Per sync group (synced) or per campaign (individual) |
| Quality Score | Daily 9 AM | Scheduled | Per sync group (synced) or per campaign (individual) |
| Landing Page | Weekly Tue 10 AM | Scheduled + on-demand from QS | Per sync group (deduplicated URLs) |
| Ad Copy | On-demand | From Campaign Health or QS | Per sync group (synced) or per campaign (individual) |
| Bid Modifier | Weekly Mon 9 AM | Scheduled | Per-campaign (geo-specific bids) |

## Slack Approval Enhancements

### Approval Message for Synced Recommendations
```
📊 Keyword Recommendation: Add Negative Keyword
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sync Group: NonBrand_AI-Code
Target: 5 campaigns (US, UK, DE, FR, JP)

Negative Keyword: "free" (phrase match)
Reason: 127 clicks, $45.20 spend, 0 conversions across all geos

This will apply to ALL 5 campaigns in the sync group:
  • NonBrand_AI-Code_US
  • NonBrand_AI-Code_UK
  • NonBrand_AI-Code_DE
  • NonBrand_AI-Code_FR
  • NonBrand_AI-Code_JP

[Approve] [Reject] [View Details]
```

### Taxonomy Management Modal (`/sem-agents taxonomy`)
```
Campaign Taxonomy Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sync Group: nonbrand_ai_code
Strategy: Synced ▼
Template: NonBrand_AI-Code_US ▼

Campaigns (5):
  ✓ NonBrand_AI-Code_US (Template) | Geo: US ▼
  ✓ NonBrand_AI-Code_UK           | Geo: UK ▼
  ✓ NonBrand_AI-Code_DE           | Geo: DE ▼
  ✓ NonBrand_AI-Code_FR           | Geo: FR ▼
  ✓ NonBrand_AI-Code_JP           | Geo: JP ▼

[Detect New Campaigns] [Save Changes]
```

## Edge Cases & Solutions

### 1. New Campaign Added to Google Ads
**Detection**: Daily detection script (`scripts/detect_new_campaigns.py`)
- High confidence (≥0.8) → Auto-classify + Slack notification
- Low confidence (<0.8) → Default to `individual` strategy + Slack alert for manual review

### 2. Campaign Paused/Removed in Google Ads
**Sync**: Daily sync updates `campaign_status` from Google Ads
- Paused/removed campaigns excluded from sync group queries
- Taxonomy row preserved for history

### 3. Test Keyword in One Geo First (Pilot Mode)
**Phase 1**: Slack message clearly states scope; user can reject and apply manually
**Phase 2**: Add `pilot_mode` flag to Recommendation
- Apply to template campaign only
- Auto-promote to full sync group after observation period

### 4. Unclassified Campaign in Agent Run
**Handling**: LEFT JOIN means unclassified campaigns still appear in Campaign Health
- Taxonomy fields are NULL
- Excluded from sync-group-aggregated queries
- Slack alert sent for manual classification

### 5. Auto-Detection Failure
**Fallback**: Default to `management_strategy=individual` (safe — no accidental propagation)
- Send Slack alert for manual review
- User can reclassify via `/sem-agents taxonomy` modal

## Verification & Testing

### Seed Script Verification
```bash
python scripts/seed_taxonomy.py --customer-id 1234567890 --dry-run

Expected output:
✓ Fetched 42 campaigns from Google Ads API
✓ Auto-detected 38 campaigns (90% confidence)
✓ Low confidence: 4 campaigns need manual review
  - "Test_Campaign_2024" (confidence: 0.45)
  - "Brand_Test" (confidence: 0.60)
  - ...
✓ Created 6 sync groups:
  - nonbrand_ai_code: 5 campaigns (template: US)
  - nonbrand_code: 5 campaigns (template: US)
  - nonbrand_languages: 4 campaigns (template: US)
  - nonbrand_security: 3 campaigns (template: UK)
  - brand: 6 campaigns (template: US)
  - competitor_github: 1 campaign
✓ Would insert 42 rows into campaign_taxonomy
```

### Sync Group Query Verification
```sql
-- Verify aggregated search term data matches sum of individual campaigns
WITH individual AS (
  SELECT
    search_term,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks
  FROM `{project}.sem_ads_raw.p_SearchTermView_*`
  WHERE campaign_id IN (
    SELECT campaign_id FROM sem_agents.campaign_taxonomy
    WHERE sync_group = 'nonbrand_ai_code'
  )
  GROUP BY 1
),
aggregated AS (
  SELECT
    search_term,
    total_impressions,
    total_clicks
  FROM sem_agents.vw_search_term_report_sync_group
  WHERE sync_group = 'nonbrand_ai_code'
)
SELECT
  i.search_term,
  i.total_impressions as individual_impressions,
  a.total_impressions as aggregated_impressions,
  ABS(i.total_impressions - a.total_impressions) as diff
FROM individual i
JOIN aggregated a ON i.search_term = a.search_term
WHERE ABS(i.total_impressions - a.total_impressions) > 0;

-- Expected: 0 rows (perfect match)
```

### Keyword Agent Propagation Test
```python
# Test: Add negative keyword to synced campaign
async def test_keyword_agent_synced_propagation():
    agent = KeywordAgent()

    # Run for NonBrand_AI-Code sync group
    sg_context = await taxonomy_service.get_sync_group("nonbrand_ai_code")

    recommendations = await agent.run(sg_context)

    # Verify target_campaign_ids includes all campaigns
    assert len(recommendations[0].target_campaign_ids) == 5
    assert set(recommendations[0].target_campaign_ids) == set(sg_context.campaign_ids)

    # Apply recommendation
    await agent.apply_changes(recommendations)

    # Verify keyword added to all 5 campaigns
    for campaign_id in sg_context.campaign_ids:
        keywords = await google_ads_client.get_negative_keywords(campaign_id)
        assert "free" in keywords
```

## Migration Path

### Step 1: Deploy Tables
```bash
cd terraform
terraform apply -target=module.bigquery.google_bigquery_table.campaign_taxonomy
terraform apply -target=module.bigquery.google_bigquery_table.quality_score_history
terraform apply -target=module.bigquery.google_bigquery_table.landing_page_audits
```

### Step 2: Seed Taxonomy
```bash
python scripts/seed_taxonomy.py --customer-id 1234567890
# Review low-confidence detections in Slack
# Manually classify via /sem-agents taxonomy if needed
```

### Step 3: Update Existing Queries
```sql
-- Add taxonomy JOIN to Campaign Health query
-- (already done in PR 2)
```

### Step 4: Deploy Agents Incrementally
1. Quality Score Agent (read-only, no Google Ads changes)
2. Landing Page Agent (read-only, audit storage only)
3. Keyword Agent with sync group support (requires careful testing)

### Step 5: Monitor & Validate
- Check sync group query performance (should be fast with clustering)
- Verify Slack approval messages show correct campaign counts
- Audit log: "Applied to N campaigns in sync group X"

## Performance Considerations

### campaign_taxonomy Table
- **Size**: ~200 rows, <1 MB
- **Queries**: Mostly in-memory cache (TaxonomyService)
- **Cost**: Negligible (clustering on sync_group makes lookups instant)

### quality_score_history Table
- **Size**: ~30 GB after 6 months (365 days × ~5K keywords × ~100 bytes/row)
- **Partitioning**: Daily by snapshot_date (1-year retention)
- **Queries**: Efficient with partition pruning + clustering on sync_group

### landing_page_audits Table
- **Size**: ~5 GB after 6 months (~500 unique URLs × 30 audits × ~350 bytes/row)
- **Partitioning**: Daily by audit_date (1-year retention)
- **Queries**: Fast lookups via url_hash cluster

### Sync-Group-Aggregated Queries
- **Performance**: Similar to single-campaign queries (clustering + partitioning)
- **Cost**: Slightly higher (scan 3-5x more campaigns) but still low due to partition pruning

## Future Enhancements

### 1. Multi-Language Sync Groups
Support campaigns with same vertical but different languages:
```
sync_group: nonbrand_code_en (US, UK, AU)
sync_group: nonbrand_code_de (DE, AT, CH)
sync_group: nonbrand_code_fr (FR, BE, CA)
```

### 2. Partial Sync (Advanced)
Allow some keywords to be geo-specific within a synced campaign:
```python
class KeywordTaxonomy:
    keyword_text: str
    sync_scope: Literal["all_geos", "geo_specific", "template_only"]
```

### 3. Sync Drift Detection
Monitor keyword/ad copy differences across geos:
```sql
-- Keywords in US but not in UK for same sync group
SELECT keyword_text
FROM keywords WHERE campaign_id = 'US_campaign'
EXCEPT DISTINCT
SELECT keyword_text
FROM keywords WHERE campaign_id = 'UK_campaign'
```

### 4. Taxonomy Versioning
Track taxonomy changes over time:
```sql
CREATE TABLE campaign_taxonomy_history (
  history_id STRING,
  campaign_id STRING,
  sync_group STRING,
  changed_at TIMESTAMP,
  changed_by STRING,
  change_type STRING -- 'reclassified', 'sync_group_split', 'sync_group_merge'
)
```

## Summary

The Campaign Taxonomy & Sync Group System transforms the agent framework from campaign-centric to intelligent multi-campaign orchestration. By understanding campaign relationships, agents can:

1. **Aggregate data** across geos for better signal-to-noise
2. **Propagate changes** to ensure sync group consistency
3. **Detect patterns** that only emerge when comparing geos
4. **Reduce redundancy** by deduplicating URLs and running analysis once per sync group
5. **Prevent drift** by enforcing synced keyword/ad copy across geos

This enables the agents to manage the account the way a human SEM manager would: treating geo variants as a cohesive unit while respecting the independence of truly distinct campaigns.
