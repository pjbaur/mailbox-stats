from __future__ import annotations

"""Gmail mailbox statistics dashboard.

This script authenticates with the Gmail API, samples recent messages, and
prints a small "dashboard" with label totals, daily volume, top senders, and
unread counts. It is designed as a practical mailbox inspection tool rather
than a reusable library.

Prerequisites:
  - OAuth client JSON (see get_creds) in the project root.
  - A token cache file (token.json) will be created on first run.
  - A .env file with configuration (copy from .env.example)

Run:
  python gmail_stats.py
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import atexit
import json
import logging
import os
import random
import re
import time
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

# Load environment variables
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Configuration from environment
BATCH_DELAY = float(os.getenv("BATCH_DELAY", "0.25"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
DAYS = int(os.getenv("DAYS", "30"))
INITIAL_RETRY_DELAY = float(os.getenv("INITIAL_RETRY_DELAY", "1.0"))
LOG_EVERY = int(os.getenv("LOG_EVERY", "100"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
MAX_RETRY_DELAY = float(os.getenv("MAX_RETRY_DELAY", "60.0"))
SAMPLE_MAX_IDS = int(os.getenv("SAMPLE_MAX_IDS", "5000"))
SLEEP_BETWEEN_BATCHES = float(os.getenv("SLEEP_BETWEEN_BATCHES", "0.5"))
SLEEP_EVERY_N_BATCHES = int(os.getenv("SLEEP_EVERY_N_BATCHES", "10"))
SLEEP_LONG_DURATION = float(os.getenv("SLEEP_LONG_DURATION", "2.0"))

# Configure logging to use UTC timestamps
logging.Formatter.converter = time.gmtime

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s UTC %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("gmail_stats.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("gmail_stats")

# Conservative email matcher for From headers and sender stats.
EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)


def get_local_tz():
    """Get the local timezone as a timezone-aware object."""
    return datetime.now().astimezone().tzinfo


def get_local_tz_name():
    """Get the local timezone abbreviation (e.g., 'PST', 'EST')."""
    return datetime.now().astimezone().strftime('%Z')


def get_local_tz_offset():
    """Get the local timezone offset (e.g., '-0800', '+0530')."""
    return datetime.now().astimezone().strftime('%z')


REQUEST_TOTAL = 0
REQUESTS_BY_ENDPOINT: Dict[str, int] = defaultdict(int)


def count_request(endpoint: str, count: int = 1) -> None:
    global REQUEST_TOTAL
    REQUEST_TOTAL += count
    REQUESTS_BY_ENDPOINT[endpoint] += count


def execute_request(request, endpoint: str):
    count_request(endpoint)
    return request.execute()


def log_request_totals() -> None:
    if REQUEST_TOTAL == 0:
        log.info("API request totals: none")
        return
    log.info("API request totals: %d", REQUEST_TOTAL)
    for endpoint, count in sorted(REQUESTS_BY_ENDPOINT.items(), key=lambda x: (-x[1], x[0])):
        log.info("API request totals by endpoint: %s=%d", endpoint, count)


atexit.register(log_request_totals)


def get_creds() -> Credentials:
    """Load cached credentials or run the OAuth flow to create them.

    Returns:
        Credentials: Authorized Gmail API credentials with read-only scope.
    """
    t0 = time.perf_counter()
    source = "unknown"
    creds: Optional[Credentials] = None
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception:
        creds = None

    if creds and creds.valid:
        source = "cache"
        log.info("OAuth token acquisition: source=%s elapsed=%.2fs", source, time.perf_counter() - t0)
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        source = "refresh"
        log.info("OAuth token acquisition: source=%s elapsed=%.2fs", source, time.perf_counter() - t0)
        return creds

    # First-time auth: open a local server to complete OAuth and cache token.json.
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    source = "oauth_flow"
    log.info("OAuth token acquisition: source=%s elapsed=%.2fs", source, time.perf_counter() - t0)
    return creds


def extract_email(from_header: Optional[str]) -> str:
    """Extract a normalized email address from a From header value."""
    if not from_header:
        return "(unknown)"
    m = EMAIL_RE.search(from_header)
    return m.group(1).lower() if m else from_header.strip().lower()


def extract_domain(email: str) -> str:
    """Extract domain from email address.

    Args:
        email: Email address (already normalized by extract_email)

    Returns:
        Domain portion (e.g., 'example.com') or '(unknown)' if not extractable
    """
    if email == "(unknown)" or "@" not in email:
        return "(unknown)"
    return email.split("@")[1].lower()


def has_attachment(payload: dict) -> Optional[bool]:
    """Detect if message has attachments from payload structure.

    This works WITHOUT fetching attachment data - we only check metadata.

    Args:
        payload: Message payload dict from Gmail API (format="metadata")

    Returns:
        True if attachments detected, False if none, None if insufficient data
    """
    if not payload or "parts" not in payload:
        # Single-part message (plain text/HTML only) or insufficient metadata
        return False

    parts = payload.get("parts", [])
    for part in parts:
        # Check for filename (indicates attachment)
        if part.get("filename"):
            return True
        # Check for attachmentId in body (indicates external attachment)
        if part.get("body", {}).get("attachmentId"):
            return True
        # Recursively check nested parts (for multipart/mixed, etc.)
        if part.get("parts"):
            if has_attachment({"parts": part["parts"]}):
                return True

    return False


@dataclass
class SenderStats:
    """Aggregated statistics for a sender (domain or email)."""
    message_count: int = 0
    total_size_bytes: int = 0
    messages_with_attachments: int = 0
    emails: Dict[str, int] = None  # For domain-level: email -> count mapping

    def __post_init__(self):
        if self.emails is None:
            self.emails = {}


def iso_date_from_internal_ms(ms: str) -> str:
    """Convert Gmail internalDate (milliseconds since epoch) to YYYY-MM-DD in local timezone."""
    # internalDate is milliseconds since epoch UTC, convert to local timezone
    dt_utc = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    dt_local = dt_utc.astimezone()  # Convert to local timezone
    return dt_local.date().isoformat()


def chunked(xs: List[str], n: int) -> Iterable[List[str]]:
    """Yield list slices of size n (last chunk may be smaller)."""
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def list_all_message_ids(service, query: str, label_ids: Optional[List[str]], max_ids: int) -> List[str]:
    """Page through Gmail list() results until max_ids reached (or exhausted).

    Args:
        service: Gmail API service resource from googleapiclient.discovery.build.
        query: Gmail search query string (e.g., "newer_than:30d").
        label_ids: Optional list of label IDs to constrain the query.
        max_ids: Hard cap on how many IDs to return (0 or None means no cap).

    Returns:
        List of Gmail message IDs.
    """
    ids: List[str] = []
    page_token = None
    page = 0

    while True:
        page += 1
        log.info("Listing message IDs: page=%d collected=%d query=%r labels=%s",
                 page, len(ids), query, label_ids)

        resp = execute_request(
            service.users().messages().list(
            userId="me",
            q=query,
            labelIds=label_ids,
            maxResults=min(500, max_ids - len(ids)) if max_ids else 500,
            pageToken=page_token,
            ),
            "users.messages.list",
        )

        batch = resp.get("messages", [])
        log.info("List page=%d returned=%d nextPageToken=%s",
                 page, len(batch), "yes" if resp.get("nextPageToken") else "no")

        for m in batch:
            ids.append(m["id"])
            if max_ids and len(ids) >= max_ids:
                log.info("Reached max_ids=%d", max_ids)
                return ids

        page_token = resp.get("nextPageToken")
        if not page_token:
            log.info("Listing complete: total_ids=%d", len(ids))
            return ids


def list_all_message_ids_random(service, query: str, label_ids: Optional[List[str]], max_ids: int) -> List[str]:
    """Fetch ALL message IDs matching the query, then randomly sample max_ids.

    Unlike list_all_message_ids() which stops early, this fetches the complete
    result set first to enable unbiased random sampling.

    Args:
        service: Gmail API service instance
        query: Gmail search query string
        label_ids: Optional list of label IDs to filter by
        max_ids: Maximum number of IDs to return (0 = return all)

    Returns:
        List of randomly sampled message IDs (or all IDs if max_ids=0 or fewer IDs than max_ids)
    """
    all_ids: List[str] = []
    page_token = None
    page = 0

    log.info("Fetching ALL message IDs for random sampling (query=%r)", query)

    while True:
        page += 1
        resp = execute_request(
            service.users().messages().list(
                userId="me",
                q=query,
                labelIds=label_ids,
                maxResults=500,  # Fetch in chunks of 500
                pageToken=page_token,
            ),
            "users.messages.list",
        )

        if not resp:
            break

        messages = resp.get("messages", [])
        all_ids.extend(m["id"] for m in messages)

        if page % 10 == 0:
            log.info("Fetched %d message IDs so far (page %d)...", len(all_ids), page)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    log.info("Fetched %d total message IDs", len(all_ids))

    # Handle edge cases
    if max_ids == 0:
        # No limit - return all IDs
        return all_ids

    if len(all_ids) <= max_ids:
        # Fewer IDs than sample size - return all
        log.info("Available IDs (%d) <= sample size (%d), using all", len(all_ids), max_ids)
        return all_ids

    # Perform random sampling
    log.info("Randomly sampling %d IDs from %d available", max_ids, len(all_ids))
    sampled_ids = random.sample(all_ids, max_ids)

    return sampled_ids


def batch_get_metadata(service, msg_ids: List[str], full_metadata: bool = False) -> List[Dict]:
    """Fetch metadata for multiple messages using batch requests with rate limiting.

    Args:
        service: Gmail API service resource from googleapiclient.discovery.build.
        msg_ids: List of Gmail message IDs to fetch.
        full_metadata: If True, fetch all headers and payload structure. If False, fetch only "From" header.

    Returns:
        List of message metadata dictionaries.
    """
    results = []
    errors = []
    
    def callback(request_id, response, exception):
        if exception:
            log.error(f"Error fetching message {request_id}: {exception}")
            errors.append((request_id, exception))
            return
        results.append(response)
    
    # Use smaller batches to avoid "too many concurrent requests"
    # Gmail allows ~10 concurrent requests, so use batch size of 8-10
    SAFE_BATCH_SIZE = 10
    total_batches = (len(msg_ids) + SAFE_BATCH_SIZE - 1) // SAFE_BATCH_SIZE
    log.info(f"Fetching {len(msg_ids)} messages in {total_batches} batches of {SAFE_BATCH_SIZE}")
    start_time = time.monotonic()
    
    for i, chunk in enumerate(chunked(msg_ids, SAFE_BATCH_SIZE), start=1):
        retry_delay = INITIAL_RETRY_DELAY
        
        for attempt in range(MAX_RETRIES):
            try:
                batch = service.new_batch_http_request(callback=callback)
                
                for msg_id in chunk:
                    count_request("users.messages.get")
                    # Fetch all headers + payload structure if full_metadata, otherwise just "From"
                    if full_metadata:
                        batch.add(
                            service.users().messages().get(
                                userId="me",
                                id=msg_id,
                                format="metadata"
                                # No metadataHeaders = fetch all headers
                            )
                        )
                    else:
                        batch.add(
                            service.users().messages().get(
                                userId="me",
                                id=msg_id,
                                format="metadata",
                                metadataHeaders=["From"]
                            )
                        )
                
                batch.execute()
                count_request("batch.execute")
                
                # Progress logging
                if i % 50 == 0:
                    elapsed = time.monotonic() - start_time
                    msgs_per_sec = len(results) / elapsed if elapsed > 0 else 0.0
                    log.info(
                        f"Processed {i}/{total_batches} batches "
                        f"({len(results)} messages, {100*len(results)/len(msg_ids):.1f}%, "
                        f"{msgs_per_sec:.1f} msg/s)"
                    )
                
                # Small delay between batches
                time.sleep(BATCH_DELAY)  # between batches of 10 = ~100 msg/sec
                
                break  # Success, exit retry loop
                
            except HttpError as e:
                is_rate_limit = (
                    e.resp.status in [403, 429]
                )
                
                if is_rate_limit:
                    if attempt < MAX_RETRIES - 1:
                        log.warning(
                            f"Rate limit hit on batch {i}/{total_batches}, "
                            f"retry {attempt+1}/{MAX_RETRIES}, waiting {retry_delay:.1f}s..."
                        )
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                    else:
                        log.error(f"Rate limit exceeded after {MAX_RETRIES} retries on batch {i}")
                        raise
                else:
                    log.error(f"HTTP error on batch {i}: {e}")
                    raise
            except Exception as e:
                log.error(f"Unexpected error on batch {i}: {e}")
                raise
    
    log.info(f"Batch fetch complete: {len(results)} messages retrieved, {len(errors)} errors")
    return results


def label_counts(service) -> List[Dict]:
    """Fetch detailed label stats for all labels on the mailbox."""
    res = execute_request(service.users().labels().list(userId="me"), "users.labels.list")
    labels = res.get("labels", [])
    details = []
    for lab in labels:
        d = execute_request(
            service.users().labels().get(userId="me", id=lab["id"]),
            "users.labels.get",
        )
        details.append(d)
    # Sort: system labels first-ish by name
    details.sort(key=lambda x: x.get("name", "").lower())
    return details


def print_header(title: str) -> None:
    """Print a simple ASCII section header for the CLI output."""
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Gmail Statistics Dashboard - Analyze your Gmail mailbox"
    )
    parser.add_argument(
        '--random-sample',
        action='store_true',
        help='Use random sampling instead of chronological (newest first)'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        metavar='N',
        help='Number of messages to sample (default: SAMPLE_MAX_IDS from .env, typically 5000). Use 0 for unlimited.'
    )
    parser.add_argument(
        '--export-csv',
        action='store_true',
        help='Export statistics to CSV files (3 files: domain stats, email stats, run metadata)'
    )
    parser.add_argument(
        '--export-dir',
        type=str,
        default='.',
        metavar='DIR',
        help='Directory for CSV exports (default: current directory)'
    )
    parser.add_argument(
        '--out',
        type=str,
        metavar='DIR',
        help='Output directory for all artifacts (CSVs, JSON, HTML). Creates dated subfolder automatically.'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate an HTML report (report.html) in the output directory'
    )
    parser.add_argument(
        '--serve',
        nargs='?',
        const=8000,
        type=int,
        metavar='PORT',
        help='Start web server after analysis (default port: 8000)'
    )
    return parser.parse_args()


def main(args=None) -> None:
    """Fetch and print the mailbox stats dashboard."""
    if args is None:
        args = parse_args()

    # Track run timing for summary.json
    run_started = datetime.now(timezone.utc).isoformat()

    # Determine effective sample size: CLI arg takes precedence over env var
    sample_size = args.sample_size if args.sample_size is not None else SAMPLE_MAX_IDS

    log.info(f"Configuration: DAYS={DAYS}, SAMPLE_MAX_IDS={SAMPLE_MAX_IDS}, BATCH_SIZE={BATCH_SIZE}")
    if args.sample_size is not None:
        log.info(f"Sample size overridden by CLI: {sample_size}")
    log.info(f"Rate limiting: SLEEP_BETWEEN_BATCHES={SLEEP_BETWEEN_BATCHES}s, SLEEP_LONG_DURATION={SLEEP_LONG_DURATION}s every {SLEEP_EVERY_N_BATCHES} batches")
    log.info(f"Retry config: MAX_RETRIES={MAX_RETRIES}, INITIAL_RETRY_DELAY={INITIAL_RETRY_DELAY}s, MAX_RETRY_DELAY={MAX_RETRY_DELAY}s")
    
    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    # ----- Tile 1: profile totals -----
    profile = execute_request(service.users().getProfile(userId="me"), "users.getProfile")
    email = profile.get("emailAddress")
    total_msgs = profile.get("messagesTotal", 0)
    total_threads = profile.get("threadsTotal", 0)

    log.info(
        "[MAILBOX_PROFILE] account=%s total_messages=%d total_threads=%d",
        email, total_msgs, total_threads
    )

    # Get timezone name for report header
    tz_name = get_local_tz_name()
    generated_time = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')

    # Print simplified executive memo style header
    print("=" * 50)
    print("Mailbox Stats Report")
    print(f"Generated: {generated_time} {tz_name}")
    print("=" * 50)
    print(f"\nAccount: {email}")
    print(f"Total messages in mailbox: {total_msgs:,}")

    # Get labels for later use (inbox unread count)
    labels = label_counts(service)

    since_dt = datetime.now().astimezone() - timedelta(days=DAYS)
    since_query = f"newer_than:{DAYS}d"

    # Get timezone offset for logging
    tz_offset = get_local_tz_offset()

    log.info(
        "[DAILY_VOLUME_RANGE] timezone=%s(UTC%s) start=%s end=%s days=%d query=%r",
        tz_name,
        tz_offset,
        since_dt.isoformat(),
        datetime.now().astimezone().isoformat(),
        DAYS,
        since_query
    )

    # Log sampling method for auditability
    sampling_method = "random" if args.random_sample else "chronological"
    log.info(
        "[SAMPLING_METHOD] method=%s query=%r max_ids=%d days=%d",
        sampling_method,
        since_query,
        sample_size,
        DAYS
    )

    log.info("Building sample: query=%r cap=%d", since_query, sample_size)
    list_start = time.perf_counter()
    # Build sample using selected sampling strategy
    if args.random_sample:
        ids = list_all_message_ids_random(service, since_query, None, sample_size)
    else:
        ids = list_all_message_ids(service, query=since_query, label_ids=None, max_ids=sample_size)
    log.info("Message list fetch elapsed=%.2fs", time.perf_counter() - list_start)
    log.info("Collected %d message IDs. Starting metadata fetch...", len(ids))

    was_capped = len(ids) >= sample_size if sample_size > 0 else False
    coverage_pct = (len(ids) / total_msgs * 100) if total_msgs > 0 else 0
    log.info(
        "[SAMPLING_INFO] requested=%s returned=%d capped=%s coverage=%.1f%%",
        sample_size if sample_size > 0 else "unlimited",
        len(ids),
        was_capped,
        coverage_pct
    )

    if not ids:
        print("No messages found for time window.")
        return

    # Fetch all metadata using batching
    # When using random sampling, fetch complete metadata (all headers + payload structure)
    metadata_scope = "all headers + payload structure" if args.random_sample else "From header only"
    log.info(f"Fetching metadata: scope={metadata_scope}")
    batch_start = time.perf_counter()
    messages = batch_get_metadata(service, ids, full_metadata=args.random_sample)
    batch_elapsed = time.perf_counter() - batch_start
    log.info(f"Batch metadata fetch complete: elapsed={batch_elapsed:.2f}s, rate={len(messages)/batch_elapsed:.1f} msg/s")

    # Log complete message metadata when using random sampling
    if args.random_sample:
        log.info("[MESSAGE_METADATA_START] Logging %d messages with complete metadata", len(messages))
        for i, msg in enumerate(messages, 1):
            # Log the complete message metadata as JSON
            log.info("[MESSAGE_METADATA] msg_num=%d/%d data=%s", i, len(messages), json.dumps(msg, default=str))
        log.info("[MESSAGE_METADATA_END] Logged %d messages", len(messages))

    # Aggregate statistics
    by_day = Counter()
    total_size = 0

    # Rich sender statistics
    domain_stats: Dict[str, SenderStats] = defaultdict(SenderStats)
    email_stats: Dict[str, SenderStats] = defaultdict(SenderStats)

    # Track if attachment data is available (only in random sample mode)
    has_attachment_data = args.random_sample

    # Log timezone conversion example with first message
    if messages:
        first_msg_ms = messages[0]["internalDate"]
        example_utc = datetime.fromtimestamp(int(first_msg_ms) / 1000, tz=timezone.utc)
        example_local = example_utc.astimezone()
        log.info(
            "[TIMEZONE_EXAMPLE] utc=%s local=%s timezone=%s offset=%s",
            example_utc.isoformat(),
            example_local.isoformat(),
            tz_name,
            tz_offset
        )

    for msg in messages:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_email = extract_email(headers.get("From"))
        domain = extract_domain(from_email)
        iso_date = iso_date_from_internal_ms(msg["internalDate"])
        size = int(msg.get("sizeEstimate", 0))

        # Detect attachments (only possible with full metadata)
        has_attach = has_attachment(msg.get("payload", {})) if has_attachment_data else None

        # Update daily volume (unchanged)
        by_day[iso_date] += 1
        total_size += size

        # Update email-level stats
        email_stats[from_email].message_count += 1
        email_stats[from_email].total_size_bytes += size
        if has_attach:
            email_stats[from_email].messages_with_attachments += 1

        # Update domain-level stats
        domain_stats[domain].message_count += 1
        domain_stats[domain].total_size_bytes += size
        if has_attach:
            domain_stats[domain].messages_with_attachments += 1
        domain_stats[domain].emails[from_email] = domain_stats[domain].emails.get(from_email, 0) + 1

    # Calculate date range for display and logging
    start_date = since_dt.date()
    end_date = datetime.now().astimezone().date()

    # Log aggregation results
    days_with_data = len([d for d in by_day.values() if d > 0])
    date_range_str = f"{start_date.isoformat()}...{end_date.isoformat()}"

    # Sort email senders by message count for logging
    top_25_emails = sorted(
        email_stats.items(),
        key=lambda x: x[1].message_count,
        reverse=True
    )[:25]

    # Sort domains by message count for logging
    top_25_domains = sorted(
        domain_stats.items(),
        key=lambda x: x[1].message_count,
        reverse=True
    )[:25]

    log.info(
        "[DAILY_VOLUME_RESULT] query=%r timezone=%s date_range=%s total_messages=%d "
        "days_examined=%d days_with_data=%d size_mb=%.1f sample_cap=%d",
        since_query,
        tz_name,
        date_range_str,
        len(messages),
        (end_date - start_date).days + 1,
        days_with_data,
        total_size / (1024 * 1024),
        sample_size
    )

    log.info(
        "[TOP_SENDERS_RESULT] query=%r timezone=%s total_messages=%d unique_emails=%d unique_domains=%d "
        "top_email=%s(%d) top_domain=%s(%d) top_25_email_total=%d",
        since_query,
        tz_name,
        len(messages),
        len(email_stats),
        len(domain_stats),
        top_25_emails[0][0] if top_25_emails else 'N/A',
        top_25_emails[0][1].message_count if top_25_emails else 0,
        top_25_domains[0][0] if top_25_domains else 'N/A',
        top_25_domains[0][1].message_count if top_25_domains else 0,
        sum(stats.message_count for _, stats in top_25_emails)
    )

    # Save to database for historical tracking
    from gmail_stats_db import save_run

    log.info("Saving run to database...")
    db_save_start = time.perf_counter()
    run_id = save_run(
        account_email=email,
        days_analyzed=DAYS,
        sample_size=sample_size,
        sampling_method=sampling_method,
        messages_examined=len(messages),
        total_mailbox_messages=total_msgs,
        domain_stats=dict(domain_stats),  # Convert defaultdict to dict
        email_stats=dict(email_stats)
    )
    db_save_elapsed = time.perf_counter() - db_save_start
    log.info(f"Database save complete: run_id={run_id} elapsed={db_save_elapsed:.2f}s")

    # Export to CSV if requested
    if getattr(args, 'export_csv', False):
        from gmail_stats_export import export_to_csv
        from pathlib import Path

        log.info("Exporting to CSV...")
        export_start = time.perf_counter()

        domain_path, email_path, metadata_path = export_to_csv(
            domain_stats=dict(domain_stats),
            email_stats=dict(email_stats),
            run_metadata={
                'account_email': email,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'days_analyzed': DAYS,
                'sample_size': sample_size,
                'sampling_method': sampling_method,
                'messages_examined': len(messages),
                'total_mailbox_messages': total_msgs,
                'total_size_mb': total_size / (1024 * 1024)
            },
            output_dir=Path(getattr(args, 'export_dir', '.'))
        )

        export_elapsed = time.perf_counter() - export_start
        log.info(f"CSV export complete: elapsed={export_elapsed:.2f}s")
        print(f"\nCSV exports written:")
        print(f"  Domain stats: {domain_path}")
        print(f"  Email stats:  {email_path}")
        print(f"  Run metadata: {metadata_path}")

    # --out: Export to dated subfolder with count/size CSVs and summary.json
    if getattr(args, 'out', None):
        from gmail_stats_export import (
            create_dated_output_dir, export_top_senders_csv,
            export_daily_volume_csv, export_summary_json
        )

        log.info("Exporting to dated output directory...")
        export_start = time.perf_counter()

        # Create dated subfolder
        output_dir = create_dated_output_dir(args.out)

        # Track run_finished time
        run_finished = datetime.now(timezone.utc).isoformat()

        # Build run metadata for summary.json
        run_metadata = {
            'account_email': email,
            'run_started': run_started,
            'run_finished': run_finished,
            'days_analyzed': DAYS,
            'sample_size': sample_size,
            'sampling_method': sampling_method,
            'messages_examined': len(messages),
            'total_mailbox_messages': total_msgs,
            'total_bytes': total_size
        }

        # Export count/size CSVs
        count_path, size_path = export_top_senders_csv(
            domain_stats=dict(domain_stats),
            email_stats=dict(email_stats),
            output_dir=output_dir
        )

        # Export daily volume CSV
        volume_path = export_daily_volume_csv(
            daily_volume=dict(by_day),
            output_dir=output_dir
        )

        # Export summary.json
        summary_path = export_summary_json(
            run_metadata=run_metadata,
            domain_stats=dict(domain_stats),
            email_stats=dict(email_stats),
            output_dir=output_dir
        )

        # Generate HTML report if requested
        if getattr(args, 'html', False):
            from gmail_stats_html import generate_html_report

            html_path = generate_html_report(
                domain_stats=dict(domain_stats),
                email_stats=dict(email_stats),
                run_metadata=run_metadata,
                output_dir=output_dir
            )
            log.info(f"HTML report generated: {html_path}")

        export_elapsed = time.perf_counter() - export_start
        log.info(f"Dated export complete: elapsed={export_elapsed:.2f}s dir={output_dir}")
        print(f"\nOutput written to: {output_dir}/")
        print(f"  {count_path.name}")
        print(f"  {size_path.name}")
        print(f"  {volume_path.name}")
        print(f"  {summary_path.name}")
        if getattr(args, 'html', False):
            print(f"  report.html")

    # Print analysis summary
    print(f"\nTotal messages scanned: {len(messages):,}")
    print(f"Time window: Last {DAYS} days")

    # Top senders by message count
    print("\nTop Senders by Message Count")
    print("-" * 40)

    # Domain-level ranking
    print("\nBy Domain (Top 20):")
    sorted_domains = sorted(
        domain_stats.items(),
        key=lambda x: x[1].message_count,
        reverse=True
    )[:20]

    for domain, stats in sorted_domains:
        email_count = len(stats.emails)
        pct = (stats.message_count / len(messages) * 100) if len(messages) > 0 else 0
        print(f"  {stats.message_count:>5}  {domain:<40} "
              f"({email_count} {'address' if email_count == 1 else 'addresses'}, {pct:.1f}%)")

    # Email-level ranking
    print("\nBy Email Address (Top 20):")
    sorted_emails = sorted(
        email_stats.items(),
        key=lambda x: x[1].message_count,
        reverse=True
    )[:20]

    for email_addr, stats in sorted_emails:
        pct = (stats.message_count / len(messages) * 100) if len(messages) > 0 else 0
        print(f"  {stats.message_count:>5}  {email_addr:<50} ({pct:.1f}%)")

    # Top senders by storage size
    print("\nTop Senders by Total Size")
    print("-" * 40)

    print("\nBy Domain (Top 20):")
    sorted_domains_size = sorted(
        domain_stats.items(),
        key=lambda x: x[1].total_size_bytes,
        reverse=True
    )[:20]

    for domain, stats in sorted_domains_size:
        size_mb = stats.total_size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024
        pct = (stats.total_size_bytes / total_size * 100) if total_size > 0 else 0

        if size_gb >= 1.0:
            print(f"  {size_gb:>6.2f} GB  {domain:<40} ({pct:.1f}% of examined)")
        else:
            print(f"  {size_mb:>6.1f} MB  {domain:<40} ({pct:.1f}% of examined)")

    # Top 10 share of total size
    top_10_size = sum(stats.total_size_bytes for _, stats in sorted_domains_size[:10])
    top_10_pct = (top_10_size / total_size * 100) if total_size > 0 else 0
    print(f"\nTop 10 domains account for {top_10_pct:.1f}% of examined storage")

    # Attachment statistics (if available)
    if has_attachment_data:
        print("\nAttachment Summary")
        print("-" * 40)

        # Overall attachment summary
        total_with_attachments = sum(s.messages_with_attachments for s in email_stats.values())
        overall_attach_pct = (total_with_attachments / len(messages) * 100) if len(messages) > 0 else 0
        print(f"\nAttachments: {overall_attach_pct:.1f}% of messages ({total_with_attachments:,} of {len(messages):,})")

        print("\nBy Domain (Top 20 by attachment count):")
        sorted_attach = sorted(
            [(d, s) for d, s in domain_stats.items() if s.messages_with_attachments > 0],
            key=lambda x: x[1].messages_with_attachments,
            reverse=True
        )[:20]

        for domain, stats in sorted_attach:
            attach_pct = (stats.messages_with_attachments / stats.message_count * 100) if stats.message_count > 0 else 0
            print(f"  {stats.messages_with_attachments:>5} / {stats.message_count:<5} "
                  f"({attach_pct:>4.1f}%)  {domain}")
    else:
        print("\nAttachment Summary")
        print("-" * 40)
        print("\n[Attachment statistics unavailable - use --random-sample to enable]")

    print("\nDone.")

    # Start web server if requested
    if getattr(args, 'serve', None):
        port = args.serve
        print(f"\nStarting web server at http://127.0.0.1:{port}")
        print("Press Ctrl+C to stop...")

        import uvicorn
        from gmail_stats_server import app

        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    args = parse_args()
    main(args)
