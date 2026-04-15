# Deployment Guide: GitHub to Google Cloud Platform

This guide walks you through publishing the SEM GCP Agents project to GitHub and deploying it to Google Cloud Platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [GitHub Setup](#github-setup)
3. [Google Cloud Platform Setup](#gcp-setup)
4. [Integration Options](#integration-options)
   - [Option A: GitHub Actions with Workload Identity (Recommended)](#option-a-github-actions-with-workload-identity-recommended)
   - [Option B: Cloud Build Triggers](#option-b-cloud-build-triggers)
5. [Initial Deployment](#initial-deployment)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Git**: Version 2.30 or later
- **gcloud CLI**: [Install Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- **Terraform**: Version 1.5 or later ([Download](https://www.terraform.io/downloads))
- **Docker**: For local testing ([Download](https://www.docker.com/get-started))
- **Python**: 3.11 or later

### Required Accounts
- GitHub account with repository creation permissions
- Google Cloud Platform account with billing enabled
- Permissions to create projects and service accounts in GCP

### Required Access
- Google Ads API access (MCC account or client account)
- Slack workspace admin access (for creating Slack app)

---

## GitHub Setup

### 1. Create GitHub Repository

```bash
# Navigate to project directory
cd C:\Users\patrick.gilbertson\SEM-GCP-Agents

# Initialize git (if not already initialized)
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: SEM GCP Agents framework"
```

### 2. Create Repository on GitHub

1. Go to [github.com](https://github.com) and sign in
2. Click the **+** icon → **New repository**
3. Repository settings:
   - **Name**: `sem-gcp-agents`
   - **Description**: "AI-powered SEM campaign management on GCP"
   - **Visibility**: Private (recommended for production systems)
   - **DO NOT** initialize with README, .gitignore, or license (we have these)
4. Click **Create repository**

### 3. Push to GitHub

```bash
# Add remote origin (replace YOUR-USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR-USERNAME/sem-gcp-agents.git

# Verify remote
git remote -v

# Push code
git branch -M main
git push -u origin main
```

### 4. Protect Main Branch (Recommended)

1. Go to repository → **Settings** → **Branches**
2. Under "Branch protection rules", click **Add rule**
3. Branch name pattern: `main`
4. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require conversation resolution before merging
5. Click **Create**

---

## GCP Setup

### 1. Set Up GCP Project

Choose **ONE** of the following paths:

#### Option A: Use Existing Project (Recommended if you already have a project)

```bash
# List your existing projects
gcloud projects list

# Set your existing project ID
export PROJECT_ID="your-existing-project-id"
export REGION="us-central1"

# Set as active project
gcloud config set project $PROJECT_ID

# Verify billing is enabled
gcloud billing projects describe $PROJECT_ID --format="value(billingEnabled)"
# Should output: True

# If billing is not enabled, link billing account
# gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

#### Option B: Create New GCP Project

```bash
# Set your project ID (must be globally unique)
export PROJECT_ID="sem-gcp-agents-prod"
export REGION="us-central1"

# Create project
gcloud projects create $PROJECT_ID --name="SEM GCP Agents"

# Set as active project
gcloud config set project $PROJECT_ID

# Link billing account (replace BILLING_ACCOUNT_ID with yours)
# Find your billing account: gcloud billing accounts list
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

### 2. Enable Required APIs

```bash
# Check which APIs are already enabled (optional)
gcloud services list --enabled

# Enable all required APIs (safe to run even if some are already enabled)
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    bigquery.googleapis.com \
    pubsub.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    iam.googleapis.com \
    googleads.googleapis.com

# Verify all APIs are enabled
gcloud services list --enabled --filter="name:(run.googleapis.com OR bigquery.googleapis.com OR secretmanager.googleapis.com)"
```

### 3. Create Service Account for Deployment

```bash
# Check if service account already exists
gcloud iam service-accounts list --filter="email:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# If not exists, create it
gcloud iam service-accounts create sem-agents-deployer \
    --display-name="SEM Agents Deployer" \
    --description="Service account for deploying SEM GCP Agents" \
    2>/dev/null || echo "Service account already exists, skipping creation"

# Grant necessary roles (safe to run even if already granted)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Verify roles were granted
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --format="table(bindings.role)"
```

### 4. Configure Authentication for Local Development

```bash
# Authenticate with GCP
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Verify setup
gcloud config list
```

---

## Integration Options

Choose **one** of the following integration methods:

---

### Option A: GitHub Actions with Workload Identity (Recommended)

**Why?** More secure (no service account keys), native GitHub integration, easier to manage.

#### Step 1: Set Up Workload Identity Federation

```bash
# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
    --location="global" \
    --display-name="GitHub Actions Pool"

# Get pool ID
export WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" \
    --location="global" \
    --format="value(name)")

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --issuer-uri="https://token.actions.githubusercontent.com"
```

#### Step 2: Bind Service Account to GitHub Repository

```bash
# Replace YOUR-GITHUB-USERNAME with your actual GitHub username
export GITHUB_REPO="YOUR-GITHUB-USERNAME/sem-gcp-agents"

# Grant service account access to GitHub Actions
gcloud iam service-accounts add-iam-policy-binding \
    "sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

#### Step 3: Add GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  workflow_dispatch: # Allow manual trigger

env:
  PROJECT_ID: sem-gcp-agents-prod
  REGION: us-central1
  SERVICE_NAME: sem-gcp-agents

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write # Required for Workload Identity

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'sem-agents-deployer@${{ env.PROJECT_ID }}.iam.gserviceaccount.com'

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for GCR
        run: gcloud auth configure-docker

      - name: Build Docker image
        run: |
          docker build -t gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }} .
          docker tag gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }} gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:latest

      - name: Push to Container Registry
        run: |
          docker push gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }}
          docker push gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:latest

      - name: Set up Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.0

      - name: Terraform Init
        run: terraform init
        working-directory: terraform

      - name: Terraform Apply
        run: terraform apply -auto-approve -var="cloud_run_image=gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }}"
        working-directory: terraform
        env:
          TF_VAR_project_id: ${{ env.PROJECT_ID }}
          TF_VAR_region: ${{ env.REGION }}

      - name: Get Service URL
        run: |
          SERVICE_URL=$(gcloud run services describe ${{ env.SERVICE_NAME }} --region=${{ env.REGION }} --format='value(status.url)')
          echo "Service deployed to: $SERVICE_URL"
```

#### Step 4: Add GitHub Secrets

1. Go to repository → **Settings** → **Secrets and variables** → **Actions**
2. Add repository secrets:
   - `GCP_PROJECT_ID`: Your GCP project ID
   - `WORKLOAD_IDENTITY_PROVIDER`: Full provider path (get with command below)

```bash
# Get Workload Identity Provider path
gcloud iam workload-identity-pools providers describe "github-provider" \
    --workload-identity-pool="github-pool" \
    --location="global" \
    --format="value(name)"
```

#### Step 5: Update Workflow File

Replace `PROJECT_NUMBER` in `.github/workflows/deploy.yml` with your actual project number:

```bash
# Get project number
gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
```

---

### Option B: Cloud Build Triggers

**Why?** Fully managed by GCP, integrated with Cloud Console, good for GCP-centric teams.

#### Step 1: Create cloudbuild.yaml

Create `cloudbuild.yaml` in project root:

```yaml
steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'
      - '.'

  # Push Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'

  # Deploy with Terraform
  - name: 'hashicorp/terraform:1.5'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        cd terraform
        terraform init
        terraform apply -auto-approve \
          -var="cloud_run_image=gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA" \
          -var="project_id=$PROJECT_ID" \
          -var="region=$_REGION"
    env:
      - 'TF_VAR_project_id=$PROJECT_ID'

substitutions:
  _REGION: us-central1

options:
  logging: CLOUD_LOGGING_ONLY

images:
  - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'
  - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'
```

#### Step 2: Connect GitHub Repository to Cloud Build

```bash
# Install Cloud Build GitHub app (one-time setup)
# Visit: https://github.com/apps/google-cloud-build
# Click "Install" and select your repository

# Or use gcloud command
gcloud alpha builds connections create github "github-connection" \
    --region=$REGION
```

#### Step 3: Create Build Trigger

```bash
# Create trigger via gcloud
gcloud builds triggers create github \
    --name="deploy-main" \
    --repo-name="sem-gcp-agents" \
    --repo-owner="YOUR-GITHUB-USERNAME" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml" \
    --region=$REGION
```

**Or create via Console:**

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click **Create Trigger**
3. Configure:
   - **Name**: `deploy-main`
   - **Event**: Push to branch
   - **Repository**: Select your GitHub repo
   - **Branch**: `^main$`
   - **Build configuration**: Cloud Build configuration file
   - **Location**: `cloudbuild.yaml`
4. Click **Create**

#### Step 4: Grant Cloud Build Permissions

```bash
# Get Cloud Build service account
export CLOUD_BUILD_SA=$(gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.role:roles/cloudbuild.builds.builder" \
    --format="value(bindings.members)" | grep @cloudbuild)

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="$CLOUD_BUILD_SA" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="$CLOUD_BUILD_SA" \
    --role="roles/iam.serviceAccountUser"
```

---

## Initial Deployment

### 1. Configure Secrets in GCP Secret Manager

```bash
# Check existing secrets
echo "Checking for existing secrets..."
gcloud secrets list

# Function to create or update secret
create_or_update_secret() {
    SECRET_NAME=$1
    SECRET_VALUE=$2

    if gcloud secrets describe $SECRET_NAME &>/dev/null; then
        echo "Secret $SECRET_NAME exists. Updating..."
        echo -n "$SECRET_VALUE" | gcloud secrets versions add $SECRET_NAME --data-file=-
    else
        echo "Creating secret $SECRET_NAME..."
        echo -n "$SECRET_VALUE" | gcloud secrets create $SECRET_NAME --data-file=-
    fi
}

# Create or update secrets (replace with actual values)
create_or_update_secret "anthropic-api-key" "YOUR_ANTHROPIC_API_KEY"
create_or_update_secret "google-ads-developer-token" "YOUR_GOOGLE_ADS_DEVELOPER_TOKEN"
create_or_update_secret "google-ads-client-id" "YOUR_GOOGLE_ADS_CLIENT_ID"
create_or_update_secret "google-ads-client-secret" "YOUR_GOOGLE_ADS_CLIENT_SECRET"
create_or_update_secret "google-ads-refresh-token" "YOUR_GOOGLE_ADS_REFRESH_TOKEN"
create_or_update_secret "slack-bot-token" "YOUR_SLACK_BOT_TOKEN"
create_or_update_secret "slack-signing-secret" "YOUR_SLACK_SIGNING_SECRET"

# Alternative: Create all at once (will fail if secrets exist)
# echo -n "YOUR_ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=- 2>/dev/null || echo "anthropic-api-key already exists"
# ... repeat for each secret

# Grant access to Cloud Run service account (safe to run multiple times)
for SECRET in anthropic-api-key google-ads-developer-token google-ads-client-id google-ads-client-secret google-ads-refresh-token slack-bot-token slack-signing-secret; do
    gcloud secrets add-iam-policy-binding $SECRET \
        --member="serviceAccount:sem-agents-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "Permission already granted for $SECRET"
done

# Verify secrets and permissions
echo -e "\nVerifying secrets..."
gcloud secrets list --filter="name:(anthropic-api-key OR slack-bot-token)"
```

### 2. Configure Terraform Variables

Create `terraform/terraform.tfvars`:

```hcl
project_id = "sem-gcp-agents-prod"
region     = "us-central1"

# Google Ads Configuration
google_ads_customer_id = "1234567890"  # Replace with your customer ID (no dashes)
google_ads_login_customer_id = "9876543210"  # Replace with your MCC ID (if applicable)

# BigQuery Configuration
bigquery_dataset_id = "sem_agents"
bigquery_location = "US"

# Cloud Run Configuration
cloud_run_min_instances = 0
cloud_run_max_instances = 10
cloud_run_cpu = "1"
cloud_run_memory = "512Mi"

# Slack Configuration
slack_approval_channel_id = "C01234567"  # Replace with your Slack channel ID

# Safety Settings
dry_run_mode = true  # Start with dry run enabled
kill_switch_enabled = false
```

### 3. Deploy Infrastructure with Terraform

```bash
cd terraform

# Initialize Terraform
terraform init

# Review changes
terraform plan

# Apply infrastructure
terraform apply

# Note the outputs (service URL, BigQuery dataset, etc.)
```

### 4. Set Up Google Ads Data Transfer

1. Go to [BigQuery Data Transfer](https://console.cloud.google.com/bigquery/transfers)
2. Click **Create Transfer**
3. Select **Google Ads**
4. Configure:
   - **Display name**: "Google Ads Data Transfer"
   - **Schedule**: Daily at 2 AM
   - **Destination dataset**: `sem_agents`
   - **Customer ID**: Your Google Ads customer ID
5. Authorize and create

### 5. Deploy Application

**For GitHub Actions:**
```bash
# Trigger deployment by pushing to main
git add .
git commit -m "Configure deployment"
git push origin main

# Monitor deployment
# Go to GitHub repository → Actions tab
```

**For Cloud Build:**
```bash
# Trigger deployment by pushing to main
git add .
git commit -m "Configure deployment"
git push origin main

# Monitor deployment
gcloud builds list --limit=5
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")
```

**Manual deployment:**
```bash
# Use the deployment script
./scripts/deploy.sh
```

---

## Verification

### 1. Check Cloud Run Service

```bash
# Get service URL
gcloud run services describe sem-gcp-agents --region=$REGION --format='value(status.url)'

# Test health endpoint
curl $(gcloud run services describe sem-gcp-agents --region=$REGION --format='value(status.url)')/health
```

Expected response:
```json
{"status": "healthy", "timestamp": "2026-04-09T12:00:00Z"}
```

### 2. Verify BigQuery Tables

```bash
# List datasets
bq ls

# List tables in sem_agents dataset
bq ls sem_agents

# Check agent_audit_log table
bq show sem_agents.agent_audit_log
```

### 3. Test Agent Endpoint (Dry Run)

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe sem-gcp-agents --region=$REGION --format='value(status.url)')

# Trigger Campaign Health Agent
curl -X POST "${SERVICE_URL}/api/v1/orchestrator/run" \
    -H "Content-Type: application/json" \
    -d '{"agent_type": "campaign_health", "config": {"dry_run": true}}'
```

### 4. Check Logs

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sem-gcp-agents" \
    --limit=50 \
    --format=json

# Or view in Console
# https://console.cloud.google.com/run/detail/$REGION/sem-gcp-agents/logs
```

### 5. Verify Scheduled Jobs

```bash
# List Cloud Scheduler jobs
gcloud scheduler jobs list --location=$REGION

# Test scheduler job
gcloud scheduler jobs run campaign-health-daily --location=$REGION
```

---

## Troubleshooting

### Issue: "Permission denied" during deployment

**Solution:**
```bash
# Verify service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:sem-agents-deployer"

# Grant missing roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/editor"
```

### Issue: "Image not found" in Cloud Run

**Solution:**
```bash
# Verify image exists in Container Registry
gcloud container images list --repository=gcr.io/$PROJECT_ID

# Check image tags
gcloud container images list-tags gcr.io/$PROJECT_ID/sem-gcp-agents
```

### Issue: GitHub Actions workflow fails authentication

**Solution:**
```bash
# Verify Workload Identity Pool setup
gcloud iam workload-identity-pools describe github-pool --location=global

# Re-bind service account
gcloud iam service-accounts add-iam-policy-binding \
    "sem-agents-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR-GITHUB-USERNAME/sem-gcp-agents"
```

### Issue: Terraform apply fails with "state lock" error

**Solution:**
```bash
# Force unlock (use with caution)
cd terraform
terraform force-unlock LOCK_ID

# Or enable state locking in Cloud Storage
# Update terraform/backend.tf to use GCS backend
```

### Issue: BigQuery "Access Denied" errors

**Solution:**
```bash
# Grant BigQuery permissions to Cloud Run service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
```

### Issue: Secrets not accessible in Cloud Run

**Solution:**
```bash
# Verify secret exists
gcloud secrets describe anthropic-api-key

# Grant access
gcloud secrets add-iam-policy-binding anthropic-api-key \
    --member="serviceAccount:sem-agents-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Verify Cloud Run service account
gcloud run services describe sem-gcp-agents --region=$REGION --format="value(spec.template.spec.serviceAccountName)"
```

---

## Next Steps

After successful deployment:

1. **Review logs for first dry run**: Check `agent_audit_log` in BigQuery
2. **Configure Slack app**: Follow instructions in `scripts/slack_manifest.yml`
3. **Test approval workflow**: Trigger an agent and approve via Slack
4. **Monitor for 1 week**: Keep `dry_run_mode=true` and review recommendations
5. **Enable production mode**: Set `dry_run_mode=false` in `terraform.tfvars` and re-apply
6. **Set up monitoring**: Create dashboards in Cloud Monitoring
7. **Configure alerting**: Set up alerts for errors, budget overruns, approval timeouts

---

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [GitHub Actions for GCP](https://github.com/google-github-actions)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [BigQuery Data Transfer](https://cloud.google.com/bigquery-transfer/docs)

For project-specific guidance, see:
- `CLAUDE.md` - Project architecture and patterns
- `README.md` - Local development setup
- `IMPLEMENTATION_STATUS.md` - Current phase and roadmap
