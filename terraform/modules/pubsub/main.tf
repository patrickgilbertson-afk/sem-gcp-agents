resource "google_pubsub_topic" "topics" {
  for_each = toset(var.topics)

  name    = each.key
  project = var.project_id

  labels = {
    managed_by = "terraform"
  }
}

resource "google_pubsub_subscription" "subscriptions" {
  for_each = toset(var.topics)

  name    = "${each.key}-subscription"
  topic   = google_pubsub_topic.topics[each.key].id
  project = var.project_id

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = "2678400s" # 31 days
  }
}
