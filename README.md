# Gmail Cloud Run App

A serverless Python application deployed on Google Cloud Run that accesses Gmail using service account authentication.

## Architecture

- **Platform**: Google Cloud Run (serverless, pay-per-use)
- **Language**: Python 3.11
- **Framework**: Flask
- **Authentication**: Service Account (domain-wide delegation)
- **API**: Gmail API

## Prerequisites

- Google Cloud account
- Google Workspace account (required for domain-wide delegation)
- `gcloud` CLI installed and authenticated
- Python 3.11+

## Project Structure

```
gmail-cloud-run/
├── main.py                 # Flask application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── .dockerignore          # Docker ignore rules
├── .gitignore            # Git ignore rules
├── credentials.json       # OAuth credentials (for local testing, gitignored)
├── service-account.json   # Service account key (for Cloud Run, gitignored)
└── README.md             # This file
```

## Setup Instructions

### 1. Local Development Setup

#### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure OAuth for Local Testing
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to project root
5. Configure OAuth consent screen and add test users
6. Run locally:
   ```bash
   python main.py
   curl http://localhost:8080/gmail-test
   ```

### 2. Service Account Setup (for Cloud Run)

#### A. Create Service Account

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Create service account
gcloud iam service-accounts create gmail-reader \
    --display-name="Gmail API Reader" \
    --description="Service account for reading Gmail via Cloud Run"

# Get the service account email
export SA_EMAIL="gmail-reader@${PROJECT_ID}.iam.gserviceaccount.com"
echo $SA_EMAIL
```

#### B. Create and Download Service Account Key

```bash
# Create key
gcloud iam service-accounts keys create service-account.json \
    --iam-account=$SA_EMAIL

# Verify the file was created
ls -l service-account.json
```

⚠️ **Security Note**: `service-account.json` contains sensitive credentials. It's in `.gitignore` and should NEVER be committed to git.

#### C. Enable Domain-Wide Delegation

**Important**: This requires a Google Workspace account (not just a regular Gmail account).

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin** > **Service Accounts**
3. Find your `gmail-reader` service account
4. Click the three dots (⋮) and select **Manage details**
5. In the **Advanced settings** section, click **Enable Google Workspace Domain-wide Delegation**
6. Note the **Client ID** (numeric, e.g., 1234567890)

#### D. Authorize Service Account in Workspace Admin Console

**You must be a Google Workspace Super Admin to complete this step.**

1. Go to [Google Workspace Admin Console](https://admin.google.com)
2. Navigate to **Security** > **Access and data control** > **API Controls**
3. Click **Manage Domain Wide Delegation**
4. Click **Add new**
5. Enter:
   - **Client ID**: The numeric Client ID from step C.6
   - **OAuth Scopes**: `https://www.googleapis.com/auth/gmail.readonly`
6. Click **Authorize**

#### E. Update Code with Service Account

The code needs to know which user's Gmail to impersonate. Update `main.py`:

```python
# In the get_gmail_service() function, set this to your email:
USER_EMAIL = 'your-email@yourdomain.com'
```

## Deployment to Cloud Run

### Option 1: Deploy from Source (Recommended)

```bash
# Deploy directly from source code
gcloud run deploy gmail-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --set-env-vars USE_SERVICE_ACCOUNT=true
```

The service account key will be included in the container during build.

### Option 2: Build and Deploy Separately

```bash
# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/gmail-app

# Deploy to Cloud Run
gcloud run deploy gmail-app \
  --image gcr.io/$PROJECT_ID/gmail-app \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --set-env-vars USE_SERVICE_ACCOUNT=true
```

### Get Your Service URL

After deployment:
```bash
gcloud run services describe gmail-app --region us-central1 --format 'value(status.url)'
```

## Testing

### Local Testing
```bash
# Start local server
python main.py

# Test Hello World
curl http://localhost:8080/

# Test Gmail integration
curl http://localhost:8080/gmail-test
```

### Cloud Run Testing
```bash
# Get your service URL
export SERVICE_URL=$(gcloud run services describe gmail-app --region us-central1 --format 'value(status.url)')

# Test Hello World
curl $SERVICE_URL/

# Test Gmail integration
curl $SERVICE_URL/gmail-test
```

## API Endpoints

- `GET /` - Hello World endpoint
- `GET /gmail-test` - Lists all Gmail labels for the authenticated user

## Environment Variables

- `PORT` - Server port (set automatically by Cloud Run)
- `USE_SERVICE_ACCOUNT` - Set to "true" to use service account authentication

## Cost Considerations

Cloud Run pricing (as of 2024):
- **Free tier**: 2 million requests/month, 360,000 GB-seconds compute time
- **After free tier**: ~$0.40 per million requests
- **Key feature**: You only pay when requests are being handled

For a learning/development app, you'll likely stay within the free tier.

## Security Best Practices

1. **Never commit secrets**:
   - `credentials.json` ✅ In `.gitignore`
   - `service-account.json` ✅ In `.gitignore`
   - `token.pickle` ✅ In `.gitignore`

2. **Service Account Key Management**:
   - Rotate keys periodically
   - Use Secret Manager in production (not included in this basic setup)
   - Delete unused keys

3. **Principle of Least Privilege**:
   - Only grant necessary Gmail scopes
   - Consider using `gmail.readonly` instead of full access

## Troubleshooting

### "Access blocked" error during OAuth
- Make sure your email is added as a test user in OAuth consent screen

### Service account authentication fails
- Verify domain-wide delegation is enabled and authorized
- Check that the Client ID matches in both Cloud Console and Workspace Admin
- Ensure the correct scopes are authorized
- Verify `USER_EMAIL` is set correctly in `main.py`

### "Not a valid workspace account"
- Service account domain-wide delegation requires Google Workspace
- Regular Gmail accounts cannot use this feature
- Alternative: Use OAuth flow with user consent (Option B)

## Alternative: Using OAuth Instead of Service Account

If you don't have Google Workspace, you'll need to use OAuth flow. The current `main.py` includes OAuth code for local testing, but for Cloud Run you'd need to:

1. Implement a web-based OAuth callback flow
2. Store tokens in Cloud Storage or Secret Manager
3. Handle token refresh logic

This is more complex and beyond the scope of this basic setup.

## Next Steps

Once you have the basic app working:

1. **Add more Gmail functionality**:
   - Read messages
   - Send emails
   - Search inbox
   - Manage labels

2. **Improve error handling**:
   - Better error messages
   - Logging
   - Retry logic

3. **Add security**:
   - Require authentication for Cloud Run endpoints
   - Use Secret Manager for service account keys
   - Implement rate limiting

4. **Monitoring**:
   - Set up Cloud Logging
   - Create alerts
   - Monitor costs

## Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Service Account Domain-Wide Delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)
- [Google Cloud Free Tier](https://cloud.google.com/free)

## License

MIT