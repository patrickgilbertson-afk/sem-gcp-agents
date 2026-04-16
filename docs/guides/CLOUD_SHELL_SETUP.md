# Deploy SEM GCP Agents Using Cloud Shell

**Recommended for users who:**
- Don't have gcloud CLI installed locally
- Want to avoid local authentication issues
- Prefer a browser-based workflow
- Need a fresh, pre-configured environment

Cloud Shell provides a free, pre-authenticated terminal with gcloud, terraform, docker, and git already installed.

---

## Quick Start

### 1. Open Cloud Shell

**Option A: From GCP Console**
1. Go to https://console.cloud.google.com
2. Click the **Cloud Shell** icon (terminal icon) in the top-right toolbar
3. Wait for Cloud Shell to initialize (~30 seconds)

**Option B: Direct URL**
- Open: https://shell.cloud.google.com

**Cloud Shell Features:**
- ✅ gcloud pre-installed and pre-authenticated
- ✅ 5GB persistent home directory
- ✅ Built-in code editor
- ✅ Terraform, Docker, git, Python 3.11 pre-installed
- ✅ No local setup required

---

### 2. Clone Repository

```bash
# In Cloud Shell terminal
cd ~
git clone https://github.com/YOUR-USERNAME/sem-gcp-agents.git
cd sem-gcp-agents
```

**Or use Cloud Shell Editor:**
1. Click **Open Editor** in Cloud Shell toolbar
2. File → Clone Repository
3. Enter: `https://github.com/YOUR-USERNAME/sem-gcp-agents.git`
4. Click **Clone**

---

### 3. Set Project Variables

```bash
# Set your project ID (replace with your actual project)
export PROJECT_ID="your-existing-project-id"
export REGION="us-central1"

# Set as active project
gcloud config set project $PROJECT_ID

# Verify you're authenticated
gcloud auth list
# Should show your account as ACTIVE

# Verify project is set
gcloud config get-value project
```

**Note**: Cloud Shell is already authenticated with your Google account - no need for `gcloud auth login`!

---

## Full Deployment Steps (Cloud Shell)

### Step 1: Enable Required APIs

```bash
# No authentication needed - already done!
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
gcloud services list --enabled | grep -E "run|bigquery|secretmanager"
```

---

### Step 2: Create Service Account

```bash
# Check if exists
gcloud iam service-accounts list | grep sem-agents

# Create if not exists
gcloud iam service-accounts create sem-agents \
    --display-name="SEM Agents Runtime" \
    --description="Service account for SEM GCP Agents" \
    2>/dev/null || echo "Service account already exists"

# Grant roles
for role in roles/bigquery.dataEditor roles/bigquery.jobUser roles/run.invoker roles/secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:sem-agents@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="$role" \
        --condition=None
done
```

---

### Step 3: Create BigQuery Datasets

```bash
# Check if dataset exists
bq ls | grep sem_agents

# Create if not exists
bq mk --dataset --location=US $PROJECT_ID:sem_agents 2>/dev/null || echo "Dataset exists"

# Verify
bq ls sem_agents
```

---

### Step 4: Configure Secrets

**Use Cloud Shell Editor to create a secrets script:**

```bash
# Create secrets setup script
cat > ~/setup_secrets.sh <<'EOF'
#!/bin/bash

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

# Replace these with your actual values
create_or_update_secret "google-ads-credentials" '{"developer_token":"YOUR_TOKEN","client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_SECRET","refresh_token":"YOUR_REFRESH"}'
create_or_update_secret "slack-bot-token" "xoxb-YOUR_BOT_TOKEN"
create_or_update_secret "slack-signing-secret" "YOUR_SIGNING_SECRET"
create_or_update_secret "portkey-api-key" "pk-YOUR_PORTKEY_KEY"
create_or_update_secret "portkey-virtual-key-anthropic" "anthropic-YOUR_VIRTUAL_KEY"
create_or_update_secret "portkey-virtual-key-google" "google-YOUR_VIRTUAL_KEY"

echo "All secrets created!"
EOF

chmod +x ~/setup_secrets.sh
```

**Edit the script with your values:**

```bash
# Open in Cloud Shell Editor
cloudshell edit ~/setup_secrets.sh

# Or use nano
nano ~/setup_secrets.sh
```

**Run the script:**

```bash
# Execute
~/setup_secrets.sh

# Verify
gcloud secrets list
```

**Grant access to service account:**

```bash
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

for secret in google-ads-credentials slack-bot-token slack-signing-secret portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "Already granted: $secret"
done
```

---

### Step 5: Deploy with Terraform

```bash
cd ~/sem-gcp-agents/terraform

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
project_id                  = "$PROJECT_ID"
region                      = "$REGION"
google_ads_customer_id      = "1234567890"  # Replace with yours
slack_approval_channel_id   = "C01234567"   # Replace with yours
dry_run_mode                = true
EOF

# Edit with Cloud Shell Editor if needed
cloudshell edit terraform.tfvars

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Apply (type 'yes' when prompted)
terraform apply
```

---

### Step 6: Build and Deploy Container

**Option A: Use Cloud Build (Recommended)**

```bash
cd ~/sem-gcp-agents

# Submit build to Cloud Build (no Docker daemon needed!)
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0

# Wait for build to complete (~5 minutes)
```

**Option B: Build locally in Cloud Shell**

```bash
# Note: Cloud Shell has limited resources
cd ~/sem-gcp-agents

# Authenticate Docker
gcloud auth configure-docker

# Build image
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 .

# Push to GCR
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
```

---

### Step 7: Deploy to Cloud Run

```bash
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 \
    --platform managed \
    --region $REGION \
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

# Allow all traffic (type 'y' when prompted)
```

---

### Step 8: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe sem-agents --region=$REGION --format='value(status.url)')
echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health

# Expected output: {"status": "ok", "version": "1.0.0"}
```

---

## Cloud Shell Tips & Tricks

### File Management

**Upload files to Cloud Shell:**
1. Click **⋮** (three dots) in Cloud Shell toolbar
2. Select **Upload**
3. Choose files

**Download files from Cloud Shell:**
1. Click **⋮** → **Download**
2. Enter file path (e.g., `~/sem-gcp-agents/terraform/terraform.tfstate`)

**Edit files:**
```bash
# Use Cloud Shell Editor (GUI)
cloudshell edit ~/sem-gcp-agents/.env

# Or use nano (terminal)
nano ~/sem-gcp-agents/.env

# Or use vim
vim ~/sem-gcp-agents/.env
```

---

### Persistent Storage

Cloud Shell provides **5GB persistent storage** in your home directory (`~`):

```bash
# Your code and configs persist here
~/sem-gcp-agents/

# Check disk usage
df -h ~

# Files outside ~ are deleted when Cloud Shell restarts!
```

---

### Session Management

**Cloud Shell sessions:**
- Auto-disconnect after **60 minutes of inactivity**
- Reconnect at: https://shell.cloud.google.com
- Your home directory persists (code is safe)

**Keep session alive:**
```bash
# Run this to prevent auto-disconnect
while true; do echo "keepalive $(date)"; sleep 300; done
```

---

### Cloud Shell Editor

**Open files:**
```bash
cloudshell edit ~/sem-gcp-agents/src/config.py
```

**Features:**
- Syntax highlighting
- Git integration
- Terminal access
- File explorer
- Search & replace

**Access Editor:**
1. Click **Open Editor** in Cloud Shell toolbar
2. Or: Ctrl+O (Windows/Linux), Cmd+O (Mac)

---

### Environment Variables

**Save variables for next session:**

```bash
# Add to .bashrc to persist
cat >> ~/.bashrc <<EOF
export PROJECT_ID="your-project-id"
export REGION="us-central1"
EOF

# Reload
source ~/.bashrc
```

---

### Run Commands in Background

```bash
# Long-running commands
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 &

# Check progress
jobs

# View output
fg
```

---

## Troubleshooting

### "Permission denied"

```bash
# Cloud Shell uses your current user - check permissions
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:$(gcloud config get-value account)"

# You need at least Editor role
```

### "Command not found: terraform"

```bash
# Terraform should be pre-installed, but if missing:
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
terraform version
```

### "Disk quota exceeded"

```bash
# Check usage
du -sh ~ | sort -h

# Clean up
rm -rf ~/.cache
docker system prune -a
```

### "Cloud Shell disconnected"

```bash
# Reconnect at: https://shell.cloud.google.com
# Your files in ~ are still there

cd ~/sem-gcp-agents
git status  # Verify your code is intact
```

---

## Workflow: Making Changes

### Edit Code in Cloud Shell

```bash
# 1. Navigate to repo
cd ~/sem-gcp-agents

# 2. Create a new branch
git checkout -b feature/my-changes

# 3. Edit files
cloudshell edit src/agents/campaign_health/agent.py

# 4. Test locally (if applicable)
python -m pytest tests/

# 5. Commit changes
git add .
git commit -m "My changes"

# 6. Push to GitHub
git push origin feature/my-changes

# 7. Create PR on GitHub
```

### Deploy Updates

```bash
# Rebuild container
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.1.0

# Update Cloud Run
gcloud run services update sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:v1.1.0 \
    --region $REGION
```

---

## Comparison: Cloud Shell vs Local CLI

| Feature | Cloud Shell | Local CLI |
|---------|-------------|-----------|
| **Setup Time** | 0 minutes (instant) | 15-30 minutes |
| **Authentication** | Pre-authenticated | Manual setup required |
| **gcloud Version** | Always latest | Manual updates |
| **Cost** | Free (5GB storage) | Free |
| **Access** | Any browser | Requires installation |
| **Persistent Storage** | 5GB | Unlimited (local disk) |
| **Session** | 60 min timeout | Always available |
| **Performance** | Moderate | Fast (local) |
| **Best For** | Quick tasks, new users | Heavy development |

---

## Complete Deployment Script (Cloud Shell)

**Run this all-in-one script:**

```bash
# Save as ~/deploy_sem_agents.sh
cat > ~/deploy_sem_agents.sh <<'SCRIPT'
#!/bin/bash
set -e

# Configuration
export PROJECT_ID="your-project-id"  # CHANGE THIS
export REGION="us-central1"
export GOOGLE_ADS_CUSTOMER_ID="1234567890"  # CHANGE THIS
export SLACK_CHANNEL_ID="C01234567"  # CHANGE THIS

echo "=== SEM GCP Agents Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Set project
gcloud config set project $PROJECT_ID

# Enable APIs
echo "Enabling APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com bigquery.googleapis.com secretmanager.googleapis.com

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create sem-agents --display-name="SEM Agents Runtime" 2>/dev/null || echo "Already exists"

# Grant roles
echo "Granting IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sem-agents@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/editor"

# Create BigQuery dataset
echo "Creating BigQuery dataset..."
bq mk --dataset --location=US $PROJECT_ID:sem_agents 2>/dev/null || echo "Already exists"

# Clone repo if not exists
if [ ! -d ~/sem-gcp-agents ]; then
    echo "Cloning repository..."
    git clone https://github.com/YOUR-USERNAME/sem-gcp-agents.git ~/sem-gcp-agents
fi

cd ~/sem-gcp-agents

# Build and deploy
echo "Building container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:latest

echo "Deploying to Cloud Run..."
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:latest \
    --platform managed \
    --region $REGION \
    --service-account sem-agents@$PROJECT_ID.iam.gserviceaccount.com \
    --allow-unauthenticated

echo "=== Deployment Complete ==="
gcloud run services describe sem-agents --region=$REGION --format='value(status.url)'
SCRIPT

chmod +x ~/deploy_sem_agents.sh

# Edit with your values
cloudshell edit ~/deploy_sem_agents.sh

# Run
~/deploy_sem_agents.sh
```

---

## Next Steps

1. ✅ Complete deployment in Cloud Shell
2. ✅ Set up Portkey account: https://portkey.ai
3. ✅ Configure secrets (see script above)
4. ✅ Set up Google Ads Data Transfer in BigQuery
5. ✅ Create Slack app from `scripts/slack_manifest.yml`
6. ✅ Test in dry run mode for 1-2 weeks

---

## Resources

- [Cloud Shell Documentation](https://cloud.google.com/shell/docs)
- [Cloud Shell Editor](https://cloud.google.com/shell/docs/editor-overview)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Secrets Checklist](../../GCP_SECRETS_CHECKLIST.md)

**Last Updated**: 2026-04-15
