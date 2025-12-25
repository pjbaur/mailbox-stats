# Implementation Plan: Provable Logging for gmail_stats.py

## Overview

Add comprehensive audit logging to make all counts and aggregations in the dashboard verifiable and traceable. Each statistic should be accompanied by logs that prove how it was calculated.

## Design Principles

1. **Auditability**: Every count should be traceable to its source query and parameters
2. **Timezone Clarity**: Explicitly state whether UTC or local timezone is used
3. **Reproducibility**: Provide enough information to reproduce the same results
4. **Performance**: Use INFO level for key metrics, DEBUG for detailed traces
5. **Structured Format**: Use consistent log format for easy parsing/automation

## Log Format Standard

All provable logging should follow this format:

```
[AGGREGATION_NAME] query=<query> timezone=<tz> date_range=<start>...<end> total=<count> [additional_metrics]
```

Example:
```
[DAILY_VOLUME] query='newer_than:30d' timezone=PST(UTC-8) date_range=2024-11-26...2024-12-25 total=5000 size_mb=342.5
[TOP_SENDERS] query='newer_than:30d' timezone=PST(UTC-8) total=5000 unique_senders=1234 top_sender=newsletter@example.com(421)
```

---

## Aggregations to Log

### 1. Mailbox Profile (Lines 340-349)

**Current logging**: None specific to aggregation

**What to add**:
```python
log.info(
    "[MAILBOX_PROFILE] account=%s total_messages=%d total_threads=%d",
    profile['emailAddress'],
    profile['messagesTotal'],
    profile['threadsTotal']
)
```

**Location**: After line 347 (after getting profile)

**Rationale**: Document the mailbox totals at the start for baseline comparison

---

### 2. Label Statistics (Lines 350-362)

**Current logging**: None specific to aggregation

**What to add**:
```python
log.info(
    "[LABEL_STATS] total_labels=%d key_labels=%s",
    len(labels),
    ','.join([l['id'] for l in KEY_LABEL_IDS if any(lbl['id'] == l for lbl in labels)])
)

# For each key label:
for l in labels:
    if l.get('id') in KEY_LABEL_IDS:
        log.info(
            "[LABEL_DETAIL] label=%s messages=%d unread=%d threads=%d",
            l['id'],
            l.get('messagesTotal', 0),
            l.get('messagesUnread', 0),
            l.get('threadsTotal', 0)
        )
```

**Location**: After line 350 (inside the Key Labels section)

**Rationale**: Prove label counts are from Gmail API, not calculated

---

### 3. Daily Volume Aggregation (Lines 364-413)

**Current logging**:
- Line 371: `"Building sample: query=%r cap=%d"`
- Line 375: `"Collected %d message IDs"`

**What to add**:

**Step 3a - Date Range Logging (after line 364)**:
```python
# Log date range calculation with timezone info
local_tz = get_local_tz()
tz_offset = datetime.now(local_tz).strftime('%z')  # e.g., "-0800"
tz_abbr = get_local_tz_name()  # e.g., "PST"

log.info(
    "[DAILY_VOLUME_RANGE] timezone=%s(UTC%s) start=%s end=%s days=%d query=%r",
    tz_abbr,
    tz_offset,
    since_dt.isoformat(),
    datetime.now().astimezone().isoformat(),
    DAYS,
    since_query
)
```

**Step 3b - Post-Aggregation Summary (after line 400)**:
```python
# Log aggregation results with proof
days_with_data = len([d for d in by_day.values() if d > 0])
date_range_str = f"{start_date.isoformat()}...{end_date.isoformat()}"

log.info(
    "[DAILY_VOLUME_RESULT] query=%r timezone=%s date_range=%s total_messages=%d "
    "days_examined=%d days_with_data=%d size_mb=%.1f sample_cap=%d",
    since_query,
    tz_abbr,
    date_range_str,
    len(messages),
    (end_date - start_date).days + 1,
    days_with_data,
    total_size / (1024 * 1024),
    SAMPLE_MAX_IDS
)
```

**Location**:
- Step 3a: After line 365 (before building sample)
- Step 3b: After line 400 (after aggregation loop)

**Rationale**:
- Makes timezone boundaries explicit and provable
- Shows the relationship between query, date range, and results
- Distinguishes between "days examined" (date range span) and "days with data" (actual counts)

---

### 4. Top Senders Aggregation (Lines 416-418)

**Current logging**: None specific

**What to add** (after line 400, with daily volume result):
```python
# Log top senders summary
top_25 = by_sender.most_common(25)
log.info(
    "[TOP_SENDERS_RESULT] query=%r timezone=%s total_messages=%d unique_senders=%d "
    "top_sender=%s(%d) top_25_total=%d",
    since_query,
    tz_abbr,
    len(messages),
    len(by_sender),
    top_25[0][0] if top_25 else 'N/A',
    top_25[0][1] if top_25 else 0,
    sum(cnt for _, cnt in top_25)
)
```

**Location**: After line 400 (in same section as daily volume result)

**Rationale**:
- Proves top senders are from same message set as daily volume
- Shows coverage: how much of total volume is represented by top 25

---

### 5. Unread Inbox (Lines 420-424)

**Current logging**: None specific

**What to add** (after line 424):
```python
if inbox:
    log.info(
        "[UNREAD_INBOX] label=INBOX unread=%d total=%d threads=%d",
        inbox.get('messagesUnread', 0),
        inbox.get('messagesTotal', 0),
        inbox.get('threadsTotal', 0)
    )
```

**Location**: After line 424 (inside the inbox block)

**Rationale**: Log the source data for unread count

---

## Additional Enhancements

### 6. Sampling Transparency

**Current**: Line 371 logs the cap, but not whether sampling occurred

**Enhancement** (after line 375):
```python
was_capped = len(ids) >= SAMPLE_MAX_IDS
log.info(
    "[SAMPLING_INFO] requested=%d returned=%d capped=%s coverage=%.1f%%",
    SAMPLE_MAX_IDS if SAMPLE_MAX_IDS > 0 else float('inf'),
    len(ids),
    was_capped,
    (len(ids) / profile['messagesTotal'] * 100) if profile['messagesTotal'] > 0 else 0
)
```

**Rationale**: Make it clear when results are sampled vs complete

---

### 7. UTC vs Local Timezone Conversion Proof

**Enhancement**: Add a helper function to log timezone conversions:

```python
def log_timezone_conversion_example():
    """Log an example timestamp conversion to demonstrate UTC→Local handling."""
    # Use the first message timestamp as example
    example_utc_ms = "1703462400000"  # 2024-12-25 00:00:00 UTC
    example_utc = datetime.fromtimestamp(int(example_utc_ms) / 1000, tz=timezone.utc)
    example_local = example_utc.astimezone()

    log.info(
        "[TIMEZONE_EXAMPLE] utc=%s local=%s timezone=%s offset=%s",
        example_utc.isoformat(),
        example_local.isoformat(),
        get_local_tz_name(),
        example_local.strftime('%z')
    )
```

**Location**: Call once after line 386 (after getting messages, before aggregation)

**Rationale**:
- Provides concrete example of UTC→Local conversion
- Makes it easy to verify date bucketing logic

---

## Implementation Checklist

- [ ] Add timezone offset helper (get UTC offset like "-0800")
- [ ] Add `[MAILBOX_PROFILE]` logging (after line 347)
- [ ] Add `[LABEL_STATS]` summary logging (after line 350)
- [ ] Add `[LABEL_DETAIL]` per-label logging (in label loop)
- [ ] Add `[DAILY_VOLUME_RANGE]` logging (after line 365)
- [ ] Add `[DAILY_VOLUME_RESULT]` logging (after line 400)
- [ ] Add `[TOP_SENDERS_RESULT]` logging (after line 400)
- [ ] Add `[SAMPLING_INFO]` logging (after line 375)
- [ ] Add `[UNREAD_INBOX]` logging (after line 424)
- [ ] Add `[TIMEZONE_EXAMPLE]` logging (after line 386)
- [ ] Update CLAUDE.md documentation
- [ ] Add tests for logging output
- [ ] Verify log format is grep/parseable

---

## Testing Strategy

### Manual Testing
1. Run script and check `gmail_stats.log` for all `[AGGREGATION_NAME]` entries
2. Verify each aggregation has corresponding log entry
3. Grep for specific aggregations: `grep "\[DAILY_VOLUME" gmail_stats.log`
4. Verify timezone information is consistent

### Automated Testing
Add tests to verify:
- Each aggregation produces expected log messages
- Log format is consistent and parseable
- Timezone information is included where required
- Counts in logs match displayed counts

Example test structure:
```python
def test_daily_volume_logging(caplog):
    """Verify daily volume aggregation produces provable logs."""
    # Run aggregation
    # Check caplog for [DAILY_VOLUME_RANGE] and [DAILY_VOLUME_RESULT]
    # Verify required fields are present
    assert "[DAILY_VOLUME_RANGE]" in caplog.text
    assert "timezone=" in caplog.text
    assert "date_range=" in caplog.text
```

---

## Example Log Output

After implementation, running the script should produce logs like:

```
2025-12-25 09:00:00 UTC INFO [MAILBOX_PROFILE] account=user@example.com total_messages=45231 total_threads=12845
2025-12-25 09:00:01 UTC INFO [LABEL_STATS] total_labels=15 key_labels=INBOX,SENT,DRAFT,SPAM,TRASH,IMPORTANT,STARRED
2025-12-25 09:00:01 UTC INFO [LABEL_DETAIL] label=INBOX messages=2341 unread=156 threads=1234
2025-12-25 09:00:01 UTC INFO [LABEL_DETAIL] label=SENT messages=12456 unread=0 threads=8901
2025-12-25 09:00:01 UTC INFO [DAILY_VOLUME_RANGE] timezone=PST(UTC-0800) start=2024-11-26T00:00:00-08:00 end=2024-12-25T09:00:00-08:00 days=30 query='newer_than:30d'
2025-12-25 09:00:02 UTC INFO Building sample: query='newer_than:30d' cap=5000
2025-12-25 09:00:03 UTC INFO Collected 5000 message IDs. Starting metadata fetch...
2025-12-25 09:00:03 UTC INFO [SAMPLING_INFO] requested=5000 returned=5000 capped=True coverage=11.1%
2025-12-25 09:00:15 UTC INFO [TIMEZONE_EXAMPLE] utc=2024-12-25T00:00:00+00:00 local=2024-12-24T16:00:00-08:00 timezone=PST offset=-0800
2025-12-25 09:00:15 UTC INFO [DAILY_VOLUME_RESULT] query='newer_than:30d' timezone=PST date_range=2024-11-26...2024-12-25 total_messages=5000 days_examined=30 days_with_data=28 size_mb=342.5 sample_cap=5000
2025-12-25 09:00:15 UTC INFO [TOP_SENDERS_RESULT] query='newer_than:30d' timezone=PST total_messages=5000 unique_senders=1234 top_sender=newsletters@example.com(421) top_25_total=2847
2025-12-25 09:00:15 UTC INFO [UNREAD_INBOX] label=INBOX unread=156 total=2341 threads=1234
```

---

## Benefits

1. **Auditability**: Every number on the dashboard can be traced to a log entry
2. **Debugging**: Easy to spot discrepancies between expected and actual counts
3. **Timezone Transparency**: Clear documentation of UTC vs local timezone usage
4. **Reproducibility**: Logs provide all parameters needed to reproduce results
5. **Automation**: Structured logs can be parsed for monitoring/alerting
6. **Compliance**: Provides audit trail for data analysis

---

## Future Enhancements

- Add JSON-formatted structured logging option
- Export provable logs to separate audit file
- Add log aggregation summary at end of run
- Include Git commit hash in logs for version tracking
- Add option to verify counts against historical logs
