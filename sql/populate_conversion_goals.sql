-- Populate conversion_goal and conversion_source fields in campaign_taxonomy
-- Run this after deploying the schema updates
--
-- Usage:
--   1. Replace {project_id} with your GCP project ID
--   2. Run in BigQuery console or via bq command-line tool
--   3. Adjust conversion goals based on your campaign strategies

-- ============================================================================
-- NonBrand Campaigns: Optimize for SQC Org Creates
-- ============================================================================
-- NonBrand campaigns focus on acquisition, so primary conversion is org creation

UPDATE `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
SET
    conversion_goal = 'sc_org_create',
    conversion_source = 'google_analytics',
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = 'sql_script_initial_setup'
WHERE campaign_type = 'non_brand'
AND conversion_goal IS NULL;

-- Output: Updated X rows


-- ============================================================================
-- Brand Campaigns: Optimize for New Signups
-- ============================================================================
-- Brand campaigns capture high-intent users, optimize for signup completion

UPDATE `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
SET
    conversion_goal = 'sc_new_signup',
    conversion_source = 'google_analytics',
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = 'sql_script_initial_setup'
WHERE campaign_type = 'brand'
AND conversion_goal IS NULL;

-- Output: Updated X rows


-- ============================================================================
-- Competitor Campaigns: Optimize for Trial Upgrades
-- ============================================================================
-- Competitor campaigns target switchers, focus on trial upgrade quality

UPDATE `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
SET
    conversion_goal = 'sc_trial_upgrade',
    conversion_source = 'google_analytics',
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = 'sql_script_initial_setup'
WHERE campaign_type = 'competitor'
AND conversion_goal IS NULL;

-- Output: Updated X rows


-- ============================================================================
-- Verify Results
-- ============================================================================
-- Check distribution of conversion goals across campaign types

SELECT
    campaign_type,
    conversion_goal,
    conversion_source,
    COUNT(*) as campaign_count,
    STRING_AGG(DISTINCT sync_group ORDER BY sync_group LIMIT 5) as sample_sync_groups
FROM `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
GROUP BY campaign_type, conversion_goal, conversion_source
ORDER BY campaign_type, conversion_goal;


-- ============================================================================
-- Alternative: More Granular Approach
-- ============================================================================
-- If you want to set different conversion goals for specific verticals or sync groups:

-- Example: Set high-value NonBrand campaigns to optimize for engaged visitors
/*
UPDATE `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
SET
    conversion_goal = 'engaged_visitor_2025',
    conversion_source = 'google_analytics',
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = 'sql_script_granular_setup'
WHERE campaign_type = 'non_brand'
AND vertical IN ('Enterprise', 'High-Value')
AND conversion_goal IS NULL;
*/

-- Example: Set specific sync groups to optimize for downloads
/*
UPDATE `marketing-bigquery-490714.sem_agents.campaign_taxonomy`
SET
    conversion_goal = 'sq_download',
    conversion_source = 'google_analytics',
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = 'sql_script_granular_setup'
WHERE sync_group IN ('NonBrand_Developer-Tools_US', 'NonBrand_Developer-Tools_UK')
AND conversion_goal IS NULL;
*/


-- ============================================================================
-- Knowledge Base Mapping
-- ============================================================================
-- Your conversion goals map to knowledge base tags in docs/knowledge/INDEX.md:
--
-- conversion_goal           -> knowledge tag
-- ─────────────────────────────────────────────────
-- sc_org_create            -> conversion_sqc_org_creates
-- sc_new_signup            -> (no specific tag, uses campaign_type)
-- sc_trial_upgrade         -> (no specific tag, uses campaign_type)
-- engaged_visitor_2025     -> (no specific tag, uses campaign_type)
-- submittedForm            -> (no specific tag, uses campaign_type)
-- sq_download              -> (no specific tag, uses campaign_type)
--
-- The knowledge service normalizes conversion_goal to lowercase with underscores
-- for tag matching: "SQC Org Creates" -> "sqc_org_creates"
