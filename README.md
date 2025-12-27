# Mailbox Stats (Gmail Statistics Dashboard)

A command-line tool that analyzes Gmail mailbox data to provide insights and help identify cleanup opportunities. Features include top sender analysis, storage usage tracking, attachment statistics, and multiple output formats (console, CSV, JSON, HTML, web UI).

## Architecture

- **Platform**: Local CLI / Optional Cloud Run deployment
- **Language**: Python 3.12
- **CLI Framework**: argparse
- **Web Framework**: FastAPI (optional `--serve` mode)
- **Authentication**: OAuth (local) or Service Account (Cloud Run)
- **API**: Gmail API (read-only scope)
- **Database**: SQLite (for historical tracking)

## Prerequisites

- Google Cloud account
- Google Workspace account (required for domain-wide delegation in Cloud Run)
- `gcloud` CLI installed and authenticated
- Python 3.12+

## Project Structure

```
mailbox-stats/
├── gmail_stats.py          # Main CLI tool with core functionality
├── gmail_stats_db.py       # SQLite persistence layer
├── gmail_stats_export.py   # CSV/JSON export functionality
├── gmail_stats_html.py     # Static HTML report generator
├── gmail_stats_server.py   # FastAPI web server (--serve mode)
├── gcs_upload.py           # Google Cloud Storage upload utility
├── gmail_pull.py           # Quick API connectivity test
├── main.py                 # Flask app (legacy Cloud Run)
├── dockerfile              # Container configuration for Cloud Run
├── requirements.txt        # Python dependencies
├── pytest.ini              # Test configuration
├── client_secret.json      # OAuth credentials (gitignored)
├── token.json              # Cached OAuth token (gitignored)
├── gmail_stats.db          # SQLite database (gitignored)
├── .env                    # Environment configuration (gitignored)
├── out/                    # Output directory for --out exports
│   └── YYYY-MM-DD_HHMM/    # Dated subfolders
├── tests/                  # Test suite (250 tests)
├── CLAUDE.md               # Detailed CLI documentation
└── README.md               # This file
```

## Setup Instructions

### 1. Local Development Setup

#### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure OAuth for Local Testing (Local)
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

The code needs to know which user's Gmail to impersonate. Update environment or `.env`:

```bash
# In .env, set this to your email:
USER_EMAIL = 'your-email@yourdomain.com'
```

## Deployment to Cloud Run

### Cloud Run Jobs (Recommended for Batch Analysis)

Cloud Run Jobs are ideal for this batch workload - they run on-demand and don't require a persistent server.

#### 1. Setup

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
gcloud config set project $PROJECT_ID

# Create Artifact Registry repository
gcloud artifacts repositories create mailbox-stats \
  --repository-format=docker --location=$REGION

gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Store OAuth token in Secret Manager (run locally first to generate token.json)
gcloud secrets create gmail-token --data-file=token.json

# Create GCS bucket for outputs
gsutil mb -l $REGION gs://${PROJECT_ID}-mailbox-stats-output
```

#### 2. Build and Push Container

```bash
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/mailbox-stats/gmail-stats:$(git rev-parse --short HEAD)"
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

#### 3. Create Cloud Run Job

```bash
gcloud run jobs create mailbox-stats \
  --image "$IMAGE" \
  --region $REGION \
  --memory 2Gi --cpu 2 \
  --task-timeout 3600 \
  --set-env-vars "MODE=sample,SAMPLE_SIZE=5000,EXPORT_CSV=1,HTML_REPORT=1,SKIP_DB=1,GCS_BUCKET=gs://${PROJECT_ID}-mailbox-stats-output/reports,OUTPUT_DIR=/tmp/out" \
  --set-secrets "TOKEN_JSON=gmail-token:latest"
```

#### 4. Execute Job

```bash
# Run the job
gcloud run jobs execute mailbox-stats --region $REGION

# Watch logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=mailbox-stats" --limit=100
```

### Cloud Run Services (Legacy - Web Server)

For the legacy Flask web app (`main.py`):

```bash
# Deploy from source
gcloud run deploy gmail-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars USE_SERVICE_ACCOUNT=true

# Get service URL
gcloud run services describe gmail-app --region us-central1 --format 'value(status.url)'
```

## Testing

### Automated Test Suite

The project includes a comprehensive test suite with **250 tests** covering unit, integration, and end-to-end scenarios. Test coverage: **93%**.

#### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test category
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/e2e/            # End-to-end tests only

# Run with coverage report
pytest --cov=gmail_stats --cov-report=html
# Coverage report generated in htmlcov/index.html

# Run tests by priority marker
pytest -m p0                 # Critical priority tests
pytest -m "p0 or p1"         # High priority tests
pytest -m "not slow"         # Skip slow performance tests
```

#### Test Organization

```
tests/
├── unit/                    # Unit tests (pure functions)
│   ├── test_email_extraction.py
│   ├── test_date_conversion.py
│   ├── test_chunked.py
│   ├── test_print_header.py
│   ├── test_request_tracking.py
│   ├── test_random_sampling.py
│   ├── test_export.py       # CSV/JSON export tests
│   └── test_html_report.py  # HTML report generator tests
├── integration/             # Integration tests (with mocks)
│   ├── test_execute_request.py
│   ├── test_get_creds.py
│   ├── test_list_all_message_ids.py
│   ├── test_batch_get_metadata.py
│   ├── test_label_counts.py
│   ├── test_cli_args.py     # CLI argument tests
│   └── test_server.py       # FastAPI endpoint tests
├── e2e/                     # End-to-end workflow tests
│   └── test_main_workflow.py
├── edge_cases/              # Edge case handling
├── performance/             # Performance tests
├── reliability/             # Reliability tests
├── security/                # Security tests
└── conftest.py              # Shared fixtures
```

#### Test Dependencies

Required packages (already installed if you followed setup):
- `pytest` - Testing framework
- `pytest-mock` - Mocking support
- `pytest-cov` - Coverage reporting

Install test dependencies:
```bash
pip install pytest pytest-mock pytest-cov
```

For detailed test plan and implementation guide, see `TEST_PLAN_GMAIL_STATS.md`.

### Local Testing

```bash
# Start local server
python main.py

# Test Hello World
curl http://localhost:8080/

# Test Gmail integration
curl http://localhost:8080/gmail-test
```

## CLI Usage

The main tool is `gmail_stats.py`, a command-line interface for analyzing Gmail data.

### Basic Usage

```bash
# Default analysis (full chronological scan)
python gmail_stats.py

# Random sampling with full metadata (recommended for accurate stats)
python gmail_stats.py --mode sample
# or legacy flag:
python gmail_stats.py --random-sample

# Custom sample size
python gmail_stats.py --mode sample --sample-size 2500
```

### Output Options

```bash
# Export to dated folder with CSVs and JSON summary
python gmail_stats.py --mode sample --out ./out

# Add HTML report
python gmail_stats.py --mode sample --out ./out --html

# Upload outputs to Google Cloud Storage
python gmail_stats.py --mode sample --out ./out --html --gcs-bucket gs://my-bucket/reports

# Start interactive web dashboard after analysis
python gmail_stats.py --mode sample --serve

# Specify custom port for web server
python gmail_stats.py --mode sample --serve 3000

# Skip SQLite database persistence (for cloud runs)
python gmail_stats.py --mode sample --skip-db
```

### Environment Variable Configuration

All CLI flags can be configured via environment variables (useful for Cloud Run):

```bash
# Run with env vars instead of CLI flags
MODE=sample SAMPLE_SIZE=5000 EXPORT_CSV=1 HTML_REPORT=1 SKIP_DB=1 python gmail_stats.py
```

### Output Files (with --out)

```
out/2025-12-26_1430/
├── top_senders_by_count.csv   # All senders sorted by message count
├── top_senders_by_size.csv    # All senders sorted by storage size
├── summary.json               # Run metadata and aggregate stats
└── report.html                # Static HTML dashboard (with --html)
```

### Web Server (with --serve)

The `--serve` flag starts a FastAPI server with an interactive dashboard:

- `GET /` - Interactive dashboard
- `GET /api/summary` - Run metadata and totals
- `GET /api/top?metric=count|size&level=domain|email&limit=50` - Top senders
- `GET /api/runs` - Historical analysis runs

Or run the server standalone (uses existing database):

```bash
python gmail_stats_server.py --port 8000
```

### Legacy CSV Export

```bash
# Original export format (timestamped files)
python gmail_stats.py --random-sample --export-csv --export-dir ./reports
```

### Utility Scripts
```bash
# Quick inspection and validation of API connectivity
python gmail_pull.py
```

For detailed documentation, see `CLAUDE.md`.

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

- `GET /` - Hello World + auth info
- `GET /gmail-test` - Lists Gmail labels for the authenticated user
- `GET /gmail-messages` - Lists recent messages (metadata only)
- `GET /health` - Health check

## Environment Variables

### CLI Configuration (for Cloud Run Jobs)

| Variable | Default | Description |
|----------|---------|-------------|
| `MODE` | `full` | Run mode: `full` (chronological) or `sample` (random) |
| `SAMPLE_SIZE` | `5000` | Number of messages to sample |
| `RANDOM_SAMPLE` | `false` | Legacy: set to `1` for sample mode |
| `EXPORT_CSV` | `false` | Export CSV files (`1`, `true`, `yes`) |
| `HTML_REPORT` | `false` | Generate HTML report |
| `OUTPUT_DIR` | `None` | Local output directory for exports |
| `GCS_BUCKET` | `None` | GCS bucket URI (e.g., `gs://bucket/path`) |
| `SKIP_DB` | `false` | Skip SQLite database persistence |
| `DAYS` | `30` | Number of days to analyze |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKEN_JSON` | `None` | OAuth token JSON string (from Secret Manager) |
| `TOKEN_PATH` | `token.json` | Path to token file |
| `CLIENT_SECRET_PATH` | `client_secret.json` | Path to client secret file |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `gmail_stats.db` | Path to SQLite database file |

### Server (legacy Flask app)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server port (set automatically by Cloud Run) |
| `USE_SERVICE_ACCOUNT` | `false` | Use service account authentication |
| `USER_EMAIL` | `None` | Email for service account impersonation |

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
- Verify `USER_EMAIL` is set correctly in environment or `.env`

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
