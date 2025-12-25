from __future__ import annotations

"""Gmail mailbox statistics dashboard.

This script authenticates with the Gmail API, samples recent messages, and
prints a small "dashboard" with label totals, daily volume, top senders, and
unread counts. It is designed as a practical mailbox inspection tool rather
than a reusable library.

Prerequisites:
  - OAuth client JSON (see get_creds) in the project root.
  - A token cache file (token.json) will be created on first run.

Run:
  python gmail_stats.py
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
import time
from typing import Dict, Iterable, List, Optional, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

LOG_EVERY = 100  # progress checkpoint cadence

logging.basicConfig(
    level=logging.INFO,
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


def get_message_metadata(service, msg_id: str) -> Tuple[str, str, int]:
    """Fetch minimal metadata for a single message.

    Args:
        service: Gmail API service resource from googleapiclient.discovery.build.
        msg_id: Gmail message ID.

    Returns:
        Tuple of (from_email, iso_date, sizeEstimate) for the message.
    """
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["From"],
    ).execute()

    # Build a simple header map for quick lookups.
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    from_email = extract_email(headers.get("From"))
    iso_date = iso_date_from_internal_ms(msg["internalDate"])
    size = int(msg.get("sizeEstimate", 0))
    return from_email, iso_date, size


def batch_get_metadata(service, msg_ids, batch_size=100):
    """Fetch metadata for multiple messages using batch requests with rate limiting."""
    results = []
    errors = []
    
    def callback(request_id, response, exception):
        if exception:
            log.error(f"Error fetching message {request_id}: {exception}")
            errors.append((request_id, exception))
            return
        results.append(response)
    
    for i, chunk in enumerate(chunked(msg_ids, batch_size), start=1):
        max_retries = 5
        retry_delay = 1.0  # Start with 1 second
        
        for attempt in range(max_retries):
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
                
                # Add small delay between batches to avoid rate limits
                if i % 10 == 0:  # Every 10 batches
                    log.info(f"Processed {i} batches ({len(results)} messages), pausing briefly...")
                    time.sleep(2)  # 2 second pause
                else:
                    time.sleep(0.5)  # 500ms between batches
                
                break  # Success, exit retry loop
                
            except HttpError as e:
                if e.resp.status == 403 and 'rateLimitExceeded' in str(e):
                    if attempt < max_retries - 1:
                        log.warning(f"Rate limit hit on batch {i}, retry {attempt+1}/{max_retries}, waiting {retry_delay:.1f}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        log.error(f"Rate limit exceeded after {max_retries} retries on batch {i}")
                        raise
                else:
                    log.error(f"HTTP error on batch {i}: {e}")
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

    # ----- Config for sampled stats -----
    # Keep this bounded: your mailbox is huge.
    DAYS = 30
    SAMPLE_MAX_IDS = 5000      # how many message IDs to examine for sender/day stats
    BATCH_SIZE = 50            # API-friendly batching

    since_dt = datetime.now(tz=timezone.utc) - timedelta(days=DAYS)
    since_query = f"newer_than:{DAYS}d"

    # ----- Tile 3: daily volume last N days (sampled/complete depending on volume) -----
    print_header(f"Daily Volume (last {DAYS} days)")

    log.info("Building 30-day sample: query=%r cap=%d", since_query, SAMPLE_MAX_IDS)
    list_start = time.perf_counter()
    ids = list_all_message_ids(service, query=since_query, label_ids=None, max_ids=SAMPLE_MAX_IDS)
    log.info("Message list fetch elapsed=%.2fs", time.perf_counter() - list_start)
    log.info("Collected %d message IDs. Starting metadata fetch...", len(ids))

    if not ids:
        print("No messages found for time window.")
        return

    # Pull metadata for ids and bucket by day + sender.
    by_day = Counter()
    by_sender = Counter()
    total_size = 0

    log.info("Fetching metadata in batches of %d...", BATCH_SIZE)
    batch_start = time.perf_counter()
    messages = batch_get_metadata(service, ids, batch_size=BATCH_SIZE)
    log.info("Batch fetch complete: elapsed=%.2fs", time.perf_counter() - batch_start)

    # Process all messages
    for msg in messages:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_email = extract_email(headers.get("From"))
        iso_date = iso_date_from_internal_ms(msg["internalDate"])
        size = int(msg.get("sizeEstimate", 0))
        
        by_day[iso_date] += 1
        by_sender[from_email] += 1
        total_size += size
    
    examined = len(messages)

    # Print last N days, even if some days are missing
    start_date = since_dt.date()
    end_date = datetime.now(tz=timezone.utc).date()
    d = start_date
    while d <= end_date:
        ds = d.isoformat()
        print(f"{ds}  {by_day.get(ds, 0):>5}")
        d += timedelta(days=1)

    approx_mb = total_size / (1024 * 1024)
    print(f"\nExamined messages: {examined} (cap={SAMPLE_MAX_IDS})")
    print(f"Approx total size of examined msgs: {approx_mb:.1f} MB")

    # ----- Tile 4: top senders (last N days) -----
    print_header(f"Top Senders (last {DAYS} days, examined {examined})")
    for sender, cnt in by_sender.most_common(25):
        print(f"{cnt:>5}  {sender}")

    # ----- Tile 5: quick “unread inbox” -----
    inbox = next((l for l in labels if l.get("id") == "INBOX" or l.get("name") == "INBOX"), None)
    if inbox:
        print_header("Unread")
        print(f"INBOX unread: {inbox.get('messagesUnread', 0)}")

    print("\nDone. ✅")


if __name__ == "__main__":
    main()
