#!/bin/bash

# Run the application locally with proper environment setup

echo "Starting SEM GCP Agents locally..."

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Set dry run mode for local testing
export DRY_RUN=true
export ENVIRONMENT=development

# Run with uvicorn
uvicorn src.main:app --reload --port 8080 --log-level info
