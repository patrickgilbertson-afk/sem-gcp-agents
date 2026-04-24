# BigQuery dataset for agent data
resource "google_bigquery_dataset" "agents" {
  dataset_id  = var.dataset_id
  project     = var.project_id
  location    = var.location
  description = "SEM agent recommendations and audit logs"

  labels = {
    managed_by = "terraform"
    purpose    = "sem-agents"
  }
}

# Agent recommendations table
resource "google_bigquery_table" "agent_recommendations" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "agent_recommendations"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["agent_type", "status"]

  schema = jsonencode([
    {
      name = "id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "agent_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "created_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "title"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "description"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "rationale"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "impact_estimate"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "risk_level"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "action_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "action_params"
      type = "JSON"
      mode = "NULLABLE"
    },
    {
      name = "status"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "approval_status"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "approved_by"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "approved_at"
      type = "TIMESTAMP"
      mode = "NULLABLE"
    },
    {
      name = "applied_at"
      type = "TIMESTAMP"
      mode = "NULLABLE"
    },
    {
      name = "applied_result"
      type = "JSON"
      mode = "NULLABLE"
    },
    {
      name = "error_message"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "metadata"
      type = "JSON"
      mode = "NULLABLE"
    }
  ])
}

# Agent audit log table
resource "google_bigquery_table" "agent_audit_log" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "agent_audit_log"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["agent_type", "event_type"]

  schema = jsonencode([
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "agent_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "event_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "details"
      type = "JSON"
      mode = "NULLABLE"
    }
  ])
}

# Agent state tracking
resource "google_bigquery_table" "agent_state" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "agent_state"
  project    = var.project_id

  schema = jsonencode([
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "parent_run_id"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "agent_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "status"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "started_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "completed_at"
      type = "TIMESTAMP"
      mode = "NULLABLE"
    },
    {
      name = "error"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])
}

# Brand guidelines
resource "google_bigquery_table" "brand_guidelines" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "brand_guidelines"
  project    = var.project_id

  schema = jsonencode([
    {
      name = "customer_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "brand_voice"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "prohibited_terms"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "required_phrases"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "updated_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "updated_by"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])
}

# Agent config for thresholds
resource "google_bigquery_table" "agent_config" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "agent_config"
  project    = var.project_id

  schema = jsonencode([
    {
      name = "agent_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "config_key"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "config_value"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "description"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "updated_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    }
  ])
}

# Recommendation history for lifecycle tracking
resource "google_bigquery_table" "recommendation_history" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "recommendation_history"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["recommendation_id", "event_type"]

  schema = jsonencode([
    {
      name = "history_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "recommendation_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "event_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "event_timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "from_status"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "to_status"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "actor_type"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "actor_id"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "actor_name"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "event_details"
      type = "JSON"
      mode = "NULLABLE"
    }
  ])
}

# LLM API call tracking
resource "google_bigquery_table" "llm_calls" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "llm_calls"
  project    = var.project_id

  time_partitioning {
    type                 = "DAY"
    field                = "timestamp"
    expiration_ms        = 7776000000  # 90 days
  }

  clustering = ["provider", "model", "agent_type"]

  schema = jsonencode([
    {
      name = "call_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "agent_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "provider"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "model"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "prompt_tokens"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "completion_tokens"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "total_tokens"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "response_time_ms"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "cost_usd"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "error_code"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "error_message"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "portkey_request_id"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "cache_hit"
      type = "BOOL"
      mode = "NULLABLE"
    }
  ])
}

# Approval event tracking
resource "google_bigquery_table" "approval_events" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "approval_events"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["user_id", "decision"]

  schema = jsonencode([
    {
      name = "event_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "recommendation_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "run_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "event_timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "user_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "user_name"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "decision"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "decision_reason"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "time_to_decision_seconds"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "slack_message_ts"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])
}

# Performance metrics tracking
resource "google_bigquery_table" "performance_metrics" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "performance_metrics"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "metric_date"
  }

  clustering = ["recommendation_id", "metric_type"]

  schema = jsonencode([
    {
      name = "metric_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "recommendation_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "campaign_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "ad_group_id"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "metric_date"
      type = "DATE"
      mode = "REQUIRED"
    },
    {
      name = "metric_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "before_value"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "after_value"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "change_value"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "change_percent"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "is_statistically_significant"
      type = "BOOL"
      mode = "NULLABLE"
    }
  ])
}

# Campaign taxonomy for sync group management
resource "google_bigquery_table" "campaign_taxonomy" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "campaign_taxonomy"
  project    = var.project_id

  clustering = ["sync_group", "campaign_type"]

  schema = jsonencode([
    {
      name = "campaign_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "campaign_name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "customer_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "campaign_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "vertical"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "geo"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "sync_group"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "management_strategy"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "is_template"
      type = "BOOL"
      mode = "REQUIRED"
    },
    {
      name = "detection_method"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "detection_confidence"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "campaign_status"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "conversion_goal"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "conversion_source"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "created_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "updated_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "updated_by"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "notes"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "agent_exclusions"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "external_manager"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])
}

# Quality Score history for trend analysis
resource "google_bigquery_table" "quality_score_history" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "quality_score_history"
  project    = var.project_id

  time_partitioning {
    type          = "DAY"
    field         = "snapshot_date"
    expiration_ms = 31536000000  # 365 days
  }

  clustering = ["sync_group", "campaign_id"]

  schema = jsonencode([
    {
      name = "snapshot_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "snapshot_date"
      type = "DATE"
      mode = "REQUIRED"
    },
    {
      name = "campaign_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "ad_group_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "keyword_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "keyword_text"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "match_type"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "quality_score"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "expected_ctr"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "ad_relevance"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "landing_page_experience"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "impressions"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "clicks"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "cost_micros"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "conversions"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "sync_group"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "campaign_type"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "vertical"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "geo"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "created_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    }
  ])
}

# Landing page audits for LP health and content relevance
resource "google_bigquery_table" "landing_page_audits" {
  dataset_id = google_bigquery_dataset.agents.dataset_id
  table_id   = "landing_page_audits"
  project    = var.project_id

  time_partitioning {
    type          = "DAY"
    field         = "audit_date"
    expiration_ms = 31536000000  # 365 days
  }

  clustering = ["url_hash"]

  schema = jsonencode([
    {
      name = "audit_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "audit_date"
      type = "DATE"
      mode = "REQUIRED"
    },
    {
      name = "url"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "url_hash"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "performance_score"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "fcp_ms"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "lcp_ms"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "cls"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "mobile_friendly"
      type = "BOOL"
      mode = "NULLABLE"
    },
    {
      name = "is_accessible"
      type = "BOOL"
      mode = "NULLABLE"
    },
    {
      name = "http_status_code"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "redirect_chain"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "content_hash"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "content_relevance_score"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "keyword_alignment_score"
      type = "FLOAT64"
      mode = "NULLABLE"
    },
    {
      name = "improvement_suggestions"
      type = "JSON"
      mode = "NULLABLE"
    },
    {
      name = "sync_groups"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "campaign_ids"
      type = "STRING"
      mode = "REPEATED"
    },
    {
      name = "keyword_count"
      type = "INT64"
      mode = "NULLABLE"
    },
    {
      name = "created_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "next_audit_date"
      type = "DATE"
      mode = "NULLABLE"
    }
  ])
}
