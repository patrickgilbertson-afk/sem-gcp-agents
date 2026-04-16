#!/bin/bash
# Deploy SEM GCP Agents to Cloud Run
# Run from project root: ./scripts/deploy_cloud_run.sh

set -e

# Check required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set"
    echo "Run: export PROJECT_ID=\"\$(gcloud config get-value project)\""
    exit 1
fi

if [ -z "$REGION" ]; then
    echo "Error: REGION not set"
    echo "Run: export REGION=\"us-central1\""
    exit 1
fi

# Configuration
IMAGE="gcr.io/$PROJECT_ID/sem-gcp-agents:v1.0.0"
SERVICE_NAME="sem-agents"
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

# Google Ads configuration (update these!)
GOOGLE_ADS_CUSTOMER_ID="${GOOGLE_ADS_CUSTOMER_ID:-1234567890}"  # TODO: Update
GOOGLE_ADS_LOGIN_CUSTOMER_ID="${GOOGLE_ADS_LOGIN_CUSTOMER_ID:-$GOOGLE_ADS_CUSTOMER_ID}"

# Slack configuration (update this!)
SLACK_CHANNEL_ID="${SLACK_CHANNEL_ID:-C01234567}"  # TODO: Update

echo "========================================"
echo "Deploying SEM GCP Agents to Cloud Run"
echo "========================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Image: $IMAGE"
echo "Service Account: $SERVICE_ACCOUNT"
echo ""

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE \
    --platform managed \
    --region $REGION \
    --service-account $SERVICE_ACCOUNT \
    --timeout 900 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --port 8080 \
    --allow-unauthenticated \
    --set-env-vars "\
GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION,\
GCP_SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT,\
GOOGLE_ADS_CUSTOMER_ID=$GOOGLE_ADS_CUSTOMER_ID,\
GOOGLE_ADS_LOGIN_CUSTOMER_ID=$GOOGLE_ADS_LOGIN_CUSTOMER_ID,\
SLACK_APPROVAL_CHANNEL_ID=$SLACK_CHANNEL_ID,\
BQ_DATASET_RAW=sem_ads_raw,\
BQ_DATASET_AGENTS=sem_agents,\
ENVIRONMENT=development,\
DRY_RUN=true,\
KILL_SWITCH_ENABLED=false,\
LOG_LEVEL=INFO,\
PORTKEY_ENABLE_CACHE=true,\
PORTKEY_CACHE_TTL=3600" \
    --set-secrets "\
GOOGLE_ADS_DEVELOPER_TOKEN=google-ads-developer-token:latest,\
GOOGLE_ADS_CLIENT_ID=google-ads-client-id:latest,\
GOOGLE_ADS_CLIENT_SECRET=google-ads-client-secret:latest,\
GOOGLE_ADS_REFRESH_TOKEN=google-ads-refresh-token:latest,\
SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
PORTKEY_API_KEY=portkey-api-key:latest,\
PORTKEY_VIRTUAL_KEY_ANTHROPIC=portkey-virtual-key-anthropic:latest,\
PORTKEY_VIRTUAL_KEY_GOOGLE=portkey-virtual-key-google:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test endpoints:"
echo "  Health: curl $SERVICE_URL/health"
echo "  Root: curl $SERVICE_URL/"
echo ""
echo "View logs:"
echo "  gcloud run services logs tail $SERVICE_NAME --region=$REGION"
