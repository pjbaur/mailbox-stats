# Quick Deployment Guide

## Prerequisites Check

Before deploying, ensure you have:
- [ ] Google Workspace account (required for service account delegation)
- [ ] Service account created
- [ ] `service-account.json` file in project root
- [ ] Domain-wide delegation enabled and authorized in Workspace Admin
- [ ] Updated `USER_EMAIL` in `main.py`

## One-Command Deployment

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Deploy
gcloud run deploy gmail-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --set-env-vars USE_SERVICE_ACCOUNT=true
```

## Get Service URL

```bash
export SERVICE_URL=$(gcloud run services describe gmail-app --region us-central1 --format 'value(status.url)')
echo "Your app is running at: $SERVICE_URL"
```

## Test Deployed App

```bash
# Hello World
curl $SERVICE_URL/

# Gmail labels
curl $SERVICE_URL/gmail-test

# Recent messages
curl $SERVICE_URL/gmail-messages
```

## If You Don't Have Google Workspace

**Service account delegation won't work with regular Gmail accounts.**

You have two options:

### Option 1: Get Google Workspace
- Sign up at https://workspace.google.com
- Even the cheapest plan supports domain-wide delegation
- You can use a trial to test

### Option 2: Use OAuth Flow (more complex)
- Keep using the current OAuth setup for local development
- For Cloud Run, you'd need to:
  1. Implement web-based OAuth callback
  2. Store tokens in Cloud Storage or Secret Manager
  3. Add endpoints for OAuth authorization flow

For learning purposes, Option 1 (getting Workspace trial) is easier.

## Common Issues

### "Subject not authorized"
- Domain-wide delegation not properly configured
- Wrong Client ID in Workspace Admin
- Scopes don't match
- USER_EMAIL not in your domain

### "Service account not found"
- `service-account.json` not in the project directory
- File not being included in Docker build

### "Invalid grant"
- USER_EMAIL is not a valid email in your Workspace domain
- Service account doesn't have delegation enabled

## Cost Estimate

For a learning/testing app with ~100 requests/day:
- **Cloud Run**: Free tier (2M requests/month)
- **Total**: $0/month

Even with heavier use:
- 10,000 requests/day = 300,000/month
- Still within free tier
- If exceeded: ~$0.12/month

## Next Steps After Deployment

1. Test all endpoints
2. Review Cloud Run logs: `gcloud run logs tail gmail-app`
3. Monitor in Cloud Console
4. Add more Gmail functionality
5. Set up alerts for errors