output "service_url" {
  description = "URL of the Cloud Run service"
  value       = module.cloud_run.service_url
}

output "service_account_email" {
  description = "Service account email"
  value       = module.iam.service_account_email
}

output "bigquery_dataset" {
  description = "BigQuery agent dataset ID"
  value       = module.bigquery.dataset_id
}

output "pubsub_topics" {
  description = "Created Pub/Sub topics"
  value       = module.pubsub.topic_names
}
