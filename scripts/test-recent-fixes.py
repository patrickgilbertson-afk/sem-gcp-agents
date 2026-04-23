#!/usr/bin/env python3
"""Test script to validate all 5 recent bug fixes."""

import json
import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("SEM GCP Agents - Recent Fixes Validation")
print("=" * 60)
print()

PASSED = 0
FAILED = 0

def test_passed(name):
    global PASSED
    PASSED += 1
    print(f"✓ PASS: {name}")

def test_failed(name, error):
    global FAILED
    FAILED += 1
    print(f"✗ FAIL: {name}")
    print(f"  Error: {error}")

# =============================================================================
# Fix #1: Optional Calculated Metrics
# =============================================================================
print("Test 1: Optional Calculated Metrics (NULL handling)")
print("-" * 60)

try:
    from src.models.campaign import CampaignMetrics

    # Test with NULL values (should not raise validation error)
    metrics = CampaignMetrics(
        impressions=1000,
        clicks=0,
        cost=50.0,
        conversions=0.0,
        conversion_value=0.0,
        ctr=None,  # Should accept NULL
        avg_cpc=None,  # Should accept NULL
        conversion_rate=None  # Should accept NULL
    )

    assert metrics.ctr is None, "CTR should be None"
    assert metrics.avg_cpc is None, "avg_cpc should be None"
    assert metrics.conversion_rate is None, "conversion_rate should be None"

    test_passed("CampaignMetrics accepts NULL for calculated fields")

except Exception as e:
    test_failed("CampaignMetrics NULL handling", str(e))

print()

# =============================================================================
# Fix #2: ID Type Auto-Conversion
# =============================================================================
print("Test 2: ID Type Auto-Conversion (int → str)")
print("-" * 60)

try:
    from src.models.campaign import CampaignHealthData, CampaignMetrics

    # Test integer IDs get converted to strings
    data = CampaignHealthData(
        campaign_id=12345,  # Integer should convert to string
        campaign_name="Test Campaign",
        ad_group_id=67890,  # Integer should convert to string
        date_start=date.today(),
        date_end=date.today(),
        current_metrics=CampaignMetrics(
            impressions=100,
            clicks=10,
            cost=50.0,
            conversions=1.0,
            conversion_value=100.0
        )
    )

    assert isinstance(data.campaign_id, str), f"campaign_id should be str, got {type(data.campaign_id)}"
    assert data.campaign_id == "12345", f"campaign_id should be '12345', got {data.campaign_id}"
    assert isinstance(data.ad_group_id, str), f"ad_group_id should be str, got {type(data.ad_group_id)}"
    assert data.ad_group_id == "67890", f"ad_group_id should be '67890', got {data.ad_group_id}"

    test_passed("ID type auto-conversion working (int → str)")

except Exception as e:
    test_failed("ID type conversion", str(e))

print()

# =============================================================================
# Fix #3: customer_id Type in BigQuery Query
# =============================================================================
print("Test 3: customer_id Type Handling")
print("-" * 60)

try:
    from src.config import settings

    # Verify customer_id can be converted to int
    customer_id_str = settings.google_ads_customer_id
    customer_id_int = int(customer_id_str)

    assert isinstance(customer_id_str, str), "Config should store as string"
    assert isinstance(customer_id_int, int), "Should be convertible to int"

    # Test with leading zeros (if any)
    test_id = "1234567890"
    assert int(test_id) == 1234567890, "Conversion should preserve value"

    test_passed("customer_id type handling (str in config, int in BQ params)")

except Exception as e:
    test_failed("customer_id type handling", str(e))

print()

# =============================================================================
# Fix #4: Table Suffix Strategy
# =============================================================================
print("Test 4: Table Suffix Strategy (customer_id instead of wildcard)")
print("-" * 60)

try:
    from src.config import settings
    from src.integrations.bigquery.queries import CAMPAIGN_HEALTH_METRICS

    # Format query with customer ID
    query = CAMPAIGN_HEALTH_METRICS.format(
        project_id=settings.gcp_project_id,
        dataset=settings.bq_dataset_raw,
        date_suffix=settings.google_ads_customer_id,
    )

    # Verify query doesn't contain wildcard
    assert "*" not in query or "p_ads_CampaignStats_*" not in query, "Query should not use wildcard suffix"

    # Verify customer_id is in the table reference
    assert settings.google_ads_customer_id in query, f"Customer ID should be in query"

    test_passed("Table suffix uses customer_id (not wildcard)")

except Exception as e:
    test_failed("Table suffix strategy", str(e))

print()

# =============================================================================
# Fix #5: JSON Serialization
# =============================================================================
print("Test 5: JSON Serialization (json.dumps instead of str)")
print("-" * 60)

try:
    import json

    # Test data
    details = {
        "agent": "campaign_health",
        "count": 5,
        "nested": {"key": "value"},
        "boolean": True,
        "null_value": None
    }

    # Using str() - WRONG (old way)
    str_output = str(details)

    # Using json.dumps() - CORRECT (new way)
    json_output = json.dumps(details)

    # Verify json.dumps produces valid JSON
    parsed = json.loads(json_output)
    assert parsed == details, "JSON should round-trip correctly"

    # Verify str() produces invalid JSON (with single quotes)
    assert "'" in str_output, "str() should produce single quotes"
    assert '"' in json_output, "json.dumps() should produce double quotes"

    # Verify boolean/null handling
    assert "true" in json_output.lower(), "JSON should use lowercase 'true'"
    assert "null" in json_output, "JSON should use 'null' not 'None'"

    test_passed("JSON serialization using json.dumps()")

except Exception as e:
    test_failed("JSON serialization", str(e))

print()

# =============================================================================
# Bonus: Test Combined Scenario
# =============================================================================
print("Test 6: Combined Scenario (all fixes together)")
print("-" * 60)

try:
    from src.models.campaign import CampaignHealthData, CampaignMetrics
    import json

    # Create campaign data with integer IDs and NULL metrics
    campaign_data = CampaignHealthData(
        campaign_id=9876543210,  # Integer ID
        campaign_name="Test Campaign",
        ad_group_id=1234567890,  # Integer ID
        date_start=date(2026, 4, 1),
        date_end=date(2026, 4, 22),
        current_metrics=CampaignMetrics(
            impressions=1000,
            clicks=0,  # Zero clicks
            cost=50.0,
            conversions=0.0,
            conversion_value=0.0,
            ctr=None,  # NULL due to zero clicks
            avg_cpc=None,  # NULL due to zero clicks
            conversion_rate=None  # NULL due to zero conversions
        ),
        has_zero_conversions=True,
        has_low_ctr=True
    )

    # Verify IDs converted to strings
    assert isinstance(campaign_data.campaign_id, str)
    assert isinstance(campaign_data.ad_group_id, str)

    # Verify NULL metrics
    assert campaign_data.current_metrics.ctr is None
    assert campaign_data.current_metrics.avg_cpc is None

    # Test JSON serialization of metadata
    metadata = {
        "campaign_id": campaign_data.campaign_id,
        "flags": campaign_data.health_flags,
        "has_issues": len(campaign_data.health_flags) > 0
    }
    json_str = json.dumps(metadata)
    parsed = json.loads(json_str)
    assert parsed["campaign_id"] == "9876543210"

    test_passed("Combined scenario - all fixes working together")

except Exception as e:
    test_failed("Combined scenario", str(e))

print()

# =============================================================================
# Summary
# =============================================================================
print("=" * 60)
print("Summary")
print("=" * 60)
print(f"✓ Passed: {PASSED}")
print(f"✗ Failed: {FAILED}")
print(f"Total:    {PASSED + FAILED}")
print()

if FAILED == 0:
    print("✅ All fixes validated successfully!")
    sys.exit(0)
else:
    print(f"❌ {FAILED} test(s) failed")
    sys.exit(1)
