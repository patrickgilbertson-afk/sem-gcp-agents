output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.agents.dataset_id
}

output "dataset_name" {
  description = "BigQuery dataset full name"
  value       = google_bigquery_dataset.agents.id
}
