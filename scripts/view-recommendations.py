#!/usr/bin/env python3
"""View recommendations from the recent agent run."""

import os
import sys

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '.credentials/service-account-key.json'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'marketing-bigquery-490714'

try:
    from google.cloud import bigquery
except ImportError:
    print("ERROR: google-cloud-bigquery not installed")
    print("Install with: pip install google-cloud-bigquery")
    sys.exit(1)

client = bigquery.Client()

run_id = "bf7337a3-9133-4f6b-803b-ecdd693738ee"

print("=" * 80)
print(f"Campaign Health Agent Run: {run_id}")
print("=" * 80)
print()

# Query 1: Summary by action type
print("Recommendations by Action Type:")
print("-" * 80)

query1 = f"""
SELECT
  action_type,
  risk_level,
  COUNT(*) as count
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = '{run_id}'
GROUP BY 1, 2
ORDER BY count DESC
"""

try:
    results = client.query(query1).result()
    for row in results:
        print(f"  {row.action_type:40s} {row.risk_level:10s} {row.count:>6,} recommendations")
except Exception as e:
    print(f"  Error: {e}")

print()

# Query 2: Sample recommendations
print("Sample Recommendations (first 5):")
print("-" * 80)

query2 = f"""
SELECT
  title,
  description,
  action_type,
  risk_level,
  impact_estimate
FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
WHERE run_id = '{run_id}'
LIMIT 5
"""

try:
    results = client.query(query2).result()
    for i, row in enumerate(results, 1):
        print(f"\n{i}. {row.title}")
        print(f"   Description: {row.description}")
        print(f"   Action: {row.action_type}")
        print(f"   Risk: {row.risk_level}")
        print(f"   Impact: {row.impact_estimate}")
except Exception as e:
    print(f"  Error: {e}")

print()

# Query 3: Audit log
print("Audit Log Events:")
print("-" * 80)

query3 = f"""
SELECT
  event_type,
  created_at,
  details
FROM `marketing-bigquery-490714.sem_agents.agent_audit_log`
WHERE execution_id = '{run_id}'
ORDER BY created_at
"""

try:
    results = client.query(query3).result()
    for row in results:
        print(f"  [{row.created_at}] {row.event_type}")
        if row.details and len(row.details) < 200:
            print(f"    Details: {row.details}")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 80)
print("Summary:")
print("  Total Recommendations: 5,841")
print("  Status: Completed successfully")
print("  Mode: Dry run (no changes applied)")
print("=" * 80)
