#!/bin/bash
# Quick deploy script to push the recommendations save fix

set -e

PROJECT_ID="marketing-bigquery-490714"
REGION="us-central1"
SERVICE_NAME="sem-gcp-agents"
IMAGE_NAME="us-central1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE_NAME}/${SERVICE_NAME}"

echo "================================================"
echo "Deploying Recommendations Save Fix"
echo "================================================"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo ""

# Build and submit to Cloud Build
echo "Step 1: Building container image..."
gcloud builds submit \
  --tag="${IMAGE_NAME}:latest" \
  --project=${PROJECT_ID} \
  . 2>&1 | grep -v InsecureRequestWarning

echo ""
echo "Step 2: Deploying to Cloud Run..."
gcloud run services update ${SERVICE_NAME} \
  --image="${IMAGE_NAME}:latest" \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  2>&1 | grep -v InsecureRequestWarning

echo ""
echo "================================================"
echo "Deployment Complete!"
echo "================================================"
echo ""
echo "Changes deployed:"
echo "  ✓ Recommendations now saved to BigQuery"
echo "  ✓ agent_recommendations table will be populated"
echo ""
echo "Next steps:"
echo "  1. Trigger a test run"
echo "  2. Check BigQuery for recommendations"
echo ""
