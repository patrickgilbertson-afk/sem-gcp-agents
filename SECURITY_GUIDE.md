# Security Guide - SEM GCP Agents

## Current Security Implementation

### Authentication Layers

#### 1. Application-Level Auth (AuthMiddleware)
**File**: `src/api/middleware.py`

All non-Slack endpoints require one of:
- **API Key**: `X-API-Key` header (for manual triggers)
- **OIDC Token**: `Authorization: Bearer <token>` (for Cloud Scheduler)

**Public endpoints** (no auth required):
- `/health` - Health check
- `/` - Root/docs
- `/api/v1/slack/*` - Protected by Slack signature verification

#### 2. Slack Signature Verification
**File**: `src/integrations/slack/app.py`

- Slack Bolt framework automatically verifies all webhook requests
- Validates HMAC signature using `SLACK_SIGNING_SECRET`
- Prevents replay attacks via timestamp validation

#### 3. Slack Approval User Whitelist
**File**: `src/integrations/slack/app.py` - `is_user_authorized()`

- Optional whitelist of Slack user IDs who can approve/reject
- Configured via `SLACK_APPROVAL_USER_WHITELIST` in `.env`
- Empty = allow all users in channel
- Non-empty = only whitelisted users can approve

### Secret Management

All secrets stored in **GCP Secret Manager**:
- `google-ads-developer-token`, `google-ads-client-id`, `google-ads-client-secret`, `google-ads-refresh-token`
- `slack-bot-token`, `slack-signing-secret`
- `portkey-api-key`, `portkey-virtual-key-anthropic`, `portkey-virtual-key-google`
- `anthropic-api-key`, `google-ai-api-key`
- **`api-auth-key`** (NEW) - For authenticating manual API calls

**Access**: Only `sa-sem-agents` service account has `roles/secretmanager.secretAccessor`

### IAM & Permissions

**Service Account**: `sa-sem-agents@{project}.iam.gserviceaccount.com`

**Roles**:
- `roles/bigquery.dataEditor` on `sem_agents` dataset (can write recommendations)
- `roles/bigquery.dataViewer` on `raw_google_ads`, `analytics_*` (read-only)
- `roles/bigquery.jobUser` (can run queries)
- `roles/secretmanager.secretAccessor` (can read secrets)
- `roles/pubsub.publisher`, `roles/pubsub.subscriber`
- `roles/run.invoker` (for inter-service calls)

**No owner/editor roles** - follows principle of least privilege.

---

## Setup Instructions

### 1. Generate API Auth Key

```bash
# Generate a secure random key
API_KEY=$(openssl rand -hex 32)

# Store in Secret Manager
echo -n "$API_KEY" | gcloud secrets create api-auth-key \
  --project=marketing-bigquery-490714 \
  --data-file=-

# Save the key securely for manual API calls
echo "Your API key: $API_KEY"
```

### 2. Deploy Updated Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This will:
- Create `api-auth-key` secret in Secret Manager
- Mount it to Cloud Run as `API_AUTH_KEY` env var
- Update IAM bindings

### 3. Configure Slack Approval Whitelist (Optional)

To restrict who can approve recommendations:

```bash
# Get Slack user IDs
# In Slack: Click user profile → More → Copy member ID

# Add to .env
SLACK_APPROVAL_USER_WHITELIST=U01ABC123,U02DEF456,U03GHI789
```

Leave empty to allow all users in the approval channel.

### 4. Test Authentication

```bash
# This should work (with API key)
curl -X POST https://your-url/api/v1/orchestrator/run \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# This should fail with 401 (no auth)
curl -X POST https://your-url/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

---

## GCP-Native Security Enhancements (Future)

### Option 1: Cloud Armor (Recommended for Production)

**What it does**: Web Application Firewall that filters traffic before it reaches Cloud Run

**Benefits**:
- Block traffic by IP, geo, or request patterns
- Rate limiting and DDoS protection
- Layer 7 filtering (inspect headers, query params, etc.)

**Setup**:
```terraform
# Create Cloud Armor security policy
resource "google_compute_security_policy" "sem_agents_policy" {
  name = "sem-agents-waf"

  # Block traffic from high-risk countries (optional)
  rule {
    action   = "deny(403)"
    priority = "1000"
    match {
      expr {
        expression = "origin.region_code == 'CN' || origin.region_code == 'RU'"
      }
    }
  }

  # Rate limit: 100 requests/minute per IP
  rule {
    action   = "rate_based_ban"
    priority = "2000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      rate_limit_threshold {
        count        = 100
        interval_sec = 60
      }
    }
  }

  # Allow Slack IP ranges (for webhooks)
  rule {
    action   = "allow"
    priority = "500"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = [
          "3.33.236.0/23",    # Slack webhooks
          "3.33.238.0/24",
          # ... add all Slack CIDR blocks from https://api.slack.com/docs/slack-ip-ranges
        ]
      }
    }
  }

  # Default: Allow authenticated traffic
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

# Attach to Cloud Run via Load Balancer
# (Cloud Armor requires HTTPS Load Balancer, not direct Cloud Run)
```

**Cost**: ~$0.75/policy/month + $0.75/1M requests

### Option 2: VPC Service Controls

**What it does**: Creates a security perimeter around GCP services

**Benefits**:
- Prevent data exfiltration
- Restrict access to authorized networks
- Block unauthorized API calls

**Setup**:
```terraform
resource "google_access_context_manager_service_perimeter" "sem_agents_perimeter" {
  parent = "accessPolicies/${var.access_policy}"
  name   = "accessPolicies/${var.access_policy}/servicePerimeters/semAgents"
  title  = "SEM Agents Perimeter"

  status {
    resources = [
      "projects/${var.project_number}",
    ]

    restricted_services = [
      "bigquery.googleapis.com",
      "secretmanager.googleapis.com",
      "run.googleapis.com",
    ]

    vpc_accessible_services {
      enable_restriction = true
      allowed_services = [
        "bigquery.googleapis.com",
        "secretmanager.googleapis.com",
      ]
    }
  }
}
```

**Cost**: Free (part of Access Context Manager)

### Option 3: Identity-Aware Proxy (IAP)

**What it does**: OAuth 2.0 authentication layer in front of your app

**Benefits**:
- Google/corporate SSO for human users
- Fine-grained access control (user + group based)
- Works with Cloud Run via Load Balancer

**When to use**: If you want human users to access a web UI for managing agents

**Not suitable for**: Slack webhooks (Slack doesn't support OAuth redirects)

### Option 4: API Gateway

**What it does**: Managed API gateway with authentication, rate limiting, quotas

**Benefits**:
- OpenAPI-based configuration
- Multiple auth methods (API key, OAuth, JWT)
- Built-in rate limiting and quotas
- Request/response transformation

**Setup**:
```yaml
# openapi.yaml
swagger: '2.0'
info:
  title: SEM Agents API
  version: 1.0.0
host: sem-agents-gateway.endpoints.YOUR_PROJECT.cloud.goog
schemes:
  - https
security:
  - api_key: []
securityDefinitions:
  api_key:
    type: apiKey
    name: x-api-key
    in: header
paths:
  /orchestrator/run:
    post:
      operationId: runOrchestrator
      x-google-backend:
        address: https://sem-gcp-agents-ivxfiybalq-uc.a.run.app
      security:
        - api_key: []
```

**Cost**: $0.20/1M calls + $2/1M transforms

### Option 5: Cloud Run Ingress Controls

**What it does**: Restricts which traffic can reach Cloud Run

**Options**:
- `all` - Public internet (current)
- `internal-and-cloud-load-balancing` - Only from LB + VPC
- `internal` - Only from VPC

**Limitation**: Slack webhooks come from public internet, so `internal` won't work

### Option 6: BigQuery Customer-Managed Encryption Keys (CMEK)

**What it does**: Encrypt data with your own KMS keys instead of Google-managed keys

**Benefits**:
- Full control over encryption keys
- Can revoke access by disabling key
- Compliance requirements (HIPAA, PCI DSS)

**Setup**:
```terraform
resource "google_kms_key_ring" "sem_agents" {
  name     = "sem-agents-keyring"
  location = "us-central1"
}

resource "google_kms_crypto_key" "bigquery" {
  name     = "bigquery-key"
  key_ring = google_kms_key_ring.sem_agents.id
}

resource "google_bigquery_dataset" "agents" {
  # ... existing config ...

  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.bigquery.id
  }
}
```

**Cost**: $0.06/key/month + $0.03/10K operations

---

## Recommended Security Roadmap

### Phase 1: Immediate (Before DRY_RUN=false)
- [x] API authentication middleware
- [x] Slack approval user whitelist
- [x] API key in Secret Manager
- [ ] Deploy and test auth

### Phase 2: Pre-Production (Next 2 weeks)
- [ ] Enable Cloud Armor with rate limiting
- [ ] Configure allowed IP ranges for known sources
- [ ] Add BigQuery CMEK encryption
- [ ] Enable Cloud Audit Logs for compliance

### Phase 3: Production (Month 1)
- [ ] VPC Service Controls perimeter
- [ ] Consider API Gateway for advanced features
- [ ] Set up monitoring alerts for failed auth attempts
- [ ] Implement Cloud Armor geo-blocking if needed

---

## Security Monitoring

### Logs to Monitor

**Failed authentication attempts**:
```bash
gcloud logging read 'jsonPayload.event="unauthenticated_request_blocked"' \
  --project=marketing-bigquery-490714 \
  --limit=50
```

**Unauthorized approval attempts**:
```bash
gcloud logging read 'jsonPayload.event="unauthorized_approval_attempt"' \
  --project=marketing-bigquery-490714 \
  --limit=50
```

**API key usage**:
```bash
gcloud logging read 'jsonPayload.event="api_key_authenticated"' \
  --project=marketing-bigquery-490714 \
  --limit=50
```

### Alerts to Set Up

- Alert on >10 failed auth attempts in 5 minutes (potential attack)
- Alert on unauthorized approval attempts
- Alert on Secret Manager access by non-service-account
- Alert on BigQuery data exports (data exfiltration)

---

## Compliance Notes

**GDPR**: User IDs are stored in `approval_events` table. Ensure you have data retention and deletion policies.

**SOC 2**: Enable Cloud Audit Logs for all services. Keep logs for 1+ year.

**PCI DSS**: If handling payment card data, enable VPC Service Controls and CMEK.

---

## Questions?

See:
- [Cloud Run Security](https://cloud.google.com/run/docs/securing/service-security)
- [Cloud Armor Docs](https://cloud.google.com/armor/docs)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
