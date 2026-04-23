#!/bin/bash
# Setup Cloud Scheduler jobs for SEM GCP Agents

set -e

PROJECT_ID="marketing-bigquery-490714"
REGION="us-central1"
SERVICE_URL="https://sem-gcp-agents-ivxfiybalq-uc.a.run.app"
SERVICE_ACCOUNT="sa-sem-agents@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================"
echo "Setting up Cloud Scheduler Jobs"
echo "================================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service URL: $SERVICE_URL"
echo "Service Account: $SERVICE_ACCOUNT"
echo ""

# =============================================================================
# 1. Campaign Health Agent - Daily at 7 AM ET
# =============================================================================
echo "Creating: campaign-health-daily"
echo "  Schedule: Daily at 7 AM Eastern Time"
echo "  Agent: campaign_health"
echo ""

gcloud scheduler jobs create http campaign-health-daily \
  --location=$REGION \
  --schedule="0 7 * * *" \
  --time-zone="America/New_York" \
  --uri="${SERVICE_URL}/api/v1/orchestrator/run" \
  --http-method=POST \
  --message-body='{"agent_type":"campaign_health","context":{}}' \
  --headers="Content-Type=application/json" \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience=$SERVICE_URL \
  --attempt-deadline=600s \
  --max-retry-attempts=3 \
  --max-doublings=3 \
  --description="Run Campaign Health Agent daily at 7 AM ET" \
  2>&1 | grep -v InsecureRequestWarning || echo "  Job may already exist"

echo ""

# =============================================================================
# 2. Quality Score Agent - Daily at 9 AM ET (TODO - Phase 2.5)
# =============================================================================
# Commented out until Quality Score Agent is implemented
# echo "Creating: quality-score-daily"
# echo "  Schedule: Daily at 9 AM Eastern Time"
# echo "  Agent: quality_score"
# echo ""
#
# gcloud scheduler jobs create http quality-score-daily \
#   --location=$REGION \
#   --schedule="0 9 * * *" \
#   --time-zone="America/New_York" \
#   --uri="${SERVICE_URL}/api/v1/orchestrator/run" \
#   --http-method=POST \
#   --message-body='{"agent_type":"quality_score","context":{}}' \
#   --headers="Content-Type=application/json" \
#   --oidc-service-account-email=$SERVICE_ACCOUNT \
#   --oidc-token-audience=$SERVICE_URL \
#   --attempt-deadline=600s \
#   --max-retry-attempts=3 \
#   --description="Run Quality Score Agent daily at 9 AM ET" \
#   2>&1 | grep -v InsecureRequestWarning || echo "  Job may already exist"

# =============================================================================
# 3. Keyword Agent - Daily at 8 AM ET (TODO - Phase 3)
# =============================================================================
# Commented out until Keyword Agent is implemented
# echo "Creating: keyword-daily"
# echo "  Schedule: Daily at 8 AM Eastern Time"
# echo "  Agent: keyword"
# echo ""
#
# gcloud scheduler jobs create http keyword-daily \
#   --location=$REGION \
#   --schedule="0 8 * * *" \
#   --time-zone="America/New_York" \
#   --uri="${SERVICE_URL}/api/v1/orchestrator/run" \
#   --http-method=POST \
#   --message-body='{"agent_type":"keyword","context":{}}' \
#   --headers="Content-Type=application/json" \
#   --oidc-service-account-email=$SERVICE_ACCOUNT \
#   --oidc-token-audience=$SERVICE_URL \
#   --attempt-deadline=600s \
#   --max-retry-attempts=3 \
#   --description="Run Keyword Agent daily at 8 AM ET" \
#   2>&1 | grep -v InsecureRequestWarning || echo "  Job may already exist"

# =============================================================================
# 4. Bid Modifier Agent - Weekly Monday 9 AM ET (TODO - Phase 5)
# =============================================================================
# Commented out until Bid Modifier Agent is implemented
# echo "Creating: bid-modifier-weekly"
# echo "  Schedule: Monday at 9 AM Eastern Time"
# echo "  Agent: bid_modifier"
# echo ""
#
# gcloud scheduler jobs create http bid-modifier-weekly \
#   --location=$REGION \
#   --schedule="0 9 * * 1" \
#   --time-zone="America/New_York" \
#   --uri="${SERVICE_URL}/api/v1/orchestrator/run" \
#   --http-method=POST \
#   --message-body='{"agent_type":"bid_modifier","context":{}}' \
#   --headers="Content-Type=application/json" \
#   --oidc-service-account-email=$SERVICE_ACCOUNT \
#   --oidc-token-audience=$SERVICE_URL \
#   --attempt-deadline=600s \
#   --max-retry-attempts=3 \
#   --description="Run Bid Modifier Agent weekly on Monday at 9 AM ET" \
#   2>&1 | grep -v InsecureRequestWarning || echo "  Job may already exist"

echo ""
echo "================================================"
echo "Summary"
echo "================================================"
echo ""
echo "Created scheduler jobs:"
gcloud scheduler jobs list --location=$REGION --format="table(name,schedule,state,httpTarget.uri)" 2>&1 | grep -v InsecureRequestWarning | grep -E "(NAME|campaign-health|quality-score|keyword|bid-modifier)"

echo ""
echo "================================================"
echo "Next Steps"
echo "================================================"
echo ""
echo "1. Verify jobs were created:"
echo "   gcloud scheduler jobs list --location=$REGION"
echo ""
echo "2. Manually trigger a test run:"
echo "   gcloud scheduler jobs run campaign-health-daily --location=$REGION"
echo ""
echo "3. Check execution logs:"
echo "   gcloud run services logs read sem-gcp-agents --region=$REGION --limit=50"
echo ""
echo "4. Pause/resume jobs as needed:"
echo "   gcloud scheduler jobs pause campaign-health-daily --location=$REGION"
echo "   gcloud scheduler jobs resume campaign-health-daily --location=$REGION"
echo ""
