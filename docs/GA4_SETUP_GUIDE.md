# GA4 Integration Setup Guide

**Last Updated**: 2026-04-23

This guide walks you through configuring GA4 BigQuery export for SEM GCP Agents.

---

## Overview

**What You're Sending**: 12 events (~508k events/day)
**BigQuery Cost**: Well under 1M events/day free tier
**Value**: Holistic campaign analysis (Google Ads + web engagement)

---

## Step 1: Configure GA4 BigQuery Export

### 1.1 Navigate to BigQuery Links

1. Go to **GA4 Admin** → **Property Settings** → **BigQuery Links**
2. Click **Link** (or **Configure** if already linked)

### 1.2 Select Events to Export

✅ **Include these events only**:

```
Session & User Tracking:
━━━━━━━━━━━━━━━━━━━━━━
☑ session_start          (109,810/day)
☑ first_visit             (77,653/day)
☑ user_engagement        (143,472/day)

Engagement:
━━━━━━━━━━━━━━━━━━━━━━
☑ page_view              (145,773/day)
☑ engaged_visitor_2025    (13,044/day) ⭐ Custom high-value metric

Key Conversions:
━━━━━━━━━━━━━━━━━━━━━━
☑ sc_org_create              (484/day) ⭐ PRIMARY CONVERSION
☑ sc_new_signup              (859/day)
☑ sc_trial_upgrade            (57/day)
☑ submittedForm              (222/day)
☑ sq_download                (173/day)

Supporting Events:
━━━━━━━━━━━━━━━━━━━━━━
☑ form_submit             (16,475/day)
☑ sc_signup_clicks           (586/day)
```

**Total**: ~508k events/day (68% reduction from original ~750k)

### 1.3 Export Settings

- **Export Frequency**: Daily (recommended)
- **Include Advertising Identifiers**: ✅ Yes (for Google Ads integration)
- **Include User ID**: Your choice (not required for SEM)
- **Dataset Location**: Same region as your Google Ads data (e.g., `us-central1`)

### 1.4 Dataset Naming

Your BigQuery dataset will be named: `analytics_<PROPERTY_ID>`

Example: If your GA4 property ID is `123456789`, the dataset will be:
```
analytics_123456789
```

---

## Step 2: Configure Environment Variables

### 2.1 Update `.env` File

Add these lines to your `.env` file:

```bash
# Google Analytics 4 Integration (Optional)
GA4_DATASET=analytics_123456789        # Replace with your actual dataset
GA4_PROPERTY_ID=123456789              # Replace with your GA4 property ID
```

### 2.2 Verify Configuration

```bash
# Check that settings are loaded
python -c "from src.config import settings; print(f'GA4 Dataset: {settings.ga4_dataset}')"
```

Expected output:
```
GA4 Dataset: analytics_123456789
```

---

## Step 3: Populate Conversion Goals in Taxonomy

### 3.1 Download SQL Script

The SQL script is located at: `sql/populate_conversion_goals.sql`

### 3.2 Update Project ID

Replace `{project_id}` in the SQL file with your actual GCP project ID.

Example:
```sql
-- Before:
UPDATE `{project_id}.sem_agents.campaign_taxonomy`

-- After:
UPDATE `my-gcp-project.sem_agents.campaign_taxonomy`
```

### 3.3 Run SQL Script

**Option A: BigQuery Console**
1. Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Copy the SQL from `sql/populate_conversion_goals.sql`
3. Click **COMPOSE NEW QUERY**
4. Paste and run

**Option B: Command Line**
```bash
bq query --use_legacy_sql=false < sql/populate_conversion_goals.sql
```

### 3.4 Verify Results

```sql
SELECT
    campaign_type,
    conversion_goal,
    conversion_source,
    COUNT(*) as campaign_count
FROM `your-project.sem_agents.campaign_taxonomy`
GROUP BY campaign_type, conversion_goal, conversion_source
ORDER BY campaign_type;
```

Expected output:
```
campaign_type  conversion_goal     conversion_source    campaign_count
─────────────────────────────────────────────────────────────────────
brand          sc_new_signup       google_analytics     4
competitor     sc_trial_upgrade    google_analytics     6
non_brand      sc_org_create       google_analytics     12
```

---

## Step 4: Test the Integration

### 4.1 Run Campaign Health Agent

Trigger a test run:

```bash
curl -X POST http://localhost:8080/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

### 4.2 Check Logs

Look for this log message:
```
ga4_metrics_loaded campaigns_with_ga4_data=X
```

If `campaigns_with_ga4_data > 0`, the integration is working!

### 4.3 Verify GA4 Metrics in Prompt

Check the BigQuery `agent_audit_log` table for the most recent run:

```sql
SELECT details
FROM `your-project.sem_agents.agent_audit_log`
WHERE event_type = 'analyze'
ORDER BY timestamp DESC
LIMIT 1
```

The `details` should include GA4 metrics in the prompt sent to Claude:
```
GA4 Web Metrics:
- Users: 1,234
- Sessions: 1,567
- Page Views: 5,432
- Engagement Rate: 75.2%
- Engaged Visitors: 456 (37.0% of users)
- GA4 Conversions: 25
- GA4 Conv Rate: 1.6%
```

---

## Step 5: Update Knowledge Base (Optional)

### 5.1 Add Conversion-Specific Content

If you want to provide additional context for specific conversion goals, edit:

**`docs/knowledge/INDEX.md`**:
```markdown
## Conversion Goal Tags

- **conversion_sc_org_create**: product_info.md, strategy_nonbrand.md
- **conversion_sc_new_signup**: strategy_brand.md, marketing_directives.md
- **conversion_sc_trial_upgrade**: product_info.md, marketing_directives.md
```

### 5.2 Create Conversion-Specific Files (Optional)

Example: `docs/knowledge/conversion_sc_org_create.md`
```markdown
# SQC Org Create Optimization

## What is SQC Org Create?

Self-Serve Qualified Customer - Organization Create event fires when a user:
1. Completes signup
2. Creates an organization (not just individual account)
3. Indicates team/company use case

## Why It Matters

- **Higher LTV**: Org accounts convert to paid at 3x the rate of individual accounts
- **Target CPA**: $80-$100 (vs. $20-$30 for generic signups)
- **Optimization Strategy**: Optimize for quality, not quantity

## Campaign Strategy

- Focus on keywords indicating team/enterprise intent
- Bid more aggressively on "team", "collaboration", "enterprise" modifiers
- Avoid pure individual developer keywords
```

---

## Troubleshooting

### Issue: "No GA4 data found"

**Cause**: Dataset not configured or data not yet exported

**Solutions**:
1. Check that `GA4_DATASET` is set in `.env`
2. Verify BigQuery export is enabled in GA4
3. Wait 24 hours after enabling export (first export takes time)
4. Check dataset exists:
   ```bash
   bq ls analytics_*
   ```

### Issue: "Query timeout" or "Quota exceeded"

**Cause**: Query is scanning too much data

**Solutions**:
1. Check date range in queries (default is 30 days)
2. Reduce `days_back` parameter in agent runs
3. Add campaign_filter to limit scope:
   ```python
   ga4_data = await get_ga4_campaign_metrics(
       bq_client=self.bq_client,
       start_date=start_date.isoformat(),
       end_date=end_date.isoformat(),
       campaign_filter="NonBrand",  # Only NonBrand campaigns
   )
   ```

### Issue: "Conversion events missing"

**Cause**: Event names don't match between GA4 export and queries

**Solutions**:
1. Verify event names in BigQuery:
   ```sql
   SELECT event_name, COUNT(*) as count
   FROM `your-project.analytics_123456789.events_*`
   WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', CURRENT_DATE())
   GROUP BY event_name
   ORDER BY count DESC
   LIMIT 20
   ```

2. Update `analytics_queries.py` if event names differ

### Issue: "Campaign names don't match"

**Cause**: UTM campaign parameter doesn't match Google Ads campaign name

**Solutions**:
1. Ensure UTM parameters in Google Ads auto-tagging are correct
2. Check `traffic_source.campaign` in GA4 data:
   ```sql
   SELECT traffic_source.campaign, COUNT(*) as sessions
   FROM `your-project.analytics_123456789.events_*`
   WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', CURRENT_DATE())
   AND event_name = 'session_start'
   GROUP BY traffic_source.campaign
   ORDER BY sessions DESC
   LIMIT 20
   ```

---

## Cost Management

### Current Configuration

- **Events/day**: ~508k
- **GA4 Free Tier**: 1M events/day (streaming)
- **BigQuery Free Tier**: 10 GB storage, 1 TB queries/month
- **Status**: ✅ Well under limits

### Monthly Costs (Estimated)

Assuming you stay under free tiers:
- **GA4 BigQuery Export**: $0 (under 1M/day)
- **BigQuery Storage**: $0 (event data ~2-3 GB/month)
- **BigQuery Queries**: $0 (agent queries ~100 GB/month)

**Total**: **$0/month** for first 6-12 months (until you scale significantly)

### If You Exceed Free Tier

GA4 BigQuery export pricing beyond 1M events/day:
- **$0.002 per 1,000 events**
- Your 508k/day → $0.00 (under threshold)

BigQuery query pricing beyond 1 TB/month:
- **$5 per TB**
- Agent queries: ~100 GB/month → $0.00 (under threshold)

---

## Monitoring

### Daily Health Check

```sql
-- Check today's event volume by type
SELECT
    event_name,
    COUNT(*) as event_count
FROM `your-project.analytics_123456789.events_*`
WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', CURRENT_DATE())
GROUP BY event_name
ORDER BY event_count DESC;
```

### Weekly Report

```sql
-- Check weekly GA4 data joined with Google Ads campaigns
SELECT
    traffic_source.campaign,
    COUNT(DISTINCT user_pseudo_id) as users,
    COUNTIF(event_name = 'session_start') as sessions,
    COUNTIF(event_name = 'sc_org_create') as org_creates
FROM `your-project.analytics_123456789.events_*`
WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
AND traffic_source.source = 'google'
AND traffic_source.medium = 'cpc'
GROUP BY traffic_source.campaign
ORDER BY sessions DESC
LIMIT 20;
```

---

## Next Steps

1. ✅ **Configured GA4 export** with 12 events (~508k/day)
2. ✅ **Set environment variables** (GA4_DATASET, GA4_PROPERTY_ID)
3. ✅ **Populated conversion goals** in campaign_taxonomy table
4. ✅ **Tested integration** - verified GA4 metrics appear in agent prompts
5. ⏭️ **Monitor for 1 week** - ensure data quality and query performance
6. ⏭️ **Review agent recommendations** - verify GA4 context improves decisions
7. ⏭️ **Iterate on conversion goals** - refine based on business priorities

---

## Support

**Documentation**: See `IMPLEMENTATION_COMPLETE.md` for full technical details
**Logs**: Cloud Run logs show GA4 query execution and results
**Analytics**: BigQuery console to explore GA4 data manually

**Questions?** Check the troubleshooting section above or review the code:
- `src/integrations/bigquery/analytics_queries.py` - SQL queries
- `src/agents/campaign_health/agent.py` - Integration logic
