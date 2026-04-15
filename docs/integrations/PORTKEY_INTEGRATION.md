# Portkey Integration Guide

## Overview

All LLM API calls (Claude and Gemini) are routed through [Portkey](https://portkey.ai), an AI gateway that provides:

- **Unified API**: Single interface for multiple LLM providers
- **Observability**: Detailed logging and analytics for all LLM calls
- **Caching**: Semantic caching to reduce costs and latency
- **Load Balancing**: Automatic failover between providers
- **Cost Tracking**: Real-time cost monitoring per agent/model
- **Rate Limiting**: Intelligent rate limiting across providers
- **Retry Logic**: Automatic retries with exponential backoff

## Architecture

```
Agent → Portkey Client → Portkey Gateway → LLM Provider (Claude/Gemini)
                              ↓
                         BigQuery (llm_calls table)
```

All calls are logged to the `sem_agents.llm_calls` table for cost analysis and debugging.

## Setup

### 1. Create Portkey Account

1. Go to [portkey.ai](https://portkey.ai) and sign up
2. Navigate to **Virtual Keys** in dashboard
3. Create virtual keys for each provider:
   - **Anthropic**: Add your `ANTHROPIC_API_KEY`
   - **Google**: Add your `GOOGLE_AI_API_KEY`
4. Copy the virtual key IDs

### 2. Configure Environment Variables

```bash
# Add to .env file
PORTKEY_API_KEY=your-portkey-api-key
PORTKEY_VIRTUAL_KEY_ANTHROPIC=your-anthropic-virtual-key-id
PORTKEY_VIRTUAL_KEY_GOOGLE=your-google-virtual-key-id

# Optional: Configure caching
PORTKEY_ENABLE_CACHE=true
PORTKEY_CACHE_TTL=3600  # 1 hour
```

### 3. Add to Secret Manager (Production)

```bash
# Create secrets
gcloud secrets create portkey-api-key --data-file=- <<< "your-key"
gcloud secrets create portkey-virtual-key-anthropic --data-file=- <<< "your-key"
gcloud secrets create portkey-virtual-key-google --data-file=- <<< "your-key"

# Update terraform.tfvars
secrets = {
  ...
  "portkey-api-key"                = ""
  "portkey-virtual-key-anthropic"  = ""
  "portkey-virtual-key-google"     = ""
}
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

## Migration from Direct Clients

The Portkey clients are **already configured** as the default in `src/core/__init__.py`:

```python
# This imports the Portkey versions
from src.core import AnthropicClient, GeminiClient
```

To use direct clients (bypassing Portkey):

```python
# Import original clients
from src.core.llm_clients import AnthropicClient, GeminiClient
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

## Resources

- [Portkey Documentation](https://docs.portkey.ai)
- [Portkey Dashboard](https://app.portkey.ai)
- [BigQuery Architecture](./BIGQUERY_ARCHITECTURE.md)
- [Cost Optimization Guide](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)
