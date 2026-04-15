resource "google_cloud_run_v2_service" "agent_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  template {
    service_account = var.service_account

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      # Environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secrets from Secret Manager
      dynamic "env" {
        for_each = var.secrets
        content {
          name = upper(replace(env.key, "-", "_"))
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      ports {
        container_port = 8080
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    timeout = "300s"

    max_instance_request_concurrency = 1
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access (protected by Slack signing secret)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.agent_service.name
  location = google_cloud_run_v2_service.agent_service.location
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}
