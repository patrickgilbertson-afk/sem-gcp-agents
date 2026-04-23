#!/usr/bin/env python3
"""Query and display Campaign Health Agent recommendations."""

import os
import sys

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '.credentials/service-account-key.json'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'marketing-bigquery-490714'

try:
    from google.cloud import bigquery
except ImportError:
    print("ERROR: google-cloud-bigquery not installed")
    print("\nPlease install dependencies first:")
    print("  pip install google-cloud-bigquery")
    sys.exit(1)

client = bigquery.Client()

print("=" * 80)
print("Campaign Health Agent - Recommendations Summary")
print("=" * 80)
print()

# Use the most recent run
run_id = "bf7337a3-9133-4f6b-803b-ecdd693738ee"

# Query 1: Summary by action type
print("📊 Summary by Action Type and Risk Level")
print("-" * 80)

query1 = f"""
SELECT
  action_type,
  risk_level,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = '{run_id}'
GROUP BY action_type, risk_level
ORDER BY count DESC
"""

try:
    results = client.query(query1).result()
    total = 0
    for row in results:
        print(f"  {row.action_type:35s} {row.risk_level:10s} {row.count:>6,} ({row.percentage:>5.1f}%)")
        total += row.count
    print(f"\n  {'TOTAL':35s} {'':<10s} {total:>6,}")
except Exception as e:
    print(f"  Error: {e}")

print()
print()

# Query 2: Sample recommendations (pause_ad_group)
print("🚫 Sample: Pause Ad Group Recommendations (Top 10)")
print("-" * 80)

query2 = f"""
SELECT
  title,
  description,
  impact_estimate,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = '{run_id}'
  AND action_type = 'pause_ad_group'
ORDER BY created_at DESC
LIMIT 10
"""

try:
    results = client.query(query2).result()
    for i, row in enumerate(results, 1):
        print(f"\n{i}. {row.title}")
        print(f"   → {row.description}")
        print(f"   💰 Impact: {row.impact_estimate}")
        if row.campaign_id:
            print(f"   📍 Campaign: {row.campaign_id}, Ad Group: {row.ad_group_id}")
except Exception as e:
    print(f"  Error: {e}")

print()
print()

# Query 3: Sample recommendations (keyword review)
print("🔍 Sample: Keyword Review Recommendations (Top 10)")
print("-" * 80)

query3 = f"""
SELECT
  title,
  description,
  impact_estimate,
  JSON_EXTRACT_SCALAR(action_params, '$.campaign_id') as campaign_id,
  JSON_EXTRACT_SCALAR(action_params, '$.ad_group_id') as ad_group_id
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = '{run_id}'
  AND action_type = 'delegate_keyword_review'
ORDER BY created_at DESC
LIMIT 10
"""

try:
    results = client.query(query3).result()
    for i, row in enumerate(results, 1):
        print(f"\n{i}. {row.title}")
        print(f"   → {row.description}")
        print(f"   💰 Impact: {row.impact_estimate}")
        if row.campaign_id:
            print(f"   📍 Campaign: {row.campaign_id}, Ad Group: {row.ad_group_id}")
except Exception as e:
    print(f"  Error: {e}")

print()
print()
print("=" * 80)
print("Next Steps:")
print("  1. Review recommendations in BigQuery Console:")
print("     https://console.cloud.google.com/bigquery?project=marketing-bigquery-490714")
print("  2. Use queries in scripts/review-recommendations.sql for more details")
print("  3. Set up Slack integration for approval workflow")
print("=" * 80)
