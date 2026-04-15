# Portkey Setup - Quick Start

## Step-by-Step Setup

### 1. Create Portkey Account (5 minutes)

1. Go to [portkey.ai](https://portkey.ai)
2. Sign up with email or Google
3. Verify email

### 2. Create Virtual Keys (5 minutes)

#### For Anthropic (Claude)

1. In Portkey dashboard, go to **Virtual Keys**
2. Click **+ Add Key**
3. Select **Anthropic** as provider
4. Paste your Anthropic API key: `sk-ant-...`
5. Name it: `sem-agents-anthropic`
6. Click **Create**
7. **Copy the Virtual Key ID** (starts with `key_...`)

#### For Google (Gemini)

1. Click **+ Add Key** again
2. Select **Google AI** as provider
3. Paste your Google AI API key
4. Name it: `sem-agents-google`
5. Click **Create**
6. **Copy the Virtual Key ID**

### 3. Get Portkey API Key (1 minute)

1. In dashboard, go to **Settings** → **API Keys**
2. Copy your Portkey API key (starts with `portkey_...`)

### 4. Configure Local Environment (2 minutes)

```bash
# Add to .env file
PORTKEY_API_KEY=portkey_abc123...
PORTKEY_VIRTUAL_KEY_ANTHROPIC=key_anthropic123...
PORTKEY_VIRTUAL_KEY_GOOGLE=key_google123...
PORTKEY_ENABLE_CACHE=true
PORTKEY_CACHE_TTL=3600
```

### 5. Configure Production (GCP Secret Manager) (5 minutes)

```bash
# Create secrets in GCP
gcloud secrets create portkey-api-key \
  --data-file=- <<< "portkey_abc123..."

gcloud secrets create portkey-virtual-key-anthropic \
  --data-file=- <<< "key_anthropic123..."

gcloud secrets create portkey-virtual-key-google \
  --data-file=- <<< "key_google123..."

# Grant access to service account
gcloud secrets add-iam-policy-binding portkey-api-key \
  --member="serviceAccount:sa-sem-agents@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding portkey-virtual-key-anthropic \
  --member="serviceAccount:sa-sem-agents@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding portkey-virtual-key-google \
  --member="serviceAccount:sa-sem-agents@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 6. Update Terraform (2 minutes)

Edit `terraform/variables.tf`:

```hcl
variable "secrets" {
  description = "Map of secrets to create"
  type        = map(string)
  default     = {
    "anthropic-api-key"              = ""
    "google-ads-developer-token"     = ""
    "google-ads-refresh-token"       = ""
    "google-ads-client-id"           = ""
    "google-ads-client-secret"       = ""
    "slack-bot-token"                = ""
    "slack-signing-secret"           = ""
    "google-ai-api-key"              = ""
    # NEW: Portkey secrets
    "portkey-api-key"                = ""
    "portkey-virtual-key-anthropic"  = ""
    "portkey-virtual-key-google"     = ""
  }
}
```

### 7. Test Locally (2 minutes)

```bash
# Install dependencies
pip install -e ".[dev]"

# Test Portkey connection
python -c "
from src.core import AnthropicClient
import asyncio

async def test():
    client = AnthropicClient()
    response = await client.generate(
        prompt='Say hello',
        run_id='test-run',
        agent_type='test'
    )
    print(response)

asyncio.run(test())
"
```

Expected output:
```
Hello! How can I assist you today?
```

### 8. Deploy to Production (5 minutes)

```bash
# Update secrets in terraform.tfvars
cd terraform
terraform plan
terraform apply

# Redeploy Cloud Run with new secrets
cd ..
./scripts/deploy.sh
```

### 9. Verify in Portkey Dashboard (2 minutes)

1. Go to [app.portkey.ai](https://app.portkey.ai)
2. Navigate to **Requests**
3. You should see test requests appearing
4. Check **Analytics** for cost and latency metrics

## Testing

### Test Campaign Health Agent with Portkey

```bash
# Trigger agent
curl -X POST "http://localhost:8080/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Check BigQuery for LLM calls
bq query --use_legacy_sql=false \
  "SELECT * FROM sem_agents.llm_calls ORDER BY timestamp DESC LIMIT 5"
```

Expected output:
```
+----------+---------------+------------+-------+
| call_id  | agent_type    | provider   | cost  |
+----------+---------------+------------+-------+
| call-123 | campaign_health| anthropic | 0.003 |
+----------+---------------+------------+-------+
```

### Test Caching

```bash
# First call
curl -X POST "http://localhost:8080/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Second call (should use cache)
curl -X POST "http://localhost:8080/api/v1/orchestrator/run" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Check cache hits
bq query --use_legacy_sql=false \
  "SELECT cache_hit, COUNT(*) as count
   FROM sem_agents.llm_calls
   WHERE DATE(timestamp) = CURRENT_DATE()
   GROUP BY cache_hit"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'portkey_ai'"

```bash
pip install portkey-ai>=1.8.0
```

### "Invalid API key" error

```bash
# Check environment variable
echo $PORTKEY_API_KEY

# Should output: portkey_abc123...
# If empty, source .env:
export $(cat .env | grep -v '^#' | xargs)
```

### "Virtual key not found"

Verify in Portkey dashboard:
1. Go to **Virtual Keys**
2. Check that keys are active (green status)
3. Copy the exact key ID (starts with `key_`)

### No logs in BigQuery

Check that:
1. `llm_calls` table exists in BigQuery
2. Service account has `bigquery.dataEditor` role
3. `run_id` and `agent_type` are passed to `generate()`:

```python
# ❌ Wrong - won't log
await client.generate(prompt="test")

# ✅ Correct - will log
await client.generate(
    prompt="test",
    run_id=str(self.run_id),
    agent_type=self.agent_type.value
)
```

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORTKEY_API_KEY` | Yes | - | Your Portkey API key |
| `PORTKEY_VIRTUAL_KEY_ANTHROPIC` | Yes | - | Virtual key for Anthropic |
| `PORTKEY_VIRTUAL_KEY_GOOGLE` | Yes | - | Virtual key for Google |
| `PORTKEY_ENABLE_CACHE` | No | `true` | Enable semantic caching |
| `PORTKEY_CACHE_TTL` | No | `3600` | Cache TTL in seconds (1 hour) |

## Cost Estimates

With Portkey caching enabled (30% cache hit rate):

| Agent | Calls/Day | Cost Without Cache | Cost With Cache | Savings |
|-------|-----------|-------------------|-----------------|---------|
| Campaign Health | 30 | $0.90 | $0.63 | $0.27/day |
| Keyword | 50 | $1.20 | $0.84 | $0.36/day |
| Ad Copy | 10 | $0.60 | $0.42 | $0.18/day |
| Bid Modifier | 7 | $0.35 | $0.25 | $0.10/day |
| **Total** | 97 | **$3.05/day** | **$2.14/day** | **$0.91/day** |

**Monthly savings**: ~$27 (~30% reduction)

## Next Steps

1. ✅ Portkey configured
2. Monitor dashboard for first week
3. Review cache hit rates (target >30%)
4. Set up cost alerts in Portkey
5. Optimize expensive prompts
6. Enable fallback providers (optional)

## Support

- **Portkey Docs**: https://docs.portkey.ai
- **Portkey Support**: support@portkey.ai
- **Project Docs**: [PORTKEY_INTEGRATION.md](./PORTKEY_INTEGRATION.md)
