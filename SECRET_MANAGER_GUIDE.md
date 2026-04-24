# GCP Secret Manager Integration Guide

## Overview

**All secrets are loaded from GCP Secret Manager at runtime** - not from `.env` file.

This approach provides:
- ✅ **Security**: No secrets in code or files
- ✅ **Consistency**: Same secret source for local dev and production
- ✅ **Audit Trail**: GCP tracks all secret access
- ✅ **Rotation**: Update secrets in one place, no code changes needed

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Application Startup                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Load .env file                                          │
│     ↓                                                        │
│     • GCP_PROJECT_ID=marketing-bigquery-490714              │
│     • GOOGLE_ADS_CUSTOMER_ID=1234567890                     │
│     • SLACK_APPROVAL_CHANNEL_ID=C01234567                   │
│     • (non-secret config only)                              │
│                                                             │
│  2. Initialize Settings object                              │
│     ↓                                                        │
│     • Creates src.config.settings singleton                 │
│                                                             │
│  3. On first access to secret property:                     │
│     ↓                                                        │
│     settings.google_ads_developer_token                     │
│     ↓                                                        │
│     • Connects to Secret Manager                            │
│     • Loads secret value from GCP                           │
│     • Caches result (subsequent calls are instant)          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Code Example

```python
from src.config import settings

# Non-secret config - loaded from .env
print(settings.gcp_project_id)  # "marketing-bigquery-490714"

# Secret - loaded from GCP Secret Manager on first access
print(settings.google_ads_developer_token)  # Fetches from GCP, then cached

# Subsequent access is instant (cached)
token = settings.google_ads_developer_token  # No GCP call
```

---

## Setup Instructions

### 1. Verify Secrets Exist in GCP

```bash
# List all secrets
gcloud secrets list --project=marketing-bigquery-490714

# Expected output:
# NAME                           CREATED
# google-ads-credentials         2026-04-16
# portkey-api-key               2026-04-16
# portkey-virtual-key-anthropic 2026-04-16
# portkey-virtual-key-google    2026-04-16
# slack-bot-token               2026-04-16
# slack-signing-secret          2026-04-16
# anthropic-api-key             2026-04-16 (optional)
```

If secrets are missing, create them:

```bash
# Option 1: Use setup script
bash scripts/setup_secrets_individual.sh

# Option 2: Manual creation
echo -n "YOUR_VALUE" | gcloud secrets create SECRET_NAME --data-file=-
```

See `GCP_SECRETS_CHECKLIST.md` for full secret list.

---

### 2. Configure .env File (Non-Secrets Only)

Your `.env` file should **NOT** contain any secrets:

```bash
# .env - Non-secret configuration only
GCP_PROJECT_ID=marketing-bigquery-490714
GCP_REGION=us-central1
GA4_DATASET=analytics_272839261
GA4_PROPERTY_ID=272839261

# Update these with your values:
GOOGLE_ADS_CUSTOMER_ID=YOUR_CUSTOMER_ID_HERE
GOOGLE_ADS_LOGIN_CUSTOMER_ID=YOUR_CUSTOMER_ID_HERE
SLACK_APPROVAL_CHANNEL_ID=YOUR_CHANNEL_ID_HERE

ENVIRONMENT=development
DRY_RUN=true
```

**DO NOT ADD**:
- ❌ `GOOGLE_ADS_DEVELOPER_TOKEN`
- ❌ `GOOGLE_ADS_CLIENT_SECRET`
- ❌ `PORTKEY_API_KEY`
- ❌ `SLACK_BOT_TOKEN`
- ❌ Any other secrets

These are loaded from Secret Manager automatically.

---

### 3. Authenticate with GCP

```bash
# For local development
gcloud auth application-default login

# Set quota project (if needed)
gcloud auth application-default set-quota-project marketing-bigquery-490714
```

---

### 4. Test Configuration

```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows Git Bash
# OR: .venv\Scripts\activate.ps1  # PowerShell

# Test non-secret config loads
python -c "from src.config import settings; print(f'Project: {settings.gcp_project_id}')"

# Test secret loading (this will connect to Secret Manager)
python -c "from src.config import settings; print(f'Token length: {len(settings.google_ads_developer_token)}')"

# If successful, you should see:
# Project: marketing-bigquery-490714
# Token length: 22
```

---

## Local Development Fallback

For local development **without** Secret Manager access, you can set secrets as environment variables:

```bash
# Option 1: Export directly
export GOOGLE_ADS_DEVELOPER_TOKEN="your-token"
export PORTKEY_API_KEY="your-key"
# ... etc

# Option 2: Source from file (NOT RECOMMENDED - for testing only)
# Create .env.local with secrets (add to .gitignore!)
# Then: set -a; source .env.local; set +a
```

The config will:
1. First check environment variables
2. If not found, load from Secret Manager
3. If both fail, raise an error

**Production should NEVER use environment variable fallback** - always use Secret Manager.

---

## Production (Cloud Run)

### Terraform Configuration

Secrets are automatically mounted as environment variables by Terraform:

```hcl
# terraform/modules/cloud_run/main.tf
resource "google_cloud_run_service" "sem_agents" {
  # ...

  template {
    spec {
      containers {
        # Secrets mounted as env vars
        env {
          name = "GOOGLE_ADS_CREDENTIALS"
          value_source {
            secret_key_ref {
              secret  = "google-ads-credentials"
              version = "latest"
            }
          }
        }

        env {
          name = "PORTKEY_API_KEY"
          value_source {
            secret_key_ref {
              secret  = "portkey-api-key"
              version = "latest"
            }
          }
        }

        # ... other secrets
      }
    }
  }
}
```

### Deployment

```bash
cd terraform
terraform apply

# Secrets are automatically available as environment variables
# The config.py fallback mechanism will use these values
```

---

## Secret Manager Access Control

### Required IAM Permissions

The application service account needs:

```bash
# Grant Secret Manager access
gcloud projects add-iam-policy-binding marketing-bigquery-490714 \
  --member="serviceAccount:sem-agents@marketing-bigquery-490714.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Or grant per-secret (more restrictive)
gcloud secrets add-iam-policy-binding google-ads-credentials \
  --member="serviceAccount:sem-agents@marketing-bigquery-490714.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Monitoring & Auditing

### View Secret Access Logs

```bash
# View who accessed which secrets
gcloud logging read "resource.type=secretmanager.googleapis.com/Secret" \
  --project=marketing-bigquery-490714 \
  --limit=50 \
  --format=json

# Filter by secret name
gcloud logging read "resource.type=secretmanager.googleapis.com/Secret AND resource.labels.secret_id=portkey-api-key" \
  --project=marketing-bigquery-490714 \
  --limit=10
```

### Secret Access Metrics

GCP automatically tracks:
- Access count per secret
- Last access timestamp
- Accessing service account
- Access failures

View in [Secret Manager Console](https://console.cloud.google.com/security/secret-manager?project=marketing-bigquery-490714).

---

## Secret Rotation

### Rotating a Secret

```bash
# Example: Rotate Portkey API key
echo -n "NEW_API_KEY_VALUE" | gcloud secrets versions add portkey-api-key --data-file=-

# No code changes needed!
# Next time the app starts, it will load the new value
```

### Force Reload in Running App

For Cloud Run:
```bash
# Deploy with no-traffic (forces new instances)
gcloud run services update sem-agents --region=us-central1 --no-traffic

# Then route traffic to new revision
gcloud run services update-traffic sem-agents --to-latest --region=us-central1
```

For local dev:
- Just restart the application
- Secrets are cached per-process, so restart picks up new values

---

## Troubleshooting

### Error: "Failed to load X from Secret Manager"

**Cause**: Secret doesn't exist or no permission

**Fix**:
```bash
# Check secret exists
gcloud secrets describe SECRET_NAME --project=marketing-bigquery-490714

# If not found, create it
echo -n "VALUE" | gcloud secrets create SECRET_NAME --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:sem-agents@marketing-bigquery-490714.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Error: "google.auth.exceptions.DefaultCredentialsError"

**Cause**: Not authenticated with GCP

**Fix**:
```bash
gcloud auth application-default login
```

### Secret Value is Cached and Outdated

**Cause**: Application caches secrets on first access

**Fix**:
- Restart the application
- Secrets are cached with `@cached_property`, so they persist for the lifetime of the Settings object

---

## Cost

**Secret Manager Pricing** (as of 2024):
- Storage: $0.06 per secret per month
- Access: $0.03 per 10,000 operations

**Monthly Estimate** (7 secrets, 100K accesses):
- Storage: 7 × $0.06 = $0.42/month
- Access: 100K × $0.03/10K = $0.30/month
- **Total: ~$0.72/month**

---

## Security Best Practices

1. ✅ **Never commit secrets** to git (`.env` is in `.gitignore`)
2. ✅ **Use Secret Manager** for all environments (local dev + production)
3. ✅ **Rotate secrets** every 90 days
4. ✅ **Grant least privilege** - only sem-agents service account can access
5. ✅ **Enable audit logging** - track who accesses what
6. ✅ **Use Portkey virtual keys** - avoid storing direct LLM API keys

---

## Migration Checklist

If you previously had secrets in `.env`:

- [x] Remove all secret values from `.env` file
- [x] Verify secrets exist in GCP Secret Manager
- [x] Update `src/config.py` to load from Secret Manager
- [x] Create `src/core/secrets.py` helper module
- [x] Test locally with `gcloud auth application-default login`
- [x] Update documentation
- [ ] Test in production (Cloud Run)
- [ ] Update team onboarding docs

---

## Summary

**Before** (Insecure):
```bash
# .env
PORTKEY_API_KEY=pk-abc123...
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-xyz...
SLACK_BOT_TOKEN=xoxb-123...
```

**After** (Secure):
```bash
# .env - Non-secrets only
GCP_PROJECT_ID=marketing-bigquery-490714
GOOGLE_ADS_CUSTOMER_ID=1234567890
SLACK_APPROVAL_CHANNEL_ID=C01234567
```

```python
# Secrets loaded from GCP Secret Manager automatically
from src.config import settings
settings.portkey_api_key  # Loaded from Secret Manager, cached
```

---

**Last Updated**: 2026-04-23
**Status**: ✅ All secrets migrated to Secret Manager
