variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
}

variable "image" {
  description = "Docker image URL"
  type        = string
}

variable "service_account" {
  description = "Service account email"
  type        = string
}

variable "env_vars" {
  description = "Environment variables"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Map of secret names"
  type        = map(string)
  default     = {}
}
