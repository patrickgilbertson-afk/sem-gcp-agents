# SEM GCP Agents - System Overview

## Executive Summary

An AI-powered SEM campaign management framework that automates campaign optimization through specialized agents. Each agent monitors specific aspects of Google Ads performance, generates recommendations via LLM analysis, and executes approved changes with full audit trails.

**Key Principles**:
- **Human-in-the-Loop**: All recommendations require Slack approval before execution
- **Safety First**: Dry run mode, kill switch, rate limiting, operation caps
- **Audit Everything**: Complete audit trail in BigQuery for compliance
- **Modular Design**: Specialist agents for specific domains (keywords, ad copy, bids, etc.)

---

## System Architecture

### Tech Stack

| Component | Technology |
|-----------|-----------|
| **Runtime** | Python 3.11, FastAPI |
| **Compute** | Google Cloud Run (serverless containers) |
| **Data Warehouse** | Google BigQuery |
| **Messaging** | Google Cloud Pub/Sub |
| **Orchestration** | Google Cloud Scheduler |
| **AI Models** | Anthropic Claude Sonnet 4.5, Google Gemini Pro/Flash |
| **Ads API** | Google Ads API v17 |
| **Notifications** | Slack Bot API |
| **IaC** | Terraform |

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                        │
│                                                                   │
│  ┌───────────────┐      ┌──────────────────────────────────┐   │
│  │ Cloud         │      │  Cloud Run (FastAPI)              │   │
│  │ Scheduler     │─────>│  ┌────────────────────────────┐  │   │
│  │               │      │  │  Orchestrator              │  │   │
│  │ - 7am: Health │      │  │  - Routes to agents        │  │   │
│  │ - 8am: Keyword│      │  │  - Manages execution       │  │   │
│  │ - 9am: QS     │      │  └────────────────────────────┘  │   │
│  │ - Weekly: Bids│      │                                    │   │
│  └───────────────┘      │  ┌────────────────────────────┐  │   │
│                         │  │  Specialized Agents         │  │   │
│  ┌───────────────┐      │  │  - Campaign Health         │  │   │
│  │ BigQuery      │<────>│  │  - Keyword Manager         │  │   │
│  │               │      │  │  - Quality Score Monitor   │  │   │
│  │ - Ads Data    │      │  │  - Ad Copy Generator       │  │   │
│  │ - Agent Config│      │  │  - Bid Modifier Optimizer  │  │   │
│  │ - Audit Logs  │      │  │  - Landing Page Analyzer   │  │   │
│  │ - QS History  │      │  └────────────────────────────┘  │   │
│  │ - Taxonomy    │      │                                    │   │
│  └───────────────┘      │  ┌────────────────────────────┐  │   │
│                         │  │  LLM Clients                │  │   │
│  ┌───────────────┐      │  │  - Claude (analysis)       │  │   │
│  │ Pub/Sub       │<────>│  │  - Gemini (generation)     │  │   │
│  │               │      │  └────────────────────────────┘  │   │
│  │ - agent-tasks │      │                                    │   │
│  │ - approvals   │      │  ┌────────────────────────────┐  │   │
│  └───────────────┘      │  │  Integrations               │  │   │
│                         │  │  - Google Ads API          │  │   │
│  ┌───────────────┐      │  │  - Slack API               │  │   │
│  │ Secret Manager│<────>│  │  - BigQuery Client         │  │   │
│  │               │      │  └────────────────────────────┘  │   │
│  │ - API Keys    │      └──────────────────────────────────┘   │
│  │ - Tokens      │                                              │
│  └───────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Slack Workspace │
                    │  - Approval UI   │
                    │  - Alerts        │
                    └──────────────────┘
```

---

## Agent Hierarchy

### Agent Organization

All agents inherit from `BaseAgent` which implements the standard pipeline:

```
BaseAgent (Abstract)
├── gather_data()           # Query BigQuery/Ads API
├── analyze()               # LLM-powered analysis
├── generate_recommendations() # Create structured actions
├── request_approval()      # Post to Slack
└── apply_changes()         # Execute via Google Ads API
```

### Specialized Agents

#### 1. **Campaign Health Agent** (Phase 1 - COMPLETED)
- **Model**: Claude Sonnet 4.5
- **Schedule**: Daily @ 7:00 AM
- **Scope**: Account-level campaign monitoring
- **Triggers**: Quality Score < 5, Zero conversions (30d), CTR < 2%
- **Actions**:
  - Pause underperforming ad groups
  - Delegate to Keyword Agent (low QS)
  - Delegate to Ad Copy Agent (low CTR)
- **Output**: Up to 50 recommendations/day

#### 2. **Quality Score Agent** (Phase 2.5 - TODO)
- **Model**: Claude Sonnet 4.5
- **Schedule**: Daily @ 9:00 AM (after Campaign Health & Keyword)
- **Scope**: Keyword-level QS monitoring with trend analysis
- **Triggers**: QS drop ≥2 points (7d), Sub-component degradation
- **Actions**:
  - Diagnose which sub-component degraded (Expected CTR, Ad Relevance, LP Experience)
  - Delegate to Keyword Agent (Expected CTR issues)
  - Delegate to Ad Copy Agent (Ad Relevance issues)
  - Delegate to Landing Page Agent (LP Experience issues)
- **Sync-Group Aware**: Aggregates QS by keyword text across geos

#### 3. **Keyword Agent** (Phase 3 - TODO)
- **Model**: Claude Sonnet
- **Schedule**: Daily @ 8:00 AM
- **Scope**: Search term analysis & keyword expansion
- **Triggers**: 30-day search term report analysis
- **Actions**:
  - Add negative keywords (phrase match, campaign-level)
  - Add positive keywords (exact match, PAUSED status for review)
  - Remove low-volume keywords (0 impr/90d)
- **Sync-Group Aware**: Propagates keyword changes to all campaigns in sync group

#### 4. **Ad Copy Agent** (Phase 4 - TODO)
- **Models**: Gemini Flash (generation) + Claude Sonnet (strategy)
- **Schedule**: On-demand only (triggered by Campaign Health or QS Agent)
- **Scope**: RSA asset generation with brand compliance
- **Triggers**: Manual trigger, or automated for CTR < 3%, QS Ad Relevance < "Average"
- **Actions**:
  - Generate new RSA headlines (15) and descriptions (4)
  - Create new RSA (does NOT pause existing ads)
  - Pin brand compliance elements
- **Sync-Group Aware**: Propagates new RSAs to all campaigns in sync group

#### 5. **Bid Modifier Agent** (Phase 5 - TODO)
- **Model**: Gemini Pro
- **Schedule**: Weekly @ Monday 9:00 AM
- **Scope**: Device/location/time/audience bid modifiers
- **Triggers**: Weekly performance analysis
- **Actions**:
  - Adjust device modifiers (-30% to +30% max change/week)
  - Adjust location modifiers (zip/DMA level)
  - Adjust time-of-day modifiers
- **Guardrails**: Max ±30 percentage points per week

#### 6. **Landing Page Agent** (Phase 2.5 - TODO)
- **Model**: Claude Sonnet
- **Schedule**: Weekly @ Tuesday 10:00 AM, or on-demand (QS Agent trigger)
- **Scope**: Landing page health checks and content relevance
- **Triggers**: Weekly audit, or QS LP Experience < "Average"
- **Actions**:
  - Run PageSpeed Insights audits (performance, FCP, LCP, CLS)
  - Analyze content relevance vs. ad copy
  - Generate improvement recommendations (Slack only, no auto-execution)
  - Store audit results in BigQuery
- **Sync-Group Aware**: Deduplicates URLs across geos (same URL checked once)

### Agent Dependencies & Delegation

```
Campaign Health Agent
├─> Quality Score Agent (if QS < 5)
├─> Keyword Agent (if low search term quality)
└─> Ad Copy Agent (if CTR < 2%)

Quality Score Agent
├─> Keyword Agent (if Expected CTR degraded)
├─> Ad Copy Agent (if Ad Relevance degraded)
└─> Landing Page Agent (if LP Experience degraded)
```

---

## Data Flow

### Complete Request Flow

```
1. TRIGGER (Cloud Scheduler)
   │
   ├─> POST /api/v1/orchestrator/run
   │   Headers: { agent_type: "campaign_health" }
   │
2. ORCHESTRATOR
   │
   ├─> Validate request
   ├─> Check kill switch status
   ├─> Route to specialist agent
   │
3. AGENT EXECUTION (gather_data)
   │
   ├─> Query BigQuery for campaign metrics (30d)
   ├─> Query Google Ads API for real-time data
   ├─> Load agent config from `agent_config` table
   ├─> Check sync group taxonomy for campaign
   │
4. AGENT EXECUTION (analyze)
   │
   ├─> Prepare analysis prompt
   ├─> Call LLM (Claude/Gemini)
   ├─> Parse structured JSON response
   ├─> Filter recommendations by confidence threshold
   │
5. AGENT EXECUTION (generate_recommendations)
   │
   ├─> Convert LLM output to Recommendation objects
   ├─> Validate against Google Ads API constraints
   ├─> Apply sync group logic (propagate to all geos if synced)
   ├─> Store in `agent_recommendations` table
   │
6. APPROVAL REQUEST
   │
   ├─> Build Slack block UI with action buttons
   ├─> Post to configured channel (#sem-agent-approvals)
   ├─> Store approval_request_id in BigQuery
   ├─> Start 8-hour timeout timer
   │
7. USER INTERACTION (Slack)
   │
   ├─> User clicks "Approve" or "Reject"
   ├─> Slack sends webhook to /api/v1/slack/interaction
   ├─> Update `agent_recommendations.approval_status`
   ├─> Update Slack message with result
   │
8. AGENT EXECUTION (apply_changes) - If Approved
   │
   ├─> Check DRY_RUN mode
   ├─> Check kill switch
   ├─> Apply rate limiting (1 req/sec)
   ├─> Execute Google Ads API operations
   ├─> Log every mutation to `agent_audit_log`
   ├─> Handle errors with retry logic
   │
9. COMPLETION
   │
   ├─> Update recommendation status to "applied" or "failed"
   ├─> Post summary to Slack thread
   ├─> Publish completion event to Pub/Sub
   └─> Return 200 OK
```

### Data Sources & Sinks

#### Input Data Sources
1. **BigQuery** (Google Ads Data Transfer Service)
   - Campaign performance metrics (impressions, clicks, conversions, cost)
   - Keyword performance and Quality Score
   - Search term reports
   - Ad group and ad performance

2. **Google Ads API** (Real-time queries)
   - Current campaign/ad group statuses
   - Budget and bid information
   - Recommendation metadata
   - Geographic performance

3. **Agent Configuration** (BigQuery `agent_config` table)
   - Thresholds (QS min, CTR min, conversion min)
   - Rate limits
   - Operation caps
   - Dry run settings

4. **Campaign Taxonomy** (BigQuery `campaign_taxonomy` table)
   - Sync group assignments
   - Management strategies (synced vs individual)
   - Template campaign mappings

#### Output Data Sinks
1. **BigQuery Tables**
   - `agent_recommendations`: All generated recommendations
   - `agent_audit_log`: Complete audit trail of actions
   - `quality_score_history`: Daily QS snapshots
   - `landing_page_audits`: LP health check results

2. **Google Ads API** (Mutations)
   - Pause/enable operations
   - Keyword additions/removals
   - Ad creation
   - Bid modifier updates

3. **Slack API**
   - Approval request messages
   - Alert notifications
   - Completion summaries

4. **Cloud Pub/Sub**
   - Agent completion events
   - Error notifications
   - Async task triggers

---

## BigQuery Table Schemas

### Core Tables (9 Original)

#### 1. `agent_config`
Configuration for agent behavior (thresholds, limits, settings).

```sql
CREATE TABLE sem_agents.agent_config (
  config_id STRING NOT NULL,
  agent_type STRING NOT NULL,  -- 'campaign_health', 'keyword', 'ad_copy', etc.
  config_key STRING NOT NULL,
  config_value STRING NOT NULL,
  data_type STRING NOT NULL,   -- 'string', 'int', 'float', 'bool', 'json'
  description STRING,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  updated_by STRING NOT NULL
)
PARTITION BY DATE(updated_at)
CLUSTER BY agent_type, config_key;

-- Example rows:
-- config_id: 'ch_qscore_min', agent_type: 'campaign_health', config_key: 'quality_score_min', config_value: '5', data_type: 'int'
-- config_id: 'ch_ctr_min', agent_type: 'campaign_health', config_key: 'ctr_threshold', config_value: '0.02', data_type: 'float'
```

#### 2. `agent_recommendations`
All recommendations generated by agents, with approval status and execution results.

```sql
CREATE TABLE sem_agents.agent_recommendations (
  recommendation_id STRING NOT NULL,
  agent_type STRING NOT NULL,
  run_id STRING NOT NULL,               -- Links all recs from same agent execution
  entity_type STRING NOT NULL,           -- 'campaign', 'ad_group', 'keyword', 'ad'
  entity_id STRING NOT NULL,             -- Google Ads resource name
  entity_name STRING,
  recommendation_type STRING NOT NULL,   -- 'pause_ad_group', 'add_negative_keyword', etc.
  recommendation_data JSON NOT NULL,     -- Action-specific data (keyword text, match type, etc.)
  confidence_score FLOAT64,              -- 0.0 to 1.0
  estimated_impact JSON,                 -- { "metric": "CTR", "direction": "increase", "magnitude": "10-20%" }
  reasoning TEXT,                        -- LLM's explanation
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  approval_status STRING NOT NULL,       -- 'pending', 'approved', 'rejected', 'expired', 'applied', 'failed'
  approved_by STRING,
  approved_at TIMESTAMP,
  executed_at TIMESTAMP,
  execution_result JSON,                 -- { "status": "success", "operation_id": "...", "error": null }
  sync_group_id STRING                   -- NULL if individual campaign, else sync group identifier
)
PARTITION BY DATE(created_at)
CLUSTER BY agent_type, approval_status, entity_type;
```

#### 3. `agent_audit_log`
Complete audit trail of every action taken by agents.

```sql
CREATE TABLE sem_agents.agent_audit_log (
  audit_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  agent_type STRING NOT NULL,
  run_id STRING,
  recommendation_id STRING,
  action_type STRING NOT NULL,           -- 'analyze', 'recommend', 'approve', 'execute', 'error'
  entity_type STRING,
  entity_id STRING,
  action_details JSON NOT NULL,          -- Full context of what happened
  user_email STRING,                     -- Who approved (if applicable)
  dry_run BOOL NOT NULL,
  success BOOL NOT NULL,
  error_message STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY agent_type, action_type;
```

#### 4. `agent_runs`
Summary of each agent execution (start time, end time, result counts).

```sql
CREATE TABLE sem_agents.agent_runs (
  run_id STRING NOT NULL,
  agent_type STRING NOT NULL,
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  completed_at TIMESTAMP,
  status STRING NOT NULL,                -- 'running', 'completed', 'failed', 'dry_run'
  trigger_source STRING,                 -- 'scheduler', 'manual', 'delegate'
  total_recommendations INT64,
  approved_count INT64,
  rejected_count INT64,
  applied_count INT64,
  failed_count INT64,
  error_message STRING,
  execution_metadata JSON                -- { "llm_tokens": 5000, "api_calls": 120, "execution_time_sec": 45 }
)
PARTITION BY DATE(started_at)
CLUSTER BY agent_type, status;
```

#### 5. `kill_switch_status`
Single-row table to enable/disable all agent executions.

```sql
CREATE TABLE sem_agents.kill_switch_status (
  enabled BOOL NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  updated_by STRING NOT NULL,
  reason STRING
);

-- Initialize with:
INSERT INTO sem_agents.kill_switch_status (enabled, updated_by, reason)
VALUES (FALSE, 'system', 'Initial setup');
```

#### 6. `slack_approvals`
Tracks approval request messages sent to Slack.

```sql
CREATE TABLE sem_agents.slack_approvals (
  approval_id STRING NOT NULL,
  run_id STRING NOT NULL,
  agent_type STRING NOT NULL,
  slack_channel_id STRING NOT NULL,
  slack_message_ts STRING NOT NULL,      -- Timestamp ID of message for updates
  recommendation_ids ARRAY<STRING> NOT NULL,
  request_sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  expires_at TIMESTAMP NOT NULL,         -- Auto-reject after 8 hours
  escalated_at TIMESTAMP,                -- Escalation reminder at 4 hours
  resolved_at TIMESTAMP,
  resolution STRING                      -- 'approved', 'rejected', 'expired', 'error'
)
PARTITION BY DATE(request_sent_at)
CLUSTER BY agent_type, resolution;
```

#### 7. `google_ads_sync_log`
Tracks successful synchronizations from Google Ads Data Transfer Service.

```sql
CREATE TABLE sem_agents.google_ads_sync_log (
  sync_id STRING NOT NULL,
  table_name STRING NOT NULL,            -- 'p_ads_Campaign_1234567890', etc.
  data_date DATE NOT NULL,               -- Date of data in the table
  sync_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  rows_imported INT64,
  sync_status STRING NOT NULL,           -- 'success', 'partial', 'failed'
  error_message STRING
)
PARTITION BY data_date
CLUSTER BY table_name, sync_status;
```

#### 8. `llm_usage_log`
Tracks LLM API usage for cost monitoring and debugging.

```sql
CREATE TABLE sem_agents.llm_usage_log (
  usage_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  agent_type STRING NOT NULL,
  run_id STRING,
  model_provider STRING NOT NULL,        -- 'anthropic', 'google'
  model_name STRING NOT NULL,            -- 'claude-sonnet-4.5', 'gemini-pro'
  prompt_tokens INT64,
  completion_tokens INT64,
  total_tokens INT64,
  latency_ms INT64,
  cost_usd FLOAT64,
  request_metadata JSON                  -- { "temperature": 0.7, "max_tokens": 4096, "purpose": "campaign_analysis" }
)
PARTITION BY DATE(timestamp)
CLUSTER BY agent_type, model_provider;
```

#### 9. `rate_limit_tracker`
Per-agent rate limiting state.

```sql
CREATE TABLE sem_agents.rate_limit_tracker (
  agent_type STRING NOT NULL,
  window_start TIMESTAMP NOT NULL,       -- Start of rate limit window (1-minute buckets)
  operation_count INT64 NOT NULL,        -- Number of operations in this window
  last_operation_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(window_start)
CLUSTER BY agent_type;
```

---

### Phase 2.5 Tables (3 New)

#### 10. `campaign_taxonomy`
Campaign classification and sync group management.

```sql
CREATE TABLE sem_agents.campaign_taxonomy (
  campaign_id STRING NOT NULL,           -- Google Ads campaign ID
  campaign_name STRING NOT NULL,
  account_id STRING NOT NULL,

  -- Classification
  campaign_type STRING NOT NULL,         -- 'brand', 'nonbrand', 'competitor', 'shopping', 'display'
  intent_category STRING,                -- 'ai_code', 'ai_chat', 'alternatives', 'comparison', etc.
  geo STRING,                            -- 'US', 'UK', 'DE', 'FR', etc.

  -- Sync Group Configuration
  sync_group_id STRING,                  -- NULL if individual, else e.g., 'nonbrand_ai_code_v1'
  sync_group_role STRING,                -- 'template', 'replica', 'individual'
  template_campaign_id STRING,           -- Points to template campaign if this is a replica
  management_strategy STRING NOT NULL,   -- 'synced' (propagate changes) or 'individual'

  -- Metadata
  auto_detected BOOL NOT NULL DEFAULT TRUE,  -- TRUE if auto-classified from naming convention
  confidence_score FLOAT64,              -- 0.0 to 1.0 for auto-detection confidence
  manually_verified BOOL NOT NULL DEFAULT FALSE,
  verified_by STRING,
  verified_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(updated_at)
CLUSTER BY sync_group_id, campaign_type;

-- Example rows:
-- NonBrand_AI-Code_US: sync_group_id='nonbrand_ai_code_v1', sync_group_role='template', management_strategy='synced'
-- NonBrand_AI-Code_UK: sync_group_id='nonbrand_ai_code_v1', sync_group_role='replica', template_campaign_id='12345', management_strategy='synced'
-- Competitor_GitHub: sync_group_id=NULL, sync_group_role='individual', management_strategy='individual'
```

#### 11. `quality_score_history`
Daily snapshots of keyword Quality Scores for trend analysis.

```sql
CREATE TABLE sem_agents.quality_score_history (
  snapshot_id STRING NOT NULL,
  snapshot_date DATE NOT NULL,

  -- Entity identifiers
  campaign_id STRING NOT NULL,
  campaign_name STRING NOT NULL,
  ad_group_id STRING NOT NULL,
  ad_group_name STRING NOT NULL,
  keyword_id STRING NOT NULL,
  keyword_text STRING NOT NULL,
  match_type STRING NOT NULL,

  -- Quality Score components
  quality_score INT64,                   -- 1-10 or NULL if unavailable
  quality_score_expected_ctr STRING,     -- 'BELOW_AVERAGE', 'AVERAGE', 'ABOVE_AVERAGE'
  quality_score_ad_relevance STRING,
  quality_score_landing_page STRING,

  -- Performance context (last 30 days)
  impressions INT64,
  clicks INT64,
  ctr FLOAT64,
  cost_micros INT64,
  conversions FLOAT64,

  -- Sync group context
  sync_group_id STRING,                  -- From campaign_taxonomy

  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY snapshot_date
CLUSTER BY sync_group_id, campaign_id, quality_score;

-- Enables queries like:
-- "Show me keywords where QS dropped ≥2 points in last 7 days"
-- "Find geo-specific QS issues for sync group 'nonbrand_ai_code_v1'"
```

#### 12. `landing_page_audits`
Landing page health checks and content relevance analysis.

```sql
CREATE TABLE sem_agents.landing_page_audits (
  audit_id STRING NOT NULL,
  audit_date DATE NOT NULL,

  -- Page identifiers
  final_url STRING NOT NULL,             -- The landing page URL
  url_hash STRING NOT NULL,              -- SHA256 hash for deduplication
  campaigns ARRAY<STRING>,               -- List of campaign IDs using this URL
  sync_groups ARRAY<STRING>,             -- Deduplicated sync groups using this URL

  -- PageSpeed Insights metrics
  performance_score INT64,               -- 0-100
  first_contentful_paint_ms INT64,       -- FCP
  largest_contentful_paint_ms INT64,     -- LCP
  cumulative_layout_shift FLOAT64,       -- CLS
  time_to_interactive_ms INT64,          -- TTI
  speed_index INT64,

  -- Content relevance analysis (LLM-powered)
  content_summary TEXT,                  -- Claude's understanding of page content
  relevance_score FLOAT64,               -- 0.0-1.0: how well LP matches expected keywords/ads
  relevance_reasoning TEXT,              -- Why this score was assigned
  improvement_suggestions ARRAY<STRING>, -- Actionable recommendations

  -- Audit metadata
  audit_triggered_by STRING,             -- 'scheduled', 'qs_agent', 'manual'
  audit_status STRING NOT NULL,          -- 'completed', 'failed', 'partial'
  error_message STRING,

  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY audit_date
CLUSTER BY url_hash;

-- Deduplication logic: Same URL used in US/UK/DE campaigns = single audit
-- URLs stored with trailing slash normalized, query params sorted
```

---

## Next Steps: Deployment to GCP

### Prerequisites Checklist

- [ ] **Google Cloud Project** created with billing enabled
- [ ] **APIs Enabled**:
  - Cloud Run API
  - BigQuery API
  - Cloud Scheduler API
  - Pub/Sub API
  - Secret Manager API
  - Cloud Build API
- [ ] **Google Ads Account** with API access enabled
- [ ] **Anthropic API Key** (Claude Sonnet 4.5)
- [ ] **Google Cloud AI API** enabled (for Gemini)
- [ ] **Slack Workspace** with admin access
- [ ] **Service Account** with permissions:
  - BigQuery Admin
  - Cloud Run Admin
  - Secret Manager Admin
  - Pub/Sub Admin
  - Service Account User

---

### Step 1: Set Up BigQuery

#### 1.1 Enable Google Ads Data Transfer
1. Go to BigQuery Console → **Data Transfers**
2. Click **Create Transfer**
3. Select **Google Ads**
4. Configure:
   - **Customer ID**: Your Google Ads account ID
   - **Destination Dataset**: `google_ads_raw`
   - **Schedule**: Daily at 2 AM
   - **Tables**: Select all (Campaign, AdGroup, Keyword, SearchTerm, etc.)
5. Authorize with Google Ads OAuth
6. Wait 24-48 hours for initial backfill

#### 1.2 Create Agent Datasets & Tables
```bash
cd terraform/modules/bigquery
terraform init
terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform apply
```

This creates:
- Dataset: `sem_agents`
- All 12 tables listed above
- Views for common queries (e.g., `v_active_campaigns`, `v_low_qs_keywords`)

**Manual Alternative** (if not using Terraform):
```bash
# Run SQL scripts in order
bq mk --dataset --location=US YOUR_PROJECT_ID:sem_agents
bq query < sql/schema/01_agent_config.sql
bq query < sql/schema/02_agent_recommendations.sql
# ... (repeat for all 12 tables)
```

#### 1.3 Verify Data
```bash
# Check that Google Ads data is flowing
bq ls google_ads_raw
bq head -n 10 google_ads_raw.p_ads_Campaign_CUSTOMER_ID

# Check agent tables exist
bq ls sem_agents
```

---

### Step 2: Configure Secrets

#### 2.1 Create Secrets in Secret Manager
```bash
# Google Ads credentials
echo '{"developer_token": "YOUR_TOKEN", "client_id": "...", "client_secret": "...", "refresh_token": "..."}' | \
  gcloud secrets create google-ads-credentials --data-file=-

# Anthropic API key
echo "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-

# Slack bot token
echo "xoxb-..." | gcloud secrets create slack-bot-token --data-file=-

# Slack signing secret
echo "..." | gcloud secrets create slack-signing-secret --data-file=-
```

**Or use Terraform**:
```bash
cd terraform/modules/secrets
terraform apply -var="google_ads_creds_json=..." -var="anthropic_key=..."
```

#### 2.2 Grant Service Account Access
```bash
SERVICE_ACCOUNT="sem-agents@YOUR_PROJECT_ID.iam.gserviceaccount.com"

for secret in google-ads-credentials anthropic-api-key slack-bot-token slack-signing-secret; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

### Step 3: Create Slack App

#### 3.1 Create App from Manifest
1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From an app manifest**
3. Select your workspace
4. Paste contents of `scripts/slack_manifest.yml`
5. Review permissions:
   - `chat:write` (post messages)
   - `commands` (slash commands)
   - `incoming-webhook` (notifications)
6. Click **Create**

#### 3.2 Configure Interactivity
1. In app settings → **Interactivity & Shortcuts**
2. Turn on **Interactivity**
3. Set **Request URL**: `https://YOUR_CLOUD_RUN_URL/api/v1/slack/interaction`
4. Save changes

#### 3.3 Install to Workspace
1. Go to **Install App**
2. Click **Install to Workspace**
3. Authorize the app
4. Copy **Bot User OAuth Token** → Store in Secret Manager (already done in Step 2)
5. Copy **Signing Secret** → Store in Secret Manager (already done in Step 2)

#### 3.4 Create Approval Channel
```bash
# In Slack, create channel: #sem-agent-approvals
# Invite the bot: /invite @SEM Agents
```

---

### Step 4: Deploy Infrastructure with Terraform

#### 4.1 Initialize Terraform
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars:
# project_id = "your-project-id"
# region = "us-central1"
# google_ads_customer_id = "1234567890"
# slack_channel_id = "C01XXXXXXXXX"  # From #sem-agent-approvals

terraform init
```

#### 4.2 Plan & Apply
```bash
terraform plan -out=tfplan
terraform apply tfplan
```

This provisions:
- **BigQuery**: Datasets and tables
- **Pub/Sub**: Topics (`agent-tasks`, `agent-approvals`)
- **Cloud Run**: Service with container image placeholder
- **Cloud Scheduler**: Jobs for each agent (initially paused)
- **IAM**: Service account with permissions
- **Secret Manager**: Secrets (if not already created)

**Expected Output**:
```
Apply complete! Resources: 47 added, 0 changed, 0 destroyed.

Outputs:
cloud_run_url = "https://sem-agents-HASH-uc.a.run.app"
service_account_email = "sem-agents@your-project-id.iam.gserviceaccount.com"
```

---

### Step 5: Build & Deploy Application

#### 5.1 Build Docker Image
```bash
# Authenticate Docker to GCR
gcloud auth configure-docker

# Build image
docker build -t gcr.io/YOUR_PROJECT_ID/sem-gcp-agents:v1.0.0 .
docker push gcr.io/YOUR_PROJECT_ID/sem-gcp-agents:v1.0.0
```

**Or use Cloud Build**:
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/sem-gcp-agents:v1.0.0
```

#### 5.2 Deploy to Cloud Run
```bash
gcloud run deploy sem-agents \
  --image gcr.io/YOUR_PROJECT_ID/sem-gcp-agents:v1.0.0 \
  --platform managed \
  --region us-central1 \
  --service-account sem-agents@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "PROJECT_ID=YOUR_PROJECT_ID,DRY_RUN=true" \
  --set-secrets "GOOGLE_ADS_CREDENTIALS=google-ads-credentials:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,SLACK_BOT_TOKEN=slack-bot-token:latest,SLACK_SIGNING_SECRET=slack-signing-secret:latest" \
  --max-instances 10 \
  --timeout 900 \
  --memory 2Gi \
  --cpu 2 \
  --allow-unauthenticated  # For Slack webhooks (validate with signing secret)
```

**Verify Deployment**:
```bash
SERVICE_URL=$(gcloud run services describe sem-agents --region=us-central1 --format='value(status.url)')
curl $SERVICE_URL/health
# Expected: {"status": "ok", "version": "1.0.0"}
```

---

### Step 6: Initialize Database State

#### 6.1 Populate Agent Config
```bash
# Insert default thresholds
bq query --use_legacy_sql=false < sql/seed/agent_config_defaults.sql
```

**Example config rows**:
```sql
INSERT INTO sem_agents.agent_config (config_id, agent_type, config_key, config_value, data_type, description, updated_by)
VALUES
  ('ch_qscore_min', 'campaign_health', 'quality_score_min', '5', 'int', 'Minimum acceptable Quality Score', 'system'),
  ('ch_ctr_min', 'campaign_health', 'ctr_threshold', '0.02', 'float', 'Minimum CTR (2%)', 'system'),
  ('ch_zero_conv_days', 'campaign_health', 'zero_conversion_window_days', '30', 'int', 'Flag if 0 conversions in this window', 'system'),
  ('kw_negative_threshold', 'keyword', 'negative_keyword_min_cost', '50.0', 'float', 'Min cost to consider for negative keyword ($50)', 'system');
```

#### 6.2 Initialize Kill Switch
```bash
bq query --use_legacy_sql=false "
  INSERT INTO sem_agents.kill_switch_status (enabled, updated_by, reason)
  VALUES (FALSE, 'deployment', 'Initial deployment - agents enabled');
"
```

#### 6.3 Populate Campaign Taxonomy (Optional)
If you want to pre-classify campaigns:
```bash
python scripts/classify_campaigns.py --project-id YOUR_PROJECT_ID --auto-detect
```

This script:
- Queries all active campaigns from Google Ads API
- Auto-detects sync groups from naming conventions
- Populates `campaign_taxonomy` table
- Outputs CSV for manual review

---

### Step 7: Test in Dry Run Mode

#### 7.1 Trigger Campaign Health Agent Manually
```bash
curl -X POST "$SERVICE_URL/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

**Expected Flow**:
1. Agent queries BigQuery for campaign metrics
2. LLM analyzes data
3. Recommendations posted to Slack (#sem-agent-approvals)
4. **No changes applied** (DRY_RUN=true)

#### 7.2 Check Slack
- Verify message appears in #sem-agent-approvals
- Click "Approve" to test interaction endpoint
- Verify Slack message updates with ✅

#### 7.3 Verify BigQuery Logs
```sql
-- Check agent run summary
SELECT * FROM sem_agents.agent_runs
ORDER BY started_at DESC LIMIT 1;

-- Check recommendations created
SELECT recommendation_id, entity_name, recommendation_type, approval_status
FROM sem_agents.agent_recommendations
WHERE run_id = 'LATEST_RUN_ID';

-- Check audit log
SELECT timestamp, action_type, action_details
FROM sem_agents.agent_audit_log
WHERE run_id = 'LATEST_RUN_ID'
ORDER BY timestamp;
```

---

### Step 8: Enable Scheduled Execution

#### 8.1 Resume Cloud Scheduler Jobs
```bash
# Campaign Health Agent - Daily @ 7 AM
gcloud scheduler jobs resume campaign-health-daily --location=us-central1

# Quality Score Agent - Daily @ 9 AM (Phase 2.5)
gcloud scheduler jobs resume quality-score-daily --location=us-central1

# Keyword Agent - Daily @ 8 AM (Phase 3)
# gcloud scheduler jobs resume keyword-daily --location=us-central1

# Bid Modifier Agent - Weekly Monday @ 9 AM (Phase 5)
# gcloud scheduler jobs resume bid-modifier-weekly --location=us-central1
```

#### 8.2 Verify Schedules
```bash
gcloud scheduler jobs list --location=us-central1
```

---

### Step 9: Monitor Initial Week (Dry Run)

#### 9.1 Daily Checks
- [ ] Review Slack approval requests
- [ ] Check `agent_runs` table for errors
- [ ] Monitor LLM token usage in `llm_usage_log`
- [ ] Verify no Google Ads API quota issues

#### 9.2 Quality Assessment
- [ ] Review recommendation quality with SEM manager
- [ ] Adjust thresholds in `agent_config` if needed
- [ ] Check for false positives (pausing healthy ad groups)
- [ ] Verify sync group logic (propagation across geos)

**Example threshold adjustment**:
```sql
-- Increase CTR threshold from 2% to 3%
UPDATE sem_agents.agent_config
SET config_value = '0.03', updated_at = CURRENT_TIMESTAMP(), updated_by = 'john@company.com'
WHERE config_id = 'ch_ctr_min';
```

---

### Step 10: Enable Production Mode

Once confident after 1-2 weeks of dry run:

#### 10.1 Disable Dry Run
```bash
gcloud run services update sem-agents \
  --region us-central1 \
  --update-env-vars "DRY_RUN=false"
```

#### 10.2 Start Small (Canary)
Option 1: **Limit to specific campaigns**
```sql
-- Add config to only apply to test campaigns
INSERT INTO sem_agents.agent_config (config_id, agent_type, config_key, config_value, data_type, updated_by)
VALUES ('ch_allowed_campaigns', 'campaign_health', 'allowed_campaign_ids', '["12345", "67890"]', 'json', 'john@company.com');
```

Option 2: **Limit max operations per day**
```sql
INSERT INTO sem_agents.agent_config (config_id, agent_type, config_key, config_value, data_type, updated_by)
VALUES ('ch_max_daily_ops', 'campaign_health', 'max_operations_per_day', '10', 'int', 'john@company.com');
```

#### 10.3 Monitor First Production Run
```bash
# Watch Cloud Run logs
gcloud run services logs tail sem-agents --region=us-central1

# Check audit log for mutations
bq query --use_legacy_sql=false "
  SELECT
    timestamp,
    entity_type,
    entity_id,
    action_details
  FROM sem_agents.agent_audit_log
  WHERE
    action_type = 'execute'
    AND dry_run = FALSE
  ORDER BY timestamp DESC
  LIMIT 20;
"
```

#### 10.4 Verify in Google Ads UI
- Check that ad groups were actually paused
- Verify change history matches audit log
- Ensure no unintended side effects

---

### Step 11: Rollout Additional Agents (Phases 3-5)

As you build out new agents:

1. **Deploy new agent code** (same Cloud Run service)
2. **Add scheduler job** for new agent
3. **Run in dry run for 1 week**
4. **Adjust thresholds** based on recommendations
5. **Enable production** mode
6. **Monitor for 2 weeks** before next agent

**Recommended Rollout Order**:
- ✅ Phase 1: Campaign Health Agent (DONE)
- 🔄 Phase 2.5: Quality Score + Landing Page Agents (foundation for others)
- 📅 Phase 3: Keyword Agent (highest impact)
- 📅 Phase 4: Ad Copy Agent (requires brand review process)
- 📅 Phase 5: Bid Modifier Agent (most complex, lowest risk)

---

## Emergency Procedures

### Kill Switch Activation
```bash
# Pause all agents immediately (forces dry run)
bq query --use_legacy_sql=false "
  UPDATE sem_agents.kill_switch_status
  SET enabled = TRUE, updated_at = CURRENT_TIMESTAMP(), updated_by = 'john@company.com', reason = 'Emergency stop due to...';
"

# Or via Slack:
# /sem-agents pause --reason "Unexpected behavior in prod"
```

### Rollback Deployment
```bash
# Revert to previous image
gcloud run services update sem-agents \
  --region us-central1 \
  --image gcr.io/YOUR_PROJECT_ID/sem-gcp-agents:v0.9.0
```

### Undo Agent Changes
Google Ads API does not support bulk undo. Options:
1. **Manual revert** in Google Ads UI
2. **Query audit log** for change history:
   ```sql
   SELECT entity_type, entity_id, action_details
   FROM sem_agents.agent_audit_log
   WHERE
     run_id = 'PROBLEMATIC_RUN_ID'
     AND action_type = 'execute'
     AND success = TRUE;
   ```
3. **Create inverse operations** (e.g., if paused → enable)

---

## Cost Estimates (Monthly)

| Service | Usage | Cost |
|---------|-------|------|
| **Cloud Run** | 100 invocations/day, 2 min avg | ~$5 |
| **BigQuery Storage** | 50 GB (ads data + logs) | ~$1 |
| **BigQuery Queries** | 500 GB processed/month | ~$2.50 |
| **Pub/Sub** | 10K messages/month | <$1 |
| **Secret Manager** | 4 secrets, 30K accesses | <$1 |
| **Cloud Scheduler** | 5 jobs | <$1 |
| **Anthropic Claude** | 5M tokens/month (Sonnet 4.5) | ~$15 |
| **Google Gemini** | 2M tokens/month (Pro/Flash) | ~$3 |
| **Google Ads API** | Free (within quota) | $0 |
| **Slack API** | Free tier | $0 |
| **TOTAL** | | **~$30/month** |

*Scales with campaign count and agent frequency.*

---

## Support & Troubleshooting

### Logs
```bash
# Cloud Run logs
gcloud run services logs tail sem-agents --region=us-central1

# BigQuery audit log
SELECT * FROM sem_agents.agent_audit_log
WHERE success = FALSE
ORDER BY timestamp DESC LIMIT 50;

# LLM usage and costs
SELECT
  agent_type,
  model_name,
  SUM(total_tokens) as total_tokens,
  SUM(cost_usd) as total_cost
FROM sem_agents.llm_usage_log
WHERE DATE(timestamp) = CURRENT_DATE()
GROUP BY agent_type, model_name;
```

### Common Issues

**Issue**: "No recommendations generated"
- Check if campaigns meet thresholds (QS < 5, CTR < 2%, etc.)
- Verify BigQuery data exists for date range (last 30 days)
- Check LLM response in `llm_usage_log`

**Issue**: "Slack approval not working"
- Verify signing secret is correct
- Check Cloud Run logs for webhook errors
- Test interaction endpoint: `curl -X POST $SERVICE_URL/api/v1/slack/interaction`

**Issue**: "Google Ads API quota exceeded"
- Check rate limiting in code (1 req/sec)
- Review operation count in `agent_audit_log`
- Request quota increase in Google Ads API console

---

## Maintenance Checklist

### Weekly
- [ ] Review approved vs rejected recommendations
- [ ] Check error rates in `agent_runs`
- [ ] Monitor LLM costs in `llm_usage_log`

### Monthly
- [ ] Update agent thresholds based on performance
- [ ] Review sync group taxonomy for new campaigns
- [ ] Archive old audit logs (>90 days)
- [ ] Check BigQuery storage costs

### Quarterly
- [ ] Update LLM system prompts based on learnings
- [ ] Review and update CLAUDE.md instructions
- [ ] Terraform state refresh
- [ ] Security audit (rotate secrets)

---

## Appendix: Useful Queries

### Dashboard Queries

```sql
-- Agent performance summary (last 30 days)
SELECT
  agent_type,
  COUNT(DISTINCT run_id) as total_runs,
  SUM(total_recommendations) as total_recs,
  SUM(approved_count) as approved,
  SUM(applied_count) as applied,
  SAFE_DIVIDE(SUM(approved_count), SUM(total_recommendations)) as approval_rate,
  SAFE_DIVIDE(SUM(applied_count), SUM(approved_count)) as success_rate
FROM sem_agents.agent_runs
WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY agent_type;

-- Top recommendation types
SELECT
  agent_type,
  recommendation_type,
  COUNT(*) as count,
  AVG(confidence_score) as avg_confidence,
  COUNTIF(approval_status = 'approved') as approved_count
FROM sem_agents.agent_recommendations
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY agent_type, recommendation_type
ORDER BY count DESC;

-- Quality Score trends for sync groups
SELECT
  h.sync_group_id,
  h.snapshot_date,
  AVG(h.quality_score) as avg_qs,
  COUNTIF(h.quality_score < 5) as low_qs_count,
  AVG(CASE WHEN h.quality_score_expected_ctr = 'ABOVE_AVERAGE' THEN 1
           WHEN h.quality_score_expected_ctr = 'AVERAGE' THEN 0.5
           ELSE 0 END) as expected_ctr_score
FROM sem_agents.quality_score_history h
WHERE
  h.snapshot_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND h.sync_group_id IS NOT NULL
GROUP BY h.sync_group_id, h.snapshot_date
ORDER BY h.sync_group_id, h.snapshot_date;

-- Landing page performance
SELECT
  a.final_url,
  a.audit_date,
  a.performance_score,
  a.relevance_score,
  ARRAY_TO_STRING(a.campaigns, ', ') as campaign_list,
  a.improvement_suggestions
FROM sem_agents.landing_page_audits a
WHERE
  a.audit_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND (a.performance_score < 70 OR a.relevance_score < 0.7)
ORDER BY a.relevance_score ASC;
```

---

**Document Version**: 1.0
**Last Updated**: 2026-04-15
**Maintained By**: SEM Engineering Team
