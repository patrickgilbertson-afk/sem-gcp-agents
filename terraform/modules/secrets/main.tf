resource "google_secret_manager_secret" "secrets" {
  for_each = var.secrets

  secret_id = each.key
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    managed_by = "terraform"
  }
}

resource "google_secret_manager_secret_version" "secret_versions" {
  for_each = var.secrets

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value != "" ? each.value : "placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}
