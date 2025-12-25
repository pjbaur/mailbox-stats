# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gmail Statistics Dashboard - A command-line tool that analyzes Gmail mailbox data to provide insights and help identify cleanup opportunities. The tool generates a comprehensive dashboard showing:

- **Mailbox totals**: Overall message and thread counts
- **Label statistics**: Message counts across key labels (INBOX, SENT, DRAFT, SPAM, TRASH, IMPORTANT, STARRED)
- **Daily volume trends**: Message distribution over a configurable time window (default: 30 days)
- **Top senders**: Ranked list of email senders by message count
- **Size estimates**: Approximate total size of examined messages
- **Unread counts**: Quick overview of unread messages in INBOX

This tool is designed as a practical inspection utility rather than a reusable library. It uses sampling to handle large mailboxes efficiently while staying within Gmail API rate limits.

## Tech Stack

- **Python**: 3.12
- **Cloud Platform**: Google Cloud Platform (GCP)
- **API**: Gmail API v1 (read-only scope)
- **Key Libraries**:
  - `google-api-python-client`: Gmail API interaction
  - `google-auth-oauthlib`: OAuth2 authentication flow
  - `google-auth`: Credential management
  - `python-dotenv`: Environment variable management

## Project Structure

```
.
├── gmail_stats.py          # Main script with all functionality
├── client_secret.json      # OAuth2 credentials (user-provided, gitignored)
├── token.json             # Cached OAuth token (auto-generated, gitignored)
├── .env                   # Environment configuration (user-provided, gitignored)
├── .env.example           # Template for environment variables
├── gmail_stats.log        # Execution logs (auto-generated)
└── CLAUDE.md             # This file
```

## Setup & Prerequisites

### 1. Google Cloud Project Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable the Gmail API for your project
3. Create OAuth 2.0 credentials (Desktop application type)
4. Download the credentials JSON file and save as `client_secret.json` in the project root

### 2. Environment Configuration

Create a `.env` file in the project root (use `.env.example` as a template):

```bash
# Analysis Parameters
DAYS=30                    # Number of days to analyze
SAMPLE_MAX_IDS=5000       # Maximum messages to examine (0 = no limit)

# Rate Limiting
BATCH_DELAY=0.25          # Delay between batches (seconds)
BATCH_SIZE=50             # Batch size for API requests
SLEEP_BETWEEN_BATCHES=0.5 # Short sleep between batches (seconds)
SLEEP_EVERY_N_BATCHES=10  # Apply long sleep every N batches
SLEEP_LONG_DURATION=2.0   # Long sleep duration (seconds)

# Retry Configuration
MAX_RETRIES=5             # Maximum retry attempts for failed requests
INITIAL_RETRY_DELAY=1.0   # Initial retry delay (seconds)
MAX_RETRY_DELAY=60.0      # Maximum retry delay (seconds)

# Logging
LOG_LEVEL=INFO            # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_EVERY=100             # Log progress every N messages
```

### 3. Python Dependencies

Install required packages:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv
```

### 4. First Run Authentication

On first run, the script will:
1. Open a browser window for OAuth authentication
2. Request read-only Gmail access
3. Cache credentials in `token.json` for future runs

## Usage

```bash
python gmail_stats.py
```

The script will:
1. Authenticate (using cached token or OAuth flow)
2. Fetch mailbox profile and label statistics
3. Sample recent messages based on `DAYS` and `SAMPLE_MAX_IDS` configuration
4. Display a dashboard with statistics
5. Log detailed execution metrics to `gmail_stats.log`

### Example Output

```
====================================
Mailbox Stats Dashboard (Gmail)
====================================
Account: user@example.com
Total messages: 45,231
Total threads : 12,845

==================
Key Labels
==================
INBOX      msgs=  2,341 unread=    156 threads=  1,234
SENT       msgs= 12,456 unread=      0 threads=  8,901
...

====================================
Daily Volume (last 30 days)
====================================
2024-11-26    42
2024-11-27    38
...

Examined messages: 5000 (cap=5000)
Approx total size of examined msgs: 342.5 MB

====================================
Top Senders (last 30 days, examined 5000)
====================================
  421  newsletters@example.com
  318  notifications@github.com
...
```

## Architecture & Implementation Details

### Authentication Flow

- **OAuth 2.0**: Uses installed application flow
- **Scope**: `https://www.googleapis.com/auth/gmail.readonly` (read-only access)
- **Token caching**: Credentials cached in `token.json`, auto-refreshed when expired
- **Performance tracking**: Logs token acquisition time and source (cache, refresh, or new OAuth flow)

### API Request Strategy

The script uses several strategies to work efficiently within Gmail API limits:

1. **Batch Requests**: Groups multiple message.get() calls into batches of 10 (hard-coded for stability)
2. **Rate Limiting**: Implements multiple layers:
   - 0.25s delay between batches (configurable via `BATCH_DELAY`)
   - Longer pauses every N batches (configurable via `SLEEP_EVERY_N_BATCHES`)
   - Exponential backoff for rate limit errors (429, 403)
3. **Request Tracking**: Counts all API calls by endpoint, logged at exit
4. **Metadata Only**: Fetches message metadata (headers only) instead of full content for efficiency

### Message Sampling

To handle large mailboxes without exceeding quotas:
- Uses Gmail search query: `newer_than:{DAYS}d`
- Caps total messages examined at `SAMPLE_MAX_IDS` (default: 5000)
- Pages through results 500 at a time
- Logs progress every 50 batches during metadata fetch

### Error Handling

- **Rate limit handling**: Exponential backoff with configurable retry count (default: 5 retries)
- **Batch errors**: Individual message failures logged but don't stop processing
- **HTTP errors**: Logged with context (batch number, retry attempt)
- **Graceful degradation**: Continues with partial data if some requests fail

### Performance Characteristics

Based on typical execution:
- **Message listing**: ~1-2 seconds for 5,000 message IDs
- **Batch metadata fetch**: ~50-100 messages/second (depends on rate limits)
- **Total runtime**: ~1-2 minutes for 5,000 messages
- **API quota impact**: Moderate (typically <1,000 API calls for default config)

## Development Guidelines

### Code Style

- Type hints used throughout (Python 3.12+ style)
- Docstrings for all public functions
- Logging for all significant operations
- Constants in UPPER_CASE (loaded from environment)

### Logging Strategy

The script maintains detailed logs in `gmail_stats.log`:
- **INFO**: Progress updates, timing, configuration
- **WARNING**: Rate limit hits, retries
- **ERROR**: Failed requests, exceptions
- **DEBUG**: Detailed operation traces (when LOG_LEVEL=DEBUG)

Request statistics are always logged at script exit via `atexit.register()`.

### Testing Considerations

When testing or developing:

1. **Use smaller samples**: Set `SAMPLE_MAX_IDS=100` for quick iterations
2. **Adjust logging**: Set `LOG_LEVEL=DEBUG` for detailed traces
3. **Monitor rate limits**: Watch for 429/403 errors and adjust `BATCH_DELAY`
4. **Check log file**: Review `gmail_stats.log` for performance insights

### Extending Functionality

To add new statistics or features:

1. **New metrics**: Add calculation logic after line 375 (statistics aggregation)
2. **New dashboard sections**: Add after line 408 (unread section)
3. **Additional headers**: Extend `metadataHeaders` parameter at line 243
4. **Different time windows**: Modify query construction at line 350

### Gmail API Quotas & Limits

Be aware of:
- **Quota**: 1,000,000,000 quota units per day (typically not an issue)
- **Rate limit**: 250 quota units per second per user
- **Batch limit**: ~10 concurrent requests per batch (enforced in code)
- **Message size**: `sizeEstimate` is approximate, not exact

See [Gmail API usage limits](https://developers.google.com/gmail/api/reference/quota) for details.

## Known Limitations

1. **Sampling approach**: For mailboxes with >5,000 messages in the analysis window, results are sampled (configurable)
2. **Read-only**: Cannot modify messages, labels, or perform cleanup directly
3. **CLI only**: No web interface or GUI
4. **Single account**: Processes one Gmail account per execution
5. **Email regex**: Conservative pattern may miss some non-standard email formats
6. **Size estimates**: Gmail's `sizeEstimate` field is approximate

## Future Enhancement Ideas

- Add domain grouping (e.g., all `@github.com` senders combined)
- Export results to CSV/JSON for external analysis
- Add size-based sender ranking (largest storage consumers)
- Implement interactive cleanup suggestions
- Add filtering by label or custom queries
- Support batch processing of multiple accounts
- Create visualization graphs (with matplotlib)

## Security & Privacy Notes

- OAuth credentials in `client_secret.json` should be kept private (gitignored)
- Token file `token.json` contains access credentials (gitignored)
- Script requests read-only access (cannot modify or delete emails)
- No data is sent to external services (except Google Gmail API)
- Logs may contain email addresses; secure `gmail_stats.log` appropriately

## Troubleshooting

### "Access blocked" during OAuth
- Ensure Gmail API is enabled in your GCP project
- Verify OAuth consent screen is configured
- Check that `client_secret.json` matches your GCP project

### Rate limit errors persist
- Increase `BATCH_DELAY` (try 0.5 or 1.0)
- Decrease `BATCH_SIZE` (try 25)
- Increase `INITIAL_RETRY_DELAY` (try 2.0)

### "Token expired" errors
- Delete `token.json` and re-authenticate
- Check system clock is accurate

### Missing messages in results
- Increase `SAMPLE_MAX_IDS` (may increase runtime)
- Adjust `DAYS` to match desired time window
- Check Gmail search syntax in query construction

## Contributing

This is a personal utility script but contributions welcome:
1. Keep dependencies minimal
2. Maintain read-only API scope
3. Preserve CLI-first approach
4. Add tests for new features
5. Update this CLAUDE.md with architectural changes

## License

See the LICENSE file.