This is day 4 of this project.

---

# Day 4 Goal

**Fetch enough data to aggregate:**

* Message count per sender
* Total message size per sender
* Optional: attachment indicators
* Do it **fast**, **cheap**, and **correctly**

---

## 1️⃣ Decide the Minimal Data Contract (This Is Key)

You do **not** want full messages. You want *just enough* to answer questions.

### Use:

```python
format="metadata"
```

### From each message, extract:

* `payload.headers`:

  * `From`
  * `Date` (optional if you want time windows later)
* `sizeEstimate` ✅ (this is gold)
* `payload.parts` (structure only, not bodies)

### Explicitly skip:

* Message body
* Attachment binary data
* Snippets (optional, not useful here)

📌 **Important insight**
`sizeEstimate` already includes attachments. That means:

* You can rank senders by “how much mailbox space they consume”
* You don’t need to download attachments to count their impact

---

## 2️⃣ Attachment Detection Without Fetching Attachments

You can infer attachments safely and cheaply:

```python
def has_attachment(payload):
    if not payload or "parts" not in payload:
        return False

    for part in payload["parts"]:
        if part.get("filename"):
            return True
        if part.get("body", {}).get("attachmentId"):
            return True
    return False
```

Store:

* `has_attachment: bool`
* Optional: `attachment_count` if you want later

This costs **zero extra API calls**.

---

## 3️⃣ Normalize the Sender (Critical for Aggregation)

Raw `From` headers are chaos:

```
"Amazon.com <order-update@amazon.com>"
"AMAZON <no-reply@amazon.com>"
```

### Normalize to:

* Email domain (recommended): `amazon.com`
* Or full email address

Example:

```python
def normalize_sender(from_header):
    # extract email, lowercase, strip display name
```

📌 **Recommendation**
Use **domain-level aggregation first**, keep raw sender for drill-down later.

---

## 4️⃣ Aggregation Data Model (In-Memory First)

Use a dict keyed by sender:

```python
stats = {
  "amazon.com": {
      "message_count": 1234,
      "total_size": 987654321,
      "messages_with_attachments": 456
  }
}
```

Update per message:

* `+1` message_count
* `+sizeEstimate`
* `+1` attachments if detected

This lets you:

* Stream results
* Avoid storing per-message rows unless you want historical detail later

---

## 5️⃣ Pagination Strategy (Quota-Safe)

* `users.messages.list` gives IDs only
* Page size: `maxResults=500`
* Fetch messages in batches
* Log progress every N messages

Example checkpoint log:

```
Fetched 5,000 / ~77,000 messages (6.4%)
Elapsed: 00:02:11
```

This gives you:

* Confidence
* Kill-switch capability
* Debug visibility

---

## 6️⃣ Output Artifacts to Produce Today

You should end Day 4 with **actual answers**, not just plumbing.

### Minimum outputs:

* Top 20 senders by message count
* Top 20 senders by total size (MB/GB)
* Percentage of mailbox size from top N senders

Optional but powerful:

* CSV export
* JSON snapshot for later dashboards

---

## 7️⃣ What You Explicitly Do *Not* Do Today

❌ Full message fetch
❌ Body decoding
❌ Thread reconstruction
❌ Attachment downloads
❌ Database persistence (unless you already planned it)

Those are Day 5+ problems.

---

## Day 4 “Shipped” Definition ✅

You can confidently say:

> “I know who fills my mailbox, how much space they consume, and whether attachments are the culprit.”

* Add timing + quota guards
* Persist results to SQLite
