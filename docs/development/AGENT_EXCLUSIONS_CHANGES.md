# Agent Exclusions Implementation - Deployment Guide

## Summary
Added agent exclusion system to allow campaigns (especially Brand campaigns) to be excluded from specific agents (e.g., keyword, bid_modifier) when managed by external vendors.

## Files Changed/Created

### 1. Infrastructure (Terraform)
- **Modified**: `terraform/modules/bigquery/main.tf`
  - Added `agent_exclusions` (REPEATED STRING) column
  - Added `external_manager` (STRING, NULLABLE) column
  - To `campaign_taxonomy` table schema

### 2. New Python Files
- **Created**: `src/models/taxonomy.py`
  - Pydantic models: CampaignTaxonomy, SyncGroupContext
  - Enums: CampaignType, ManagementStrategy, DetectionMethod
  - Exclusion checking logic

- **Created**: `src/services/taxonomy.py`
  - TaxonomyService with methods:
    - `get_by_campaign_id()`, `get_sync_group_context()`
    - `is_agent_excluded()`, `is_agent_excluded_for_sync_group()`
    - `update_exclusions()`, `upsert_taxonomy()`

- **Created**: `src/utils/taxonomy.py`
  - `parse_campaign_name()` - auto-detection from naming conventions
  - `validate_taxonomy()` - validation logic
  - Brand campaigns get default exclusions: ["keyword", "bid_modifier"]

- **Created**: `scripts/seed_taxonomy.py`
  - CLI tool to populate taxonomy from Google Ads campaigns
  - Supports custom exclusions via flags

- **Created**: `src/services/__init__.py`
- **Created**: `src/utils/__init__.py`

### 3. Modified Python Files
- **Modified**: `src/models/__init__.py`
  - Added imports for taxonomy models

- **Modified**: `src/core/orchestrator.py`
  - Added TaxonomyService integration
  - Enhanced `run_agent()` to check exclusions before routing
  - Added `_log_exclusion()` method for audit trail
  - Accepts `campaign_id` or `sync_group` parameters

- **Modified**: `src/integrations/bigquery/client.py`
  - Enhanced `_convert_params()` to support ARRAY parameters
  - Now handles None values and empty arrays properly

## Deployment Steps

### 1. Pre-Deployment Checklist
```bash
# Verify all files compile
cd /path/to/SEM-GCP-Agents
python -m py_compile src/models/taxonomy.py
python -m py_compile src/services/taxonomy.py
python -m py_compile src/utils/taxonomy.py
python -m py_compile src/core/orchestrator.py
python -m py_compile scripts/seed_taxonomy.py

# Run tests (if available)
pytest tests/

# Lint code
ruff check src/ scripts/
```

### 2. GitHub Push
```bash
# Initialize git if needed
git init
git remote add origin <your-repo-url>

# Stage all changes
git add terraform/modules/bigquery/main.tf
git add src/models/taxonomy.py
git add src/models/__init__.py
git add src/services/
git add src/utils/
git add src/core/orchestrator.py
git add src/integrations/bigquery/client.py
git add scripts/seed_taxonomy.py

# Commit
git commit -m "feat: add agent exclusion system for campaign taxonomy

- Add agent_exclusions and external_manager to campaign_taxonomy table
- Create taxonomy models and service layer
- Add auto-detection with Brand campaign defaults
- Enhance orchestrator to enforce exclusions before routing
- Add seed script for initial taxonomy population
- Fix BigQuery client to handle ARRAY parameters

Relates to Phase 2.5 Campaign Taxonomy implementation"

# Push
git push origin main
```

### 3. GCP Infrastructure Deployment
```bash
cd terraform

# Plan changes (verify BigQuery schema update)
terraform plan

# Apply infrastructure changes
terraform apply

# Verify the campaign_taxonomy table has new columns
bq show --schema --format=prettyjson \
  ${PROJECT_ID}:sem_agents.campaign_taxonomy
```

### 4. Seed Taxonomy Data
```bash
# Option 1: Dry run first to see what would be created
python scripts/seed_taxonomy.py \
  --customer-id YOUR_CUSTOMER_ID \
  --brand-exclusions keyword,bid_modifier \
  --brand-manager "brand_vendor" \
  --dry-run

# Option 2: Actually populate the table
python scripts/seed_taxonomy.py \
  --customer-id YOUR_CUSTOMER_ID \
  --brand-exclusions keyword,bid_modifier \
  --brand-manager "brand_vendor"
```

### 5. Deploy Application to Cloud Run
```bash
# Build and push Docker image
docker build -t gcr.io/${PROJECT_ID}/sem-gcp-agents:latest .
docker push gcr.io/${PROJECT_ID}/sem-gcp-agents:latest

# Deploy to Cloud Run
gcloud run deploy sem-gcp-agents \
  --image gcr.io/${PROJECT_ID}/sem-gcp-agents:latest \
  --region us-central1 \
  --platform managed

# Or use deployment script if available
./scripts/deploy.sh
```

## Verification Steps

### 1. Verify BigQuery Schema
```sql
SELECT column_name, data_type, is_nullable
FROM `${PROJECT_ID}.sem_agents.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'campaign_taxonomy'
AND column_name IN ('agent_exclusions', 'external_manager');
```

### 2. Verify Taxonomy Data
```sql
-- Check Brand campaigns have exclusions
SELECT
  campaign_name,
  campaign_type,
  sync_group,
  agent_exclusions,
  external_manager
FROM `${PROJECT_ID}.sem_agents.campaign_taxonomy`
WHERE campaign_type = 'brand';

-- Check sync group distribution
SELECT
  sync_group,
  campaign_type,
  management_strategy,
  COUNT(*) as campaign_count,
  STRING_AGG(DISTINCT geo ORDER BY geo) as geos
FROM `${PROJECT_ID}.sem_agents.campaign_taxonomy`
GROUP BY sync_group, campaign_type, management_strategy
ORDER BY sync_group;
```

### 3. Test Orchestrator Exclusions
```bash
# Trigger orchestrator for a Brand campaign
curl -X POST https://your-cloud-run-url/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "keyword",
    "sync_group": "brand"
  }'

# Should return without running (agent excluded)
# Check audit log for exclusion event
```

```sql
-- Verify exclusion was logged
SELECT
  run_id,
  agent_type,
  event_type,
  timestamp,
  JSON_EXTRACT_SCALAR(details, '$.event') as event,
  JSON_EXTRACT_SCALAR(details, '$.reason') as reason
FROM `${PROJECT_ID}.sem_agents.agent_audit_log`
WHERE JSON_EXTRACT_SCALAR(details, '$.event') = 'agent_excluded'
ORDER BY timestamp DESC
LIMIT 10;
```

## Rollback Plan

If issues are found:

```bash
# Rollback Terraform changes (remove new columns)
cd terraform
git checkout HEAD~1 terraform/modules/bigquery/main.tf
terraform apply

# Rollback application code
git revert <commit-hash>
git push origin main

# Redeploy previous version
docker pull gcr.io/${PROJECT_ID}/sem-gcp-agents:previous-tag
gcloud run deploy sem-gcp-agents \
  --image gcr.io/${PROJECT_ID}/sem-gcp-agents:previous-tag
```

## Notes

- **No Breaking Changes**: All new fields have defaults, existing code continues to work
- **Backward Compatible**: Unclassified campaigns (not in taxonomy table) are not excluded
- **Conservative**: If ANY campaign in a sync group has an exclusion, the whole group is excluded
- **Audit Trail**: All exclusion skips are logged to `agent_audit_log`
- **Mock Data**: `seed_taxonomy.py` currently uses mock campaign data. Replace with actual Google Ads API call when ready.

## Dependencies

All required dependencies are already in `pyproject.toml`:
- pydantic>=2.10.0
- pydantic-settings>=2.6.0
- google-cloud-bigquery>=3.27.0
- structlog>=24.4.0

## Future Enhancements (Not in this PR)

1. Quality Score Agent delegation guards (when QS agent is implemented)
2. Slack modal UI for managing exclusions (when Slack integration is complete)
3. Replace mock data in seed script with actual Google Ads API integration
4. Add AGENT_EXCLUDED event type to EventType enum (currently uses ERROR)
