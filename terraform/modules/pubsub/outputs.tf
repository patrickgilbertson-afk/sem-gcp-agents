output "topic_names" {
  description = "Map of topic names"
  value       = { for k, v in google_pubsub_topic.topics : k => v.name }
}

output "subscription_names" {
  description = "Map of subscription names"
  value       = { for k, v in google_pubsub_subscription.subscriptions : k => v.name }
}
