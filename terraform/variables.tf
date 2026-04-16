variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "dataset_agents" {
  description = "BigQuery dataset for agent data"
  type        = string
  default     = "sem_agents"
}

variable "dataset_raw" {
  description = "BigQuery dataset for raw Google Ads data"
  type        = string
  default     = "sem_ads_raw"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "sem-gcp-agents"
}

variable "cloud_run_image" {
  description = "Docker image for Cloud Run"
  type        = string
  default     = "gcr.io/cloudrun/hello"  # Placeholder
}

variable "env_vars" {
  description = "Environment variables for Cloud Run"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Map of secrets to create"
  type        = map(string)
  default     = {
    "anthropic-api-key"           = ""
    "google-ads-developer-token"  = ""
    "google-ads-refresh-token"    = ""
    "google-ads-client-id"        = ""
    "google-ads-client-secret"    = ""
    "slack-bot-token"             = ""
    "slack-signing-secret"        = ""
    "google-ai-api-key"           = ""
  }
}

variable "pubsub_topics" {
  description = "List of Pub/Sub topics to create"
  type        = list(string)
  default     = [
    "agent-tasks",
    "agent-results",
    "approval-requests",
    "approval-responses",
    "audit-events"
  ]
}

variable "scheduler_jobs" {
  description = "Map of Cloud Scheduler jobs"
  type = map(object({
    schedule    = string
    time_zone   = string
    agent_type  = string
  }))
  default = {
    "campaign-health-daily" = {
      schedule    = "0 7 * * *"
      time_zone   = "America/New_York"
      agent_type  = "campaign_health"
    }
    "keyword-daily" = {
      schedule    = "0 8 * * *"
      time_zone   = "America/New_York"
      agent_type  = "keyword"
    }
    "bid-modifier-weekly" = {
      schedule    = "0 9 * * 1"
      time_zone   = "America/New_York"
      agent_type  = "bid_modifier"
    }
  }
}

# Google Ads Configuration
variable "google_ads_customer_id" {
  description = "Google Ads customer ID (without dashes)"
  type        = string
}

variable "google_ads_login_customer_id" {
  description = "Google Ads MCC/login customer ID (optional, for MCC accounts)"
  type        = string
  default     = ""
}

# Slack Configuration
variable "slack_approval_channel_id" {
  description = "Slack channel ID for approval requests (e.g., C01234567)"
  type        = string
}

# Application Settings
variable "dry_run_mode" {
  description = "Enable dry run mode (no changes applied)"
  type        = bool
  default     = true
}

variable "kill_switch_enabled" {
  description = "Enable kill switch (forces dry run)"
  type        = bool
  default     = false
}

variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"
}

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "development"
}
