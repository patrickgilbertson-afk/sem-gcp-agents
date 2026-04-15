output "secret_ids" {
  description = "Map of secret IDs"
  value       = { for k, v in google_secret_manager_secret.secrets : k => v.secret_id }
}

output "secret_names" {
  description = "Map of secret full names"
  value       = { for k, v in google_secret_manager_secret.secrets : k => v.id }
}
