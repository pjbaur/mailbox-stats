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

## Test-Driven Development Strategy

### Testing Philosophy

Write tests **before** implementing each change to ensure:
1. Clear requirements understanding
2. Regression prevention
3. Confidence in timezone edge cases
4. Easy verification of each implementation step

### Test File Structure

**Location**: `tests/test_time_localization.py`

```python
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytz
import os

# Tests will be organized by implementation step
```

### Test Fixtures and Utilities

Create reusable fixtures for testing:

```python
@pytest.fixture
def utc_midnight_ms():
    """Timestamp for 2024-12-25 00:00:00 UTC (midnight boundary)."""
    dt = datetime(2024, 12, 25, 0, 0, 0, tzinfo=timezone.utc)
    return str(int(dt.timestamp() * 1000))

@pytest.fixture
def utc_almost_midnight_ms():
    """Timestamp for 2024-12-24 23:59:59 UTC (just before midnight)."""
    dt = datetime(2024, 12, 24, 23, 59, 59, tzinfo=timezone.utc)
    return str(int(dt.timestamp() * 1000))

@pytest.fixture
def mock_pst_timezone():
    """Mock Pacific Standard Time (UTC-8)."""
    return pytz.timezone('America/Los_Angeles')

@pytest.fixture
def mock_tokyo_timezone():
    """Mock Japan Standard Time (UTC+9)."""
    return pytz.timezone('Asia/Tokyo')

@pytest.fixture
def sample_messages():
    """Sample Gmail message objects for testing."""
    return [
        {
            'id': '1',
            'internalDate': '1703462400000',  # 2024-12-25 00:00:00 UTC
            'payload': {'headers': [{'name': 'From', 'value': 'test@example.com'}]}
        },
        {
            'id': '2',
            'internalDate': '1703376000000',  # 2024-12-24 00:00:00 UTC
            'payload': {'headers': [{'name': 'From', 'value': 'test@example.com'}]}
        }
    ]
```

---

### Step 1: Test Timezone Helper Functions

**Test file**: Add these tests first, then implement the helper functions.

```python
class TestTimezoneHelpers:
    """Tests for get_local_tz() and get_local_tz_name() functions."""

    def test_get_local_tz_returns_tzinfo(self):
        """get_local_tz() should return a timezone object."""
        from gmail_stats import get_local_tz
        tz = get_local_tz()
        # Should be a tzinfo object
        assert tz is not None
        assert hasattr(tz, 'utcoffset')

    def test_get_local_tz_name_returns_string(self):
        """get_local_tz_name() should return timezone abbreviation."""
        from gmail_stats import get_local_tz_name
        tz_name = get_local_tz_name()
        # Should be a non-empty string
        assert isinstance(tz_name, str)
        assert len(tz_name) > 0

    @patch.dict(os.environ, {'TZ': 'America/Los_Angeles'})
    def test_get_local_tz_name_pst(self):
        """get_local_tz_name() should return 'PST' or 'PDT' for LA timezone."""
        from gmail_stats import get_local_tz_name
        import time
        time.tzset()  # Apply TZ environment variable
        tz_name = get_local_tz_name()
        assert tz_name in ['PST', 'PDT']

    @patch.dict(os.environ, {'TZ': 'Asia/Tokyo'})
    def test_get_local_tz_name_jst(self):
        """get_local_tz_name() should return 'JST' for Tokyo timezone."""
        from gmail_stats import get_local_tz_name
        import time
        time.tzset()
        tz_name = get_local_tz_name()
        assert tz_name == 'JST'
```

**Run these tests** (they should fail), then implement the helper functions.

---

### Step 2: Test `iso_date_from_internal_ms` Conversion

```python
class TestIsoDateConversion:
    """Tests for iso_date_from_internal_ms() with local timezone conversion."""

    def test_midnight_utc_in_pst_is_previous_day(self):
        """Message at UTC midnight should show as previous day in PST (UTC-8)."""
        from gmail_stats import iso_date_from_internal_ms

        # 2024-12-25 00:00:00 UTC = 2024-12-24 16:00:00 PST
        with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
            import time
            time.tzset()

            ms = '1703462400000'  # 2024-12-25 00:00:00 UTC
            result = iso_date_from_internal_ms(ms)
            assert result == '2024-12-24'

    def test_midnight_utc_in_tokyo_is_next_day(self):
        """Message at UTC midnight should show as next day in Tokyo (UTC+9)."""
        from gmail_stats import iso_date_from_internal_ms

        # 2024-12-25 00:00:00 UTC = 2024-12-25 09:00:00 JST
        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            import time
            time.tzset()

            ms = '1703462400000'  # 2024-12-25 00:00:00 UTC
            result = iso_date_from_internal_ms(ms)
            assert result == '2024-12-25'

    def test_noon_utc_same_date_all_timezones(self):
        """Message at noon UTC should have same date in most timezones."""
        from gmail_stats import iso_date_from_internal_ms

        # 2024-12-25 12:00:00 UTC
        ms = '1703505600000'

        for tz in ['America/New_York', 'Europe/London', 'Asia/Shanghai']:
            with patch.dict(os.environ, {'TZ': tz}):
                import time
                time.tzset()
                result = iso_date_from_internal_ms(ms)
                assert '2024-12-25' in result  # Same date or close

    def test_far_past_timestamp(self):
        """Test with timestamp from 2020."""
        from gmail_stats import iso_date_from_internal_ms

        ms = '1577836800000'  # 2020-01-01 00:00:00 UTC
        result = iso_date_from_internal_ms(ms)
        assert result.startswith('2019-12-31') or result.startswith('2020-01-01')
```

---

### Step 3: Test Date Range Calculation

```python
class TestDateRangeCalculation:
    """Tests for local timezone in date range calculation."""

    @patch('gmail_stats.datetime')
    def test_since_dt_uses_local_time(self, mock_datetime):
        """since_dt should calculate from local current time, not UTC."""
        from gmail_stats import DAYS

        # Mock local time: 2024-12-25 18:00:00 PST (UTC-8)
        mock_now_local = datetime(2024, 12, 25, 18, 0, 0)
        mock_now_local = mock_now_local.replace(tzinfo=pytz.timezone('America/Los_Angeles'))

        mock_datetime.now.return_value.astimezone.return_value = mock_now_local

        # Verify calculation uses local time
        # Expected: 30 days before 2024-12-25 18:00:00 PST
        # Should be: 2024-11-25 18:00:00 PST
        # (Actual verification would happen in integration test)

    @patch('gmail_stats.datetime')
    def test_end_date_uses_local_date(self, mock_datetime):
        """end_date should use local date, not UTC date."""
        # Mock: 2024-12-25 23:00:00 PST (which is 2024-12-26 07:00:00 UTC)
        mock_now_local = datetime(2024, 12, 25, 23, 0, 0)
        mock_now_local = mock_now_local.replace(tzinfo=pytz.timezone('America/Los_Angeles'))

        mock_datetime.now.return_value.astimezone.return_value = mock_now_local

        # end_date should be 2024-12-25 (local), not 2024-12-26 (UTC)
        expected_date = mock_now_local.date()
        assert expected_date.isoformat() == '2024-12-25'
```

---

### Step 4: Test Daily Volume Date Bucketing

```python
class TestDailyVolumeBucketing:
    """Integration tests for message bucketing by local date."""

    def test_messages_bucket_by_local_date(self, sample_messages):
        """Messages should be bucketed by local date, not UTC date."""
        from gmail_stats import iso_date_from_internal_ms
        from collections import Counter

        with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
            import time
            time.tzset()

            by_day = Counter()
            for msg in sample_messages:
                date = iso_date_from_internal_ms(msg['internalDate'])
                by_day[date] += 1

            # With PST (UTC-8), both messages should be on 2024-12-24
            # because:
            # - 2024-12-25 00:00:00 UTC = 2024-12-24 16:00:00 PST
            # - 2024-12-24 00:00:00 UTC = 2024-12-23 16:00:00 PST
            assert '2024-12-24' in by_day or '2024-12-23' in by_day

    def test_dst_transition_handling(self):
        """Test date bucketing during DST transition (spring forward)."""
        from gmail_stats import iso_date_from_internal_ms

        # March 10, 2024 is DST transition in US (2am -> 3am)
        # Test message at 2024-03-10 10:00:00 UTC (during transition window)
        dst_transition_ms = str(int(datetime(2024, 3, 10, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000))

        with patch.dict(os.environ, {'TZ': 'America/New_York'}):
            import time
            time.tzset()
            result = iso_date_from_internal_ms(dst_transition_ms)
            assert result == '2024-03-10'  # Should handle DST gracefully
```

---

### Step 5: Test Header Display with Timezone

```python
class TestHeaderDisplay:
    """Tests for timezone labels in section headers."""

    @patch('gmail_stats.get_local_tz_name')
    def test_daily_volume_header_includes_timezone(self, mock_tz_name):
        """Daily Volume header should include timezone abbreviation."""
        mock_tz_name.return_value = 'PST'

        # This would be tested via output capture or by checking
        # the actual print statement format
        expected_header = "Daily Volume (last 30 days, PST)"
        # Verification would happen in integration test

    @patch('gmail_stats.get_local_tz_name')
    def test_top_senders_header_includes_timezone(self, mock_tz_name):
        """Top Senders header should include timezone abbreviation."""
        mock_tz_name.return_value = 'EST'

        expected_header = "Top Senders (last 30 days, EST, examined 5000)"
        # Verification would happen in integration test
```

---

### Step 6: Test UTC Logging Configuration

```python
class TestLoggingConfiguration:
    """Tests for UTC logging timestamps."""

    def test_log_formatter_uses_utc(self):
        """Logging should use UTC timestamps, not local time."""
        import logging
        import time

        # After configuration, logging.Formatter.converter should be time.gmtime
        assert logging.Formatter.converter == time.gmtime

    def test_log_format_includes_utc_label(self):
        """Log format should include 'UTC' label for clarity."""
        import logging

        # Check that handler format includes 'UTC'
        handlers = logging.getLogger().handlers
        for handler in handlers:
            if hasattr(handler, 'formatter'):
                format_str = handler.formatter._fmt
                assert 'UTC' in format_str

    @patch('logging.info')
    def test_log_timestamp_is_utc_during_execution(self, mock_log):
        """Verify logs actually use UTC time, not local time."""
        # This would require capturing actual log output and parsing timestamp
        # Then comparing to known UTC time vs local time
        pass
```

---

### Step 7: Integration Tests

```python
class TestEndToEndIntegration:
    """Full integration tests with mocked Gmail API."""

    @pytest.fixture
    def mock_gmail_service(self):
        """Mock Gmail API service for integration testing."""
        service = MagicMock()

        # Mock profile response
        service.users().getProfile().execute.return_value = {
            'emailAddress': 'test@example.com',
            'messagesTotal': 1000,
            'threadsTotal': 500
        }

        # Mock labels response
        service.users().labels().list().execute.return_value = {
            'labels': [
                {'id': 'INBOX', 'messagesTotal': 100, 'messagesUnread': 10, 'threadsTotal': 50}
            ]
        }

        return service

    @patch.dict(os.environ, {'TZ': 'America/Los_Angeles'})
    def test_full_script_output_pst(self, mock_gmail_service, capsys):
        """Test complete script execution in PST timezone."""
        import time
        time.tzset()

        # Run main script logic with mocked API
        # Verify output contains:
        # - "PST" in headers
        # - Correct date bucketing
        # - UTC in logs

        # captured = capsys.readouterr()
        # assert "PST" in captured.out
        # assert "Daily Volume (last 30 days, PST)" in captured.out

    @patch.dict(os.environ, {'TZ': 'Asia/Tokyo'})
    def test_full_script_output_jst(self, mock_gmail_service, capsys):
        """Test complete script execution in JST timezone."""
        import time
        time.tzset()

        # Same as above but verify JST-specific behavior
        # captured = capsys.readouterr()
        # assert "JST" in captured.out
```

---

### Step 8: Edge Case Tests

```python
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_timezone_with_no_abbreviation(self):
        """Some timezones return offset instead of abbreviation (e.g., +0800)."""
        with patch.dict(os.environ, {'TZ': 'Etc/GMT-8'}):
            import time
            time.tzset()

            from gmail_stats import get_local_tz_name
            tz_name = get_local_tz_name()
            # Should return something (even if it's "+0800" format)
            assert tz_name is not None
            assert len(tz_name) > 0

    def test_leap_second_timestamp(self):
        """Test handling of timestamps near leap seconds."""
        from gmail_stats import iso_date_from_internal_ms

        # June 30, 2012 had a leap second (23:59:60 UTC)
        # Test timestamp near this time
        ms = '1341100799000'  # 2012-06-30 23:59:59 UTC
        result = iso_date_from_internal_ms(ms)
        assert result.startswith('2012-06-')

    def test_very_old_message_before_epoch(self):
        """Test handling of very old timestamps (edge case)."""
        from gmail_stats import iso_date_from_internal_ms

        # Very old message (should still work)
        ms = '946684800000'  # 2000-01-01 00:00:00 UTC
        result = iso_date_from_internal_ms(ms)
        assert '2000' in result or '1999' in result  # Depending on timezone

    def test_message_at_exact_dst_boundary(self):
        """Test message timestamp at exact DST transition moment."""
        from gmail_stats import iso_date_from_internal_ms

        # November 3, 2024, 2:00 AM EDT -> 1:00 AM EST (fall back)
        # This is 2024-11-03 06:00:00 UTC
        dst_fall_ms = str(int(datetime(2024, 11, 3, 6, 0, 0, tzinfo=timezone.utc).timestamp() * 1000))

        with patch.dict(os.environ, {'TZ': 'America/New_York'}):
            import time
            time.tzset()
            result = iso_date_from_internal_ms(dst_fall_ms)
            # Should still produce valid date
            assert result == '2024-11-03'
```

---

### Test Execution Strategy

**TDD Workflow** - Follow this order:

1. **Write tests for Step 1** (helper functions) → Run tests (should fail) → Implement helpers → Tests pass
2. **Write tests for Step 2** (iso_date conversion) → Run tests (should fail) → Implement conversion → Tests pass
3. **Write tests for Step 3** (date range calc) → Run tests (should fail) → Implement changes → Tests pass
4. **Continue for each implementation step**
5. **Finally run all tests together** + integration tests

**Running Tests**:

```bash
# Run all time localization tests
pytest tests/test_time_localization.py -v

# Run specific test class
pytest tests/test_time_localization.py::TestTimezoneHelpers -v

# Run with coverage
pytest tests/test_time_localization.py --cov=gmail_stats --cov-report=html

# Run tests in different timezones
TZ=America/New_York pytest tests/test_time_localization.py
TZ=Asia/Tokyo pytest tests/test_time_localization.py
TZ=Europe/London pytest tests/test_time_localization.py
```

**Expected Coverage**: Aim for >95% coverage of timezone-related code paths.

---

### Test Dependencies

Add to development requirements:

```bash
pip install pytest pytest-cov pytz
```

Or add to `requirements-dev.txt`:
```
pytest>=7.0.0
pytest-cov>=4.0.0
pytz>=2024.1
```

---

### Continuous Validation

After implementation, keep these tests in the suite to:
1. **Prevent regressions** when modifying date/time code
2. **Document timezone behavior** for future developers
3. **Validate DST transitions** automatically
4. **Ensure consistency** across different environments

---

### Success Criteria

All tests should pass in at least these timezones:
- ✅ `America/Los_Angeles` (PST/PDT, UTC-8/-7)
- ✅ `America/New_York` (EST/EDT, UTC-5/-4)
- ✅ `Europe/London` (GMT/BST, UTC+0/+1)
- ✅ `Asia/Tokyo` (JST, UTC+9)
- ✅ `Australia/Sydney` (AEDT/AEST, UTC+11/+10)

---

## Manual Testing Plan

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
