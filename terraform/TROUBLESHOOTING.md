# Terraform Troubleshooting Guide

## Common Errors and Solutions

### Error: "Value for undeclared variable"

**Full Error:**
```
Warning: Value for undeclared variable

The root module does not declare a variable named "google_ads_customer_id" but a value was found in file "terraform.tfvars".
```

**Cause:** Variable used in `terraform.tfvars` but not declared in `variables.tf`

**Solution:**
```bash
# This has been fixed! Update your repository:
git pull origin main

# The variables.tf file now includes all required variable declarations
```

---

### Error: "expected a non-empty string"

**Full Error:**
```
Error: expected a non-empty string

  with provider["registry.terraform.io/hashicorp/google"],
  on main.tf line 13, in provider "google":
  13:   project = var.project_id

project was set to ``
```

**Cause:** Required variable `project_id` is not set in `terraform.tfvars`

**Solution:**

1. **Create terraform.tfvars from example:**
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit terraform.tfvars with your values:**
   ```bash
   # Use Cloud Shell Editor
   cloudshell edit terraform.tfvars

   # Or use nano
   nano terraform.tfvars
   ```

3. **Set required variables:**
   ```hcl
   # Minimal required configuration
   project_id                = "your-actual-project-id"
   region                    = "us-central1"
   google_ads_customer_id    = "1234567890"
   slack_approval_channel_id = "C01234567"
   dry_run_mode              = true
   ```

4. **Verify your project ID:**
   ```bash
   # Get your current project
   gcloud config get-value project

   # Or list all projects
   gcloud projects list
   ```

---

### Error: "terraform: command not found"

**Solution for Cloud Shell:**
```bash
# Terraform should be pre-installed in Cloud Shell
terraform version

# If missing, install manually:
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
unzip terraform_1.6.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/
terraform version
```

**Solution for Local:**
```bash
# macOS (Homebrew)
brew install terraform

# Linux (apt)
sudo apt-get update && sudo apt-get install terraform

# Windows (Chocolatey)
choco install terraform

# Or download from: https://www.terraform.io/downloads
```

---

### Error: "No valid credential sources found"

**Full Error:**
```
Error: google: could not find default credentials
```

**Solution for Cloud Shell:**
```bash
# Cloud Shell is pre-authenticated - ensure you've set the project
gcloud config set project YOUR_PROJECT_ID
gcloud config list
```

**Solution for Local:**
```bash
# Authenticate with GCP
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

---

### Error: "API has not been used in project"

**Full Error:**
```
Error: Error creating Service: googleapi: Error 403: Cloud Run API has not been used in project PROJECT_ID before or it is disabled.
```

**Solution:**
```bash
# Enable required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    bigquery.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    pubsub.googleapis.com

# Verify enabled
gcloud services list --enabled
```

---

### Error: "Error acquiring the state lock"

**Full Error:**
```
Error: Error acquiring the state lock

Lock Info:
  ID:        abc123...
  Path:      default.tfstate
  Operation: OperationTypePlan
```

**Cause:** Another terraform process is running or crashed

**Solution:**
```bash
# Wait a few minutes for other process to finish
# OR force unlock (use with caution!)

terraform force-unlock abc123...

# Replace abc123... with the actual Lock ID from the error
```

---

### Error: "Module not installed"

**Full Error:**
```
Error: Module not installed

  on main.tf line 20:
  20: module "bigquery" {

This module is not yet installed. Run "terraform init" to install all modules required by this configuration.
```

**Solution:**
```bash
cd terraform
terraform init
```

---

### Error: "Provider registry.terraform.io/hashicorp/google"

**Full Error:**
```
Error: Failed to query available provider packages

Could not retrieve the list of available versions for provider hashicorp/google
```

**Solution:**
```bash
# Re-initialize Terraform
cd terraform
rm -rf .terraform .terraform.lock.hcl
terraform init
```

---

## Step-by-Step Terraform Deployment

### 1. Verify Prerequisites

```bash
# Check you're in the right directory
pwd
# Should output: .../sem-gcp-agents/terraform

# Verify project is set
gcloud config get-value project

# Check terraform is installed
terraform version
```

### 2. Create terraform.tfvars

```bash
# Copy example
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
cloudshell edit terraform.tfvars

# Minimal required configuration:
cat > terraform.tfvars <<EOF
project_id                = "$(gcloud config get-value project)"
region                    = "us-central1"
google_ads_customer_id    = "1234567890"  # CHANGE THIS
slack_approval_channel_id = "C01234567"   # CHANGE THIS
dry_run_mode              = true
EOF
```

### 3. Initialize Terraform

```bash
terraform init

# Expected output:
# Initializing modules...
# Initializing provider plugins...
# Terraform has been successfully initialized!
```

### 4. Validate Configuration

```bash
# Check for syntax errors
terraform validate

# Expected output:
# Success! The configuration is valid.
```

### 5. Preview Changes

```bash
# See what will be created
terraform plan

# Save plan to file
terraform plan -out=tfplan
```

### 6. Review Plan Output

Look for:
- ✅ Resources to be created (green `+`)
- ⚠️ Resources to be changed (yellow `~`)
- ❌ Resources to be destroyed (red `-`)

### 7. Apply Configuration

```bash
# Apply the saved plan
terraform apply tfplan

# OR apply with confirmation
terraform apply

# Type 'yes' when prompted
```

### 8. Verify Deployment

```bash
# Check terraform outputs
terraform output

# Verify resources in GCP
gcloud run services list
bq ls
gcloud secrets list
```

---

## Quick Fixes

### Reset Terraform State

```bash
cd terraform

# DANGER: This deletes all state (use only if corrupted)
rm -rf .terraform .terraform.lock.hcl terraform.tfstate*

# Re-initialize
terraform init
```

### Import Existing Resources

If resources already exist:

```bash
# Import BigQuery dataset
terraform import google_bigquery_dataset.sem_agents PROJECT_ID:sem_agents

# Import Cloud Run service
terraform import google_cloud_run_service.sem_agents REGION/sem-gcp-agents

# Import secret
terraform import google_secret_manager_secret.portkey_api_key projects/PROJECT_ID/secrets/portkey-api-key
```

### Check State

```bash
# List all resources in state
terraform state list

# Show specific resource
terraform state show google_cloud_run_service.sem_agents
```

---

## Environment-Specific Configurations

### Development

```hcl
# terraform.tfvars
project_id   = "sem-agents-dev"
environment  = "development"
dry_run_mode = true
log_level    = "DEBUG"
```

### Staging

```hcl
# terraform.tfvars
project_id   = "sem-agents-staging"
environment  = "staging"
dry_run_mode = true
log_level    = "INFO"
```

### Production

```hcl
# terraform.tfvars
project_id   = "sem-agents-prod"
environment  = "production"
dry_run_mode = false  # Apply changes
log_level    = "WARNING"
```

---

## Variable Precedence

Terraform loads variables in this order (later overwrites earlier):

1. Environment variables (`TF_VAR_project_id`)
2. `terraform.tfvars` file
3. `*.auto.tfvars` files
4. `-var` command line flags
5. Variable defaults in `variables.tf`

---

## Getting Help

### Check Terraform Logs

```bash
# Enable detailed logging
export TF_LOG=DEBUG
terraform plan

# Disable logging
unset TF_LOG
```

### Validate Variables

```bash
# Show all variables and their values
terraform console
> var.project_id
> var.region
> exit
```

### Format Configuration

```bash
# Auto-format all .tf files
terraform fmt -recursive
```

---

## Resources

- [Terraform Documentation](https://www.terraform.io/docs)
- [Google Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Shell Setup Guide](../docs/guides/CLOUD_SHELL_SETUP.md)
- [Deployment Guide](../docs/guides/DEPLOYMENT_GUIDE.md)

---

**Last Updated**: 2026-04-15
