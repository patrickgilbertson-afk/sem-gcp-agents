variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "dataset_agents" {
  description = "BigQuery dataset ID for agent data"
  type        = string
}

variable "dataset_raw" {
  description = "BigQuery dataset ID for raw data"
  type        = string
}
