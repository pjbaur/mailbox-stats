from __future__ import annotations

import base64
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_creds() -> Credentials:
    creds: Optional[Credentials] = None

    # Check if the credentials file exists and is valid
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception:
        creds = None

    if creds and creds.valid:
        return creds

    # If there are no (valid) credentials available, let the user log in.
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds
    
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds

def main() -> None:
    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    def list_labels(service):
        res = service.users().labels().list(userId="me").execute()
        labels = res.get("labels", [])
        print(f"Labels: {len(labels)}\n")

        # Fetch details for common labels (or all if you want)
        for lab in sorted(labels, key=lambda x: x["name"].lower()):
            lab_id = lab["id"]
            detail = service.users().labels().get(userId="me", id=lab_id).execute()
            print(
                f"{detail['name']:<30} "
                f"msgs={detail.get('messagesTotal', 0):>7} "
                f"unread={detail.get('messagesUnread', 0):>7} "
                f"threads={detail.get('threadsTotal', 0):>7}"
            )

    list_labels(service)

    def latest_inbox_metadata(service, n=20):
        resp = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=n
        ).execute()
        msgs = resp.get("messages", [])
        if not msgs:
            print("No messages in INBOX.")
            return

        for m in msgs:
            msg = service.users().messages().get(
                userId="me",
                id=m["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            print("\nID:", msg["id"])
            print(" Date:", headers.get("Date"))
            print(" From:", headers.get("From"))
            print(" Subj:", headers.get("Subject"))
            print(" Labels:", msg.get("labelIds", []))
            print(" Size:", msg.get("sizeEstimate"))

    latest_inbox_metadata(service, n=10)

    unread = service.users().labels().get(userId="me", id="INBOX").execute().get("messagesUnread", 0)
    print("Unread INBOX:", unread)

    # 1) Basic mailbox identity + totals
    profile = service.users().getProfile(userId="me").execute()
    print(f"Email: {profile['emailAddress']}")
    print(f"Total messages: {profile['messagesTotal']}")
    print(f"Total threads: {profile['threadsTotal']}")
    print()

    # 2) List latest messages in INBOX (IDs only)
    resp = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=5,
    ).execute()

    msgs = resp.get("messages", [])
    if not msgs:
        print("No messages found in INBOX.")
        return
    
    print("Latest messages in INBOX (IDs only):")
    for m in msgs:
        print(" -", m["id"])
    print()

    # 3) Fetch one message and print subject + snippet
    msg_id = msgs[0]["id"]
    msg = service.users().messages().get(
        userId="me", 
        id=msg_id,
        format="metadata",
        metadataHeaders=["Subject", "From", "Date"],
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    print("Top message in INBOX:")
    print(" From:", headers.get("From"))
    print(" Date:", headers.get("Date"))
    print(" Subject:", headers.get("Subject"))
    print(" Snippet:", msg.get("snippet"))

if __name__ == "__main__":
    main()