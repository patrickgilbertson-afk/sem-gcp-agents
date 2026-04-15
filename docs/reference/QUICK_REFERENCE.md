# Quick Reference Card

## 📊 BigQuery Tables (9 total)

| Table | Purpose | Partition | Retention |
|-------|---------|-----------|-----------|
| `agent_recommendations` | All recommendations | Daily | 2 years |
| `agent_audit_log` | Complete audit trail | Daily | 1 year |
| `agent_state` | Agent run tracking | Daily | 90 days |
| `brand_guidelines` | Ad copy rules | None | Permanent |
| `agent_config` | Dynamic thresholds | None | Permanent |
| `recommendation_history` | Lifecycle tracking | Daily | 2 years |
| `llm_calls` | LLM API monitoring | Daily | 90 days |
| `approval_events` | User interactions | Daily | 1 year |
| `performance_metrics` | Campaign impact | Daily | 2 years |

**Location**: `sem_agents` dataset in BigQuery
**Documentation**: [docs/BIGQUERY_ARCHITECTURE.md](docs/BIGQUERY_ARCHITECTURE.md)

---

## 🚀 Portkey Integration

### What It Does
- Routes all LLM calls through Portkey gateway
- Logs every call to BigQuery automatically
- Caches similar prompts (30-50% cost savings)
- Provides unified observability dashboard

### Configuration
```bash
# .env file
PORTKEY_API_KEY=portkey_abc123...
PORTKEY_VIRTUAL_KEY_ANTHROPIC=key_anthropic123...
PORTKEY_VIRTUAL_KEY_GOOGLE=key_google123...
PORTKEY_ENABLE_CACHE=true
PORTKEY_CACHE_TTL=3600
```

### Usage in Agents
```python
from src.core import AnthropicClient

claude = AnthropicClient(model="claude-sonnet-4-5")
response = await claude.generate(
    prompt="Analyze campaigns...",
    system="You are an SEM analyst.",
    temperature=0.7,
    run_id=str(self.run_id),        # Required for logging
    agent_type=self.agent_type.value,  # Required for logging
)
```

**Setup Guide**: [docs/SETUP_PORTKEY.md](docs/SETUP_PORTKEY.md) (25 minutes)
**Documentation**: [docs/PORTKEY_INTEGRATION.md](docs/PORTKEY_INTEGRATION.md)

---

## 🔍 Key Queries

### LLM Cost by Agent (Last 30 Days)
```sql
SELECT
  agent_type,
  COUNT(*) as calls,
  SUM(total_tokens) as tokens,
  SUM(cost_usd) as cost,
  COUNTIF(cache_hit) as cache_hits,
  ROUND(COUNTIF(cache_hit) / COUNT(*) * 100, 2) as cache_hit_rate
FROM sem_agents.llm_calls
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
GROUP BY 1
ORDER BY 4 DESC;
```

### Recommendation Performance
```sql
SELECT
  agent_type,
  COUNT(*) as total_recommendations,
  COUNTIF(approval_status = 'approved') as approved,
  COUNTIF(applied_at IS NOT NULL) as applied,
  AVG(TIMESTAMP_DIFF(approved_at, created_at, HOUR)) as avg_approval_hours
FROM sem_agents.agent_recommendations
WHERE DATE(created_at) >= CURRENT_DATE() - 30
GROUP BY 1;
```

### Pending Approvals
```sql
SELECT * FROM sem_agents.v_pending_approvals
WHERE hours_pending < 8
ORDER BY created_at DESC;
```

### Campaign Impact (ROI)
```sql
SELECT
  ar.agent_type,
  COUNT(DISTINCT pm.recommendation_id) as recommendations_with_impact,
  SUM(CASE WHEN pm.metric_type = 'cost' THEN pm.change_value ELSE 0 END) as cost_change,
  SUM(CASE WHEN pm.metric_type = 'conversions' THEN pm.change_value ELSE 0 END) as conversion_lift
FROM sem_agents.performance_metrics pm
JOIN sem_agents.agent_recommendations ar ON pm.recommendation_id = ar.id
WHERE pm.metric_date >= CURRENT_DATE() - 30
  AND ar.applied_at IS NOT NULL
GROUP BY 1;
```

---

## 📁 Documentation Index

### Setup & Getting Started
- [README.md](README.md) - Project overview
- [GETTING_STARTED.md](GETTING_STARTED.md) - Step-by-step deployment
- [docs/SETUP_PORTKEY.md](docs/SETUP_PORTKEY.md) - Portkey setup (25 min)

### Architecture & Design
- [CLAUDE.md](CLAUDE.md) - Complete project context
- [docs/BIGQUERY_ARCHITECTURE.md](docs/BIGQUERY_ARCHITECTURE.md) - Database design
- [docs/PORTKEY_INTEGRATION.md](docs/PORTKEY_INTEGRATION.md) - LLM routing guide

### Implementation
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Current phase status
- [ENHANCEMENTS_SUMMARY.md](ENHANCEMENTS_SUMMARY.md) - Recent additions
- This file - Quick reference

---

## ⚡ Common Commands

### Local Development
```bash
# Start application
make run

# Run tests
make test

# Lint and format
make lint && make format

# Docker development
docker-compose up
```

### Deployment
```bash
# Deploy infrastructure
cd terraform && terraform apply

# Deploy application
./scripts/deploy.sh

# Seed initial data
python scripts/seed_bigquery.py
```

### Testing
```bash
# Trigger agent manually
curl -X POST "http://localhost:8080/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Check agent status
curl http://localhost:8080/api/v1/agents/status

# View recent logs
gcloud run services logs read sem-gcp-agents --region us-central1 --tail
```

### BigQuery
```bash
# Query recommendations
bq query --use_legacy_sql=false \
  "SELECT * FROM sem_agents.agent_recommendations
   WHERE DATE(created_at) = CURRENT_DATE()"

# Query LLM costs
bq query --use_legacy_sql=false \
  "SELECT SUM(cost_usd) as daily_cost
   FROM sem_agents.llm_calls
   WHERE DATE(timestamp) = CURRENT_DATE()"
```

---

## 🛠️ Troubleshooting

### Agent Issues
```bash
# Check logs
gcloud run services logs read sem-gcp-agents --region us-central1 --limit 100

# Check kill switch
curl http://localhost:8080/api/v1/agents/status

# Toggle kill switch
curl -X POST http://localhost:8080/api/v1/agents/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Portkey Issues
```bash
# Test Portkey connection
python -c "
from src.core import AnthropicClient
import asyncio

async def test():
    client = AnthropicClient()
    print(await client.generate('Hello', run_id='test', agent_type='test'))

asyncio.run(test())
"

# Check Portkey dashboard: https://app.portkey.ai
# Check BigQuery logs: bq query "SELECT * FROM sem_agents.llm_calls ORDER BY timestamp DESC LIMIT 5"
```

### BigQuery Issues
```bash
# Verify tables exist
bq ls sem_agents

# Check table schema
bq show sem_agents.llm_calls

# Verify data
bq query "SELECT COUNT(*) FROM sem_agents.llm_calls"
```

---

## 💰 Cost Estimates

### LLM Costs (with Portkey caching)
| Agent | Calls/Day | Daily Cost | Monthly Cost |
|-------|-----------|------------|--------------|
| Campaign Health | 30 | $0.63 | $18.90 |
| Keyword | 50 | $0.84 | $25.20 |
| Ad Copy | 10 | $0.42 | $12.60 |
| Bid Modifier | 7 | $0.25 | $7.50 |
| **Total** | **97** | **$2.14** | **$64.20** |

**Savings with caching**: ~$27/month vs without caching

### Infrastructure Costs (GCP)
| Service | Monthly Cost |
|---------|--------------|
| Cloud Run | $10-30 |
| BigQuery Storage | $5-15 |
| BigQuery Queries | $10-30 |
| Pub/Sub | <$5 |
| **Total** | **$30-85/month** |

### Total Monthly Cost
**$95-150/month** (infrastructure + LLM costs)

---

## 📊 Monitoring Checklist

Daily:
- [ ] Check Portkey dashboard for errors
- [ ] Review pending approvals in Slack
- [ ] Verify agents ran on schedule (Cloud Scheduler)
- [ ] Check LLM cost in BigQuery

Weekly:
- [ ] Review cache hit rate (target >30%)
- [ ] Analyze most expensive prompts
- [ ] Check recommendation approval rates
- [ ] Review applied recommendation impact

Monthly:
- [ ] Generate cost report
- [ ] Analyze agent ROI
- [ ] Optimize expensive operations
- [ ] Update agent thresholds if needed

---

## 🔗 Quick Links

**Dashboards**:
- [GCP Console](https://console.cloud.google.com)
- [BigQuery](https://console.cloud.google.com/bigquery)
- [Cloud Run](https://console.cloud.google.com/run)
- [Portkey Dashboard](https://app.portkey.ai)

**Documentation**:
- [Portkey Docs](https://docs.portkey.ai)
- [Google Ads API](https://developers.google.com/google-ads/api)
- [BigQuery Docs](https://cloud.google.com/bigquery/docs)

**Support**:
- Project Issues: IMPLEMENTATION_STATUS.md
- Portkey Support: support@portkey.ai
- GCP Support: [Google Cloud Support](https://cloud.google.com/support)

---

**Last Updated**: 2026-04-02
**Version**: 0.1.0 (Phase 1 + Enhancements)
