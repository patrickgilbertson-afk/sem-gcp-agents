# SEM GCP Agents - Current Project Context

**Last Updated**: 2026-04-24
**Phase**: 2.5 Complete - Campaign Health Agent Tested Successfully

---

## Project Overview

AI-powered SEM campaign management system running on GCP. Agents analyze Google Ads performance data in BigQuery and make automated optimizations via human-approved recommendations.

**Key Principle**: All data reads from BigQuery, not Google Ads API. API only used for applying changes.

---

## Current Status: AGENT TESTED SUCCESSFULLY

### What's Working

1. **Cloud Run**: Deployed and healthy
   - URL: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app`
   - Health: `{"status":"healthy","environment":"development","dry_run":true}`

2. **Campaign Health Agent**: First successful run
   - 130 campaigns detected and classified
   - 34 sync groups auto-populated in `campaign_taxonomy`
   - 5,886 recommendations generated
   - LLM analysis via Claude Sonnet 4.5 (Portkey routing)

3. **Taxonomy Auto-Population**: Working
   - Agent auto-detects and inserts taxonomy on first run
   - Handles two naming conventions:
     - Standard: `{Year}_Q{Q}_{Funnel}_{Type}_{Vertical}_{Region}_{Geo}_Google_...`
     - Legacy SQ: `SQ {Region} - {Type} - {Suffix}`
   - Campaign types detected: brand (43), non_brand (63), competitor (17), enterprise (7)

4. **Infrastructure**
   - BigQuery: 12 tables in `sem_agents` dataset (all created, schemas fixed)
   - Campaign data: `raw_google_ads.ads_Campaign_9624230998` (~200 campaigns)
   - GA4 data: `analytics_272839261` (~508k events/day)
   - Secrets: All in GCP Secret Manager (16 secrets)

### Known Issues (Non-Blocking)

- `llm_call_log` table missing `error_code` column (cosmetic logging error)
- Some SQ legacy campaigns get rough geo names (e.g., "EMEA_West Benelux")
- Knowledge base has placeholder content (agents work without it)

---

## Configuration

- GCP Project: `marketing-bigquery-490714`
- MCC Account: `1109417913` (for API auth)
- Campaign Account: `9624230998` (where ads run)
- GA4 Property: `272839261`
- Slack Channel: `C0AC1TGCZA6`
- Environment: `development`, DRY_RUN: `true`

---

## Important Architectural Decisions

### 1. Data Sources (Critical)
```
Reads FROM BigQuery:
|- raw_google_ads.ads_Campaign_9624230998       <- Campaign data
|- raw_google_ads.ads_AdGroupStats_9624230998   <- Performance
|- analytics_272839261.events_*                 <- GA4 web data
|- sem_agents.campaign_taxonomy                 <- Parsed structure

Writes TO:
|- sem_agents.* tables                          <- Recommendations, audit logs
|- Google Ads API                               <- Only for apply_changes()
```

### 2. Secret Management
- ALL secrets in GCP Secret Manager (16 secrets)
- `.env` file has ZERO secrets (only non-sensitive config)
- `src/config.py` loads secrets via `@cached_property` from Secret Manager
- Cloud Run auto-mounts secrets as env vars

### 3. Campaign Naming Conventions (Real Data)
```
Standard (2026+):
  2026_Q1_BOF_Brand_APJ_ANZ_Google_Search_Clicks_Beinc
  2026_Q1_MOF_NonBrand_AI-Code_EMEA_DE_Google_Search_Conversions
  2026_Q2_MOF_Competitor_Snyk_Global_Google_Search_Clicks
  2026_Q2_BOF_Enterprise_NA_AMER_Google_Leads_SLG

Legacy SQ:
  SQ APJ 1 Jap - Brand - Beinc
  SQ EMEA ACH - Generic AI
  SQ - Competitor - Aikido
```

### 4. Taxonomy & Sync Groups
- 34 sync groups across 130 campaigns
- Brand/NonBrand/Enterprise = SYNCED (changes propagate across geos)
- Competitor = INDIVIDUAL (each competitor evaluated independently)
- Agent auto-populates taxonomy when entries are missing

---

## Next Steps (In Order)

### 1. Conversion Goals via Google Ads Labels (PLANNED)
Instead of SQL scripts, apply labels in Google Ads UI (e.g., `conversion_goal:sc_org_create`) and have the agent read them from BigQuery. More maintainable than SQL scripts.

### 2. Review Recommendations in Slack
Check Slack channel `C0AC1TGCZA6` for agent recommendations. Running in DRY_RUN mode.

### 3. Fix Minor Issues
- Add `error_code` column to `llm_call_log` table
- Clean up SQ legacy geo names

### 4. Fill Knowledge Base (Optional)
`docs/knowledge/*.md` files need real company data for better recommendations.

### 5. Phase 3+: More Agents
- Phase 3: Keyword Agent (search term analysis, negative keywords)
- Phase 4: Ad Copy Agent (RSA generation)
- Phase 5: Bid Modifier Agent (device/location/time adjustments)

### 6. Production Readiness
- Set `DRY_RUN=false` after recommendation review
- Configure Cloud Scheduler for daily automated runs
- Validate Slack approval flow end-to-end

---

## Key Files

### Configuration
- `.env` - Non-secret config only
- `src/config.py` - Loads secrets from Secret Manager at runtime
- `terraform/terraform.tfvars` - Terraform variables

### Agent Code
- `src/agents/campaign_health/agent.py` - Main agent (auto-populates taxonomy)
- `src/utils/taxonomy.py` - Campaign name parser (real naming conventions)
- `src/core/base_agent.py` - Base class (guardrails, propagation)
- `src/services/taxonomy.py` - TaxonomyService (BigQuery CRUD)

### Data Integration
- `src/integrations/bigquery/analytics_queries.py` - GA4 SQL queries
- `src/secrets.py` - Secret Manager client

---

## BigQuery Table Schemas Fixed

During testing, found that several tables had incomplete schemas (created before Terraform was fully defined). Fixed via BigQuery REST API:

- `campaign_taxonomy` - Recreated with all 20 columns (was 8, truncated)
- `performance_metrics` - Recreated with all 11 columns (was 7)

---

## Quick Reference

### Trigger Agent
```bash
curl -X POST https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

### Check Taxonomy
```bash
# Via gcloud (from local machine with SSL issues, use REST API)
TOKEN=$(gcloud auth print-access-token)
curl -sk "https://bigquery.googleapis.com/bigquery/v2/projects/marketing-bigquery-490714/queries" ...
```

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sem-gcp-agents" \
  --project=marketing-bigquery-490714 --limit=20 --format="value(timestamp,jsonPayload)"
```

---

## Critical Notes for Next Session

1. **Don't create `.env` with secrets** - All secrets in GCP Secret Manager
2. **Data comes from BigQuery** - Not Google Ads API
3. **Taxonomy is auto-populated** - Agent handles it on first run
4. **Real campaign names** - Use `{Year}_Q{Q}_{Funnel}_{Type}_...` format, NOT simple `Brand_US`
5. **Corporate SSL issues** - Can't test Secret Manager locally, deploy to Cloud Run
6. **Push to main = auto-deploy** - GitHub Actions builds and deploys to Cloud Run
7. **Conversion goals** - Future plan: use Google Ads labels instead of SQL scripts

---

## Commits This Session

- `8c525bc` - Rewrite taxonomy parser for real campaign naming conventions
- `8586259` - Auto-populate campaign taxonomy on first agent run
- `2529e66` - Add comprehensive project context documentation (previous session)

---

## Contact Points

- **Cloud Run URL**: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app`
- **Slack Channel**: `C0AC1TGCZA6`
- **GitHub Repo**: https://github.com/patrickgilbertson-afk/sem-gcp-agents
- **GCP Project**: `marketing-bigquery-490714`
