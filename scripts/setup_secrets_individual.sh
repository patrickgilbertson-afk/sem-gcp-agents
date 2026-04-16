#!/bin/bash
# Setup individual secrets for SEM GCP Agents
# Use this if you prefer separate secrets instead of google-ads-credentials JSON

set -e

# Check PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set"
    echo "Run: export PROJECT_ID=\"\$(gcloud config get-value project)\""
    exit 1
fi

echo "========================================"
echo "Setting up secrets in Secret Manager"
echo "========================================"
echo "Project: $PROJECT_ID"
echo ""

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

# Prompt for values
read -p "Google Ads Developer Token: " GOOGLE_ADS_DEVELOPER_TOKEN
read -p "Google Ads Client ID: " GOOGLE_ADS_CLIENT_ID
read -p "Google Ads Client Secret: " GOOGLE_ADS_CLIENT_SECRET
read -p "Google Ads Refresh Token: " GOOGLE_ADS_REFRESH_TOKEN
read -p "Slack Bot Token (xoxb-...): " SLACK_BOT_TOKEN
read -p "Slack Signing Secret: " SLACK_SIGNING_SECRET
read -p "Portkey API Key (pk-...): " PORTKEY_API_KEY
read -p "Portkey Anthropic Virtual Key: " PORTKEY_VIRTUAL_KEY_ANTHROPIC
read -p "Portkey Google Virtual Key: " PORTKEY_VIRTUAL_KEY_GOOGLE

echo ""
echo "Creating/updating secrets..."

# Google Ads (individual secrets)
create_or_update_secret "google-ads-developer-token" "$GOOGLE_ADS_DEVELOPER_TOKEN"
create_or_update_secret "google-ads-client-id" "$GOOGLE_ADS_CLIENT_ID"
create_or_update_secret "google-ads-client-secret" "$GOOGLE_ADS_CLIENT_SECRET"
create_or_update_secret "google-ads-refresh-token" "$GOOGLE_ADS_REFRESH_TOKEN"

# Slack
create_or_update_secret "slack-bot-token" "$SLACK_BOT_TOKEN"
create_or_update_secret "slack-signing-secret" "$SLACK_SIGNING_SECRET"

# Portkey (REQUIRED)
create_or_update_secret "portkey-api-key" "$PORTKEY_API_KEY"
create_or_update_secret "portkey-virtual-key-anthropic" "$PORTKEY_VIRTUAL_KEY_ANTHROPIC"
create_or_update_secret "portkey-virtual-key-google" "$PORTKEY_VIRTUAL_KEY_GOOGLE"

echo ""
echo "========================================"
echo "Granting access to Cloud Run service account"
echo "========================================"

SERVICE_ACCOUNT="sem-agents@$PROJECT_ID.iam.gserviceaccount.com"

for secret in google-ads-developer-token google-ads-client-id google-ads-client-secret google-ads-refresh-token slack-bot-token slack-signing-secret portkey-api-key portkey-virtual-key-anthropic portkey-virtual-key-google; do
    echo "Granting access to: $secret"
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        2>/dev/null || echo "  (already granted)"
done

echo ""
echo "========================================"
echo "All secrets created successfully!"
echo "========================================"
echo ""
echo "Verify:"
echo "  gcloud secrets list"
echo ""
echo "Next step:"
echo "  ./scripts/deploy_cloud_run.sh"
