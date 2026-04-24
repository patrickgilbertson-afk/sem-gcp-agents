# SEM GCP Agents - Current Project Context

**Last Updated**: 2026-04-24
**Phase**: 2.5 Complete - Ready for Cloud Run Testing

---

## Project Overview

AI-powered SEM campaign management system running on GCP. Agents analyze Google Ads performance data in BigQuery and make automated optimizations via human-approved recommendations.

**Key Principle**: All data reads from BigQuery, not Google Ads API. API only used for applying changes.

---

## Current Status: READY TO TEST

### ✅ What's Complete

1. **Infrastructure**
   - BigQuery: 12 tables in `sem_agents` dataset (all created)
   - Campaign data: Exists in `raw_google_ads.ads_Campaign_9624230998`
   - GA4 data: `analytics_272839261` (~508k events/day, well under 1M limit)
   - Secrets: All in GCP Secret Manager (no secrets in `.env`)

2. **Code Implementation (Phase 2.5)**
   - ✅ Guardrails system (pre-flight validation)
   - ✅ Knowledge system (markdown-based business context)
   - ✅ Sync group propagation (multi-geo campaigns)
   - ✅ Conversion goal tagging (sc_org_create, sc_new_signup, sc_trial_upgrade)
   - ✅ Weekly reporting (performance tracking)
   - ✅ GA4 integration (web analytics + ads data)
   - ✅ Secret Manager integration (runtime loading)

3. **Configuration**
   - GCP Project: `marketing-bigquery-490714`
   - MCC Account: `1109417913` (for API auth)
   - Campaign Account: `9624230998` (where ads run)
   - GA4 Property: `272839261`
   - Slack Channel: `C0AC1TGCZA6`
   - Environment: `development`, DRY_RUN: `true`

4. **Deployment**
   - ✅ Code committed (41 files, 6,973 insertions)
   - ✅ Pushed to GitHub (auto-deploys to Cloud Run)
   - ⏳ Waiting for Cloud Run deployment

---

## Important Architectural Decisions

### 1. Data Sources (Critical Understanding)
```
Reads FROM BigQuery:
├─ raw_google_ads.ads_Campaign_9624230998       ← Campaign data
├─ raw_google_ads.ads_AdGroupStats_9624230998   ← Performance
├─ analytics_272839261.events_*                 ← GA4 web data
└─ sem_agents.campaign_taxonomy                 ← Parsed structure

Writes TO:
├─ sem_agents.* tables                          ← Recommendations, audit logs
└─ Google Ads API                               ← Only for apply_changes()
```

**NOT using Google Ads API for reads** - all campaign/performance data comes from BigQuery.

### 2. Secret Management
- **All secrets in GCP Secret Manager**
- `.env` file has ZERO secrets (only non-sensitive config)
- `src/config.py` loads secrets via `@cached_property` from Secret Manager
- Environment variable fallback for local dev (but had SSL cert issues)
- Cloud Run auto-mounts secrets as env vars (works perfectly)

### 3. Account Structure
- **MCC Account** (`1109417913`): Used for API authentication
- **Campaign Account** (`9624230998`): Where campaigns actually run
- Both needed because using Manager Account structure

### 4. GA4 Event Configuration
- Sending 12 events (~508k/day) to BigQuery
- Primary conversions: `sc_org_create`, `sc_new_signup`, `sc_trial_upgrade`
- Custom engagement: `engaged_visitor_2025`
- Well under 1M/day free tier limit

---

## Next Steps (In Order)

### 1. Monitor Cloud Run Deployment
Check: https://github.com/patrickgilbertson-afk/sem-gcp-agents/actions

### 2. Get Cloud Run URL
```bash
gcloud run services describe sem-gcp-agents \
  --region=us-central1 \
  --format="value(status.url)"
```

### 3. Trigger Campaign Health Agent
```bash
curl -X POST https://YOUR-URL/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

Expected behavior:
- Reads campaigns from `raw_google_ads.ads_Campaign_9624230998`
- Parses campaign names (detects brand/non_brand/competitor)
- Populates `sem_agents.campaign_taxonomy` (currently empty)
- Joins with GA4 data from `analytics_272839261`
- Generates recommendations
- Posts to Slack channel `C0AC1TGCZA6`
- Runs in DRY_RUN mode (won't apply changes)

### 4. After First Agent Run
Once `campaign_taxonomy` is populated:
```bash
python run_conversion_goals.py
```

This sets conversion goals for each campaign type.

---

## Key Files & Locations

### Configuration
- `.env` - Non-secret config only (project ID, customer IDs, channel ID)
- `src/config.py` - Loads secrets from Secret Manager at runtime
- `terraform/terraform.tfvars` - Terraform variables (created, ready to use)

### Documentation (Current State)
- `SETUP_STATUS.md` - What's ready, what's pending
- `SECRETS_MIGRATION_COMPLETE.md` - How secrets work now
- `SECRET_MANAGER_GUIDE.md` - Secret Manager architecture
- `GA4_EVENTS_UPDATED.md` - GA4 integration details
- `docs/GA4_SETUP_GUIDE.md` - Complete GA4 setup guide

### Agent Code
- `src/agents/campaign_health/agent.py` - Main agent (enhanced with GA4, taxonomy, knowledge)
- `src/core/base_agent.py` - Base class (has guardrails, propagation)
- `src/core/guardrails.py` - Pre-flight validation
- `src/services/knowledge.py` - Business context loader
- `src/services/sync_group_resolver.py` - Multi-geo entity matching

### Data Integration
- `src/integrations/bigquery/analytics_queries.py` - GA4 SQL queries
- `src/secrets.py` - Secret Manager client
- `sql/populate_conversion_goals.sql` - Conversion goal setup

### Knowledge Base (Templates - Need Filling)
- `docs/knowledge/INDEX.md` - Tag-to-file mapping
- `docs/knowledge/account_structure.md` - Campaign conventions
- `docs/knowledge/product_info.md` - Product features (placeholder)
- `docs/knowledge/marketing_directives.md` - Current campaigns (placeholder)
- `docs/knowledge/strategy_*.md` - Campaign strategies (placeholder)

---

## Common Issues & Solutions

### Issue: "campaign_taxonomy table is empty"
**Solution**: This is expected. Campaign Health Agent populates it on first run.

### Issue: Local testing fails with SSL cert errors
**Solution**: Cloud Run deployment works fine. Secrets load from Secret Manager without issues in GCP.

### Issue: SQL script can't run yet
**Solution**: Need to run Campaign Health Agent first to populate taxonomy table.

### Issue: "Which Google Ads account ID?"
**Answer**:
- `GOOGLE_ADS_CUSTOMER_ID=9624230998` (campaign account)
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID=1109417913` (MCC for auth)

---

## Knowledge Base Status

**Current**: Placeholder content in all knowledge files

**Optional but Recommended**: Fill in with actual company data:
- Product names, features, pricing
- Campaign naming conventions
- Current promotions
- Brand voice guidelines
- Marketing priorities

**Impact**: Agents work fine without it (data-driven), but recommendations improve significantly with business context.

---

## Phase Progression

### ✅ Phase 1: Foundation (Complete)
- Core infrastructure, base agent framework, LLM clients

### ✅ Phase 2.5: Foundational Capabilities (Complete)
- Guardrails, knowledge system, sync groups, conversion goals, GA4, reporting

### ⏸️ Phase 3: Keyword Agent (Not Started)
- Search term analysis, negative keywords, expansion

### ⏸️ Phase 4: Ad Copy Agent (Not Started)
- RSA generation with brand compliance

### ⏸️ Phase 5: Bid Modifier Agent (Not Started)
- Device/location/time/audience bid adjustments

---

## Quick Reference Commands

### Check Deployment Status
```bash
gcloud run services describe sem-gcp-agents --region=us-central1
```

### View Logs
```bash
gcloud run services logs read sem-gcp-agents --region=us-central1 --limit=50
```

### Query Campaign Taxonomy
```bash
bq query "SELECT campaign_type, COUNT(*) as count FROM sem_agents.campaign_taxonomy GROUP BY campaign_type"
```

### Check Secrets
```bash
gcloud secrets list --project=marketing-bigquery-490714
```

### Local Development (If Needed)
```bash
# Won't work locally due to SSL cert issues with Secret Manager
# Deploy to Cloud Run instead
```

---

## Critical Notes for Next Session

1. **Don't create `.env` with secrets** - We moved to Secret Manager for security
2. **Data comes from BigQuery** - Not Google Ads API (common confusion)
3. **MCC vs Campaign Account** - Two different IDs, both needed
4. **campaign_taxonomy starts empty** - Agent populates it on first run
5. **Knowledge base is optional** - Agents work without it
6. **Everything deploys via GitHub** - Push to main = auto-deploy

---

## Current Commit

**SHA**: `960e913`
**Message**: "Implement Phase 2.5 foundational capabilities and GA4 integration"
**Files**: 41 changed, 6,973 insertions
**Status**: Pushed to GitHub, deploying to Cloud Run

---

## Contact Points

- **Slack Approval Channel**: `C0AC1TGCZA6` (already configured)
- **GitHub Repo**: https://github.com/patrickgilbertson-afk/sem-gcp-agents
- **GCP Project**: `marketing-bigquery-490714`

---

**Ready to test Campaign Health Agent in Cloud Run once deployment completes!**
