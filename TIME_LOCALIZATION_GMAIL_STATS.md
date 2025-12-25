# Time Localization Plan for gmail_stats.py

## Overview
Convert all user-facing date and time references from UTC to local timezone while keeping log timestamps in UTC.

## User Preferences (confirmed)
- ✅ Daily volume dates: Display in local timezone
- ✅ Date range calculation: Use local timezone for "now"
- ✅ Timezone display: Show timezone abbreviation (e.g., "PST", "-08:00")
- ✅ Log timestamps: Explicitly use UTC

## Critical Files
- `/Users/paulbaur/projects/mailbox-stats/gmail_stats.py` - Main script with all date/time logic

## Implementation Steps

### 1. Add Local Timezone Utilities
**Location**: After line 68 (after EMAIL_RE definition, before request tracking code)

**Action**: Add helper functions for timezone handling:
```python
def get_local_tz():
    """Get the local timezone as a timezone-aware object."""
    return datetime.now().astimezone().tzinfo

def get_local_tz_name():
    """Get the local timezone abbreviation (e.g., 'PST', 'EST')."""
    return datetime.now().astimezone().strftime('%Z')
```

**Rationale**: Centralize timezone logic for consistency and reusability.

---

### 2. Update `iso_date_from_internal_ms` Function
**Location**: Lines 141-145

**Current code**:
```python
def iso_date_from_internal_ms(ms: str) -> str:
    """Convert Gmail internalDate (milliseconds since epoch) to YYYY-MM-DD."""
    # internalDate is milliseconds since epoch UTC
    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    return dt.date().isoformat()
```

**New code**:
```python
def iso_date_from_internal_ms(ms: str) -> str:
    """Convert Gmail internalDate (milliseconds since epoch) to YYYY-MM-DD in local timezone."""
    # internalDate is milliseconds since epoch UTC, convert to local timezone
    dt_utc = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    dt_local = dt_utc.astimezone()  # Convert to local timezone
    return dt_local.date().isoformat()
```

**Impact**:
- Messages will be bucketed by local date instead of UTC date
- A message arriving at 11 PM UTC on Dec 24 will show as Dec 25 if local time is UTC+2 or later
- This affects the `by_day` Counter aggregation (line 382)

**Rationale**: User expects dates to match their local perception of "when" messages arrived.

---

### 3. Update Date Range Calculation
**Location**: Line 349

**Current code**:
```python
since_dt = datetime.now(tz=timezone.utc) - timedelta(days=DAYS)
```

**New code**:
```python
since_dt = datetime.now().astimezone() - timedelta(days=DAYS)
```

**Impact**:
- "Last 30 days" calculated from local current time instead of UTC current time
- More intuitive for users in non-UTC timezones
- Gmail query `newer_than:30d` remains the same (Gmail interprets this server-side)

**Rationale**: Aligns with user's mental model of "30 days ago from now (local time)".

---

### 4. Update End Date Calculation
**Location**: Line 388

**Current code**:
```python
end_date = datetime.now(tz=timezone.utc).date()
```

**New code**:
```python
end_date = datetime.now().astimezone().date()
```

**Impact**:
- End boundary for daily volume display uses local date
- Consistent with start date calculation change

---

### 5. Update Daily Volume Display Header
**Location**: Line 353 and surrounding print statements

**Current code**:
```python
print_header(f"Daily Volume (last {DAYS} days)")
```

**New code**:
```python
tz_name = get_local_tz_name()
print_header(f"Daily Volume (last {DAYS} days, {tz_name})")
```

**Impact**:
- Users see which timezone the dates are displayed in
- Example: "Daily Volume (last 30 days, PST)"

**Rationale**: Makes timezone context explicit per user preference.

---

### 6. Configure UTC Logging
**Location**: Lines 56-63 (logging configuration)

**Current code**:
```python
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("gmail_stats.log", encoding="utf-8"),
    ],
)
```

**New code**:
```python
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
```

**Impact**:
- All log timestamps explicitly use UTC
- Format includes "UTC" label for clarity: `2025-12-25 14:30:45 UTC INFO ...`
- Requires adding `import time` (already imported at line 26)

**Rationale**: User wants logs in UTC for consistency and troubleshooting.

---

### 7. Update Section Headers with Timezone Context
**Location**: Line 400 (Top Senders header)

**Current code**:
```python
print_header(f"Top Senders (last {DAYS} days, examined {len(messages)})")
```

**New code**:
```python
tz_name = get_local_tz_name()
print_header(f"Top Senders (last {DAYS} days, {tz_name}, examined {len(messages)})")
```

**Impact**: Consistent timezone labeling across all time-based sections.

---

### 8. Optional: Add Timezone Info to Main Header
**Location**: Lines 330-333 (main dashboard header)

**Consider adding** after line 333:
```python
print(f"Timezone     : {get_local_tz_name()}")
```

**Impact**:
- Makes the timezone setting visible at the top of the report
- Users immediately know all dates are in local time

**Rationale**: Helpful context for users, especially when sharing reports.

---

## Additional Considerations

### Gmail API Query Behavior
**No change needed**: The Gmail search query `newer_than:30d` is interpreted server-side by Gmail (always UTC-based). Our local timezone changes only affect how we display and bucket the results, not what we fetch.

### Edge Cases to Test
1. **Daylight Saving Time transitions**: Ensure dates near DST boundaries are handled correctly
2. **Timezone abbreviation edge cases**: Some timezones may have unusual abbreviations (e.g., "+0800" instead of "PST")
3. **Date boundary shifts**: Verify a message at 11:59 PM UTC shows in correct local date bucket

### Performance Impact
**None**: Timezone conversion is negligible overhead. Using `astimezone()` is a lightweight operation.

### Breaking Changes
**Yes - Output Format**:
- Daily volume dates may shift by ±1 day for messages near midnight UTC
- Historical comparisons with old output may be off by 1 day at boundaries
- Log format changes (adds "UTC" label)

**Recommendation**: Document this change in CLAUDE.md after implementation.

---

## Implementation Checklist

- [ ] Add `get_local_tz()` and `get_local_tz_name()` helper functions
- [ ] Update `iso_date_from_internal_ms()` to convert to local timezone
- [ ] Update `since_dt` calculation to use local time (line 349)
- [ ] Update `end_date` calculation to use local time (line 388)
- [ ] Add timezone abbreviation to "Daily Volume" header (line 353)
- [ ] Add timezone abbreviation to "Top Senders" header (line 400)
- [ ] Configure logging to use UTC with explicit label (lines 56-63)
- [ ] (Optional) Add timezone to main dashboard header (line 333)
- [ ] Test with messages spanning midnight UTC
- [ ] Test during DST transition periods
- [ ] Update CLAUDE.md documentation

---

## Testing Plan

### Manual Testing
1. Run script and verify daily volume dates match local calendar
2. Check that section headers show timezone abbreviation
3. Verify log file shows "UTC" in timestamps
4. Compare before/after output for a known set of messages

### Edge Case Testing
1. Find messages sent around midnight UTC
2. Verify they appear in correct local date bucket
3. Test in different timezones (if possible, or simulate with TZ environment variable)

---

## Documentation Updates

After implementation, update `CLAUDE.md`:

**Section: Architecture & Implementation Details**
- Add subsection: "Timezone Handling"
  - Document that user-facing dates use local timezone
  - Document that logs use UTC
  - Document the timezone conversion approach

**Section: Usage**
- Update example output to show timezone abbreviations
- Note that dates are displayed in local time

**Section: Known Limitations**
- Remove or update any notes about UTC-only behavior

---

## Estimated Changes
- **Lines modified**: ~10-15 lines
- **Lines added**: ~15-20 lines (helpers, labels)
- **New dependencies**: None (uses stdlib `datetime.astimezone()`)
- **Risk level**: Low (mostly display logic, well-isolated changes)

## Rollback Plan
If issues arise, revert changes to restore UTC behavior:
1. Restore `iso_date_from_internal_ms()` to use `timezone.utc`
2. Restore date calculations to use `datetime.now(tz=timezone.utc)`
3. Remove timezone labels from headers
4. Remove UTC logging configuration
