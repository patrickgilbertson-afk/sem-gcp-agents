# Slack Integration Setup Guide

## Overview

The SEM GCP Agents system uses Slack for human-in-the-loop approval of recommendations. When an agent generates recommendations, it posts them to a Slack channel where SEM managers can review and approve/reject each recommendation.

---

## Prerequisites

- Slack workspace admin access
- Service account with Secret Manager access (already configured)
- Slack channel for approvals (create if needed)

---

## Step 1: Create Slack App

### Option A: Using Manifest (Recommended - 2 minutes)

1. **Go to Slack API:**
   - https://api.slack.com/apps

2. **Click "Create New App"**

3. **Select "From an app manifest"**

4. **Choose your workspace**

5. **Paste this manifest:**

```yaml
display_information:
  name: SEM GCP Agents
  description: AI-powered SEM campaign management with human approval
  background_color: "#4A154B"
features:
  bot_user:
    display_name: SEM Agent
    always_online: true
oauth_config:
  scopes:
    bot:
      - chat:write
      - chat:write.public
      - channels:read
      - groups:read
      - im:read
      - mpim:read
      - users:read
settings:
  event_subscriptions:
    request_url: https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/slack/events
    bot_events:
      - message.channels
      - message.groups
      - message.im
      - message.mpim
  interactivity:
    is_enabled: true
    request_url: https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/slack/interactions
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

6. **Click "Create"**

7. **Review permissions and click "Install to Workspace"**

8. **Authorize the app**

---

### Option B: Manual Setup (5 minutes)

If manifest doesn't work, create manually:

1. **Create App:**
   - Go to: https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name: `SEM GCP Agents`
   - Choose your workspace

2. **Add Bot Scopes:**
   - Go to "OAuth & Permissions"
   - Under "Bot Token Scopes", add:
     - `chat:write`
     - `chat:write.public`
     - `channels:read`
     - `users:read`

3. **Enable Interactivity:**
   - Go to "Interactivity & Shortcuts"
   - Toggle "Interactivity" ON
   - Request URL: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/slack/interactions`
   - Click "Save Changes"

4. **Enable Events:**
   - Go to "Event Subscriptions"
   - Toggle "Enable Events" ON
   - Request URL: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/slack/events`
   - Under "Subscribe to bot events", add:
     - `message.channels`
     - `message.groups`
     - `message.im`
   - Click "Save Changes"

5. **Install App:**
   - Go to "Install App"
   - Click "Install to Workspace"
   - Authorize

---

## Step 2: Get Credentials

After installing the app:

1. **Get Bot Token:**
   - Go to "OAuth & Permissions"
   - Copy "Bot User OAuth Token" (starts with `xoxb-`)
   - Save for next step

2. **Get Signing Secret:**
   - Go to "Basic Information"
   - Under "App Credentials", find "Signing Secret"
   - Click "Show" and copy
   - Save for next step

---

## Step 3: Create Slack Channel

1. **Create a new channel** (or use existing):
   - Name: `#sem-agent-approvals` (or your preferred name)
   - Make it public or private

2. **Invite the bot:**
   - In the channel, type: `/invite @SEM Agent`
   - Or right-click channel → "Add apps" → Find "SEM GCP Agents"

3. **Get Channel ID:**
   - Right-click the channel name → "View channel details"
   - Scroll down, copy the Channel ID (e.g., `C01234567`)

---

## Step 4: Update Secrets in GCP

Update the Slack secrets with your credentials:

### Via Console (Recommended):

1. **Go to Secret Manager:**
   - https://console.cloud.google.com/security/secret-manager?project=marketing-bigquery-490714

2. **Update `slack-bot-token`:**
   - Click on `slack-bot-token`
   - Click "NEW VERSION"
   - Paste your Bot Token (xoxb-...)
   - Click "ADD NEW VERSION"

3. **Update `slack-signing-secret`:**
   - Click on `slack-signing-secret`
   - Click "NEW VERSION"
   - Paste your Signing Secret
   - Click "ADD NEW VERSION"

### Via Command Line:

```bash
# Update bot token
echo -n "xoxb-YOUR-BOT-TOKEN" | \
  gcloud secrets versions add slack-bot-token --data-file=-

# Update signing secret
echo -n "YOUR-SIGNING-SECRET" | \
  gcloud secrets versions add slack-signing-secret --data-file=-
```

---

## Step 5: Update Cloud Run Environment Variable

Set the Slack channel ID in Cloud Run:

### Via Console:

1. **Go to Cloud Run:**
   - https://console.cloud.google.com/run/detail/us-central1/sem-gcp-agents?project=marketing-bigquery-490714

2. **Click "EDIT & DEPLOY NEW REVISION"**

3. **Scroll to "Variables & Secrets"**

4. **Add environment variable:**
   - Name: `SLACK_APPROVAL_CHANNEL_ID`
   - Value: Your channel ID (e.g., `C01234567`)

5. **Click "DEPLOY"**

### Via Command Line:

```bash
gcloud run services update sem-gcp-agents \
  --region=us-central1 \
  --update-env-vars=SLACK_APPROVAL_CHANNEL_ID=C01234567
```

---

## Step 6: Restart Cloud Run Service

After updating secrets and env vars, the service will automatically redeploy. Wait ~1-2 minutes.

---

## Step 7: Test Slack Integration

### Test 1: Health Check
Post a message in your approval channel:
```
/invite @SEM Agent
Hello!
```

The bot should be able to see messages.

### Test 2: Trigger Agent and Check Slack
Trigger the Campaign Health Agent:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"agent_type":"campaign_health","context":{}}' \
  https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/api/v1/orchestrator/run
```

You should see recommendations posted to your Slack channel with Approve/Reject buttons.

---

## Troubleshooting

### Bot not posting to channel

**Check:**
1. Bot is invited to channel (`/invite @SEM Agent`)
2. `SLACK_APPROVAL_CHANNEL_ID` env var is set correctly
3. Cloud Run service restarted after secret updates

**Debug:**
```bash
# Check Cloud Run logs
gcloud run services logs read sem-gcp-agents --region=us-central1 --limit=50

# Look for Slack-related errors
gcloud run services logs read sem-gcp-agents --region=us-central1 | grep -i slack
```

### "url_verification failed"

This happens when setting up Event Subscriptions. The URL verification should succeed automatically. If it fails:

1. Check Cloud Run service is running: https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/health
2. Check service logs for errors
3. Ensure `/slack/events` endpoint exists

### Buttons not working

**Check:**
1. Interactivity URL is set: `https://sem-gcp-agents-ivxfiybalq-uc.a.run.app/slack/interactions`
2. Signing secret is correct in Secret Manager
3. Cloud Run service restarted after secret update

---

## What Happens in Production

1. **Agent runs** (via Cloud Scheduler or manual trigger)
2. **Recommendations generated** (stored in BigQuery)
3. **Slack message posted** to `#sem-agent-approvals` with:
   - Summary of recommendations
   - Approve/Reject buttons for each
4. **Manager clicks** Approve or Reject
5. **System applies** approved changes to Google Ads
6. **Audit log** records all actions

---

## Message Format

Here's what the Slack approval message looks like:

```
🤖 Campaign Health Agent - Recommendations Ready

Run ID: bf7337a3-9133-4f6b-803b-ecdd693738ee
Generated: 5,841 recommendations

Summary by Action Type:
• pause_ad_group: 3,421 (low risk)
• delegate_keyword_review: 2,420 (medium risk)

Top Recommendations:
1. Pause ad group: Example Ad Group
   Spent $150 with zero conversions
   [Approve] [Reject]

2. Review keywords in: Another Ad Group
   Average quality score: 3.2
   [Approve] [Reject]

...

⏰ Approval expires in 8 hours
```

---

## Security Notes

- ✅ Signing secret validates requests are from Slack
- ✅ OIDC tokens secure Cloud Run endpoint
- ✅ Secrets stored in Secret Manager (not in code)
- ✅ Approval timeout (auto-reject after 8 hours)
- ✅ Audit log for all approvals/rejections

---

## Next Steps After Setup

1. Test with a small batch of recommendations
2. Review approval workflow with SEM team
3. Adjust timeout/escalation settings if needed
4. Monitor Slack channel for first real agent run (tomorrow 7 AM)

---

**Questions or issues?** Check Cloud Run logs or the troubleshooting section above.
