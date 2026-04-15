variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "topics" {
  description = "List of Pub/Sub topics to create"
  type        = list(string)
}
