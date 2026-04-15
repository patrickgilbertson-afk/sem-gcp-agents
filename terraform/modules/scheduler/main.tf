resource "google_cloud_scheduler_job" "agent_jobs" {
  for_each = var.schedules

  name      = each.key
  project   = var.project_id
  region    = var.region
  schedule  = each.value.schedule
  time_zone = each.value.time_zone

  http_target {
    uri         = "${var.cloud_run_url}/api/v1/orchestrator/run"
    http_method = "POST"

    body = base64encode(jsonencode({
      agent_type = each.value.agent_type
      context    = {}
    }))

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = var.service_account
      audience              = var.cloud_run_url
    }
  }

  retry_config {
    retry_count = 3
  }
}
