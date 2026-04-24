# Setup Status - Ready to Run Campaign Health Agent

## ✅ Infrastructure Ready

### BigQuery
```
Dataset: sem_agents (exists)
Tables: 12 tables created
├─ campaign_taxonomy       (0 rows) ← EMPTY - needs campaign data
├─ agent_audit_log         (created)
├─ agent_recommendations   (created)
├─ quality_score_history   (created)
└─ ... 8 other tables
```

### Configuration
```
✅ GCP Project: marketing-bigquery-490714
✅ MCC Account: 1109417913
✅ Campaign Account: 9624230998
✅ GA4 Dataset: analytics_272839261
✅ Slack Channel: C0AC1TGCZA6
✅ All secrets in GCP Secret Manager
```

---

## ⏸️ SQL Script Status

The conversion goals SQL script **cannot run yet** because:

**Problem**: `campaign_taxonomy` table is empty (0 rows)

**Why**: The table was created by Terraform, but it doesn't have campaign data yet.

**Solution**: The Campaign Health Agent will automatically populate this table when it runs for the first time.

---

## 🎯 Next Steps (In Order)

### Step 1: Run Campaign Health Agent

The agent will:
1. Query Google Ads for all campaigns
2. Parse campaign names to detect taxonomy (brand/non_brand/competitor)
3. Insert rows into `campaign_taxonomy`
4. Analyze campaign performance
5. Generate recommendations

**How to run**:

```bash
# Option A: Local testing
source .venv/Scripts/activate
uvicorn src.main:app --reload --port 8080

# In another terminal
curl -X POST http://localhost:8080/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

```bash
# Option B: Deploy first, then trigger
cd terraform
terraform apply

# Then trigger via Cloud Run URL
curl -X POST https://YOUR-SERVICE-URL/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'
```

---

### Step 2: Verify Taxonomy Populated

After the agent runs, check:

```bash
# Check how many campaigns were detected
gcloud alpha bq query --use_legacy_sql=false \
  "SELECT campaign_type, COUNT(*) as count
   FROM marketing-bigquery-490714.sem_agents.campaign_taxonomy
   GROUP BY campaign_type"
```

Expected output:
```
campaign_type  count
─────────────────────
brand          4
non_brand      12
competitor     6
```

---

### Step 3: Run Conversion Goals SQL

**NOW** the SQL script will work:

```bash
source .venv/Scripts/activate
python run_conversion_goals.py
```

This will update the campaigns that were just populated with conversion goals:
- NonBrand → `sc_org_create`
- Brand → `sc_new_signup`
- Competitor → `sc_trial_upgrade`

---

## Summary

**Current State**:
- ✅ BigQuery infrastructure created (tables exist)
- ✅ Configuration complete (all IDs set)
- ✅ Secrets configured (GCP Secret Manager)
- ⏸️ Campaign taxonomy empty (needs first agent run)

**To Complete Setup**:
1. Run Campaign Health Agent (populates taxonomy)
2. Verify campaigns detected
3. Run conversion goals SQL script
4. Agent is ready for ongoing use

---

## Quick Start (Recommended)

**Test locally right now**:

```bash
# Terminal 1: Start server
source .venv/Scripts/activate
uvicorn src.main:app --reload --port 8080

# Terminal 2: Trigger agent
curl -X POST http://localhost:8080/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "campaign_health"}'

# Watch the logs in Terminal 1
# Agent will:
# - Load campaigns from Google Ads
# - Populate taxonomy
# - Analyze performance
# - Generate recommendations
# - Send to Slack for approval
```

**After it completes**:

```bash
# Check taxonomy was populated
python -c "
from google.cloud import bigquery
client = bigquery.Client(project='marketing-bigquery-490714')
result = client.query('SELECT COUNT(*) as count FROM sem_agents.campaign_taxonomy').result()
for row in result:
    print(f'Campaigns in taxonomy: {row.count}')
"

# Then run conversion goals
python run_conversion_goals.py
```

---

**Status**: Ready to run! 🚀

The SQL script waits until after the first Campaign Health Agent run populates the taxonomy table.
