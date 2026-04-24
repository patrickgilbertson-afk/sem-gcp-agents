# SEM GCP Agents - Project Context

## CRITICAL CONTEXT (Read First!)

**Current Phase**: Phase 2.5 Complete - Agent Tested Successfully
**Last Updated**: 2026-04-24
**Status**: Cloud Run deployed, Campaign Health Agent working, taxonomy populated

### Key Facts to Remember

1. **Data Source Architecture** (CRITICAL - Often Confused)
   - Agents READ from BigQuery (NOT Google Ads API)
   - Campaign data: `raw_google_ads.ads_Campaign_9624230998`
   - GA4 data: `analytics_272839261.events_*`
   - Google Ads API ONLY used for WRITING changes (apply_changes)

2. **Secret Management** (DO NOT CHANGE)
   - ALL secrets in GCP Secret Manager (16 secrets)
   - `.env` file has ZERO secrets (only non-sensitive config)
   - `src/config.py` loads secrets via `@cached_property`
   - DO NOT create scripts to load secrets into `.env`

3. **Account Structure**
   - MCC Account: `1109417913` (for API authentication)
   - Campaign Account: `9624230998` (where ads actually run)
   - Both IDs needed - we use Manager Account structure

4. **Cloud Run**
   - URL: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app`
   - Health endpoint works, DRY_RUN=true
   - Push to main = auto-deploy via GitHub Actions

5. **Campaign Taxonomy** (AUTO-POPULATED)
   - 130 campaigns, 34 sync groups detected
   - Agent auto-populates on run via `src/utils/taxonomy.py`
   - Real naming: `{Year}_Q{Q}_{Funnel}_{Type}_{Vertical}_{Region}_{Geo}_Google_...`
   - Also handles legacy `SQ {Region} - {Type} - {Suffix}` format
   - DO NOT use old placeholder patterns (Brand_US, NonBrand_AI-Code_US)

6. **Next Steps** (PRIORITY ORDER)
   - SECURITY FIRST: Add API auth middleware, remove allUsers IAM binding
   - DO NOT set DRY_RUN=false until auth is implemented
   - Then: conversion goals via Google Ads labels, review Slack recs
   - Then: fix `llm_call_log`, fill knowledge base, build Phase 3+ agents

7. **Corporate Network Limitation**
   - SSL cert issues prevent local Secret Manager access
   - Always deploy to Cloud Run for testing

See `PROJECT_CONTEXT.md` for complete current state snapshot.

---

## Overview

This is an AI-powered SEM campaign management framework running on Google Cloud Platform. The system uses specialized AI agents to automate campaign health monitoring, keyword management, ad copy generation, and bid optimization.

## Architecture

**Stack**: Python 3.11, FastAPI, Google Cloud (BigQuery, Cloud Run, Pub/Sub), Anthropic Claude, Google Gemini

**Key Design Patterns**:
- Base Agent Pattern: All agents inherit from `BaseAgent` and follow: Gather → Analyze → Recommend → Approve → Apply
- Human-in-the-Loop: Slack approval flow for all recommendations before execution
- Audit Everything: Every action logged to BigQuery for compliance and debugging
- Safety First: Dry run mode, kill switch, rate limiting, operation limits

## Project Structure

```
src/
├── main.py              # FastAPI app entry point
├── config.py            # Centralized configuration
├── models/              # Pydantic data models
├── core/                # Base agent, orchestrator, LLM clients
├── agents/              # Specialized agents (campaign_health, keyword, ad_copy, bid_modifier)
├── integrations/        # External services (Google Ads, BigQuery, Slack, Pub/Sub)
├── api/                 # FastAPI routers
└── sql/                 # SQL queries for BigQuery

terraform/               # Infrastructure as code
├── modules/             # Reusable Terraform modules
│   ├── bigquery/        # Datasets and tables
│   ├── cloud_run/       # Service deployment
│   ├── secrets/         # Secret Manager
│   ├── pubsub/          # Topics & subscriptions
│   ├── iam/             # Service accounts & permissions
│   └── scheduler/       # Cron jobs
└── main.tf              # Root configuration
```

## Key Agents

### 1. Campaign Health Agent (Implemented)
- **Model**: Claude Sonnet 4.5
- **Schedule**: Daily at 7 AM
- **Function**: Monitors 30-day campaign metrics, flags quality score issues, zero conversions, low CTR
- **Actions**: Pauses underperforming ad groups, delegates to specialist agents

### 2. Keyword Agent (TODO - Phase 3)
- **Model**: Claude Sonnet
- **Schedule**: Daily at 8 AM
- **Function**: Analyzes search terms, adds negatives, expands positive keywords
- **Actions**: Add negative keywords (phrase match), add positive keywords as PAUSED

### 3. Ad Copy Agent (TODO - Phase 4)
- **Models**: Gemini Flash (generation) + Claude (strategy)
- **Schedule**: On-demand only
- **Function**: Generates RSA assets with brand compliance
- **Actions**: Creates new RSAs, does NOT pause old ads

### 4. Bid Modifier Agent (TODO - Phase 5)
- **Model**: Gemini Pro
- **Schedule**: Weekly (Monday 9 AM)
- **Function**: Optimizes device/location/time/audience bid modifiers
- **Actions**: Batch updates with guardrails (max ±30pp change/week)

### 5. Quality Score Agent (TODO - Phase 2.5)
- **Model**: Claude Sonnet (diagnostic reasoning)
- **Schedule**: Daily at 9 AM (after Campaign Health and Keyword agents)
- **Function**: Monitors QS trends, detects drops, diagnoses which sub-component degraded
- **Actions**: Delegates to Keyword Agent (low Expected CTR), Ad Copy Agent (low Ad Relevance), or Landing Page Agent (low LP Experience)
- **Taxonomy-aware**: For synced campaigns, aggregates QS by keyword text across geos to spot geo-specific issues

### 6. Landing Page Agent (TODO - Phase 2.5)
- **Model**: Claude Sonnet (content analysis + recommendations)
- **Schedule**: Weekly Tuesday 10 AM, or on-demand (triggered by QS Agent for LP issues)
- **Function**: LP health checks (PageSpeed Insights), content relevance analysis, improvement recommendations
- **Actions**: Stores audit results, posts detailed reports to Slack, can generate URL reassignment operations
- **Taxonomy-aware**: Deduplicates URLs across sync groups (same URL used in US/UK/DE → check once)

## Development Workflow

### Local Development
```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env  # Configure with your credentials

# Run
make run  # or: uvicorn src.main:app --reload --port 8080

# Test
make test
make lint
```

### Deployment
```bash
# Build and push
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:latest .
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:latest

# Deploy infrastructure
cd terraform
terraform init
terraform plan
terraform apply

# Or use script
./scripts/deploy.sh
```

## Key Files to Edit

### Adding a New Agent
1. Create `src/agents/<agent_name>/agent.py` extending `BaseAgent`
2. Implement: `gather_data()`, `analyze()`, `generate_recommendations()`, `_apply_single_recommendation()`
3. Add SQL queries to `src/sql/` or `src/integrations/bigquery/queries.py`
4. Register in `src/core/orchestrator.py` agent_map
5. Add tests in `tests/unit/test_<agent_name>.py`

### Modifying LLM Behavior
- **System prompts**: In agent's `analyze()` method
- **Model selection**: Agent `__init__` when creating LLM client
- **Temperature/tokens**: In agent's `analyze()` method call to `llm.generate()`

### Changing Thresholds
- **Runtime**: Update `src/agents/<agent>/thresholds.py` or BigQuery `agent_config` table
- **No redeploy needed**: Query config from BQ in `gather_data()`

### Slack Message Format
- **Blocks**: `src/integrations/slack/app.py` → `_build_approval_blocks()`
- **Agent-specific**: Each agent implements `_create_summary()` for batch summary

## Data Flow

1. **Cloud Scheduler** triggers `/api/v1/orchestrator/run` with `agent_type`
2. **Orchestrator** routes to specialist agent
3. **Agent** executes pipeline:
   - `gather_data()`: Queries BigQuery for last 30 days
   - `analyze()`: LLM analyzes data for issues
   - `generate_recommendations()`: Creates structured actions
   - `request_approval()`: Posts to Slack
4. **User** approves/rejects in Slack
5. **Agent** executes `apply_changes()` via Google Ads API
6. **Audit log** captures every step in BigQuery

## Safety Mechanisms

- **Dry Run Mode**: Set `DRY_RUN=true` to skip `apply_changes()`
- **Kill Switch**: `/sem-agents pause` sets `kill_switch_enabled=true` (forces dry run)
- **Rate Limiting**: Max 1 req/sec to Google Ads API
- **Operation Limits**: Max 10,000 operations per agent run
- **Budget Caps**: Blocks if daily spend increase >15%
- **Approval Timeout**: Auto-reject after 8 hours, escalate at 4 hours

## Testing Strategy

- **Unit Tests**: Mock BigQuery, Google Ads API, LLM clients
- **Integration Tests**: Use Google Ads API sandbox
- **Dry Run**: Run agents in production with `DRY_RUN=true` for 1-2 weeks per phase
- **Canary Deployments**: New agents start with small subset of campaigns

## Common Issues

### "google.auth.exceptions.DefaultCredentialsError"
- Run: `gcloud auth application-default login`

### "BigQuery table not found"
- Ensure Google Ads Data Transfer Service is set up in BQ console
- Run `terraform apply` to create agent tables

### "Slack signature verification failed"
- Check `SLACK_SIGNING_SECRET` in environment
- Verify request URL in Slack app config

### Agent runs but no recommendations
- Check `DRY_RUN=true` setting
- Verify BigQuery data exists for date range
- Check agent logs for query errors

## Phase 1 Checklist (Foundation - COMPLETED)

✅ Project structure and build system
✅ Core infrastructure (BigQuery, Cloud Run, Pub/Sub)
✅ Base agent framework
✅ LLM clients (Claude, Gemini)
✅ Campaign Health Agent implementation
✅ Slack integration skeleton
✅ Terraform modules for all infrastructure
✅ Basic tests and deployment scripts

## Next Steps (Phase 2)

1. Deploy infrastructure: `cd terraform && terraform apply`
2. Set up Google Ads Data Transfer in BigQuery console
3. Create Slack app from `scripts/slack_manifest.yml`
4. Test Campaign Health Agent in dry run mode
5. Review recommendations with SEM manager for 1 week

## Phase 2.5: Campaign Taxonomy & Sync Group System (IN PROGRESS)

**Goal**: Enable sync-group-aware operations for campaigns with multiple geo variants.

### New BigQuery Tables (12 total, was 9)

- **campaign_taxonomy**: Campaign classification and sync group management
  - Maps campaigns to sync groups (e.g., all NonBrand_AI-Code geos share keywords/ad copy)
  - Distinguishes `synced` (propagate changes to all geos) vs `individual` (evaluate independently)
  - Auto-detection from campaign naming conventions with confidence scoring

- **quality_score_history**: Daily QS snapshots for trend analysis
  - Tracks QS + 3 sub-components (Expected CTR, Ad Relevance, LP Experience) per keyword
  - Enables QS drop detection and geo variance analysis for synced campaigns

- **landing_page_audits**: LP health checks and content relevance
  - PageSpeed Insights metrics (performance score, FCP, LCP, CLS)
  - LLM-powered content relevance analysis per URL
  - URL deduplication across sync groups (each URL checked once)

### New Agents

- **Quality Score Agent**: Monitors QS trends, diagnoses sub-component issues, delegates fixes
- **Landing Page Agent**: LP health checks, content analysis, improvement recommendations

### Key Concepts

**Sync Groups**: Campaigns sharing identical keywords/ad copy (e.g., NonBrand_AI-Code has US, UK, DE, FR variants). Changes to keywords/ad copy propagate to ALL campaigns in the sync group.

**Management Strategies**:
- `synced`: NonBrand/Brand campaigns (multi-geo variants, shared content)
- `individual`: Competitor campaigns (unique per competitor, evaluated independently)

**Template Campaigns**: One campaign per sync group (preferably US) drives analysis. Aggregated data from all geos informs recommendations.

### Implementation Status

See IMPLEMENTATION_STATUS.md Phase 2.5 for detailed task breakdown.

## Important Notes

- **Never skip approval**: All recommendations require human approval (except in dry run)
- **Backward compatibility**: When updating agents, consider existing recommendations in BigQuery
- **Secrets management**: Use Secret Manager, never commit secrets to repo
- **Audit trail**: Every action must log to `agent_audit_log` table

## Support

- GitHub Issues: https://github.com/your-org/sem-gcp-agents/issues
- Documentation: See README.md and plan document
- Logs: Cloud Run logs in GCP Console
- Audit: Query BigQuery `sem_agents.agent_audit_log`
