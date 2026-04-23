# SEM GCP Agents - System Overview

## Executive Summary

An AI-powered SEM campaign management framework that automates campaign optimization through specialized agents. Each agent monitors specific aspects of Google Ads performance, generates recommendations via LLM analysis, and executes approved changes with full audit trails.

**Key Principles**:
- **Human-in-the-Loop**: All recommendations require Slack approval before execution
- **Safety First**: Dry run mode, kill switch, rate limiting, operation caps
- **Audit Everything**: Complete audit trail in BigQuery for compliance
- **Modular Design**: Specialist agents for specific domains (keywords, ad copy, bids, etc.)

---

## Implementation Status

**Document Version**: 1.1 (Updated 2026-04-23)

**Current Deployment**:
- **Project ID**: `sem-gcp-agents-prod`
- **Service URL**: `https://sem-gcp-agents-<hash>-uc.a.run.app`
- **Region**: `us-central1`

**Phase Status**:

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ **COMPLETE** | Foundation + Campaign Health Agent deployed and running |
| **Phase 2.5** | 🚧 **IN PROGRESS** | Campaign Taxonomy + Quality Score + Landing Page agents |
| **Phase 3** | 📋 **PLANNED** | Keyword Agent |
| **Phase 4** | 📋 **PLANNED** | Ad Copy Agent |
| **Phase 5** | 📋 **PLANNED** | Bid Modifier Agent |

**Phase 1 Accomplishments** (Deployed):
- ✅ Core infrastructure (BigQuery, Cloud Run, Pub/Sub, Secrets, IAM)
- ✅ Base agent framework and orchestrator
- ✅ LLM clients (Claude via Portkey, Gemini via Portkey)
- ✅ Campaign Health Agent (generates ~5,900 recommendations per run)
- ✅ Slack approval workflow (interactive buttons for approve/reject)
- ✅ Terraform IaC for all components
- ✅ CI/CD pipeline via Cloud Build
- ✅ Audit logging and LLM call tracking

**Phase 2.5 In Progress** (Partial deployment):
- 🚧 Campaign taxonomy detection and sync group management
- 🚧 Quality Score history tracking and trend analysis
- 🚧 Landing Page audit system
- 📋 Quality Score Agent (planned)
- 📋 Landing Page Agent (planned)

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

#### 1. **Campaign Health Agent** ✅ **IMPLEMENTED**
- **Status**: Deployed and running in production
- **Model**: Claude Sonnet 4.5 (via Portkey)
- **Schedule**: Daily @ 7:00 AM
- **Scope**: Account-level campaign monitoring
- **Triggers**: Quality Score < 5, Zero conversions (30d), CTR < 2%
- **Actions**:
  - Pause underperforming ad groups
  - Delegate to Keyword Agent (low QS)
  - Delegate to Ad Copy Agent (low CTR)
- **Actual Output**: ~5,900 recommendations per run (based on production data)
- **Implementation Notes**: Fully operational with Slack approval workflow, generates recommendations and posts to Slack for human approval

#### 2. **Quality Score Agent** 📋 **PLANNED** (Phase 2.5)
- **Status**: Schema deployed, agent implementation pending
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
- **Table**: `quality_score_history` exists in BigQuery

#### 3. **Keyword Agent** 📋 **PLANNED** (Phase 3)
- **Status**: Not yet implemented
- **Model**: Claude Sonnet
- **Schedule**: Daily @ 8:00 AM
- **Scope**: Search term analysis & keyword expansion
- **Triggers**: 30-day search term report analysis
- **Actions**:
  - Add negative keywords (phrase match, campaign-level)
  - Add positive keywords (exact match, PAUSED status for review)
  - Remove low-volume keywords (0 impr/90d)
- **Sync-Group Aware**: Propagates keyword changes to all campaigns in sync group

#### 4. **Ad Copy Agent** 📋 **PLANNED** (Phase 4)
- **Status**: Not yet implemented
- **Models**: Gemini Flash (generation) + Claude Sonnet (strategy)
- **Schedule**: On-demand only (triggered by Campaign Health or QS Agent)
- **Scope**: RSA asset generation with brand compliance
- **Triggers**: Manual trigger, or automated for CTR < 3%, QS Ad Relevance < "Average"
- **Actions**:
  - Generate new RSA headlines (15) and descriptions (4)
  - Create new RSA (does NOT pause existing ads)
  - Pin brand compliance elements
- **Sync-Group Aware**: Propagates new RSAs to all campaigns in sync group

#### 5. **Bid Modifier Agent** 📋 **PLANNED** (Phase 5)
- **Status**: Not yet implemented
- **Model**: Gemini Pro
- **Schedule**: Weekly @ Monday 9:00 AM
- **Scope**: Device/location/time/audience bid modifiers
- **Triggers**: Weekly performance analysis
- **Actions**:
  - Adjust device modifiers (-30% to +30% max change/week)
  - Adjust location modifiers (zip/DMA level)
  - Adjust time-of-day modifiers
- **Guardrails**: Max ±30 percentage points per week

#### 6. **Landing Page Agent** 📋 **PLANNED** (Phase 2.5)
- **Status**: Schema deployed, agent implementation pending
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

## LLM Integration Architecture

### Portkey Gateway (Production)

All LLM calls in production route through **Portkey** (https://portkey.ai), an AI gateway that provides:

**Key Features**:
- **Unified API**: Single interface for Claude (Anthropic) and Gemini (Google)
- **Semantic Caching**: Reduces costs by caching similar prompts (configurable TTL)
- **Request Logging**: All LLM calls logged with metadata to BigQuery `llm_calls` table
- **Error Handling**: Automatic retries with exponential backoff
- **Cost Tracking**: Real-time token usage and cost estimation

**Configuration**:
```python
# src/core/llm_clients_portkey.py
client = Portkey(
    api_key=settings.portkey_api_key,
    virtual_key=settings.portkey_virtual_key_anthropic,  # or _google
)

# Enable caching
if settings.portkey_enable_cache:
    kwargs["cache"] = {
        "mode": "semantic",
        "max_age": settings.portkey_cache_ttl,
    }
```

**Models in Use**:
- **Campaign Health Agent**: `claude-sonnet-4-5` via Portkey
- **Quality Score Agent**: `claude-sonnet-4-5` via Portkey (planned)
- **Keyword Agent**: `claude-sonnet-4-5` via Portkey (planned)
- **Ad Copy Agent**: `gemini-2.0-flash` via Portkey (planned)
- **Bid Modifier Agent**: `gemini-2.0-flash` via Portkey (planned)
- **Landing Page Agent**: `claude-sonnet-4-5` via Portkey (planned)

**Call Tracking**:
Every LLM call is logged to `llm_calls` table with:
- Token counts (prompt, completion, total)
- Response time (ms)
- Cost estimate (USD)
- Portkey request ID (for debugging)
- Cache hit status

**Direct API Fallback**:
The codebase also includes `src/core/llm_clients.py` for direct Anthropic/Google API calls, but this is **not used in production**. All production traffic routes through Portkey.

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
   ├─> Slack sends webhook to /api/v1/slack/interactions
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

### Current Limitations (Phase 1 Implementation)

The following features from the design spec are not yet implemented:

**Approval Workflow**:
- ✅ Slack buttons update message UI correctly
- ❌ `apply_changes()` is NOT automatically triggered after approval (requires manual execution or future implementation)
- ❌ No approval timeout (8-hour auto-reject not implemented)
- ❌ No escalation reminder (4-hour warning not implemented)
- ❌ Approval events are logged to BigQuery but don't trigger downstream actions

**Pub/Sub Integration**:
- ✅ Agents can publish delegation events to Pub/Sub topics
- ❌ No subscription handlers consuming Pub/Sub messages
- ❌ Agent delegation is logged but not actioned (e.g., Campaign Health can't actually trigger Keyword Agent yet)

**Orchestrator**:
- ✅ Can run specific agents via `/api/v1/orchestrator/run`
- ❌ Status endpoint `/api/v1/orchestrator/status/{run_id}` returns `"not_implemented"`
- ❌ Orchestrator doesn't autonomously decide which agents to run (requires explicit `agent_type` parameter)

**Kill Switch**:
- ✅ Uses environment variable `DRY_RUN=true` to prevent mutations
- ❌ Kill switch is not stored in BigQuery (no persistence across restarts)
- ❌ `/api/v1/agents/kill-switch` endpoint modifies in-memory setting only

**Tables Not Yet Used**:
- `kill_switch_status` (not created in Terraform)
- `slack_approvals` (not created in Terraform)
- `google_ads_sync_log` (not created in Terraform)
- `rate_limit_tracker` (not created in Terraform)

---

## BigQuery Table Schemas

**Dataset**: `sem_agents`

**Tables Deployed** (12 total in Terraform):
- ✅ `agent_config` - Agent configuration and thresholds
- ✅ `agent_recommendations` - Generated recommendations with approval workflow
- ✅ `agent_audit_log` - Complete audit trail
- ✅ `agent_state` - Agent run tracking (replaces `agent_runs` in original spec)
- ✅ `brand_guidelines` - Brand voice and compliance rules
- ✅ `recommendation_history` - Recommendation lifecycle events
- ✅ `llm_calls` - LLM API usage tracking (replaces `llm_usage_log` in spec)
- ✅ `approval_events` - Slack approval interaction tracking
- ✅ `performance_metrics` - Before/after performance tracking
- ✅ `campaign_taxonomy` - Campaign classification and sync groups (Phase 2.5)
- ✅ `quality_score_history` - Daily QS snapshots (Phase 2.5)
- ✅ `landing_page_audits` - LP health checks (Phase 2.5)

**Tables NOT Implemented**:
- ❌ `kill_switch_status` - Using environment variable instead
- ❌ `slack_approvals` - Approvals tracked in `approval_events`
- ❌ `google_ads_sync_log` - Not yet implemented
- ❌ `rate_limit_tracker` - Rate limiting handled in-memory

### Core Tables

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

#### 2. `agent_recommendations` ✅ **DEPLOYED**
All recommendations generated by agents, with approval status and execution results.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.agent_recommendations (
  id STRING NOT NULL,                    -- Recommendation ID
  run_id STRING NOT NULL,                -- Links all recs from same agent execution
  agent_type STRING NOT NULL,            -- 'campaign_health', 'keyword', 'ad_copy', etc.
  created_at TIMESTAMP NOT NULL,
  title STRING NOT NULL,                 -- Human-readable summary
  description STRING,                    -- Detailed description
  rationale STRING,                      -- LLM's reasoning
  impact_estimate STRING,                -- Estimated impact (text description)
  risk_level STRING,                     -- 'low', 'medium', 'high'
  action_type STRING NOT NULL,           -- 'pause_ad_group', 'add_negative_keyword', etc.
  action_params JSON,                    -- Action-specific data (campaign_id, ad_group_id, etc.)
  status STRING NOT NULL,                -- 'pending', 'approved', 'rejected', 'applied', 'failed'
  approval_status STRING,                -- Tracks approval workflow state
  approved_by STRING,                    -- User who approved
  approved_at TIMESTAMP,
  applied_at TIMESTAMP,                  -- When action was executed
  applied_result JSON,                   -- Execution result
  error_message STRING,                  -- Error if failed
  metadata JSON                          -- Additional context
)
PARTITION BY DATE(created_at)
CLUSTER BY agent_type, status;
```

**Note**: This schema differs from the original spec. Key changes:
- `id` instead of `recommendation_id`
- Simplified to `title`/`description`/`rationale` instead of `entity_type`/`entity_id`/`entity_name`
- `action_params` JSON contains all action details (more flexible than separate columns)
- `impact_estimate` is text, not structured JSON
- `applied_at` and `applied_result` instead of `executed_at` and `execution_result`

#### 3. `agent_audit_log` ✅ **DEPLOYED**
Complete audit trail of every action taken by agents.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.agent_audit_log (
  run_id STRING NOT NULL,
  agent_type STRING NOT NULL,
  event_type STRING NOT NULL,            -- 'started', 'completed', 'error', 'approval_requested', etc.
  timestamp TIMESTAMP NOT NULL,
  details JSON                           -- Full context of what happened
)
PARTITION BY DATE(timestamp)
CLUSTER BY agent_type, event_type;
```

**Note**: Simplified from original spec - uses `event_type` + `details` JSON rather than many columns.

#### 4. `agent_state` ✅ **DEPLOYED**
Summary of each agent execution (replaces `agent_runs` from spec).

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.agent_state (
  run_id STRING NOT NULL,
  parent_run_id STRING,                  -- For delegated agent runs
  agent_type STRING NOT NULL,
  status STRING NOT NULL,                -- 'running', 'completed', 'failed'
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  error STRING                           -- Error message if failed
)
-- No partitioning (small table)
```

**Note**: Simplified from original spec. Recommendation counts are computed from `agent_recommendations` table rather than stored here.

#### 5. `brand_guidelines` ✅ **DEPLOYED**
Brand voice and compliance rules for ad copy generation.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.brand_guidelines (
  customer_id STRING NOT NULL,
  brand_voice STRING,                    -- Brand voice description
  prohibited_terms ARRAY<STRING>,        -- Terms to avoid
  required_phrases ARRAY<STRING>,        -- Required brand phrases
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING
)
```

#### 6. `recommendation_history` ✅ **DEPLOYED**
Tracks lifecycle events for recommendations (created, approved, rejected, applied, etc.).

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.recommendation_history (
  history_id STRING NOT NULL,
  recommendation_id STRING NOT NULL,
  run_id STRING NOT NULL,
  event_type STRING NOT NULL,            -- 'created', 'approved', 'rejected', 'applied', 'failed'
  event_timestamp TIMESTAMP NOT NULL,
  from_status STRING,
  to_status STRING,
  actor_type STRING,                     -- 'user', 'system', 'agent'
  actor_id STRING,
  actor_name STRING,
  event_details JSON
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY recommendation_id, event_type;
```

#### 7. `llm_calls` ✅ **DEPLOYED**
Tracks LLM API usage for cost monitoring and debugging (via Portkey).

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.llm_calls (
  call_id STRING NOT NULL,
  run_id STRING NOT NULL,
  agent_type STRING NOT NULL,
  provider STRING NOT NULL,              -- 'anthropic', 'google'
  model STRING NOT NULL,                 -- 'claude-sonnet-4-5', 'gemini-2.0-flash'
  timestamp TIMESTAMP NOT NULL,
  prompt_tokens INT64,
  completion_tokens INT64,
  total_tokens INT64,
  response_time_ms INT64,
  cost_usd FLOAT64,
  error_code STRING,
  error_message STRING,
  portkey_request_id STRING,             -- Portkey gateway request ID
  cache_hit BOOL                         -- Whether response was cached
)
PARTITION BY DATE(timestamp) (90-day expiration)
CLUSTER BY provider, model, agent_type;
```

#### 8. `approval_events` ✅ **DEPLOYED**
Tracks Slack approval interactions (replaces `slack_approvals` from spec).

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.approval_events (
  event_id STRING NOT NULL,
  recommendation_id STRING NOT NULL,
  run_id STRING NOT NULL,
  event_timestamp TIMESTAMP NOT NULL,
  user_id STRING NOT NULL,               -- Slack user ID
  user_name STRING,
  decision STRING NOT NULL,              -- 'approved', 'rejected'
  decision_reason STRING,
  time_to_decision_seconds INT64,
  slack_message_ts STRING                -- Slack message timestamp
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY user_id, decision;
```

#### 9. `performance_metrics` ✅ **DEPLOYED**
Before/after performance tracking for applied recommendations.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.performance_metrics (
  metric_id STRING NOT NULL,
  recommendation_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  ad_group_id STRING,
  metric_date DATE NOT NULL,
  metric_type STRING NOT NULL,           -- 'CTR', 'conversions', 'cost', 'QS', etc.
  before_value FLOAT64,
  after_value FLOAT64,
  change_value FLOAT64,
  change_percent FLOAT64,
  is_statistically_significant BOOL
)
PARTITION BY metric_date
CLUSTER BY recommendation_id, metric_type;
```

---

### Tables NOT Implemented

The following tables from the original spec are **not** created in Terraform:

#### ❌ `kill_switch_status`
**Reason**: Using environment variable `DRY_RUN=true` instead of database table for kill switch.

#### ❌ `slack_approvals`
**Reason**: Approval tracking handled by `approval_events` table.

#### ❌ `google_ads_sync_log`
**Reason**: Not yet implemented. Google Ads Data Transfer Service runs directly without tracking.

#### ❌ `rate_limit_tracker`
**Reason**: Rate limiting handled in-memory within agent execution, not persisted.

---

### Phase 2.5 Tables (Campaign Taxonomy & Quality Analysis)

#### 10. `campaign_taxonomy` ✅ **DEPLOYED**
Campaign classification and sync group management.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.campaign_taxonomy (
  campaign_id STRING NOT NULL,
  campaign_name STRING NOT NULL,
  customer_id STRING NOT NULL,
  campaign_type STRING NOT NULL,         -- 'brand', 'nonbrand', 'competitor'
  vertical STRING NOT NULL,              -- Product vertical classification
  geo STRING NOT NULL,                   -- 'US', 'UK', 'DE', 'FR', etc.
  sync_group STRING NOT NULL,            -- Sync group identifier
  management_strategy STRING NOT NULL,   -- 'synced' or 'individual'
  is_template BOOL NOT NULL,             -- TRUE if this is the template campaign
  detection_method STRING NOT NULL,      -- How it was classified: 'naming_convention', 'manual', 'llm'
  detection_confidence FLOAT64,          -- Confidence score (0.0-1.0)
  campaign_status STRING,                -- Campaign status from Google Ads
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING,
  notes STRING,
  agent_exclusions ARRAY<STRING>,        -- Agent types to exclude from this campaign
  external_manager STRING                -- If externally managed (e.g., 'pmax_team')
)
-- No partition (relatively small table)
CLUSTER BY sync_group, campaign_type;
```

**Note**: Simplified from spec. Uses `vertical` instead of `intent_category`, `is_template` bool instead of `sync_group_role` enum.

#### 11. `quality_score_history` ✅ **DEPLOYED**
Daily snapshots of keyword Quality Scores for trend analysis.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.quality_score_history (
  snapshot_id STRING NOT NULL,
  snapshot_date DATE NOT NULL,
  campaign_id STRING NOT NULL,
  ad_group_id STRING NOT NULL,
  keyword_id STRING NOT NULL,
  keyword_text STRING NOT NULL,
  match_type STRING,

  -- Quality Score components
  quality_score INT64,                   -- 1-10 or NULL if unavailable
  expected_ctr STRING,                   -- 'BELOW_AVERAGE', 'AVERAGE', 'ABOVE_AVERAGE'
  ad_relevance STRING,
  landing_page_experience STRING,

  -- Performance metrics
  impressions INT64,
  clicks INT64,
  cost_micros INT64,
  conversions FLOAT64,

  -- Taxonomy context (denormalized from campaign_taxonomy)
  sync_group STRING,
  campaign_type STRING,
  vertical STRING,
  geo STRING,

  created_at TIMESTAMP NOT NULL
)
PARTITION BY snapshot_date (365-day expiration)
CLUSTER BY sync_group, campaign_id;
```

**Note**: Column names simplified (`expected_ctr` not `quality_score_expected_ctr`). Includes denormalized taxonomy fields for faster queries.

#### 12. `landing_page_audits` ✅ **DEPLOYED**
Landing page health checks and content relevance analysis.

**Actual Terraform Schema**:
```sql
CREATE TABLE sem_agents.landing_page_audits (
  audit_id STRING NOT NULL,
  audit_date DATE NOT NULL,
  url STRING NOT NULL,                   -- The landing page URL
  url_hash STRING NOT NULL,              -- For deduplication

  -- PageSpeed Insights metrics
  performance_score FLOAT64,             -- 0.0-100.0
  fcp_ms INT64,                          -- First Contentful Paint
  lcp_ms INT64,                          -- Largest Contentful Paint
  cls FLOAT64,                           -- Cumulative Layout Shift
  mobile_friendly BOOL,
  is_accessible BOOL,
  http_status_code INT64,
  redirect_chain ARRAY<STRING>,

  -- Content analysis
  content_hash STRING,                   -- Hash of page content for change detection
  content_relevance_score FLOAT64,       -- 0.0-1.0
  keyword_alignment_score FLOAT64,       -- How well LP matches keywords
  improvement_suggestions JSON,          -- Structured recommendations

  -- Usage context
  sync_groups ARRAY<STRING>,             -- Which sync groups use this URL
  campaign_ids ARRAY<STRING>,            -- Which campaigns use this URL
  keyword_count INT64,                   -- How many keywords point to this URL

  created_at TIMESTAMP NOT NULL,
  next_audit_date DATE                   -- When to re-audit
)
PARTITION BY audit_date (365-day expiration)
CLUSTER BY url_hash;
```

**Note**: Column names abbreviated (`fcp_ms` not `first_contentful_paint_ms`). Uses `improvement_suggestions` JSON instead of ARRAY<STRING>. Removed audit metadata fields (status, triggered_by).

---

## Next Steps: Deployment to GCP

### Choose Your Deployment Method

**Option 1: Cloud Shell (Recommended for Quick Start)**
- ✅ No local setup required
- ✅ Pre-authenticated gcloud
- ✅ Browser-based terminal
- 📖 [Cloud Shell Setup Guide](../guides/CLOUD_SHELL_SETUP.md)

**Option 2: Local CLI**
- For heavy development work
- Requires local gcloud installation
- Follow instructions below

---

### Prerequisites Checklist

- [ ] **Google Cloud Project** - existing or new with billing enabled
- [ ] **gcloud CLI** - Cloud Shell (pre-installed) OR local installation
- [ ] **APIs Enabled** (check with `gcloud services list --enabled`):
  - Cloud Run API (`run.googleapis.com`)
  - BigQuery API (`bigquery.googleapis.com`)
  - Cloud Scheduler API (`cloudscheduler.googleapis.com`)
  - Pub/Sub API (`pubsub.googleapis.com`)
  - Secret Manager API (`secretmanager.googleapis.com`)
  - Cloud Build API (`cloudbuild.googleapis.com`)
- [ ] **Google Ads Account** with API access enabled
- [ ] **Anthropic API Key** (Claude Sonnet 4.5)
- [ ] **Google Cloud AI API** key (for Gemini)
- [ ] **Portkey Account** (REQUIRED - LLM gateway) - [Setup Guide](../integrations/PORTKEY_INTEGRATION.md)
  - Portkey API key
  - Anthropic virtual key
  - Google virtual key
- [ ] **Slack Workspace** with admin access
- [ ] **Service Account** with permissions:
  - BigQuery Admin
  - Cloud Run Admin
  - Secret Manager Admin
  - Pub/Sub Admin
  - Service Account User

---

### Step 0: Configure GCP Project

**Choose ONE path:** Use an existing project or create a new one.

#### Option A: Use Existing Project (Recommended)

```bash
# List your projects
gcloud projects list

# Set your existing project
export PROJECT_ID="your-existing-project-id"
export REGION="us-central1"

# Set as active
gcloud config set project $PROJECT_ID

# Verify billing is enabled
gcloud billing projects describe $PROJECT_ID --format="value(billingEnabled)"
# Should return: True

# Check which APIs are already enabled
gcloud services list --enabled

# Enable any missing APIs (safe to run even if already enabled)
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    bigquery.googleapis.com \
    pubsub.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    iam.googleapis.com

# Check for existing service accounts
gcloud iam service-accounts list
```

#### Option B: Create New Project

```bash
# Set project ID (must be globally unique)
export PROJECT_ID="sem-gcp-agents-prod"
export REGION="us-central1"

# Create project
gcloud projects create $PROJECT_ID --name="SEM GCP Agents"

# Set as active
gcloud config set project $PROJECT_ID

# Find your billing account
gcloud billing accounts list

# Link billing (replace BILLING_ACCOUNT_ID)
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID

# Enable all required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    bigquery.googleapis.com \
    pubsub.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    iam.googleapis.com
```

#### Authenticate gcloud CLI

```bash
# Login to GCP
gcloud auth login

# Set application default credentials (for local development)
gcloud auth application-default login

# Verify setup
gcloud config list
gcloud auth list
```

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

**Check for existing datasets first:**
```bash
# List existing BigQuery datasets
bq ls

# Check if sem_agents dataset exists
bq ls sem_agents 2>/dev/null && echo "Dataset exists" || echo "Dataset does not exist"
```

**Option A: Use Terraform (Recommended)**
```bash
cd terraform/modules/bigquery
terraform init
terraform plan -var="project_id=$PROJECT_ID"

# Review what will be created
# If datasets/tables exist, Terraform will show what will be imported/updated

terraform apply -var="project_id=$PROJECT_ID"
```

**Option B: Manual Creation**
```bash
# Create dataset (skip if exists)
bq mk --dataset --location=US $PROJECT_ID:sem_agents 2>/dev/null || echo "Dataset already exists"

# Run SQL schema files
# First, check which tables already exist
bq ls sem_agents

# Then create missing tables (safe to run, will error if table exists)
bq query --use_legacy_sql=false < sql/schema/01_agent_config.sql 2>/dev/null
bq query --use_legacy_sql=false < sql/schema/02_agent_recommendations.sql 2>/dev/null
# ... (repeat for all 12 tables)
```

This creates:
- Dataset: `sem_agents`
- All 12 tables (see schema section above)
- Views for common queries (e.g., `v_active_campaigns`, `v_low_qs_keywords`)

#### 1.3 Verify Data
```bash
# Check that Google Ads data is flowing
bq ls google_ads_raw 2>/dev/null && echo "Google Ads dataset exists" || echo "Need to set up Data Transfer"
bq head -n 10 google_ads_raw.p_ads_Campaign_$CUSTOMER_ID 2>/dev/null

# Check agent tables exist
bq ls sem_agents

# Verify table schemas
bq show sem_agents.agent_config
bq show sem_agents.agent_recommendations
```

---

### Step 2: Configure Secrets

#### 2.1 Create Secrets in Secret Manager

**First, check existing secrets:**
```bash
# List all secrets
gcloud secrets list

# Check if specific secrets exist
gcloud secrets describe anthropic-api-key 2>/dev/null && echo "Exists" || echo "Does not exist"
```

**Create or update secrets:**
```bash
# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if gcloud secrets describe $secret_name &>/dev/null; then
        echo "Updating existing secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# Google Ads credentials (JSON format)
create_or_update_secret "google-ads-credentials" '{"developer_token": "YOUR_TOKEN", "client_id": "...", "client_secret": "...", "refresh_token": "..."}'

# Anthropic API key (legacy - Portkey is primary in production)
create_or_update_secret "anthropic-api-key" "sk-ant-..."

# Portkey configuration (PRODUCTION LLM GATEWAY)
create_or_update_secret "portkey-api-key" "YOUR_PORTKEY_API_KEY"
create_or_update_secret "portkey-virtual-key-anthropic" "YOUR_ANTHROPIC_VIRTUAL_KEY"
create_or_update_secret "portkey-virtual-key-google" "YOUR_GOOGLE_VIRTUAL_KEY"

# Slack bot token
create_or_update_secret "slack-bot-token" "xoxb-..."

# Slack signing secret
create_or_update_secret "slack-signing-secret" "YOUR_SIGNING_SECRET"
```

**Or use Terraform (handles create/update automatically):**
```bash
cd terraform/modules/secrets
terraform init
terraform apply -var="google_ads_creds_json=..." -var="anthropic_key=..."
```

#### 2.2 Grant Service Account Access

```bash
# Set service account (will be created by Terraform, or create manually)
SERVICE_ACCOUNT="sa-sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

# Check if service account exists
gcloud iam service-accounts describe $SERVICE_ACCOUNT 2>/dev/null || \
  gcloud iam service-accounts create sa-sem-agents --display-name="SEM Agents Runtime"

# Grant access to secrets (safe to run multiple times)
for secret in google-ads-credentials anthropic-api-key portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google slack-bot-token slack-signing-secret; do
  echo "Granting $SERVICE_ACCOUNT access to $secret..."
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    2>/dev/null || echo "  (already granted)"
done

# Verify permissions
echo -e "\nVerifying secret access..."
for secret in google-ads-credentials anthropic-api-key portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google slack-bot-token slack-signing-secret; do
  echo "Checking $secret:"
  gcloud secrets get-iam-policy $secret --filter="bindings.members:$SERVICE_ACCOUNT" --format="value(bindings.role)"
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
3. Set **Request URL**: `https://YOUR_CLOUD_RUN_URL/api/v1/slack/interactions`
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
- **BigQuery**: Datasets and 12 tables (see schema section)
- **Pub/Sub**: Topics (`agent-tasks`, `agent-approvals`)
- **Cloud Run**: Service `sem-gcp-agents` with container image placeholder
- **Cloud Scheduler**: Jobs for each agent (initially paused)
- **IAM**: Service account `sa-sem-agents@` with permissions
- **Secret Manager**: Secrets (if not already created)

**Expected Output**:
```
Apply complete! Resources: 47 added, 0 changed, 0 destroyed.

Outputs:
cloud_run_url = "https://sem-gcp-agents-HASH-uc.a.run.app"
service_account_email = "sa-sem-agents@your-project-id.iam.gserviceaccount.com"
```

---

### Step 5: Build & Deploy Application

**Note**: In production, deployment is automated via Cloud Build CI/CD pipeline. The pipeline triggers on git push to `main` branch and automatically builds and deploys to Cloud Run.

#### 5.1 Automated Deployment (Production)
```bash
# Simply push to main branch
git push origin main

# Cloud Build automatically:
# 1. Builds Docker image
# 2. Pushes to Artifact Registry (us-central1-docker.pkg.dev/...)
# 3. Deploys to Cloud Run service `sem-gcp-agents`
# 4. Updates service with latest image

# Monitor build progress
gcloud builds list --limit 5
gcloud builds log <BUILD_ID>
```

#### 5.2 Manual Deployment (Development/Testing)
```bash
# Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push image
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/sem-gcp-agents/app:v1.0.0 .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/sem-gcp-agents/app:v1.0.0

# Or use Cloud Build
gcloud builds submit --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/sem-gcp-agents/app:v1.0.0
```

#### 5.3 Deploy to Cloud Run
```bash
gcloud run deploy sem-gcp-agents \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/sem-gcp-agents/app:v1.0.0 \
  --platform managed \
  --region us-central1 \
  --service-account sa-sem-agents@YOUR_PROJECT_ID.iam.gserviceaccount.com \
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
- Test interaction endpoint: `curl -X POST $SERVICE_URL/api/v1/slack/interactions`
- Test approval workflow: `curl -X POST $SERVICE_URL/api/v1/agents/test-slack-approval`

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
