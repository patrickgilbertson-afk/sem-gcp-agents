#!/bin/bash
# Update Cloud Run service with required environment variables and secrets
# Run from project root: ./scripts/update_cloud_run_config.sh

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

# Service configuration
SERVICE_NAME="sem-gcp-agents"
SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

# Prompt for missing values
if [ -z "$GOOGLE_ADS_CUSTOMER_ID" ]; then
    read -p "Google Ads Customer ID (no dashes): " GOOGLE_ADS_CUSTOMER_ID
fi

if [ -z "$SLACK_CHANNEL_ID" ]; then
    read -p "Slack Approval Channel ID (e.g., C01234567): " SLACK_CHANNEL_ID
fi

echo ""
echo "=========================================="
echo "Updating Cloud Run Service Configuration"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "Google Ads Customer ID: $GOOGLE_ADS_CUSTOMER_ID"
echo "Slack Channel ID: $SLACK_CHANNEL_ID"
echo ""

# Update service with environment variables and secrets
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --service-account=$SERVICE_ACCOUNT \
    --timeout=900 \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=0 \
    --max-instances=10 \
    --port=8080 \
    --update-env-vars "\
GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION,\
GCP_SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT,\
GOOGLE_ADS_CUSTOMER_ID=$GOOGLE_ADS_CUSTOMER_ID,\
GOOGLE_ADS_LOGIN_CUSTOMER_ID=$GOOGLE_ADS_CUSTOMER_ID,\
SLACK_APPROVAL_CHANNEL_ID=$SLACK_CHANNEL_ID,\
BQ_DATASET_RAW=sem_ads_raw,\
BQ_DATASET_AGENTS=sem_agents,\
ENVIRONMENT=development,\
DRY_RUN=true,\
KILL_SWITCH_ENABLED=false,\
LOG_LEVEL=INFO,\
PORTKEY_ENABLE_CACHE=true,\
PORTKEY_CACHE_TTL=3600" \
    --update-secrets "\
GOOGLE_ADS_DEVELOPER_TOKEN=google-ads-developer-token:latest,\
GOOGLE_ADS_CLIENT_ID=google-ads-client-id:latest,\
GOOGLE_ADS_CLIENT_SECRET=google-ads-client-secret:latest,\
GOOGLE_ADS_REFRESH_TOKEN=google-ads-refresh-token:latest,\
SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
PORTKEY_API_KEY=portkey-api-key:latest,\
PORTKEY_VIRTUAL_KEY_ANTHROPIC=portkey-virtual-key-anthropic:latest,\
PORTKEY_VIRTUAL_KEY_GOOGLE=portkey-virtual-key-google:latest"

echo ""
echo "=========================================="
echo "Configuration Update Complete!"
echo "=========================================="
echo ""
echo "The service will automatically redeploy with new configuration."
echo "This may take 1-2 minutes."
echo ""
echo "Check deployment status:"
echo "  gcloud run services describe $SERVICE_NAME --region=$REGION"
echo ""
echo "View logs:"
echo "  gcloud run services logs read $SERVICE_NAME --region=$REGION --limit=50"
echo ""
echo "Test service:"
echo "  SERVICE_URL=\$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
echo "  curl \$SERVICE_URL/health"
echo ""
