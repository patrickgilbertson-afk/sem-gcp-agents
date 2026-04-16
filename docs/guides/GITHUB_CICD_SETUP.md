# GitHub CI/CD Setup for Cloud Run

## Overview

Automatically build and deploy to Cloud Run whenever you push to GitHub. No need to manually run `gcloud builds submit` or `deploy_cloud_run.sh`.

---

## Setup Methods

### Method 1: Cloud Run Direct GitHub Integration (Easiest)

This is the simplest approach - Cloud Run handles everything.

#### Steps

1. **Navigate to Cloud Run in GCP Console**
   ```
   https://console.cloud.google.com/run?project=YOUR_PROJECT_ID
   ```

2. **Create/Update Service with GitHub Source**
   - Click "Create Service" or select existing `sem-agents` service
   - Choose "Continuously deploy new revisions from a source repository"
   - Click "Set up with Cloud Build"

3. **Connect GitHub Repository**
   - Click "Manage Connected Repositories"
   - Authenticate with GitHub (first time only)
   - Select your repository (e.g., `your-username/SEM-GCP-Agents`)
   - Click "Next"

4. **Configure Build**
   - **Branch**: `main` (or your default branch)
   - **Build Type**: Dockerfile
   - **Dockerfile path**: `/Dockerfile`
   - **Build context**: `/` (root directory)
   - Click "Save"

5. **Configure Service Settings**
   - Keep all your existing settings (memory, CPU, env vars, secrets)
   - Click "Deploy"

6. **Done!**
   - Every push to `main` branch will trigger automatic build and deploy
   - View builds at: https://console.cloud.google.com/cloud-build/builds

---

### Method 2: Cloud Build Trigger (More Control)

Use this if you want custom build steps, environment-specific deploys, or more control.

#### 1. Create Cloud Build Trigger

```bash
# Set variables
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"
export GITHUB_REPO_OWNER="your-github-username"
export GITHUB_REPO_NAME="SEM-GCP-Agents"

# Connect GitHub repository (first time only)
# This will open browser to authorize GitHub
gcloud builds repositories create github_sem-agents \
    --project=$PROJECT_ID \
    --connection=github-connection \
    --remote-uri=https://github.com/${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}.git
```

#### 2. Create cloudbuild.yaml

This file defines the build and deploy steps.

```yaml
# cloudbuild.yaml
steps:
  # Step 1: Build the Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'
      - '.'

  # Step 2: Push the image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'

  # Step 3: Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'sem-agents'
      - '--image=gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'
      - '--region=$_REGION'
      - '--platform=managed'

substitutions:
  _REGION: us-central1

images:
  - 'gcr.io/$PROJECT_ID/sem-gcp-agents:$COMMIT_SHA'
  - 'gcr.io/$PROJECT_ID/sem-gcp-agents:latest'

timeout: 1200s

options:
  machineType: 'E2_HIGHCPU_8'
```

#### 3. Create the Trigger

```bash
gcloud builds triggers create github \
    --name="sem-agents-deploy" \
    --repo-name=$GITHUB_REPO_NAME \
    --repo-owner=$GITHUB_REPO_OWNER \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml \
    --include-logs-with-status
```

---

### Method 3: GitHub Actions (Alternative)

Use GitHub Actions instead of Cloud Build.

#### 1. Create Service Account Key

```bash
# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions CI/CD"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Create key
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com
```

#### 2. Add GitHub Secrets

In your GitHub repository:
- Go to Settings → Secrets and variables → Actions
- Add these secrets:
  - `GCP_PROJECT_ID`: Your project ID
  - `GCP_SA_KEY`: Contents of `github-actions-key.json`

#### 3. Create Workflow File

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud Run

on:
  push:
    branches:
      - main

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  SERVICE_NAME: sem-agents

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}

      - name: Configure Docker
        run: gcloud auth configure-docker

      - name: Build image
        run: |
          docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME:$GITHUB_SHA \
                       -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .

      - name: Push image
        run: |
          docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:$GITHUB_SHA
          docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy $SERVICE_NAME \
            --image gcr.io/$PROJECT_ID/$SERVICE_NAME:$GITHUB_SHA \
            --region $REGION \
            --platform managed
```

---

## Comparison

| Feature | Cloud Run Direct | Cloud Build Trigger | GitHub Actions |
|---------|-----------------|---------------------|----------------|
| **Setup Complexity** | Easy (UI only) | Medium (CLI + YAML) | Medium (YAML + secrets) |
| **Customization** | Limited | High | High |
| **Build Minutes** | Included in Cloud Build | Included in Cloud Build | GitHub free tier (2000 min/month) |
| **Logs Location** | Cloud Build console | Cloud Build console | GitHub Actions tab |
| **Multi-environment** | One service only | Easy with multiple triggers | Easy with workflow_dispatch |
| **Rollback** | Cloud Run revisions | Cloud Run revisions | Cloud Run revisions |

---

## Recommended Approach

**Use Method 1 (Cloud Run Direct GitHub Integration)** if:
- ✅ Simple project with single environment
- ✅ Standard Docker build is sufficient
- ✅ You want the easiest setup

**Use Method 2 (Cloud Build Trigger)** if:
- ✅ You need custom build steps (tests, linting, etc.)
- ✅ You want to deploy to multiple environments (dev, staging, prod)
- ✅ You prefer GCP-native tooling

**Use Method 3 (GitHub Actions)** if:
- ✅ You already use GitHub Actions for other projects
- ✅ You want to run tests/checks before deploying
- ✅ You want build logs visible in GitHub

---

## Current vs New Workflow

### Current (Manual)
```bash
# Every time you make changes:
cd ~/SEM-GCP-Agents
git pull origin main
gcloud builds submit --tag gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0
./scripts/deploy_cloud_run.sh
```

### After Setup (Automatic)
```bash
# On your local machine:
git add .
git commit -m "Update campaign health thresholds"
git push origin main

# That's it! Build and deploy happen automatically
# Check status in Cloud Build console
```

---

## Configuration Files Location

All three methods preserve your environment variables and secrets:
- Environment variables are stored in Cloud Run service configuration
- Secrets are mounted from Secret Manager
- These persist across deployments (you don't need to set them in CI/CD)

---

## Testing the Setup

After configuring, test by making a small change:

1. **Make a trivial change**
   ```bash
   # Edit README or add a comment
   echo "# Test deployment" >> README.md
   git add README.md
   git commit -m "Test automatic deployment"
   git push origin main
   ```

2. **Watch the build**
   - Method 1/2: https://console.cloud.google.com/cloud-build/builds
   - Method 3: GitHub Actions tab in your repository

3. **Verify deployment**
   ```bash
   SERVICE_URL=$(gcloud run services describe sem-agents --region=$REGION --format='value(status.url)')
   curl $SERVICE_URL/health
   ```

---

## Troubleshooting

### Build fails with "permission denied"

```bash
# Grant Cloud Build service account necessary roles
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding \
    sem-agents@${PROJECT_ID}.iam.gserviceaccount.com \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/iam.serviceAccountUser"
```

### Deploy succeeds but service is unhealthy

Environment variables and secrets are preserved from your initial deployment. If the service fails to start:
- Check Cloud Run logs: `gcloud run services logs read sem-agents --region=$REGION`
- Verify secrets are accessible: `gcloud secrets versions access latest --secret=portkey-api-key`

---

## Next Steps

1. Choose a method (recommend Method 1 for simplicity)
2. Set up the integration
3. Test with a small commit
4. Update your team's workflow documentation
5. Remove manual deployment scripts (or keep for emergency use)

---

**Last Updated**: 2026-04-16
