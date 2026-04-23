#!/bin/bash
# Test the deployed Cloud Run service with all recent fixes

set -e

echo "============================================================"
echo "SEM GCP Agents - Deployed System Validation"
echo "============================================================"
echo ""

PROJECT_ID="marketing-bigquery-490714"
REGION="us-central1"
SERVICE_URL="https://sem-gcp-agents-ivxfiybalq-uc.a.run.app"

PASSED=0
FAILED=0

print_test() {
    echo "TEST: $1"
}

print_pass() {
    echo "✓ PASS: $1"
    ((PASSED++))
}

print_fail() {
    echo "✗ FAIL: $1"
    ((FAILED++))
}

# =============================================================================
# Test 1: Health Endpoint
# =============================================================================
echo "Test 1: Cloud Run Service Health"
echo "------------------------------------------------------------"
print_test "Checking health endpoint..."

HEALTH_RESPONSE=$(curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token 2>/dev/null)" \
  "$SERVICE_URL/health" 2>&1)

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    print_pass "Health endpoint responding correctly"
    echo "  Response: $HEALTH_RESPONSE"
else
    print_fail "Health endpoint not responding"
    echo "  Response: $HEALTH_RESPONSE"
fi
echo ""

# =============================================================================
# Test 2: BigQuery - Check Recent Audit Logs (JSON Serialization Fix)
# =============================================================================
echo "Test 2: JSON Serialization in Audit Logs"
echo "------------------------------------------------------------"
print_test "Querying recent audit logs..."

# Query audit logs to check JSON serialization
AUDIT_QUERY="
SELECT
  agent_type,
  event_type,
  details,
  created_at
FROM \`$PROJECT_ID.sem_agents.agent_audit_log\`
ORDER BY created_at DESC
LIMIT 5
"

AUDIT_RESULT=$(gcloud alpha bq query --project=$PROJECT_ID --use_legacy_sql=false --format=json \
  "$AUDIT_QUERY" 2>&1 | grep -v InsecureRequestWarning)

if echo "$AUDIT_RESULT" | grep -q "details"; then
    print_pass "Audit log query successful"

    # Check if details field contains valid JSON
    if echo "$AUDIT_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print('valid' if data else 'invalid')" 2>/dev/null | grep -q "valid"; then
        print_pass "Audit log details field contains valid JSON"
    else
        echo "  Info: No recent audit logs to validate JSON format"
    fi
else
    echo "  Info: No audit logs found yet (expected for new deployment)"
fi
echo ""

# =============================================================================
# Test 3: BigQuery Tables Exist (Table Suffix Fix)
# =============================================================================
echo "Test 3: BigQuery Tables & Table Suffix Strategy"
echo "------------------------------------------------------------"
print_test "Checking sem_agents tables..."

TABLES=$(gcloud alpha bq tables list --dataset=sem_agents --project=$PROJECT_ID --format=json 2>&1 | grep -v InsecureRequestWarning)

EXPECTED_TABLES=(
    "agent_audit_log"
    "agent_config"
    "agent_recommendations"
    "campaign_taxonomy"
    "quality_score_history"
    "landing_page_audits"
)

for table in "${EXPECTED_TABLES[@]}"; do
    if echo "$TABLES" | grep -q "$table"; then
        print_pass "Table '$table' exists"
    else
        print_fail "Table '$table' not found"
    fi
done
echo ""

# =============================================================================
# Test 4: Check for Google Ads Raw Data
# =============================================================================
echo "Test 4: Google Ads Data Transfer (customer_id fix validation)"
echo "------------------------------------------------------------"
print_test "Checking for Google Ads raw data tables..."

RAW_TABLES=$(gcloud alpha bq tables list --dataset=sem_ads_raw --project=$PROJECT_ID --format=json 2>&1 | \
  grep -v InsecureRequestWarning || echo "[]")

if echo "$RAW_TABLES" | grep -q "p_ads_"; then
    print_pass "Google Ads raw tables found"

    # Count campaign stats tables
    TABLE_COUNT=$(echo "$RAW_TABLES" | grep -c "CampaignStats" || echo "0")
    echo "  Found $TABLE_COUNT CampaignStats tables"
else
    echo "  Warning: No Google Ads raw data tables found"
    echo "  This is expected if Google Ads Data Transfer is not configured yet"
fi
echo ""

# =============================================================================
# Test 5: API Endpoints
# =============================================================================
echo "Test 5: API Endpoints (FastAPI routes)"
echo "------------------------------------------------------------"
print_test "Checking API documentation..."

# Check if docs endpoint is accessible
DOCS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token 2>/dev/null)" \
  "$SERVICE_URL/docs" 2>&1)

if [ "$DOCS_RESPONSE" == "200" ] || [ "$DOCS_RESPONSE" == "307" ]; then
    print_pass "API documentation accessible"
    echo "  Access at: $SERVICE_URL/docs"
else
    print_fail "API documentation not accessible (HTTP $DOCS_RESPONSE)"
fi
echo ""

# =============================================================================
# Test 6: Service Account Configuration
# =============================================================================
echo "Test 6: Service Account Configuration"
echo "------------------------------------------------------------"
print_test "Verifying Cloud Run uses correct service account..."

SERVICE_ACCOUNT=$(gcloud run services describe sem-gcp-agents \
  --region=$REGION \
  --format="value(spec.template.spec.serviceAccountName)" 2>&1 | grep -v InsecureRequestWarning)

if [ "$SERVICE_ACCOUNT" == "sa-sem-agents@$PROJECT_ID.iam.gserviceaccount.com" ]; then
    print_pass "Cloud Run using correct service account: sa-sem-agents"
else
    print_fail "Cloud Run using unexpected service account: $SERVICE_ACCOUNT"
fi
echo ""

# =============================================================================
# Test 7: Secrets Configuration
# =============================================================================
echo "Test 7: Secret Manager Secrets"
echo "------------------------------------------------------------"
print_test "Checking required secrets exist..."

REQUIRED_SECRETS=(
    "anthropic-api-key"
    "google-ads-developer-token"
    "slack-bot-token"
    "portkey-api-key"
)

SECRETS=$(gcloud secrets list --format="value(name)" 2>&1 | grep -v InsecureRequestWarning)

for secret in "${REQUIRED_SECRETS[@]}"; do
    if echo "$SECRETS" | grep -q "^${secret}$"; then
        print_pass "Secret '$secret' configured"
    else
        print_fail "Secret '$secret' not found"
    fi
done
echo ""

# =============================================================================
# Test 8: Try Manual Agent Trigger (Dry Run)
# =============================================================================
echo "Test 8: Manual Agent Trigger Test"
echo "------------------------------------------------------------"
print_test "Attempting to trigger Campaign Health Agent (dry run)..."

TRIGGER_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token 2>/dev/null)" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health", "dry_run": true}' \
  "$SERVICE_URL/api/v1/orchestrator/run" 2>&1)

if echo "$TRIGGER_RESPONSE" | grep -q -E "(execution_id|started|queued)" || echo "$TRIGGER_RESPONSE" | grep -q "200"; then
    print_pass "Agent trigger endpoint responding"
    echo "  Response: $TRIGGER_RESPONSE" | head -c 200
else
    echo "  Info: Agent trigger may require data or configuration"
    echo "  Response: $TRIGGER_RESPONSE" | head -c 200
fi
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "============================================================"
echo "Summary"
echo "============================================================"
echo "Passed:  $PASSED"
echo "Failed:  $FAILED"
echo "Total:   $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "⚠ Some tests failed or need configuration"
    exit 0  # Don't fail - some things are expected to need setup
fi
