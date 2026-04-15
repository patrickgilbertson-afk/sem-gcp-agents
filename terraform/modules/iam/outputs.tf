output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.agent.email
}

output "service_account_id" {
  description = "Service account ID"
  value       = google_service_account.agent.id
}
