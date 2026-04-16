# Cloud Shell Quick Fixes

## Error: "invalid reference format" in Cloud Build

### Symptom
```
invalid argument "gcr.io//sem-gcp-agents:v1.0.0" for "-t, --tag" flag: invalid reference format
```

Notice the **double slash** (`//`) - this means `$PROJECT_ID` is empty!

### Solution

```bash
# Check if PROJECT_ID is set
echo $PROJECT_ID

# If empty, set it
export PROJECT_ID="$(gcloud config get-value project)"

# Verify it's set
echo $PROJECT_ID
# Should output your project ID (e.g., marketing-bigquery-490714)

# Also set REGION while you're at it
export REGION="us-central1"

# Now retry the build
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
```

### Make Environment Variables Persistent

Add these to your Cloud Shell `.bashrc` so they persist between sessions:

```bash
# Add to .bashrc
cat >> ~/.bashrc <<'EOF'

# SEM GCP Agents Environment Variables
export PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"
export REGION="us-central1"
EOF

# Reload
source ~/.bashrc

# Verify
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
```

### Alternative: Use Project ID Directly

Instead of using `$PROJECT_ID`, use your actual project ID:

```bash
# Replace with your actual project ID
gcloud builds submit --tag gcr.io/marketing-bigquery-490714/sem-gcp-agents:v1.0.0
```

---

## Error: "permission denied" or "API not enabled"

### Cloud Build API Not Enabled

```bash
# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Verify
gcloud services list --enabled | grep cloudbuild
```

### Container Registry API Not Enabled

```bash
# Enable Container Registry API
gcloud services enable containerregistry.googleapis.com

# Enable Artifact Registry API (newer)
gcloud services enable artifactregistry.googleapis.com

# Verify
gcloud services list --enabled | grep -E "container|artifact"
```

---

## Error: "INVALID_ARGUMENT: invalid Dockerfile"

### Missing Dockerfile

```bash
# Verify Dockerfile exists in current directory
ls -la Dockerfile

# If not in root, navigate there
cd ~/sem-gcp-agents
ls -la Dockerfile
```

### Dockerfile in Wrong Location

```bash
# Build from correct directory
cd ~/sem-gcp-agents
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
```

---

## Error: "denied: Permission denied"

### Service Account Permissions

```bash
# Get Cloud Build service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/run.admin"
```

---

## Error: "source does not exist"

### Build Context Issue

```bash
# Make sure you're in the project root
cd ~/sem-gcp-agents
pwd
# Should output: /home/YOUR_USERNAME/sem-gcp-agents

# List files to verify structure
ls -la
# Should see: Dockerfile, src/, terraform/, etc.

# Submit build from this directory
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
```

---

## Complete Build & Deploy Workflow

### Step 1: Set Environment Variables

```bash
# Get your project ID
gcloud config get-value project

# Set variables
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"

# Verify
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
```

### Step 2: Navigate to Project Root

```bash
cd ~/sem-gcp-agents
```

### Step 3: Enable Required APIs

```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    run.googleapis.com
```

### Step 4: Build Container

```bash
# Submit to Cloud Build
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0

# This will take 5-10 minutes
# You'll see build logs in real-time
```

### Step 5: Deploy to Cloud Run

```bash
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 \
    --platform managed \
    --region $REGION \
    --service-account sem-agents@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars "PROJECT_ID=$PROJECT_ID,DRY_RUN=true,PORTKEY_ENABLE_CACHE=true" \
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

# Type 'y' when prompted to allow unauthenticated
```

### Step 6: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe sem-agents --region=$REGION --format='value(status.url)')
echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health

# Expected: {"status": "ok", "version": "1.0.0"}
```

---

## Troubleshooting Build Issues

### Check Build Logs

```bash
# List recent builds
gcloud builds list --limit=5

# Get specific build logs
gcloud builds log BUILD_ID

# Or view in browser
echo "https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
```

### Check Image in Container Registry

```bash
# List images
gcloud container images list --repository=gcr.io/$PROJECT_ID

# List tags for specific image
gcloud container images list-tags gcr.io/$PROJECT_ID/sem-gcp-agents
```

### Check Disk Space in Cloud Shell

```bash
# Check available space
df -h ~

# If low, clean up
docker system prune -a
rm -rf ~/.cache
```

---

## Alternative: Build Locally (Not Recommended)

If Cloud Build continues to fail, you can build locally in Cloud Shell:

```bash
# Authenticate Docker
gcloud auth configure-docker

# Build image
docker build -t gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 .

# Push to GCR
docker push gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
```

**Warning:** Cloud Shell has limited resources (2GB RAM). Large builds may fail. Use Cloud Build instead.

---

## Common Build Warnings (Safe to Ignore)

### "Some files were not included in the source upload"

```
Some files were not included in the source upload.
Check the gcloud log [/tmp/xxx.log] to see which files...
```

**This is normal.** Files in `.gcloudignore` are excluded (like `.git/`, `__pycache__/`, etc.).

### "already have image (with digest)"

```
Already have image (with digest): gcr.io/cloud-builders/docker
```

**This is normal.** Cloud Build is using cached builder images.

---

## Quick Reference Commands

```bash
# Set environment
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"

# Build
cd ~/sem-gcp-agents
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0

# Deploy
gcloud run deploy sem-agents \
    --image gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0 \
    --region $REGION \
    --platform managed

# Verify
SERVICE_URL=$(gcloud run services describe sem-agents --region=$REGION --format='value(status.url)')
curl $SERVICE_URL/health
```

---

**Last Updated**: 2026-04-16
