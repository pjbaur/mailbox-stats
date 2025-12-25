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
import logging
import os
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
DAYS = int(os.getenv("DAYS", "30"))
SAMPLE_MAX_IDS = int(os.getenv("SAMPLE_MAX_IDS", "5000"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
SLEEP_BETWEEN_BATCHES = float(os.getenv("SLEEP_BETWEEN_BATCHES", "0.5"))
SLEEP_EVERY_N_BATCHES = int(os.getenv("SLEEP_EVERY_N_BATCHES", "10"))
SLEEP_LONG_DURATION = float(os.getenv("SLEEP_LONG_DURATION", "2.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
INITIAL_RETRY_DELAY = float(os.getenv("INITIAL_RETRY_DELAY", "1.0"))
MAX_RETRY_DELAY = float(os.getenv("MAX_RETRY_DELAY", "60.0"))
LOG_EVERY = int(os.getenv("LOG_EVERY", "100"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("gmail_stats.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("gmail_stats")

# Conservative email matcher for From headers and sender stats.
EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)


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
    """Convert Gmail internalDate (milliseconds since epoch) to YYYY-MM-DD."""
    # internalDate is milliseconds since epoch UTC
    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    return dt.date().isoformat()


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

        resp = service.users().messages().list(
            userId="me",
            q=query,
            labelIds=label_ids,
            maxResults=min(500, max_ids - len(ids)) if max_ids else 500,
            pageToken=page_token,
        ).execute()

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


def batch_get_metadata(service, msg_ids: List[str]) -> List[Dict]:
    """Fetch metadata for multiple messages using batch requests with rate limiting.
    
    Args:
        service: Gmail API service resource from googleapiclient.discovery.build.
        msg_ids: List of Gmail message IDs to fetch.
    
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
    
    for i, chunk in enumerate(chunked(msg_ids, SAFE_BATCH_SIZE), start=1):
        retry_delay = INITIAL_RETRY_DELAY
        
        for attempt in range(MAX_RETRIES):
            try:
                batch = service.new_batch_http_request(callback=callback)
                
                for msg_id in chunk:
                    batch.add(
                        service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="metadata",
                            metadataHeaders=["From"]
                        )
                    )
                
                batch.execute()
                
                # Progress logging
                if i % 50 == 0:
                    log.info(f"Processed {i}/{total_batches} batches ({len(results)} messages, {100*len(results)/len(msg_ids):.1f}%)")
                
                # Small delay between batches
                time.sleep(0.05)  # 100ms between batches of 10 = ~100 msg/sec
                
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
    res = service.users().labels().list(userId="me").execute()
    labels = res.get("labels", [])
    details = []
    for lab in labels:
        d = service.users().labels().get(userId="me", id=lab["id"]).execute()
        details.append(d)
    # Sort: system labels first-ish by name
    details.sort(key=lambda x: x.get("name", "").lower())
    return details


def print_header(title: str) -> None:
    """Print a simple ASCII section header for the CLI output."""
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def main() -> None:
    """Fetch and print the mailbox stats dashboard."""
    log.info(f"Configuration: DAYS={DAYS}, SAMPLE_MAX_IDS={SAMPLE_MAX_IDS}, BATCH_SIZE={BATCH_SIZE}")
    log.info(f"Rate limiting: SLEEP_BETWEEN_BATCHES={SLEEP_BETWEEN_BATCHES}s, SLEEP_LONG_DURATION={SLEEP_LONG_DURATION}s every {SLEEP_EVERY_N_BATCHES} batches")
    log.info(f"Retry config: MAX_RETRIES={MAX_RETRIES}, INITIAL_RETRY_DELAY={INITIAL_RETRY_DELAY}s, MAX_RETRY_DELAY={MAX_RETRY_DELAY}s")
    
    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    # ----- Tile 1: profile totals -----
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress")
    total_msgs = profile.get("messagesTotal", 0)
    total_threads = profile.get("threadsTotal", 0)

    print_header("Mailbox Stats Dashboard (Gmail)")
    print(f"Account: {email}")
    print(f"Total messages: {total_msgs}")
    print(f"Total threads : {total_threads}")

    # ----- Tile 2: key label counts -----
    print_header("Key Labels")
    labels = label_counts(service)
    key_names = {"INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "IMPORTANT", "STARRED"}
    key = [l for l in labels if l.get("name") in key_names]

    for l in key:
        print(
            f"{l['name']:<10} "
            f"msgs={l.get('messagesTotal', 0):>7} "
            f"unread={l.get('messagesUnread', 0):>7} "
            f"threads={l.get('threadsTotal', 0):>7}"
        )

    since_dt = datetime.now(tz=timezone.utc) - timedelta(days=DAYS)
    since_query = f"newer_than:{DAYS}d"

    # ----- Tile 3: daily volume last N days (sampled/complete depending on volume) -----
    print_header(f"Daily Volume (last {DAYS} days)")

    log.info("Building sample: query=%r cap=%d", since_query, SAMPLE_MAX_IDS)
    list_start = time.perf_counter()
    ids = list_all_message_ids(service, query=since_query, label_ids=None, max_ids=SAMPLE_MAX_IDS)
    log.info("Message list fetch elapsed=%.2fs", time.perf_counter() - list_start)
    log.info("Collected %d message IDs. Starting metadata fetch...", len(ids))

    if not ids:
        print("No messages found for time window.")
        return

    # Fetch all metadata using batching
    batch_start = time.perf_counter()
    messages = batch_get_metadata(service, ids)
    batch_elapsed = time.perf_counter() - batch_start
    log.info(f"Batch metadata fetch complete: elapsed={batch_elapsed:.2fs}, rate={len(messages)/batch_elapsed:.1f} msg/s")

    # Aggregate statistics
    by_day = Counter()
    by_sender = Counter()
    total_size = 0

    for msg in messages:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_email = extract_email(headers.get("From"))
        iso_date = iso_date_from_internal_ms(msg["internalDate"])
        size = int(msg.get("sizeEstimate", 0))
        
        by_day[iso_date] += 1
        by_sender[from_email] += 1
        total_size += size

    # Print last N days, even if some days are missing
    start_date = since_dt.date()
    end_date = datetime.now(tz=timezone.utc).date()
    d = start_date
    while d <= end_date:
        ds = d.isoformat()
        print(f"{ds}  {by_day.get(ds, 0):>5}")
        d += timedelta(days=1)

    approx_mb = total_size / (1024 * 1024)
    print(f"\nExamined messages: {len(messages)} (cap={SAMPLE_MAX_IDS})")
    print(f"Approx total size of examined msgs: {approx_mb:.1f} MB")

    # ----- Tile 4: top senders (last N days) -----
    print_header(f"Top Senders (last {DAYS} days, examined {len(messages)})")
    for sender, cnt in by_sender.most_common(25):
        print(f"{cnt:>5}  {sender}")

    # ----- Tile 5: quick "unread inbox" -----
    inbox = next((l for l in labels if l.get("id") == "INBOX" or l.get("name") == "INBOX"), None)
    if inbox:
        print_header("Unread")
        print(f"INBOX unread: {inbox.get('messagesUnread', 0)}")

    print("\nDone. ✅")


if __name__ == "__main__":
    main()