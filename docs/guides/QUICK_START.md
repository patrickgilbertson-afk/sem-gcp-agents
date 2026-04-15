# Quick Start Guide

Get SEM GCP Agents up and running in 30 minutes.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] GitHub account
- [ ] GCP account with billing enabled
- [ ] Google Ads API access (developer token)
- [ ] Slack workspace admin access
- [ ] `gcloud` CLI installed and authenticated
- [ ] `terraform` CLI installed (v1.5+)
- [ ] Docker installed (for local testing)

## 5-Step Deployment

### Step 1: Clone and Push to GitHub (5 min)

```bash
# Navigate to project
cd C:\Users\patrick.gilbertson\SEM-GCP-Agents

# Initialize git
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR-USERNAME/sem-gcp-agents.git
git push -u origin main
```

### Step 2: Set Up GCP Project (10 min)

```bash
# Set variables
export PROJECT_ID="sem-gcp-agents-prod"
export REGION="us-central1"

# Create and configure project
gcloud projects create $PROJECT_ID --name="SEM GCP Agents"
gcloud config set project $PROJECT_ID

# Link billing (replace BILLING_ACCOUNT_ID)
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID

# Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    containerregistry.googleapis.com bigquery.googleapis.com \
    pubsub.googleapis.com secretmanager.googleapis.com \
    cloudscheduler.googleapis.com iam.googleapis.com

# Create service account
gcloud iam service-accounts create sem-agents-deployer \
    --display-name="SEM Agents Deployer"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/editor"
```

### Step 3: Configure Secrets (5 min)

```bash
# Create secrets in Secret Manager
echo -n "YOUR_ANTHROPIC_API_KEY" | \
    gcloud secrets create anthropic-api-key --data-file=-

echo -n "YOUR_GOOGLE_ADS_DEVELOPER_TOKEN" | \
    gcloud secrets create google-ads-developer-token --data-file=-

echo -n "YOUR_GOOGLE_ADS_CLIENT_ID" | \
    gcloud secrets create google-ads-client-id --data-file=-

echo -n "YOUR_GOOGLE_ADS_CLIENT_SECRET" | \
    gcloud secrets create google-ads-client-secret --data-file=-

echo -n "YOUR_GOOGLE_ADS_REFRESH_TOKEN" | \
    gcloud secrets create google-ads-refresh-token --data-file=-

echo -n "YOUR_SLACK_BOT_TOKEN" | \
    gcloud secrets create slack-bot-token --data-file=-

echo -n "YOUR_SLACK_SIGNING_SECRET" | \
    gcloud secrets create slack-signing-secret --data-file=-
```

### Step 4: Configure and Deploy Infrastructure (8 min)

```bash
# Copy Terraform example
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
# - project_id
# - google_ads_customer_id
# - slack_approval_channel_id

# Deploy infrastructure
terraform init
terraform plan
terraform apply  # Review and type 'yes'
```

### Step 5: Verify Deployment (2 min)

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe sem-gcp-agents \
    --region=$REGION --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Expected: {"status": "healthy", "timestamp": "..."}
```

## What's Next?

### 1. Set Up Google Ads Data Transfer

1. Go to [BigQuery Data Transfer](https://console.cloud.google.com/bigquery/transfers)
2. Click **Create Transfer** → Select **Google Ads**
3. Configure:
   - Schedule: Daily at 2 AM
   - Destination: `sem_agents` dataset
   - Customer ID: Your Google Ads ID
4. Authorize and create

### 2. Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Click **Create New App** → From manifest
3. Paste contents from `scripts/slack_manifest.yml`
4. Install app to workspace
5. Copy Bot Token and Signing Secret to Secret Manager

### 3. Test in Dry Run Mode

```bash
# Trigger Campaign Health Agent (dry run)
curl -X POST "$SERVICE_URL/api/v1/orchestrator/run" \
    -H "Content-Type: application/json" \
    -d '{"agent_type": "campaign_health", "config": {"dry_run": true}}'

# Check logs
gcloud logging read "resource.type=cloud_run_revision" --limit=20

# Query audit log
bq query --use_legacy_sql=false \
    'SELECT * FROM `sem_agents.agent_audit_log` ORDER BY timestamp DESC LIMIT 10'
```

### 4. Review Recommendations (1 week)

- Monitor Slack for agent recommendations
- Review recommendations with SEM manager
- Check audit logs in BigQuery
- Adjust thresholds if needed

### 5. Enable Production Mode

```bash
# Update terraform.tfvars
# Change: dry_run_mode = false

# Re-apply Terraform
cd terraform
terraform apply
```

## Troubleshooting

### "Permission denied" errors

```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login
```

### "Image not found" in Cloud Run

```bash
# Verify image was pushed
gcloud container images list --repository=gcr.io/$PROJECT_ID

# If missing, build and push manually
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:latest .
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:latest
```

### "BigQuery table not found"

```bash
# Verify tables were created
bq ls sem_agents

# If missing, re-run Terraform
cd terraform
terraform apply
```

### Health check fails

```bash
# Check Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sem-gcp-agents" --limit=50

# Common issues:
# - Missing secrets (check Secret Manager IAM)
# - Terraform apply didn't complete
# - Service account permissions
```

## Monitoring

### View Logs

```bash
# Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Agent-specific logs
gcloud logging read "jsonPayload.agent_type=campaign_health" --limit=20
```

### Query Audit Trail

```sql
-- Recent agent runs
SELECT
    timestamp,
    agent_type,
    run_id,
    action,
    status
FROM `sem_agents.agent_audit_log`
ORDER BY timestamp DESC
LIMIT 100;

-- Recommendations by status
SELECT
    agent_type,
    status,
    COUNT(*) as count
FROM `sem_agents.agent_recommendations`
GROUP BY agent_type, status;
```

### Set Up Alerts

1. Go to [Cloud Monitoring](https://console.cloud.google.com/monitoring)
2. Create alert policies for:
   - Cloud Run errors (>5 errors in 5 minutes)
   - Agent failures (check audit log)
   - Budget anomalies (>15% daily increase)
   - Approval timeouts (>4 hours)

## Additional Resources

- **Full Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Project Architecture**: `CLAUDE.md`
- **Local Development**: `README.md`
- **Implementation Status**: `IMPLEMENTATION_STATUS.md`

## Support

- GitHub Issues: https://github.com/YOUR-USERNAME/sem-gcp-agents/issues
- GCP Console: https://console.cloud.google.com/run
- BigQuery Console: https://console.cloud.google.com/bigquery
- Slack App: https://api.slack.com/apps

---

**Estimated Total Time**: 30-45 minutes

**Cost Estimate** (first month):
- Cloud Run: ~$5-10 (with scale to zero)
- BigQuery: ~$10-20 (depends on data volume)
- Secret Manager: ~$0.50
- Cloud Scheduler: ~$0.10
- **Total**: ~$15-30/month

**Production Readiness Checklist**:
- [ ] All secrets configured in Secret Manager
- [ ] Google Ads Data Transfer running daily
- [ ] Slack app created and installed
- [ ] Dry run tested successfully for 1 week
- [ ] Recommendations reviewed with SEM manager
- [ ] Thresholds adjusted for your campaigns
- [ ] Monitoring and alerts configured
- [ ] Team trained on approval workflow
- [ ] `dry_run_mode = false` in production
