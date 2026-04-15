#!/bin/bash
set -e

# Deployment script for SEM GCP Agents

echo "=== SEM GCP Agents Deployment ==="

# Load configuration
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
REGION=${GCP_REGION:-us-central1}
SERVICE_NAME="sem-gcp-agents"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"

# Build Docker image
echo ""
echo "Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

# Push to Container Registry
echo ""
echo "Pushing image to GCR..."
docker push ${IMAGE_NAME}:latest

# Update Terraform with new image
echo ""
echo "Updating Terraform configuration..."
cd terraform
terraform init
terraform plan -var="cloud_run_image=${IMAGE_NAME}:latest"

read -p "Apply Terraform changes? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    terraform apply -var="cloud_run_image=${IMAGE_NAME}:latest"
fi

cd ..

echo ""
echo "=== Deployment Complete ==="
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')"
