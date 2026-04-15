# Service account for agents
resource "google_service_account" "agent" {
  account_id   = "sa-sem-agents"
  display_name = "SEM Agents Service Account"
  project      = var.project_id
  description  = "Service account for SEM agent operations"
}

# BigQuery permissions for agent dataset
resource "google_bigquery_dataset_iam_member" "agent_editor" {
  dataset_id = var.dataset_agents
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.agent.email}"
  project    = var.project_id
}

# BigQuery permissions for raw dataset (read-only)
resource "google_bigquery_dataset_iam_member" "raw_viewer" {
  dataset_id = var.dataset_raw
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.agent.email}"
  project    = var.project_id
}

# BigQuery job user (for running queries)
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Secret Manager accessor
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Pub/Sub publisher
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Pub/Sub subscriber
resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Cloud Run invoker (for Cloud Scheduler)
resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.agent.email}"
}
