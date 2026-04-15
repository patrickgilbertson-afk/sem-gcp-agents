terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery datasets and tables
module "bigquery" {
  source = "./modules/bigquery"

  project_id    = var.project_id
  dataset_id    = var.dataset_agents
  dataset_raw   = var.dataset_raw
  location      = var.region
}

# Secrets in Secret Manager
module "secrets" {
  source = "./modules/secrets"

  project_id = var.project_id
  secrets    = var.secrets
}

# Pub/Sub topics and subscriptions
module "pubsub" {
  source = "./modules/pubsub"

  project_id = var.project_id
  topics     = var.pubsub_topics
}

# IAM service accounts and roles
module "iam" {
  source = "./modules/iam"

  project_id     = var.project_id
  dataset_agents = var.dataset_agents
  dataset_raw    = var.dataset_raw
}

# Cloud Run service
module "cloud_run" {
  source = "./modules/cloud_run"

  project_id           = var.project_id
  region               = var.region
  service_name         = var.service_name
  image                = var.cloud_run_image
  service_account      = module.iam.service_account_email
  env_vars             = var.env_vars
  secrets              = module.secrets.secret_ids

  depends_on = [
    module.bigquery,
    module.secrets,
    module.pubsub,
    module.iam
  ]
}

# Cloud Scheduler jobs
module "scheduler" {
  source = "./modules/scheduler"

  project_id        = var.project_id
  region            = var.region
  cloud_run_url     = module.cloud_run.service_url
  service_account   = module.iam.service_account_email
  schedules         = var.scheduler_jobs

  depends_on = [module.cloud_run]
}
