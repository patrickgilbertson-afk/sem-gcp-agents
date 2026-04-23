#!/bin/bash
# Test Slack integration for SEM GCP Agents

set -e

echo "================================================"
echo "Slack Integration - Quick Test"
echo "================================================"
echo ""

PROJECT_ID="marketing-bigquery-490714"
SERVICE_URL="https://sem-gcp-agents-ivxfiybalq-uc.a.run.app"

echo "Current Configuration:"
echo "  Channel ID: C0AC1TGCZA6"
echo "  Service URL: $SERVICE_URL"
echo ""

# Test 1: Check if Slack event endpoint is accessible
echo "Test 1: Checking Slack events endpoint..."
HEALTH_RESPONSE=$(curl -s "$SERVICE_URL/health" 2>&1)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "  ✓ Service is healthy"
else
    echo "  ✗ Service health check failed"
fi
echo ""

# Test 2: Check current secret values (just metadata, not actual values)
echo "Test 2: Checking Slack secrets..."
BOT_TOKEN_VERSION=$(gcloud secrets versions list slack-bot-token --limit=1 --format="value(name)" 2>&1 | grep -v InsecureRequestWarning)
SIGNING_SECRET_VERSION=$(gcloud secrets versions list slack-signing-secret --limit=1 --format="value(name)" 2>&1 | grep -v InsecureRequestWarning)

if [ -n "$BOT_TOKEN_VERSION" ]; then
    echo "  ✓ slack-bot-token: version $BOT_TOKEN_VERSION exists"
else
    echo "  ✗ slack-bot-token: no versions found"
fi

if [ -n "$SIGNING_SECRET_VERSION" ]; then
    echo "  ✓ slack-signing-secret: version $SIGNING_SECRET_VERSION exists"
else
    echo "  ✗ slack-signing-secret: no versions found"
fi
echo ""

# Test 3: Check if Cloud Run has environment variables
echo "Test 3: Checking Cloud Run environment..."
ENV_CHECK=$(gcloud run services describe sem-gcp-agents --region=us-central1 --format="value(spec.template.spec.containers[0].env)" 2>&1 | grep -v InsecureRequestWarning)

if echo "$ENV_CHECK" | grep -q "SLACK_APPROVAL_CHANNEL_ID"; then
    echo "  ✓ SLACK_APPROVAL_CHANNEL_ID is set"
else
    echo "  ✗ SLACK_APPROVAL_CHANNEL_ID is not set"
fi

if echo "$ENV_CHECK" | grep -q "SLACK_BOT_TOKEN"; then
    echo "  ✓ SLACK_BOT_TOKEN secret reference configured"
else
    echo "  ✗ SLACK_BOT_TOKEN secret reference not found"
fi

if echo "$ENV_CHECK" | grep -q "SLACK_SIGNING_SECRET"; then
    echo "  ✓ SLACK_SIGNING_SECRET secret reference configured"
else
    echo "  ✗ SLACK_SIGNING_SECRET secret reference not found"
fi
echo ""

echo "================================================"
echo "Next Steps:"
echo "================================================"
echo ""
echo "If secrets need to be updated with real Slack credentials:"
echo ""
echo "1. Create/update Slack app at: https://api.slack.com/apps"
echo ""
echo "2. Update slack-bot-token secret:"
echo "   echo -n 'xoxb-YOUR-BOT-TOKEN' | gcloud secrets versions add slack-bot-token --data-file=-"
echo ""
echo "3. Update slack-signing-secret secret:"
echo "   echo -n 'YOUR-SIGNING-SECRET' | gcloud secrets versions add slack-signing-secret --data-file=-"
echo ""
echo "4. Restart Cloud Run service:"
echo "   gcloud run services update sem-gcp-agents --region=us-central1"
echo ""
echo "5. Test by triggering an agent run and checking Slack channel"
echo ""
