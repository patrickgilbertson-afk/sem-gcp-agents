# Setting Up SEM Agents in an Existing GCP Project

This guide is for users who already have a GCP project and want to deploy the SEM GCP Agents framework without creating a new project.

## Choose Your Deployment Environment

**🌐 Cloud Shell (Recommended - No Local Setup)** ⭐
- Complete guide: **[Cloud Shell Setup Guide](CLOUD_SHELL_SETUP.md)**
- Pre-authenticated, no gcloud installation needed
- Browser-based terminal with all tools pre-installed

**💻 Local CLI**
- Continue with this guide
- Requires gcloud CLI installed locally

---

## Quick Start Checklist

- [ ] Existing GCP project with billing enabled
- [ ] gcloud CLI - Cloud Shell OR local installation
- [ ] Project ID and region defined
- [ ] Required APIs enabled (or will enable during setup)
- [ ] Access to create service accounts and resources

---

## Step-by-Step Setup

### 1. Configure Your Environment

```bash
# List your existing projects
gcloud projects list

# Set your project
export PROJECT_ID="your-existing-project-id"
export REGION="us-central1"

# Set as active project
gcloud config set project $PROJECT_ID

# Verify billing is enabled
gcloud billing projects describe $PROJECT_ID --format="value(billingEnabled)"
# Should return: True
```

### 2. Check What Already Exists

```bash
# Check enabled APIs
gcloud services list --enabled

# Check existing service accounts
gcloud iam service-accounts list

# Check existing BigQuery datasets
bq ls

# Check existing secrets
gcloud secrets list

# Check existing Cloud Run services
gcloud run services list --region=$REGION
```

### 3. Enable Required APIs

```bash
# This is safe to run even if APIs are already enabled
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    bigquery.googleapis.com \
    pubsub.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    iam.googleapis.com

# Verify
gcloud services list --enabled --filter="name:(run.googleapis.com OR bigquery.googleapis.com)"
```

### 4. Set Up Service Accounts

**Check for existing service accounts first:**

```bash
# Check if sem-agents service account exists
gcloud iam service-accounts describe sem-agents@$PROJECT_ID.iam.gserviceaccount.com 2>/dev/null

# If exists, skip creation. If not, create:
gcloud iam service-accounts create sem-agents \
    --display-name="SEM Agents Runtime" \
    --description="Service account for SEM GCP Agents" \
    2>/dev/null || echo "Service account already exists"

# Grant necessary roles (safe to run multiple times)
for role in roles/bigquery.dataEditor roles/bigquery.jobUser roles/run.invoker roles/secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:sem-agents@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="$role" \
        --condition=None \
        2>/dev/null || echo "Role $role already granted"
done

# Verify roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:sem-agents@$PROJECT_ID.iam.gserviceaccount.com" \
    --format="table(bindings.role)"
```

### 5. Set Up BigQuery

**Check for existing datasets:**

```bash
# Check if datasets exist
bq ls | grep -E "sem_agents|google_ads_raw"
```

**Option A: Dataset doesn't exist - Create new**

```bash
# Create sem_agents dataset
bq mk --dataset --location=US $PROJECT_ID:sem_agents

# Create tables using Terraform
cd terraform/modules/bigquery
terraform init
terraform apply -var="project_id=$PROJECT_ID"
```

**Option B: Dataset exists - Verify schema**

```bash
# Check existing tables
bq ls sem_agents

# Compare with required tables (12 total)
# Required: agent_config, agent_recommendations, agent_audit_log, agent_runs,
#           kill_switch_status, slack_approvals, google_ads_sync_log,
#           llm_usage_log, rate_limit_tracker, campaign_taxonomy,
#           quality_score_history, landing_page_audits

# Create any missing tables
# Terraform will only create what doesn't exist
cd terraform/modules/bigquery
terraform init
terraform import google_bigquery_dataset.sem_agents $PROJECT_ID:sem_agents
terraform plan -var="project_id=$PROJECT_ID"
terraform apply -var="project_id=$PROJECT_ID"
```

### 6. Configure Secrets

**Create or update secrets safely:**

```bash
# Helper function
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

# Create or update each secret (replace with your actual values)
create_or_update_secret "anthropic-api-key" "sk-ant-YOUR_KEY"
create_or_update_secret "google-ads-credentials" '{"developer_token": "...", "client_id": "...", "client_secret": "...", "refresh_token": "..."}'
create_or_update_secret "slack-bot-token" "xoxb-YOUR_TOKEN"
create_or_update_secret "slack-signing-secret" "YOUR_SECRET"

# Grant access to service account
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

for secret in anthropic-api-key google-ads-credentials slack-bot-token slack-signing-secret; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "Permission already granted for $secret"
done
```

### 7. Deploy with Terraform

**Configure Terraform for existing project:**

```bash
cd terraform

# Create terraform.tfvars (or update existing)
cat > terraform.tfvars <<EOF
project_id                  = "$PROJECT_ID"
region                      = "$REGION"
google_ads_customer_id      = "1234567890"  # Replace with yours
slack_approval_channel_id   = "C01234567"   # Replace with yours
dry_run_mode                = true
EOF

# Initialize Terraform
terraform init

# Review what will be created/updated
terraform plan

# Apply (Terraform will only create resources that don't exist)
terraform apply

# If resources already exist, import them:
# terraform import google_bigquery_dataset.sem_agents $PROJECT_ID:sem_agents
# terraform import google_cloud_run_service.sem_agents $REGION/sem-agents
```

### 8. Build and Deploy Application

```bash
# Authenticate Docker
gcloud auth configure-docker

# Build image
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 .

# Push to GCR
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0

# Deploy to Cloud Run (or update existing)
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 \
    --platform managed \
    --region $REGION \
    --service-account sem-agents@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars "PROJECT_ID=$PROJECT_ID,DRY_RUN=true" \
    --set-secrets "GOOGLE_ADS_CREDENTIALS=google-ads-credentials:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,SLACK_BOT_TOKEN=slack-bot-token:latest,SLACK_SIGNING_SECRET=slack-signing-secret:latest" \
    --max-instances 10 \
    --timeout 900 \
    --memory 2Gi \
    --cpu 2 \
    --allow-unauthenticated
```

### 9. Initialize Database State

**Check if data already exists:**

```bash
# Check if agent config table has data
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM sem_agents.agent_config"

# Check kill switch status
bq query --use_legacy_sql=false "SELECT * FROM sem_agents.kill_switch_status LIMIT 1"
```

**Initialize only if empty:**

```bash
# Seed agent config (only if empty)
if [ $(bq query --use_legacy_sql=false --format=csv "SELECT COUNT(*) FROM sem_agents.agent_config" | tail -1) -eq 0 ]; then
    python scripts/seed_bigquery.py --project-id $PROJECT_ID
else
    echo "Agent config already populated"
fi

# Initialize kill switch (only if empty)
bq query --use_legacy_sql=false "
  INSERT INTO sem_agents.kill_switch_status (enabled, updated_by, reason)
  SELECT FALSE, 'system', 'Initial setup'
  WHERE NOT EXISTS (SELECT 1 FROM sem_agents.kill_switch_status)
"
```

### 10. Verify Deployment

```bash
# Get Cloud Run URL
SERVICE_URL=$(gcloud run services describe sem-agents --region=$REGION --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test agent endpoint (dry run)
curl -X POST "$SERVICE_URL/api/v1/orchestrator/run" \
    -H "Content-Type: application/json" \
    -d '{"agent_type": "campaign_health"}'

# Check logs
gcloud run services logs read sem-agents --region=$REGION --limit=50
```

---

## Handling Conflicts

### Resource Already Exists Errors

If you encounter "already exists" errors during deployment:

1. **BigQuery datasets/tables**: Import into Terraform state
   ```bash
   terraform import google_bigquery_dataset.sem_agents $PROJECT_ID:sem_agents
   terraform import google_bigquery_table.agent_config $PROJECT_ID:sem_agents.agent_config
   ```

2. **Cloud Run services**: Import or delete and recreate
   ```bash
   # Import existing service
   terraform import google_cloud_run_service.sem_agents $REGION/sem-agents

   # Or delete and let Terraform recreate
   gcloud run services delete sem-agents --region=$REGION
   terraform apply
   ```

3. **Secrets**: Update instead of create (handled by helper function above)

4. **Service accounts**: Import into Terraform
   ```bash
   terraform import google_service_account.sem_agents projects/$PROJECT_ID/serviceAccounts/sem-agents@$PROJECT_ID.iam.gserviceaccount.com
   ```

### Name Conflicts

If resource names conflict with existing resources:

1. **Rename in terraform.tfvars**:
   ```hcl
   cloud_run_service_name = "sem-agents-v2"
   bigquery_dataset_id = "sem_agents_v2"
   ```

2. **Use prefixes/suffixes**:
   ```bash
   export RESOURCE_PREFIX="myorg"
   # Update Terraform variables accordingly
   ```

### Permission Issues

If you get permission errors:

```bash
# Check your current permissions
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:$(gcloud config get-value account)"

# You need at least these roles:
# - roles/editor OR specific roles for each service
# - roles/iam.serviceAccountAdmin (to create service accounts)
# - roles/resourcemanager.projectIamAdmin (to grant roles)

# Ask your GCP admin to grant missing roles
```

---

## Differences from New Project Setup

| Aspect | New Project | Existing Project |
|--------|-------------|------------------|
| **Project Creation** | Create new | Use existing |
| **APIs** | Enable all fresh | Check & enable missing |
| **Service Accounts** | Create new | Check if exists, then create or reuse |
| **BigQuery** | Create datasets/tables | Check schema, create missing |
| **Secrets** | Create all | Create or update |
| **Terraform** | Fresh apply | Import existing + apply |
| **Naming** | Default names | May need prefixes/suffixes |

---

## Troubleshooting

### "Dataset already exists"
```bash
# Import into Terraform state
terraform import google_bigquery_dataset.sem_agents $PROJECT_ID:sem_agents
```

### "Service account already exists"
```bash
# Use existing or import
terraform import google_service_account.sem_agents projects/$PROJECT_ID/serviceAccounts/sem-agents@$PROJECT_ID.iam.gserviceaccount.com
```

### "Secret already exists"
```bash
# Update instead of create
echo -n "NEW_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
```

### "Permission denied"
```bash
# Check your roles
gcloud projects get-iam-policy $PROJECT_ID --filter="bindings.members:$(gcloud config get-value account)"

# Common missing roles:
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:YOUR_EMAIL" \
    --role="roles/editor"
```

---

## Next Steps

After successful setup in existing project:

1. Review [System Overview](../architecture/SYSTEM_OVERVIEW.md) for architecture details
2. Follow Steps 7-11 in [System Overview](../architecture/SYSTEM_OVERVIEW.md#step-7-test-in-dry-run-mode) for testing
3. Monitor for 1-2 weeks in dry run mode
4. Enable production mode when confident

---

**Last Updated**: 2026-04-15
