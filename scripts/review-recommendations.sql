-- Review Campaign Health Agent Recommendations
-- Run ID: bf7337a3-9133-4f6b-803b-ecdd693738ee
-- Generated: 2026-04-22
-- Total: 5,841 recommendations

-- ============================================================================
-- Query 1: Summary by Action Type and Risk Level
-- ============================================================================
SELECT
  action_type,
  risk_level,
  COUNT(*) as recommendation_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
GROUP BY action_type, risk_level
ORDER BY recommendation_count DESC;

-- ============================================================================
-- Query 2: Top 20 Recommendations by Impact
-- ============================================================================
SELECT
  title,
  description,
  action_type,
  risk_level,
  impact_estimate,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id,
  created_at
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
ORDER BY created_at DESC
LIMIT 20;

-- ============================================================================
-- Query 3: Recommendations by Campaign
-- ============================================================================
SELECT
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  action_type,
  COUNT(*) as count
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
  AND JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') IS NOT NULL
GROUP BY campaign_id, action_type
ORDER BY count DESC
LIMIT 50;

-- ============================================================================
-- Query 4: High Risk Recommendations (Review First)
-- ============================================================================
SELECT
  title,
  description,
  rationale,
  impact_estimate,
  action_type,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
  AND risk_level = 'high'
ORDER BY created_at DESC
LIMIT 50;

-- ============================================================================
-- Query 5: Pause Ad Group Recommendations
-- ============================================================================
SELECT
  title,
  description,
  rationale,
  impact_estimate,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
  AND action_type = 'pause_ad_group'
ORDER BY created_at DESC;

-- ============================================================================
-- Query 6: Keyword Review Recommendations
-- ============================================================================
SELECT
  title,
  description,
  rationale,
  impact_estimate,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = 'bf7337a3-9133-4f6b-803b-ecdd693738ee'
  AND action_type = 'delegate_keyword_review'
ORDER BY created_at DESC;
