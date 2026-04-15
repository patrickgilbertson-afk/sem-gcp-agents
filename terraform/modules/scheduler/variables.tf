variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "cloud_run_url" {
  description = "Cloud Run service URL"
  type        = string
}

variable "service_account" {
  description = "Service account email for authentication"
  type        = string
}

variable "schedules" {
  description = "Map of Cloud Scheduler jobs"
  type = map(object({
    schedule    = string
    time_zone   = string
    agent_type  = string
  }))
}
