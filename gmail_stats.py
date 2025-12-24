from __future__ import annotations

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

EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)


def get_creds() -> Credentials:
    creds: Optional[Credentials] = None
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception:
        creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def extract_email(from_header: Optional[str]) -> str:
    if not from_header:
        return "(unknown)"
    m = EMAIL_RE.search(from_header)
    return m.group(1).lower() if m else from_header.strip().lower()


def iso_date_from_internal_ms(ms: str) -> str:
    # internalDate is milliseconds since epoch UTC
    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    return dt.date().isoformat()


def chunked(xs: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def list_all_message_ids(service, query: str, label_ids: Optional[List[str]], max_ids: int) -> List[str]:
    """Page through Gmail list() results until max_ids reached (or exhausted)."""
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
    """
    Returns (from_email, iso_date, sizeEstimate) for a message.
    Uses metadata format for speed and avoids bodies.
    """
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["From"],
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    from_email = extract_email(headers.get("From"))
    iso_date = iso_date_from_internal_ms(msg["internalDate"])
    size = int(msg.get("sizeEstimate", 0))
    return from_email, iso_date, size


def label_counts(service) -> List[Dict]:
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
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def main() -> None:
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
    ids = list_all_message_ids(service, query=since_query, label_ids=None, max_ids=SAMPLE_MAX_IDS)
    log.info("Collected %d message IDs. Starting metadata fetch...", len(ids))

    if not ids:
        print("No messages found for time window.")
        return

    # Pull metadata for ids and bucket by day + sender
    by_day = Counter()
    by_sender = Counter()
    total_size = 0

    # We can't true-batch-get with this client as easily, so we do sequential gets.
    # (Still okay for 1k-5k; later we can optimize with batchHttpRequest if you want.)
    examined = 0
    t0 = time.time()
    last_t = t0

    for i, msg_id in enumerate(ids, start=1):
        from_email, iso_date, size = get_message_metadata(service, msg_id)
        by_day[iso_date] += 1
        by_sender[from_email] += 1
        total_size += size
        examined += 1

    if i % LOG_EVERY == 0:
        now = time.time()
        elapsed = now - t0
        chunk = now - last_t
        rate = i / elapsed if elapsed > 0 else 0.0
        remaining = len(ids) - i
        approx_remaining_sec = remaining / rate if rate > 0 else float("inf")
        log.info(
            "Progress: %d/%d (%.1f%%) rate=%.2f msg/s last_chunk=%.2fs approx_remaining=%.1f min",
            i, len(ids), (i / len(ids)) * 100.0, rate, chunk, approx_remaining_sec / 60.0
        )
        last_t = now

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
