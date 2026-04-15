# GCP Secret Manager - Required Secrets Checklist

## Summary

**Total Required Secrets: 7** (with Option A - recommended)
**Total Required Secrets: 10** (with Option B - individual Google Ads secrets)

---

## Required Secrets

### Option A: Consolidated Google Ads (RECOMMENDED - 7 secrets total)

| # | Secret Name | Environment Variable | Purpose | Example Value |
|---|-------------|---------------------|---------|---------------|
| 1 | `google-ads-credentials` | `GOOGLE_ADS_CREDENTIALS` | Google Ads API credentials (JSON) | `{"developer_token":"...", "client_id":"...", "client_secret":"...", "refresh_token":"..."}` |
| 2 | `slack-bot-token` | `SLACK_BOT_TOKEN` | Slack bot OAuth token | `xoxb-...` |
| 3 | `slack-signing-secret` | `SLACK_SIGNING_SECRET` | Slack webhook verification | `abc123...` |
| 4 | `portkey-api-key` | `PORTKEY_API_KEY` | **Portkey main API key** | `pk-...` |
| 5 | `portkey-virtual-key-anthropic` | `PORTKEY_VIRTUAL_KEY_ANTHROPIC` | **Portkey Anthropic virtual key** | `anthropic-...` |
| 6 | `portkey-virtual-key-google` | `PORTKEY_VIRTUAL_KEY_GOOGLE` | **Portkey Google AI virtual key** | `google-...` |
| 7 | `anthropic-api-key` | `ANTHROPIC_API_KEY` | Anthropic API key (optional fallback) | `sk-ant-...` |

**Note**: Secret #7 (`anthropic-api-key`) is **OPTIONAL** if using Portkey (recommended). The actual Anthropic key is configured in Portkey dashboard.

---

### Option B: Separate Google Ads Secrets (10 secrets total)

| # | Secret Name | Environment Variable | Purpose |
|---|-------------|---------------------|---------|
| 1 | `google-ads-developer-token` | `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads API developer token |
| 2 | `google-ads-client-id` | `GOOGLE_ADS_CLIENT_ID` | OAuth client ID |
| 3 | `google-ads-client-secret` | `GOOGLE_ADS_CLIENT_SECRET` | OAuth client secret |
| 4 | `google-ads-refresh-token` | `GOOGLE_ADS_REFRESH_TOKEN` | OAuth refresh token |
| 5 | `slack-bot-token` | `SLACK_BOT_TOKEN` | Slack bot OAuth token |
| 6 | `slack-signing-secret` | `SLACK_SIGNING_SECRET` | Slack webhook verification |
| 7 | `portkey-api-key` | `PORTKEY_API_KEY` | Portkey main API key |
| 8 | `portkey-virtual-key-anthropic` | `PORTKEY_VIRTUAL_KEY_ANTHROPIC` | Portkey Anthropic virtual key |
| 9 | `portkey-virtual-key-google` | `PORTKEY_VIRTUAL_KEY_GOOGLE` | Portkey Google AI virtual key |
| 10 | `anthropic-api-key` | `ANTHROPIC_API_KEY` | Anthropic API key (optional fallback) |

---

## Portkey Secrets (MANDATORY for Production)

⚠️ **These 3 secrets are REQUIRED:**

1. **`portkey-api-key`** - Your main Portkey account API key
   - Get from: https://app.portkey.ai → API Keys
   - Format: `pk-...`

2. **`portkey-virtual-key-anthropic`** - Portkey virtual key for Anthropic
   - Get from: https://app.portkey.ai → Virtual Keys → Add Anthropic
   - Format: `anthropic-...`

3. **`portkey-virtual-key-google`** - Portkey virtual key for Google AI
   - Get from: https://app.portkey.ai → Virtual Keys → Add Google AI
   - Format: `google-...`

**Why Portkey?**
- Mandatory for production deployments
- Provides cost tracking, caching (30-50% savings), observability
- All LLM calls route through Portkey gateway

---

## Optional Secrets

| Secret Name | When Needed | Notes |
|-------------|-------------|-------|
| `anthropic-api-key` | Local development only | DEPRECATED - Configure in Portkey instead |
| `google-ai-api-key` | Local development only | DEPRECATED - Configure in Portkey instead |

**In production, you do NOT need direct Anthropic/Google AI keys** - they are configured in the Portkey dashboard virtual keys.

---

## Quick Setup Commands

### Create All Secrets (Option A - Recommended)

```bash
# Set project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Helper function
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if gcloud secrets describe $secret_name &>/dev/null; then
        echo "Updating: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "Creating: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# 1. Google Ads (JSON format)
create_or_update_secret "google-ads-credentials" '{"developer_token":"YOUR_TOKEN","client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_SECRET","refresh_token":"YOUR_REFRESH"}'

# 2-3. Slack
create_or_update_secret "slack-bot-token" "xoxb-YOUR_BOT_TOKEN"
create_or_update_secret "slack-signing-secret" "YOUR_SIGNING_SECRET"

# 4-6. Portkey (REQUIRED)
create_or_update_secret "portkey-api-key" "pk-YOUR_PORTKEY_KEY"
create_or_update_secret "portkey-virtual-key-anthropic" "anthropic-YOUR_VIRTUAL_KEY"
create_or_update_secret "portkey-virtual-key-google" "google-YOUR_VIRTUAL_KEY"

# 7. Anthropic (OPTIONAL - only for local dev)
# create_or_update_secret "anthropic-api-key" "sk-ant-YOUR_KEY"
```

### Grant Access to Cloud Run Service Account

```bash
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

for secret in google-ads-credentials slack-bot-token slack-signing-secret portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "Already granted: $secret"
done
```

### Verify Secrets Exist

```bash
# List all secrets
gcloud secrets list

# Verify specific secrets
for secret in google-ads-credentials slack-bot-token slack-signing-secret portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google; do
    if gcloud secrets describe $secret &>/dev/null; then
        echo "✓ $secret"
    else
        echo "✗ $secret (MISSING)"
    fi
done
```

---

## Cloud Run Configuration

### Complete Cloud Run Deployment with All Secrets

```bash
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:latest \
    --platform managed \
    --region us-central1 \
    --service-account sem-agents@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars "PROJECT_ID=$PROJECT_ID,DRY_RUN=true,PORTKEY_ENABLE_CACHE=true,PORTKEY_CACHE_TTL=3600" \
    --set-secrets "\
GOOGLE_ADS_CREDENTIALS=google-ads-credentials:latest,\
SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
PORTKEY_API_KEY=portkey-api-key:latest,\
PORTKEY_VIRTUAL_KEY_ANTHROPIC=portkey-virtual-key-anthropic:latest,\
PORTKEY_VIRTUAL_KEY_GOOGLE=portkey-virtual-key-google:latest" \
    --max-instances 10 \
    --timeout 900 \
    --memory 2Gi \
    --cpu 2 \
    --allow-unauthenticated
```

**Note**: `anthropic-api-key` is **NOT** included because production uses Portkey routing.

---

## Terraform Configuration

### terraform.tfvars

```hcl
cloud_run_secrets = {
  # Google Ads
  GOOGLE_ADS_CREDENTIALS = "google-ads-credentials:latest"

  # Slack
  SLACK_BOT_TOKEN        = "slack-bot-token:latest"
  SLACK_SIGNING_SECRET   = "slack-signing-secret:latest"

  # Portkey (REQUIRED for production)
  PORTKEY_API_KEY                = "portkey-api-key:latest"
  PORTKEY_VIRTUAL_KEY_ANTHROPIC  = "portkey-virtual-key-anthropic:latest"
  PORTKEY_VIRTUAL_KEY_GOOGLE     = "portkey-virtual-key-google:latest"
}
```

---

## Secret Costs

**Secret Manager Pricing** (as of 2024):
- $0.06 per secret per month
- $0.03 per 10,000 access operations

**Monthly Cost Estimate**:
- 7 secrets × $0.06 = **$0.42/month**
- 100K accesses × $0.03/10K = **$0.30/month**
- **Total: ~$0.72/month**

---

## Security Best Practices

1. ✅ **Never commit secrets** to git
2. ✅ **Rotate secrets** every 90 days
3. ✅ **Use least privilege** - grant access only to sem-agents service account
4. ✅ **Enable audit logs** for secret access
5. ✅ **Use Portkey** to avoid storing direct LLM API keys in GCP

---

## Troubleshooting

### "Secret not found"
```bash
# Create missing secret
echo -n "YOUR_VALUE" | gcloud secrets create SECRET_NAME --data-file=-
```

### "Permission denied"
```bash
# Grant access
gcloud secrets add-iam-policy-binding SECRET_NAME \
    --member="serviceAccount:sem-agents@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### "Cloud Run can't access secret"
```bash
# Verify service account
gcloud run services describe sem-agents --region=us-central1 --format="value(spec.template.spec.serviceAccountName)"

# Should output: sem-agents@PROJECT_ID.iam.gserviceaccount.com
```

---

**Last Updated**: 2026-04-15
**Recommended Setup**: Option A (7 secrets with consolidated Google Ads credentials)
