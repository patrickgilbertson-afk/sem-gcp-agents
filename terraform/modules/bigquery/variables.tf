variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "dataset_id" {
  description = "BigQuery dataset ID for agent data"
  type        = string
}

variable "dataset_raw" {
  description = "BigQuery dataset ID for raw Google Ads data"
  type        = string
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}
