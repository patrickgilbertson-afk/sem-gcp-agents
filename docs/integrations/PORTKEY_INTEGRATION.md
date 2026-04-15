# Portkey Integration Guide

## Overview

**RECOMMENDED**: All LLM API calls (Claude and Gemini) **MUST** be routed through [Portkey](https://portkey.ai), an AI gateway that provides:

- **Unified API**: Single interface for multiple LLM providers
- **Observability**: Detailed logging and analytics for all LLM calls
- **Caching**: Semantic caching to reduce costs and latency
- **Load Balancing**: Automatic failover between providers
- **Cost Tracking**: Real-time cost monitoring per agent/model
- **Rate Limiting**: Intelligent rate limiting across providers
- **Retry Logic**: Automatic retries with exponential backoff

## Why Portkey is Required

**Portkey is the MANDATORY routing layer** for all production deployments because:

1. **Cost Visibility**: Without Portkey, LLM costs are opaque and hard to attribute
2. **Caching**: 30-50% cost savings through semantic caching
3. **Reliability**: Automatic retries and fallback mechanisms
4. **Compliance**: Full audit trail of all LLM interactions
5. **Performance Monitoring**: Latency tracking and optimization

## Architecture

### Default Routing (Production - REQUIRED)

```
Agent → PortkeyLLMClient → Portkey Gateway → LLM Provider (Claude/Gemini)
                                  ↓
                          Portkey Dashboard
                                  ↓
                         BigQuery (llm_calls table)
```

### Direct Routing (Local Development Only)

```
Agent → AnthropicClient/GeminiClient → LLM Provider (Claude/Gemini)
                                  ↓
                              (No logging)
```

**⚠️ Direct routing should ONLY be used for local development testing**

All production calls are logged to the `sem_agents.llm_calls` table for cost analysis and debugging.

## Setup (REQUIRED)

### Step 1: Create Portkey Account

**This step is MANDATORY for production deployments.**

1. Go to [portkey.ai](https://portkey.ai) and sign up
2. Navigate to **Virtual Keys** in dashboard
3. Create virtual keys for each provider:

   **For Anthropic (Claude):**
   - Click **Add Virtual Key**
   - Provider: **Anthropic**
   - Name: `sem-agents-anthropic`
   - Paste your `ANTHROPIC_API_KEY`
   - Click **Create**
   - **Copy the virtual key ID** (format: `anthropic-xxx`)

   **For Google AI (Gemini):**
   - Click **Add Virtual Key**
   - Provider: **Google AI**
   - Name: `sem-agents-google`
   - Paste your `GOOGLE_AI_API_KEY`
   - Click **Create**
   - **Copy the virtual key ID** (format: `google-xxx`)

4. Navigate to **API Keys** → Copy your **Portkey API Key** (format: `pk-xxx`)

### Step 2: Configure Local Environment

```bash
# Add to .env file (for local development)
cat >> .env <<EOF
# Portkey Configuration (REQUIRED for production)
PORTKEY_API_KEY=pk-your-api-key
PORTKEY_VIRTUAL_KEY_ANTHROPIC=anthropic-your-virtual-key
PORTKEY_VIRTUAL_KEY_GOOGLE=google-your-virtual-key

# Portkey Features (recommended)
PORTKEY_ENABLE_CACHE=true
PORTKEY_CACHE_TTL=3600  # 1 hour cache

# Original API keys (fallback only)
ANTHROPIC_API_KEY=sk-ant-your-key
GOOGLE_AI_API_KEY=your-google-key
EOF
```

**Verification:**
```bash
# Test that Portkey keys are set
python -c "from src.config import settings; print(f'Portkey enabled: {settings.portkey_api_key is not None}')"
# Expected: Portkey enabled: True
```

### Step 3: Configure Production Secrets (GCP Secret Manager)

**For existing secrets, update them:**

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

# Create or update Portkey secrets
create_or_update_secret "portkey-api-key" "pk-your-api-key"
create_or_update_secret "portkey-virtual-key-anthropic" "anthropic-your-virtual-key"
create_or_update_secret "portkey-virtual-key-google" "google-your-virtual-key"

# Grant access to Cloud Run service account
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

for secret in portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "Permission already granted for $secret"
done

# Verify secrets exist
echo "Verifying Portkey secrets..."
gcloud secrets list --filter="name:portkey"
```

### Step 4: Update Cloud Run Configuration

Add Portkey environment variables to your Cloud Run deployment:

```bash
gcloud run services update sem-agents \
    --region us-central1 \
    --set-secrets="PORTKEY_API_KEY=portkey-api-key:latest,PORTKEY_VIRTUAL_KEY_ANTHROPIC=portkey-virtual-key-anthropic:latest,PORTKEY_VIRTUAL_KEY_GOOGLE=portkey-virtual-key-google:latest" \
    --set-env-vars="PORTKEY_ENABLE_CACHE=true,PORTKEY_CACHE_TTL=3600"
```

**Or update Terraform (`terraform.tfvars`):**

```hcl
# terraform.tfvars
cloud_run_env_vars = {
  PROJECT_ID           = "your-project-id"
  DRY_RUN              = "true"
  PORTKEY_ENABLE_CACHE = "true"
  PORTKEY_CACHE_TTL    = "3600"
}

cloud_run_secrets = {
  ANTHROPIC_API_KEY              = "anthropic-api-key:latest"
  GOOGLE_ADS_CREDENTIALS         = "google-ads-credentials:latest"
  SLACK_BOT_TOKEN                = "slack-bot-token:latest"
  SLACK_SIGNING_SECRET           = "slack-signing-secret:latest"
  PORTKEY_API_KEY                = "portkey-api-key:latest"
  PORTKEY_VIRTUAL_KEY_ANTHROPIC  = "portkey-virtual-key-anthropic:latest"
  PORTKEY_VIRTUAL_KEY_GOOGLE     = "portkey-virtual-key-google:latest"
}
```

Then apply:
```bash
cd terraform
terraform apply
```

### Step 5: Verify Portkey Routing

```bash
# Get Cloud Run URL
SERVICE_URL=$(gcloud run services describe sem-agents --region=us-central1 --format='value(status.url)')

# Trigger test agent run
curl -X POST "$SERVICE_URL/api/v1/orchestrator/run" \
    -H "Content-Type: application/json" \
    -d '{"agent_type": "campaign_health"}'

# Check BigQuery for llm_calls entries
bq query --use_legacy_sql=false "
  SELECT
    call_id,
    provider,
    model,
    portkey_request_id,
    cache_hit,
    cost_usd
  FROM sem_agents.llm_calls
  ORDER BY timestamp DESC
  LIMIT 5
"

# If portkey_request_id is populated, Portkey routing is working!
```

## Usage

### Basic Usage

The Portkey clients are drop-in replacements for the original LLM clients:

```python
from src.core import AnthropicClient, GeminiClient

# Claude via Portkey
claude = AnthropicClient(model="claude-sonnet-4-5")
response = await claude.generate(
    prompt="Analyze this campaign data...",
    system="You are an SEM analyst.",
    temperature=0.7,
    run_id=str(agent.run_id),
    agent_type=agent.agent_type.value,
)

# Gemini via Portkey
gemini = GeminiClient(model="gemini-2.0-flash")
response = await gemini.generate(
    prompt="Generate RSA headlines...",
    temperature=1.0,
    run_id=str(agent.run_id),
    agent_type=agent.agent_type.value,
)
```

### Automatic Logging

When you include `run_id` and `agent_type`, all calls are automatically logged to BigQuery:

```python
# This call will be logged to sem_agents.llm_calls
analysis = await self.llm.generate(
    prompt=prompt,
    system=system_prompt,
    run_id=str(self.run_id),        # Required for logging
    agent_type=self.agent_type.value,  # Required for logging
)
```

### Without Logging (Development/Testing)

```python
# Omit run_id and agent_type to skip BigQuery logging
response = await claude.generate(
    prompt="Test prompt",
    system="Test system",
)
```

## Features

### 1. Semantic Caching

Portkey automatically caches similar prompts to reduce costs:

```python
# First call - hits API ($0.003)
response1 = await claude.generate(
    prompt="Analyze campaign X with metrics Y",
    run_id=run_id,
    agent_type="campaign_health",
)

# Similar call - served from cache ($0.000)
response2 = await claude.generate(
    prompt="Analyze campaign X with metrics Y",
    run_id=run_id,
    agent_type="campaign_health",
)
```

Cache hits are tracked in the `llm_calls.cache_hit` column.

**Cache TTL**: Configurable via `PORTKEY_CACHE_TTL` (default: 3600 seconds)

### 2. Automatic Retries

Built-in exponential backoff for transient errors:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def generate(...):
    # Automatically retries on rate limits, timeouts, etc.
```

### 3. Cost Tracking

Every call logs cost to BigQuery:

```sql
-- Daily cost by agent
SELECT
  DATE(timestamp) as date,
  agent_type,
  provider,
  model,
  COUNT(*) as calls,
  SUM(total_tokens) as tokens,
  SUM(cost_usd) as cost,
  COUNTIF(cache_hit) as cache_hits,
  AVG(response_time_ms) as avg_latency_ms
FROM sem_agents.llm_calls
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 7 DESC;
```

### 4. Load Balancing & Fallbacks

Configure in Portkey dashboard:

```json
{
  "strategy": {
    "mode": "loadbalance",
    "targets": [
      {
        "virtual_key": "anthropic-key",
        "weight": 80
      },
      {
        "virtual_key": "anthropic-backup-key",
        "weight": 20
      }
    ]
  }
}
```

### 5. Request Tracing

Every call gets a unique `portkey_request_id` for debugging:

```python
# Check Portkey dashboard for detailed trace
portkey_request_id = "req_abc123xyz"
```

View in Portkey dashboard:
- Exact prompt and response
- Token breakdown
- Latency waterfall
- Error details (if any)

## Monitoring

### Portkey Dashboard

Access at [app.portkey.ai](https://app.portkey.ai):

- **Analytics**: Cost trends, latency, error rates
- **Requests**: Search and filter all LLM calls
- **Caching**: Cache hit rate, savings
- **Alerts**: Set up alerts for cost spikes, errors

### BigQuery Queries

```sql
-- Most expensive prompts (for optimization)
SELECT
  LEFT(SHA256(prompt), 8) as prompt_hash,
  agent_type,
  model,
  COUNT(*) as call_count,
  AVG(prompt_tokens) as avg_prompt_tokens,
  SUM(cost_usd) as total_cost
FROM sem_agents.llm_calls
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
  AND cache_hit = FALSE
GROUP BY 1, 2, 3
ORDER BY 6 DESC
LIMIT 20;

-- Cache effectiveness
SELECT
  agent_type,
  model,
  COUNT(*) as total_calls,
  COUNTIF(cache_hit) as cached_calls,
  ROUND(COUNTIF(cache_hit) / COUNT(*) * 100, 2) as cache_hit_rate,
  SUM(CASE WHEN cache_hit THEN 0 ELSE cost_usd END) as actual_cost,
  SUM(cost_usd) as would_be_cost_without_cache,
  ROUND(SUM(CASE WHEN cache_hit THEN cost_usd ELSE 0 END), 2) as savings
FROM sem_agents.llm_calls
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
GROUP BY 1, 2
ORDER BY 8 DESC;

-- Error analysis
SELECT
  DATE(timestamp) as date,
  agent_type,
  model,
  error_code,
  COUNT(*) as error_count,
  STRING_AGG(DISTINCT error_message, ' | ' LIMIT 3) as sample_errors
FROM sem_agents.llm_calls
WHERE error_code IS NOT NULL
  AND DATE(timestamp) >= CURRENT_DATE() - 7
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 5 DESC;
```

### Cloud Monitoring Alerts

```sql
-- Set up alert for high LLM costs
-- Query runs every hour
SELECT
  SUM(cost_usd) as hourly_cost
FROM sem_agents.llm_calls
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR);

-- Alert if hourly_cost > $5
```

## Cost Optimization

### 1. Enable Caching

```bash
# In .env
PORTKEY_ENABLE_CACHE=true
PORTKEY_CACHE_TTL=3600
```

**Expected savings**: 30-50% for repetitive analysis tasks

### 2. Optimize Prompts

```python
# ❌ Bad: Long, repetitive prompt
prompt = f"Analyze these campaigns: {full_campaign_details_dump}"

# ✅ Good: Structured, concise prompt
prompt = f"Analyze {len(campaigns)} campaigns with these key metrics:\n"
prompt += "\n".join([f"- {c.name}: CTR {c.ctr:.2%}, Conv {c.conversions}"
                     for c in campaigns])
```

### 3. Use Appropriate Models

```python
# For complex analysis
claude = AnthropicClient(model="claude-sonnet-4-5")  # $3/1M tokens

# For simple generation
gemini = GeminiClient(model="gemini-2.0-flash")  # $0.075/1M tokens
```

### 4. Batch Similar Requests

```python
# Instead of 10 separate calls
for campaign in campaigns:
    analysis = await claude.generate(f"Analyze {campaign}")

# Batch into one call
all_campaigns = "\n".join([f"{i+1}. {c}" for i, c in enumerate(campaigns)])
analysis = await claude.generate(f"Analyze these campaigns:\n{all_campaigns}")
```

## Routing Configuration

### Production (Default - Portkey Routing)

The Portkey clients are **automatically used** when properly configured:

```python
# config.py checks for Portkey environment variables
# If PORTKEY_API_KEY is set, Portkey routing is enabled

# src/core/__init__.py automatically selects the right client:
from src.core import AnthropicClient, GeminiClient  # Routes through Portkey
```

**Environment variables required for Portkey routing:**
```bash
PORTKEY_API_KEY=pk-xxx
PORTKEY_VIRTUAL_KEY_ANTHROPIC=anthropic-xxx
PORTKEY_VIRTUAL_KEY_GOOGLE=google-xxx
```

### Local Development (Direct Routing - Optional)

For local testing without Portkey (NOT recommended for production):

```python
# Option 1: Unset Portkey env vars (clients fall back to direct)
unset PORTKEY_API_KEY

# Option 2: Explicitly import direct clients
from src.core.llm_clients import AnthropicClient, GeminiClient
```

### Verification

Check which routing is active:

```python
from src.core import AnthropicClient
import inspect

# Check if Portkey is being used
client = AnthropicClient()
print(f"Client module: {inspect.getfile(client.__class__)}")

# Expected output (production):
# Client module: .../src/core/llm_clients_portkey.py
```

### Environment Variable Priority

```bash
# Required for Portkey routing
PORTKEY_API_KEY=pk-xxx              # Main Portkey API key
PORTKEY_VIRTUAL_KEY_ANTHROPIC=xxx   # Anthropic virtual key
PORTKEY_VIRTUAL_KEY_GOOGLE=xxx      # Google virtual key

# Optional (Portkey features)
PORTKEY_ENABLE_CACHE=true           # Enable semantic caching (default: true)
PORTKEY_CACHE_TTL=3600              # Cache TTL in seconds (default: 3600)

# Fallback (if Portkey not configured)
ANTHROPIC_API_KEY=sk-ant-xxx        # Direct Anthropic access
GOOGLE_AI_API_KEY=xxx               # Direct Google AI access
```

## Troubleshooting

### "Invalid Portkey API key"

```bash
# Verify key is set
echo $PORTKEY_API_KEY

# Check Secret Manager (production)
gcloud secrets versions access latest --secret=portkey-api-key
```

### "Virtual key not found"

```bash
# Verify virtual keys in Portkey dashboard
# Keys must be created for Anthropic and Google providers
```

### "Cache not working"

```bash
# Ensure caching is enabled
PORTKEY_ENABLE_CACHE=true

# Check cache hit rate in BigQuery
SELECT
  COUNTIF(cache_hit) as hits,
  COUNT(*) as total,
  ROUND(COUNTIF(cache_hit) / COUNT(*) * 100, 2) as hit_rate
FROM sem_agents.llm_calls
WHERE DATE(timestamp) = CURRENT_DATE();
```

### High costs

```sql
-- Find most expensive agent/model combinations
SELECT
  agent_type,
  model,
  COUNT(*) as calls,
  SUM(cost_usd) as cost,
  AVG(prompt_tokens) as avg_prompt_tokens
FROM sem_agents.llm_calls
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
GROUP BY 1, 2
ORDER BY 4 DESC;
```

## Best Practices

1. **Always include `run_id` and `agent_type`** for logging and cost attribution
2. **Monitor cache hit rates** - should be >30% for production workloads
3. **Set up cost alerts** in both Portkey and Cloud Monitoring
4. **Review expensive prompts weekly** and optimize
5. **Use semantic caching** for similar analysis tasks
6. **Choose appropriate models** based on task complexity
7. **Batch requests** when possible to reduce overhead

## Advanced Configuration

### Custom Retry Strategy

```python
from portkey_ai import Portkey

portkey = Portkey(
    api_key=settings.portkey_api_key,
    virtual_key=settings.portkey_virtual_key_anthropic,
    config={
        "retry": {
            "attempts": 3,
            "on_status_codes": [429, 500, 502, 503],
        }
    }
)
```

### Request Timeouts

```python
response = await client.generate(
    prompt=prompt,
    timeout=30000,  # 30 seconds
)
```

### Custom Metadata

```python
response = await client.generate(
    prompt=prompt,
    metadata={
        "campaign_id": campaign.id,
        "user_id": user.id,
        "environment": settings.environment,
    }
)
```

## Routing Decision Logic

The system automatically selects the correct LLM client based on environment configuration:

```python
# src/core/__init__.py (simplified)

if settings.portkey_api_key:
    # Production: Route through Portkey
    from src.core.llm_clients_portkey import (
        AnthropicClient,
        GeminiClient
    )
    print("✓ LLM routing: Portkey Gateway (production)")
else:
    # Development: Direct API calls
    from src.core.llm_clients import (
        AnthropicClient,
        GeminiClient
    )
    print("⚠ LLM routing: Direct APIs (development only)")
```

**Decision Tree:**

```
Is PORTKEY_API_KEY set?
├─ YES → Use Portkey routing (RECOMMENDED)
│   ├─ Logs to BigQuery
│   ├─ Enables caching
│   ├─ Provides observability
│   └─ Tracks costs
│
└─ NO → Use direct routing (LOCAL DEV ONLY)
    ├─ No logging
    ├─ No caching
    ├─ No observability
    └─ No cost tracking
```

## Quick Reference

### Required Environment Variables (Production)

```bash
# Portkey Configuration
PORTKEY_API_KEY=pk-xxx                        # Main Portkey API key
PORTKEY_VIRTUAL_KEY_ANTHROPIC=anthropic-xxx   # Anthropic virtual key
PORTKEY_VIRTUAL_KEY_GOOGLE=google-xxx         # Google virtual key

# Portkey Features (optional)
PORTKEY_ENABLE_CACHE=true                     # Enable semantic caching
PORTKEY_CACHE_TTL=3600                        # Cache TTL (seconds)

# Original API keys (must also be in Portkey dashboard)
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_AI_API_KEY=xxx
```

### Common Commands

```bash
# Check if Portkey is configured
python -c "from src.config import settings; print('Portkey:', 'ENABLED' if settings.portkey_api_key else 'DISABLED')"

# View recent LLM calls
bq query --use_legacy_sql=false "
  SELECT timestamp, agent_type, model, cache_hit, cost_usd
  FROM sem_agents.llm_calls
  ORDER BY timestamp DESC
  LIMIT 10
"

# Check cache hit rate (last 24 hours)
bq query --use_legacy_sql=false "
  SELECT
    COUNTIF(cache_hit) as cache_hits,
    COUNT(*) as total_calls,
    ROUND(COUNTIF(cache_hit) / COUNT(*) * 100, 2) as hit_rate_percent
  FROM sem_agents.llm_calls
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
"

# Daily cost breakdown
bq query --use_legacy_sql=false "
  SELECT
    DATE(timestamp) as date,
    agent_type,
    model,
    COUNT(*) as calls,
    SUM(cost_usd) as total_cost
  FROM sem_agents.llm_calls
  WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, 5 DESC
"
```

### Troubleshooting Checklist

- [ ] Portkey account created
- [ ] Virtual keys created for Anthropic and Google
- [ ] Portkey API key copied
- [ ] Environment variables set (local) or secrets created (production)
- [ ] Cloud Run service updated with Portkey secrets
- [ ] Test run completed
- [ ] BigQuery `llm_calls` table shows `portkey_request_id` values
- [ ] Portkey dashboard shows requests

## Resources

- [Portkey Documentation](https://docs.portkey.ai)
- [Portkey Dashboard](https://app.portkey.ai)
- [Portkey Virtual Keys Setup](https://docs.portkey.ai/docs/product/ai-gateway/virtual-keys)
- [BigQuery Architecture](../architecture/BIGQUERY_ARCHITECTURE.md)
- [Cost Optimization Guide](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)
- [Deployment Guide](../guides/DEPLOYMENT_GUIDE.md)
