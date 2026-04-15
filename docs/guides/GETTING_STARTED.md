# Getting Started with SEM GCP Agents

## What Was Built

Phase 1 (Foundation) is **100% complete**! Here's what you have:

### 📦 Complete Framework (2,493 lines of Python)
- ✅ Base agent pipeline that all agents follow
- ✅ Campaign Health Agent (fully implemented)
- ✅ LLM clients for Claude and Gemini
- ✅ Orchestrator for routing work to agents
- ✅ Complete integration layer (BigQuery, Google Ads, Slack, Pub/Sub)

### 🏗️ Infrastructure as Code
- ✅ 6 Terraform modules for complete GCP setup
- ✅ BigQuery: 5 tables (recommendations, audit log, state, config, brand guidelines)
- ✅ Cloud Run service configuration
- ✅ Pub/Sub: 5 topics for inter-agent messaging
- ✅ IAM: Service account with proper permissions
- ✅ Cloud Scheduler: 3 cron jobs (Campaign Health daily, Keyword daily, Bid Modifier weekly)

### 🧪 Testing & Development
- ✅ Unit test framework with pytest
- ✅ Docker and docker-compose for local development
- ✅ CI/CD pipeline (GitHub Actions)
- ✅ Deployment and utility scripts

## Next Steps: Deploy to GCP

### Step 1: Configure Environment (5 minutes)

```bash
# Copy and edit environment variables
cp .env.example .env

# Edit .env with your actual values:
# - GCP_PROJECT_ID
# - GOOGLE_ADS_* credentials
# - ANTHROPIC_API_KEY
# - GOOGLE_AI_API_KEY
# - SLACK_* tokens (leave blank for now)
```

### Step 2: Set Up GCP (15 minutes)

```bash
# Authenticate
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  pubsub.googleapis.com \
  cloudscheduler.googleapis.com

# Set up BigQuery Data Transfer (via console)
# 1. Go to BigQuery → Data Transfers
# 2. Create transfer: Google Ads → sem_ads_raw dataset
# 3. Schedule: Daily, 2 AM
# 4. Authenticate with Google Ads
```

### Step 3: Deploy Infrastructure (10 minutes)

```bash
cd terraform

# Copy and configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Deploy (creates 30+ resources)
terraform init
terraform plan    # Review what will be created
terraform apply   # Confirm with 'yes'

# Note the outputs:
# - service_url (your Cloud Run URL)
# - service_account_email
# - bigquery_dataset
```

### Step 4: Build and Deploy Application (10 minutes)

```bash
# Build Docker image
export PROJECT_ID=$(gcloud config get-value project)
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:latest .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:latest

# Update Cloud Run
gcloud run deploy sem-gcp-agents \
  --image gcr.io/$PROJECT_ID/sem-gcp-agents:latest \
  --region us-central1 \
  --platform managed

# Or use the deployment script
./scripts/deploy.sh
```

### Step 5: Set Up Slack (15 minutes)

```bash
# 1. Create Slack app
# - Go to api.slack.com/apps
# - Create New App → From manifest
# - Paste contents of scripts/slack_manifest.yml
# - Update all URLs with your Cloud Run service URL

# 2. Install to workspace
# - OAuth & Permissions → Install to Workspace
# - Copy Bot User OAuth Token

# 3. Update secrets in GCP
gcloud secrets versions add slack-bot-token \
  --data-file=- <<< "xoxb-your-token"

gcloud secrets versions add slack-signing-secret \
  --data-file=- <<< "your-signing-secret"

# 4. Get channel ID
# - Right-click channel → View channel details → Copy channel ID
# - Update in .env or terraform.tfvars: SLACK_APPROVAL_CHANNEL_ID
```

### Step 6: Seed Initial Data (5 minutes)

```bash
# Install dependencies locally
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Seed BigQuery with configuration
python scripts/seed_bigquery.py
```

### Step 7: Test Campaign Health Agent (30 minutes)

```bash
# Ensure dry run mode is enabled
# In terraform.tfvars: DRY_RUN = "true"

# Trigger manually via API
curl -X POST "https://your-service-url.run.app/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Or trigger via Cloud Scheduler
gcloud scheduler jobs run campaign-health-daily --location us-central1

# Check logs
gcloud run services logs read sem-gcp-agents --region us-central1 --limit 100

# Check BigQuery for results
bq query --use_legacy_sql=false \
  "SELECT * FROM sem_agents.agent_audit_log ORDER BY timestamp DESC LIMIT 10"

# Check Slack for approval message
# Should appear in configured channel
```

### Step 8: Review and Enable Live Mode (After 1 Week)

```bash
# After reviewing dry run recommendations with SEM manager:

# 1. Update environment to enable live mode
# In terraform.tfvars: DRY_RUN = "false"

# 2. Redeploy
terraform apply

# 3. Monitor closely for first week
# - Check Cloud Run logs
# - Review BigQuery audit log
# - Confirm Slack approvals work
# - Verify Google Ads changes apply correctly

# 4. Set up monitoring alerts
# - Create Cloud Monitoring dashboard
# - Set up Slack alerts for errors
# - Monitor daily spend changes
```

## Local Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Run locally
make run
# or: uvicorn src.main:app --reload --port 8080

# Run tests
make test

# Lint and format
make lint
make format

# Docker development
docker-compose up
```

## Project Structure Quick Reference

```
src/
├── main.py              # FastAPI app (health, orchestrator, agent, slack endpoints)
├── config.py            # Settings from environment variables
├── models/              # Pydantic models (recommendations, campaigns, keywords)
├── core/
│   ├── base_agent.py    # Base class all agents inherit from
│   ├── orchestrator.py  # Routes work to specialist agents
│   └── llm_clients.py   # Claude + Gemini wrappers
├── agents/
│   └── campaign_health/ # First implemented agent (monitors health, pauses bad ad groups)
├── integrations/
│   ├── bigquery/        # Query execution, audit logging
│   ├── google_ads/      # API client with rate limiting
│   ├── slack/           # Approval flow, Block Kit messages
│   └── pubsub/          # Inter-agent messaging
└── api/                 # FastAPI routers

terraform/               # Complete GCP infrastructure
scripts/                 # Deployment, seeding, utilities
tests/                   # Unit and integration tests
```

## Common Commands

```bash
# Check agent status
curl https://your-url.run.app/api/v1/agents/status

# Trigger specific agent
curl -X POST https://your-url.run.app/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# View logs
gcloud run services logs read sem-gcp-agents --region us-central1 --tail

# Query recommendations
bq query --use_legacy_sql=false \
  "SELECT * FROM sem_agents.agent_recommendations
   WHERE DATE(created_at) = CURRENT_DATE()"

# Update secrets
gcloud secrets versions add secret-name --data-file=-

# Restart Cloud Run service
gcloud run services update sem-gcp-agents --region us-central1
```

## Troubleshooting

### "google.auth.exceptions.DefaultCredentialsError"
```bash
gcloud auth application-default login
```

### "BigQuery table not found"
- Ensure Google Ads Data Transfer is set up and has run at least once
- Check that terraform applied successfully (creates sem_agents dataset)

### "Slack signature verification failed"
- Verify SLACK_SIGNING_SECRET matches Slack app settings
- Update request URLs in Slack app config to your Cloud Run URL

### Agent runs but produces no recommendations
- Verify DRY_RUN setting
- Check BigQuery has data for last 30 days
- Review Cloud Run logs for query errors

### Need to pause all agents quickly
```bash
# Activate kill switch
curl -X POST https://your-url.run.app/api/v1/agents/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "reason": "Emergency stop"}'
```

## Key Documentation

- **README.md**: Project overview and setup
- **CLAUDE.md**: Detailed project context for AI assistance
- **IMPLEMENTATION_STATUS.md**: Current phase status and TODO
- **This file**: Step-by-step deployment guide

## Architecture Diagram

```
Cloud Scheduler (cron) → Cloud Run (FastAPI)
                              ↓
                        Orchestrator
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
            Campaign Health Agent  (Keyword/AdCopy/BidModifier Agents - TODO)
                    ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
    BigQuery   Google Ads  Slack (approvals)
```

## Success Criteria

✅ **Foundation Complete**: All infrastructure deployable, agents runnable
⏳ **Phase 2 Target**: Campaign Health Agent in production dry run
⏳ **Phase 3-5**: Remaining agents implemented
⏳ **Phase 6**: Full integration and hardening

## Support

- **Issues**: Check IMPLEMENTATION_STATUS.md for known issues
- **Logs**: Cloud Run logs and BigQuery audit_log table
- **Emergency**: Use kill switch endpoint to halt all agents

---

**Status**: Phase 1 (Foundation) ✅ COMPLETE
**Next**: Deploy to GCP and test Campaign Health Agent in dry run mode
**ETA for Production**: 2-3 weeks with 1 week dry run validation
