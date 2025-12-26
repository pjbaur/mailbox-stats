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
    return parser.parse_args()


def main(args=None) -> None:
    """Fetch and print the mailbox stats dashboard."""
    if args is None:
        args = parse_args()

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

    print_header("Mailbox Stats Dashboard (Gmail)")
    print(f"Account: {email}")
    print(f"Total messages: {total_msgs}")
    print(f"Total threads : {total_threads}")

    # ----- Tile 2: key label counts -----
    print_header("Key Labels")
    labels = label_counts(service)
    key_names = {"INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "IMPORTANT", "STARRED"}
    key = [l for l in labels if l.get("name") in key_names]

    log.info(
        "[LABEL_STATS] total_labels=%d key_labels=%s",
        len(labels),
        ','.join([l.get('name', l.get('id', '?')) for l in key])
    )

    for l in key:
        log.info(
            "[LABEL_DETAIL] label=%s messages=%d unread=%d threads=%d",
            l.get('name', l.get('id')),
            l.get('messagesTotal', 0),
            l.get('messagesUnread', 0),
            l.get('threadsTotal', 0)
        )
        print(
            f"{l['name']:<10} "
            f"msgs={l.get('messagesTotal', 0):>7} "
            f"unread={l.get('messagesUnread', 0):>7} "
            f"threads={l.get('threadsTotal', 0):>7}"
        )

    since_dt = datetime.now().astimezone() - timedelta(days=DAYS)
    since_query = f"newer_than:{DAYS}d"

    # ----- Tile 3: daily volume last N days (sampled/complete depending on volume) -----
    tz_name = get_local_tz_name()
    tz_offset = get_local_tz_offset()
    print_header(f"Daily Volume (last {DAYS} days, {tz_name})")

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
    by_sender = Counter()
    total_size = 0

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
        iso_date = iso_date_from_internal_ms(msg["internalDate"])
        size = int(msg.get("sizeEstimate", 0))

        by_day[iso_date] += 1
        by_sender[from_email] += 1
        total_size += size

    # Calculate date range for display and logging
    start_date = since_dt.date()
    end_date = datetime.now().astimezone().date()

    # Log aggregation results
    days_with_data = len([d for d in by_day.values() if d > 0])
    date_range_str = f"{start_date.isoformat()}...{end_date.isoformat()}"
    top_25 = by_sender.most_common(25)

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
        "[TOP_SENDERS_RESULT] query=%r timezone=%s total_messages=%d unique_senders=%d "
        "top_sender=%s(%d) top_25_total=%d",
        since_query,
        tz_name,
        len(messages),
        len(by_sender),
        top_25[0][0] if top_25 else 'N/A',
        top_25[0][1] if top_25 else 0,
        sum(cnt for _, cnt in top_25)
    )

    # Print last N days, even if some days are missing
    d = start_date
    while d <= end_date:
        ds = d.isoformat()
        print(f"{ds}  {by_day.get(ds, 0):>5}")
        d += timedelta(days=1)

    approx_mb = total_size / (1024 * 1024)
    print(f"\nExamined messages: {len(messages)} (cap={sample_size})")
    print(f"Approx total size of examined msgs: {approx_mb:.1f} MB")

    # ----- Tile 4: top senders (last N days) -----
    print_header(f"Top Senders (last {DAYS} days, {tz_name}, examined {len(messages)})")
    for sender, cnt in by_sender.most_common(25):
        print(f"{cnt:>5}  {sender}")

    # ----- Tile 5: quick "unread inbox" -----
    inbox = next((l for l in labels if l.get("id") == "INBOX" or l.get("name") == "INBOX"), None)
    if inbox:
        log.info(
            "[UNREAD_INBOX] label=INBOX unread=%d total=%d threads=%d",
            inbox.get('messagesUnread', 0),
            inbox.get('messagesTotal', 0),
            inbox.get('threadsTotal', 0)
        )
        print_header("Unread")
        print(f"INBOX unread: {inbox.get('messagesUnread', 0)}")

    print("\nDone. ✅")


if __name__ == "__main__":
    args = parse_args()
    main(args)
