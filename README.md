# SEM GCP Agents

AI-powered SEM campaign management agents running on Google Cloud Platform.

## Overview

This framework automates SEM workflows using specialized AI agents:
- **Campaign Health Agent**: Monitors and diagnoses campaign performance issues
- **Keyword Agent**: Manages search terms, negatives, and keyword expansion (sync-group-aware)
- **Quality Score Agent**: Monitors QS trends, diagnoses sub-component issues, delegates fixes
- **Landing Page Agent**: LP health checks, content relevance analysis, improvement recommendations
- **Ad Copy Agent**: Generates RSA assets with brand compliance
- **Bid Modifier Agent**: Optimizes device, location, time, and audience modifiers

**Campaign Taxonomy System**: Intelligent campaign grouping enables sync-aware operations for multi-geo campaigns. Changes to keywords/ad copy automatically propagate to all geo variants in a sync group.

## Architecture

- **Platform**: Google Cloud Platform (Cloud Run, BigQuery, Pub/Sub)
- **Data**: BigQuery (Google Ads Data Transfer Service)
- **Approvals**: Slack (human-in-the-loop)
- **Execution**: Google Ads API
- **Models**: Claude Sonnet (Anthropic), Gemini Pro/Flash (Google AI)

## Setup

### Deployment Options

**🌐 Cloud Shell (Recommended)** ⭐
- No local setup required
- Pre-authenticated gcloud
- Browser-based deployment
- 📖 **[Complete Cloud Shell Guide](docs/guides/CLOUD_SHELL_SETUP.md)**

**💻 Local Development**
- Full local environment
- Continue with prerequisites below

### Prerequisites
- Python 3.11+
- GCP project with billing enabled
- gcloud CLI (or use Cloud Shell)
- Google Ads API developer token (approved for production)
- **Portkey account** (REQUIRED - LLM gateway) - [Sign up](https://portkey.ai)
- Anthropic API key (configured in Portkey)
- Google AI API key for Gemini (configured in Portkey)
- Slack workspace with admin access

### Local Installation

1. Clone repository and create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Authenticate with GCP:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

4. Set up BigQuery Data Transfer:
- Go to BigQuery → Data Transfers
- Create Google Ads transfer to `sem_ads_raw` dataset
- Schedule daily refresh

5. Deploy infrastructure:
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars
terraform init
terraform apply
```

6. Create Slack app:
- Use manifest from `scripts/slack_manifest.yml`
- Install to workspace
- Configure request URLs after Cloud Run deployment

### Local Development

Run locally:
```bash
make run
```

Run with Docker:
```bash
make docker-up
```

Run tests:
```bash
make test
```

## Project Structure

```
src/
├── main.py              # FastAPI entrypoint
├── config.py            # Configuration management
├── models/              # Pydantic data models
├── core/                # Base agent, orchestrator, LLM clients
├── agents/              # Specialized agents (health, keyword, ad_copy, bid_modifier)
├── integrations/        # External services (Google Ads, BigQuery, Slack)
└── sql/                 # Parameterized SQL queries

terraform/               # Infrastructure as code
tests/                   # Unit and integration tests
scripts/                 # Deployment and utility scripts
```

## Safety Features

- **Dry Run Mode**: Test recommendations without applying changes
- **Kill Switch**: `/sem-agents pause` to halt all agents
- **Approval Flow**: Slack approvals with 8-hour timeout
- **Guardrails**: Budget caps, rate limits, operation limits
- **Audit Log**: Every action logged to BigQuery

## Deployment

Deploy to Cloud Run:
```bash
make deploy
```

Or manually:
```bash
docker build -t gcr.io/$GCP_PROJECT_ID/sem-gcp-agents:latest .
docker push gcr.io/$GCP_PROJECT_ID/sem-gcp-agents:latest
gcloud run deploy sem-gcp-agents \
  --image gcr.io/$GCP_PROJECT_ID/sem-gcp-agents:latest \
  --region us-central1 \
  --platform managed
```

## Usage

### Slack Commands

- `/sem-agents status` - View agent status
- `/sem-agents run <agent_type>` - Manually trigger an agent
- `/sem-agents pause` - Activate kill switch
- `/sem-agents resume` - Deactivate kill switch
- `/sem-agents brand` - Edit brand guidelines

### Scheduled Runs

- Campaign Health: Daily at 7 AM
- Keyword Management: Daily at 8 AM
- Bid Modifiers: Weekly (Monday 9 AM)
- Ad Copy: On-demand only

## Documentation

📖 **[Full Documentation Index](docs/README.md)** - Complete guide to all documentation

### Quick Links

**Getting Started:**
- [System Overview](docs/architecture/SYSTEM_OVERVIEW.md) - Architecture, data flow, deployment guide
- [Getting Started](docs/guides/GETTING_STARTED.md) - First steps and setup
- [Quick Reference](docs/reference/QUICK_REFERENCE.md) - Common commands and workflows

**Architecture:**
- [BigQuery Architecture](docs/architecture/BIGQUERY_ARCHITECTURE.md) - Schema, tables, queries (12 tables)
- [Campaign Taxonomy System](docs/architecture/CAMPAIGN_TAXONOMY_SYSTEM.md) - Sync groups, multi-geo management

**Development:**
- [CLAUDE.md](CLAUDE.md) - Project instructions and context
- [Implementation Status](docs/development/IMPLEMENTATION_STATUS.md) - Roadmap and phase tracking
- [Gemini SQL Prompts](docs/reference/GEMINI_SQL_PROMPTS.md) - SQL generation with LLMs

**Integrations:**
- [Portkey Integration](docs/integrations/PORTKEY_INTEGRATION.md) - LLM observability and caching
- [Portkey Setup](docs/integrations/SETUP_PORTKEY.md) - Configuration guide

## License

Proprietary - Internal Use Only
