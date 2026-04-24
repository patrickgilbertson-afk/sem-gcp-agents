# GA4 Events Configuration - Updated

**Date**: 2026-04-23
**Status**: ✅ Code updated to match your actual GA4 event configuration

---

## Summary

Updated all GA4 integration code to use your **actual event names** instead of generic placeholders.

**Events Configured**: 12 events (~508k/day)
**Reduction from Original**: 68% (from ~750k to ~508k events/day)
**Status**: Well under GA4's 1M events/day free tier

---

## Your GA4 Events (Configured)

### Session & User Tracking (331k/day)
```
✅ session_start          109,810/day
✅ first_visit             77,653/day
✅ user_engagement        143,472/day
```

### Engagement (159k/day)
```
✅ page_view              145,773/day
✅ engaged_visitor_2025    13,044/day  ⭐ Custom high-value metric
```

### Key Conversions (1.8k/day)
```
✅ sc_org_create              484/day  ⭐ PRIMARY CONVERSION
✅ sc_new_signup              859/day
✅ sc_trial_upgrade            57/day
✅ submittedForm              222/day
✅ sq_download                173/day
```

### Supporting Events (17k/day)
```
✅ form_submit             16,475/day
✅ sc_signup_clicks           586/day
```

---

## Files Updated

### 1. `src/integrations/bigquery/analytics_queries.py`

**Changes**:
- ✅ Updated `GA4_CAMPAIGN_EVENTS` query to use actual event names
- ✅ Added `engaged_visitors` metric (custom high-value engagement)
- ✅ Added `engaged_visitor_rate` calculation
- ✅ Updated `GA4_CONVERSION_BY_GOAL` to include all your key conversion events
- ✅ Removed generic placeholder events (purchase, generate_lead, sign_up)

**New Metrics Returned**:
```python
{
    "campaign_name": "NonBrand_AI-Code_US",
    "users": 1000,
    "sessions": 1500,
    "page_views": 5000,
    "conversions": 50,                    # Sum of all conversion events
    "engaged_visitors": 300,              # ⭐ NEW - custom engagement
    "engagement_rate": 0.75,
    "engaged_visitor_rate": 0.30,         # ⭐ NEW - % of users who are highly engaged
    "conversion_rate_ga4": 0.033,
    "avg_engagement_time_sec": 120.5,
}
```

### 2. `src/agents/campaign_health/agent.py`

**Changes**:
- ✅ Added `engaged_visitors` and `engaged_visitor_rate` to metrics dict
- ✅ Updated LLM prompt to show engaged visitors in GA4 metrics section
- ✅ Added page views to prompt output

**Example Prompt Output**:
```
GA4 Web Metrics:
- Users: 1,234
- Sessions: 1,567
- Page Views: 5,432
- Engagement Rate: 75.2%
- Engaged Visitors: 456 (37.0% of users)  ⭐ NEW
- GA4 Conversions: 25
- GA4 Conv Rate: 1.6%
```

### 3. `tests/unit/test_analytics_queries.py`

**Changes**:
- ✅ Updated test assertions to check for actual event names
- ✅ Added `engaged_visitors` and `engaged_visitor_rate` to test data
- ✅ Removed assertions for placeholder events

### 4. `sql/populate_conversion_goals.sql` ⭐ NEW

**Purpose**: Populate `conversion_goal` and `conversion_source` in taxonomy table

**Usage**:
```sql
-- NonBrand campaigns optimize for org creation
UPDATE campaign_taxonomy
SET conversion_goal = 'sc_org_create',
    conversion_source = 'google_analytics'
WHERE campaign_type = 'non_brand';

-- Brand campaigns optimize for new signups
UPDATE campaign_taxonomy
SET conversion_goal = 'sc_new_signup',
    conversion_source = 'google_analytics'
WHERE campaign_type = 'brand';

-- Competitor campaigns optimize for trial upgrades
UPDATE campaign_taxonomy
SET conversion_goal = 'sc_trial_upgrade',
    conversion_source = 'google_analytics'
WHERE campaign_type = 'competitor';
```

### 5. `docs/GA4_SETUP_GUIDE.md` ⭐ NEW

**Purpose**: Complete setup guide for GA4 integration

**Contents**:
- Step-by-step GA4 BigQuery export configuration
- Environment variable setup
- Conversion goal population
- Testing and verification
- Troubleshooting guide
- Cost management

---

## Conversion Event Mapping

Your actual GA4 events now map to conversion goals in taxonomy:

| Conversion Goal (Taxonomy) | GA4 Event Name      | Daily Volume | Campaign Types |
|----------------------------|---------------------|--------------|----------------|
| `sc_org_create`            | sc_org_create       | 484          | NonBrand       |
| `sc_new_signup`            | sc_new_signup       | 859          | Brand          |
| `sc_trial_upgrade`         | sc_trial_upgrade    | 57           | Competitor     |
| `submittedForm`            | submittedForm       | 222          | All            |
| `sq_download`              | sq_download         | 173          | NonBrand       |
| `engaged_visitor_2025`     | engaged_visitor_2025| 13,044       | High-value     |

---

## How It Works Now

### 1. Agent Gather Data
```python
# Loads GA4 metrics if configured
ga4_data = await get_ga4_campaign_metrics(
    bq_client=self.bq_client,
    start_date="2024-04-01",
    end_date="2024-04-07",
)
```

### 2. SQL Query Executes
```sql
-- Counts actual conversion events
COUNTIF(event_name IN (
    'sc_org_create',        -- YOUR events
    'sc_new_signup',
    'sc_trial_upgrade',
    'submittedForm',
    'sq_download',
    'form_submit'
)) AS conversions
```

### 3. Metrics Indexed by Campaign
```python
ga4_metrics["NonBrand_AI-Code_US"] = {
    "users": 450,
    "sessions": 600,
    "conversions_ga4": 28,        # Sum of all your conversion events
    "engaged_visitors": 180,       # Your custom metric
    "engaged_visitor_rate": 0.40,  # 40% of users are highly engaged
    ...
}
```

### 4. LLM Prompt Includes GA4 Context
```
Campaign: NonBrand_AI-Code_US
Primary Conversion: sc_org_create (Google Analytics)

Metrics:
- Cost: $1,000
- Conversions (Ads): 25

GA4 Web Metrics:
- Users: 450
- Sessions: 600
- Engaged Visitors: 180 (40.0% of users)  ⭐ High engagement!
- GA4 Conversions: 28
- GA4 Conv Rate: 4.7%
```

### 5. Claude's Enhanced Analysis
Claude can now say:
> "Despite high cost-per-click, this campaign shows strong engagement (40% engaged visitor rate) and GA4 conversion rate (4.7%) exceeds Google Ads reported rate. The issue isn't traffic quality - it's attribution. Consider using GA4's sc_org_create as the primary conversion goal instead of Google Ads conversions."

---

## Next Steps

### Immediate
1. **Configure GA4 Export**: Follow `docs/GA4_SETUP_GUIDE.md`
2. **Set Environment Variables**:
   ```bash
   export GA4_DATASET="analytics_123456789"
   export GA4_PROPERTY_ID="123456789"
   ```
3. **Run SQL Script**: Populate conversion goals
   ```bash
   bq query --use_legacy_sql=false < sql/populate_conversion_goals.sql
   ```

### Testing (Day 1)
4. **Test Integration**:
   ```bash
   curl -X POST http://localhost:8080/api/v1/orchestrator/run \
     -d '{"agent_type": "campaign_health"}'
   ```
5. **Check Logs**: Verify `ga4_metrics_loaded` appears

### Validation (Week 1)
6. **Monitor GA4 Data Quality**: Ensure campaign names match
7. **Review Agent Recommendations**: Verify GA4 context improves decisions
8. **Check BigQuery Costs**: Should be $0 (under free tier)

---

## Benefits You Get

### Before (Google Ads Only)
```
Campaign: NonBrand_AI-Code_US
- Cost: $1,000
- Conversions: 25
- CPA: $40

❌ Can't see if users engage after clicking
❌ Can't distinguish high-quality vs. low-quality conversions
❌ No visibility into user journey beyond ad click
```

### After (Google Ads + GA4)
```
Campaign: NonBrand_AI-Code_US
- Cost: $1,000
- Conversions (Ads): 25
- CPA: $40

GA4 Web Metrics:
- Users: 450
- Sessions: 600
- Engaged Visitors: 180 (40% high-value)  ⭐
- GA4 Conversions: 28 (sc_org_create)
- GA4 Conv Rate: 4.7%

✅ See full user journey (click → browse → engage → convert)
✅ Track high-value engagement (engaged_visitor_2025)
✅ Understand conversion quality (org creates vs. generic signups)
✅ Identify attribution gaps (28 GA4 vs. 25 Ads conversions)
```

---

## Key Differences from Generic Implementation

| Aspect | Generic (Before) | Your Actual Setup |
|--------|------------------|-------------------|
| Primary Conversion | "purchase" | **sc_org_create** |
| Signup Event | "sign_up" | **sc_new_signup** |
| Trial Event | "trial_start" | **sc_trial_upgrade** |
| Form Event | "generate_lead" | **submittedForm** + **form_submit** |
| Download Event | N/A | **sq_download** |
| Engagement | Generic | **engaged_visitor_2025** (custom) |
| Daily Volume | Unknown | **~508k events/day** (measured) |

---

## Questions?

**Setup**: See `docs/GA4_SETUP_GUIDE.md`
**Code**: See `src/integrations/bigquery/analytics_queries.py`
**Testing**: See `tests/unit/test_analytics_queries.py`
**Troubleshooting**: See GA4_SETUP_GUIDE.md § Troubleshooting

Your GA4 integration is now **fully customized** to your actual event configuration! 🎉
