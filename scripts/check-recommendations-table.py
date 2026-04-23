#!/usr/bin/env python3
"""Check agent_recommendations table for data."""

import os
import sys

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '.credentials/service-account-key.json'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'marketing-bigquery-490714'

try:
    from google.cloud import bigquery
except ImportError:
    print("ERROR: google-cloud-bigquery not installed")
    print("\nTo install: pip install google-cloud-bigquery")
    sys.exit(1)

client = bigquery.Client()

print("=" * 80)
print("Investigating agent_recommendations Table")
print("=" * 80)
print()

# Check 1: Table info
print("1. Checking table information...")
try:
    table = client.get_table("marketing-bigquery-490714.sem_agents.agent_recommendations")
    print(f"   ✓ Table exists")
    print(f"   - Created: {table.created}")
    print(f"   - Num rows: {table.num_rows}")
    print(f"   - Size: {table.num_bytes / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print()

# Check 2: Count total rows
print("2. Counting total recommendations...")
try:
    query = "SELECT COUNT(*) as total FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`"
    result = list(client.query(query).result())
    total = result[0].total
    print(f"   Total rows: {total:,}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print()

# Check 3: List all run IDs
print("3. Listing all run IDs...")
try:
    query = """
    SELECT
        run_id,
        COUNT(*) as count,
        MIN(created_at) as first_created,
        MAX(created_at) as last_created
    FROM `marketing-bigquery-490714.sem_agents.agent_recommendations`
    GROUP BY run_id
    ORDER BY first_created DESC
    """
    results = client.query(query).result()

    found_any = False
    for row in results:
        found_any = True
        print(f"   Run ID: {row.run_id}")
        print(f"   - Count: {row.count:,}")
        print(f"   - Created: {row.first_created}")
        print()

    if not found_any:
        print("   ⚠ No recommendations found in table!")
        print()
        print("   This suggests recommendations are not being written to BigQuery.")
        print("   Possible causes:")
        print("   - Agent completes but doesn't save recommendations")
        print("   - Write permission issue")
        print("   - Code path not calling save method")

except Exception as e:
    print(f"   ✗ Error: {e}")

print()

# Check 4: Check audit log for recent runs
print("4. Checking audit log for recent agent runs...")
try:
    query = """
    SELECT
        execution_id,
        agent_type,
        event_type,
        created_at,
        LEFT(details, 100) as details_preview
    FROM `marketing-bigquery-490714.sem_agents.agent_audit_log`
    WHERE agent_type = 'campaign_health'
    ORDER BY created_at DESC
    LIMIT 5
    """
    results = client.query(query).result()

    for row in results:
        print(f"   {row.created_at}: {row.event_type}")
        if row.details_preview:
            print(f"      Details: {row.details_preview}")

except Exception as e:
    print(f"   ✗ Error querying audit log: {e}")

print()
print("=" * 80)
print("Diagnosis:")
print("=" * 80)

# Provide diagnosis
table = client.get_table("marketing-bigquery-490714.sem_agents.agent_recommendations")
if table.num_rows == 0:
    print("⚠ The agent_recommendations table is EMPTY")
    print()
    print("The agent runs successfully but recommendations are not being saved.")
    print("This is likely a code issue where the save step is missing or failing silently.")
    print()
    print("Next steps:")
    print("1. Check agent code for recommendation save logic")
    print("2. Check Cloud Run logs for write errors")
    print("3. Verify service account has BigQuery write permissions")
else:
    print(f"✓ Table has {table.num_rows:,} recommendations")
    print("Check the run IDs above to find your data.")

print()
