# Gmail Stats Dashboard

A Python script to analyze your Gmail mailbox with batch processing, rate limiting, and configurable parameters.

## Features

- **Batch Processing**: Fetches up to 100 messages per API call for 20-25x speedup
- **Rate Limit Handling**: Automatic retry with exponential backoff for 403/429 errors
- **Configurable**: All parameters via `.env` file
- **Dashboard Output**: 
  - Account overview
  - Label statistics
  - Daily volume charts
  - Top senders analysis
  - Unread counts

## Setup

1. **Install dependencies**:
   ```bash
   pip install --break-system-packages google-auth-oauthlib google-api-python-client python-dotenv
   ```

2. **Get Gmail API credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project and enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download as `client_secret.json`

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

4. **Run**:
   ```bash
   python gmail_stats.py
   ```

## Configuration (.env)

### Batch & Rate Limiting
- `BATCH_SIZE=50` - Messages per batch (max 100, recommend 25-50)
- `BATCH_SLEEP_SECONDS=0.5` - Delay between batches
- `BATCH_PAUSE_EVERY=10` - Pause every N batches
- `BATCH_PAUSE_SECONDS=2.0` - Length of pause
- `MAX_RETRIES=5` - Max retry attempts on rate limit
- `INITIAL_RETRY_DELAY=1.0` - Starting backoff delay
- `RETRY_BACKOFF_MULTIPLIER=2.0` - Exponential backoff factor

### Analysis
- `ANALYSIS_DAYS=30` - How many days to analyze
- `SAMPLE_MAX_IDS=5000` - Max messages to examine
- `TOP_SENDERS_LIMIT=25` - Top N senders to display

### Logging
- `LOG_LEVEL=INFO` - Logging verbosity
- `LOG_FILE=gmail_stats.log` - Log file location
- `LOG_EVERY=100` - Progress log frequency

## Tuning for Rate Limits

If you're hitting rate limits:

**Conservative** (recommended start):
```env
BATCH_SIZE=25
BATCH_SLEEP_SECONDS=1.0
BATCH_PAUSE_EVERY=5
BATCH_PAUSE_SECONDS=3.0
```

**Aggressive** (if conservative works well):
```env
BATCH_SIZE=100
BATCH_SLEEP_SECONDS=0.1
BATCH_PAUSE_EVERY=20
BATCH_PAUSE_SECONDS=1.0
```

## Error Handling

The script handles:
- **403 Quota Exceeded**: Automatic exponential backoff retry
- **429 Too Many Requests**: Same retry mechanism
- Both errors are caught and retried up to `MAX_RETRIES` times

## Performance

- **Before batching**: 5,000 messages × 100ms = ~8-10 minutes
- **After batching**: 50 batches × 500ms = ~25-30 seconds
- **Speedup**: 20-25x faster

## Output

```
=================================
Mailbox Stats Dashboard (Gmail)
=================================
Account: your.email@gmail.com
Total messages: 123456
Total threads : 45678

=================
Key Labels
=================
INBOX      msgs=  12345 unread=    123 threads=   5678
SENT       msgs=   8901 unread=      0 threads=   3456
...

=================================
Daily Volume (last 30 days)
=================================
2024-11-25    156
2024-11-26    234
...

=================================
Top Senders (last 30 days)
=================================
  234  notifications@github.com
  156  team@company.com
...
```
