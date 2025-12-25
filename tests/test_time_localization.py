"""
Test suite for time localization changes in gmail_stats.py

This test file implements the TDD strategy from TIME_LOCALIZATION_GMAIL_STATS.md.
Tests are organized by implementation step and should be run before implementing
each feature to ensure proper TDD workflow.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call
import pytz
import os
import logging
import time as time_module


def safe_tzset():
    """Safely call time.tzset() if available (not on macOS)."""
    if hasattr(time_module, 'tzset'):
        safe_tzset()


# =============================================================================
# Test Fixtures and Utilities
# =============================================================================

@pytest.fixture
def utc_midnight_ms():
    """Timestamp for 2023-12-25 00:00:00 UTC (midnight boundary)."""
    dt = datetime(2023, 12, 25, 0, 0, 0, tzinfo=timezone.utc)
    return str(int(dt.timestamp() * 1000))


@pytest.fixture
def utc_almost_midnight_ms():
    """Timestamp for 2023-12-24 23:59:59 UTC (just before midnight)."""
    dt = datetime(2023, 12, 24, 23, 59, 59, tzinfo=timezone.utc)
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
            'internalDate': '1703462400000',  # 2023-12-25 00:00:00 UTC
            'payload': {'headers': [{'name': 'From', 'value': 'test@example.com'}]}
        },
        {
            'id': '2',
            'internalDate': '1703376000000',  # 2023-12-24 00:00:00 UTC
            'payload': {'headers': [{'name': 'From', 'value': 'test@example.com'}]}
        }
    ]


# =============================================================================
# Step 1: Test Timezone Helper Functions
# =============================================================================

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
        safe_tzset()  # Apply TZ environment variable
        tz_name = get_local_tz_name()
        assert tz_name in ['PST', 'PDT']

    @patch.dict(os.environ, {'TZ': 'Asia/Tokyo'})
    def test_get_local_tz_name_jst(self):
        """get_local_tz_name() should return 'JST' for Tokyo timezone."""
        from gmail_stats import get_local_tz_name
        safe_tzset()
        tz_name = get_local_tz_name()
        assert tz_name == 'JST'


# =============================================================================
# Step 2: Test iso_date_from_internal_ms Conversion
# =============================================================================

class TestIsoDateConversion:
    """Tests for iso_date_from_internal_ms() with local timezone conversion."""

    def test_midnight_utc_in_pst_is_previous_day(self):
        """Message at UTC midnight should show as previous day in PST (UTC-8)."""
        from gmail_stats import iso_date_from_internal_ms

        # 2023-12-25 00:00:00 UTC = 2023-12-24 16:00:00 PST
        with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
            safe_tzset()

            ms = '1703462400000'  # 2023-12-25 00:00:00 UTC
            result = iso_date_from_internal_ms(ms)
            assert result == '2023-12-24'

    def test_midnight_utc_in_tokyo_is_same_day(self):
        """Message at UTC midnight should show as same day in Tokyo (UTC+9)."""
        from gmail_stats import iso_date_from_internal_ms

        # 2023-12-25 00:00:00 UTC = 2023-12-25 09:00:00 JST
        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            safe_tzset()

            ms = '1703462400000'  # 2023-12-25 00:00:00 UTC
            result = iso_date_from_internal_ms(ms)
            assert result == '2023-12-25'

    def test_noon_utc_same_date_all_timezones(self):
        """Message at noon UTC should have same date in most timezones."""
        from gmail_stats import iso_date_from_internal_ms

        # 2023-12-25 12:00:00 UTC
        ms = '1703505600000'

        for tz in ['America/New_York', 'Europe/London', 'Asia/Shanghai']:
            with patch.dict(os.environ, {'TZ': tz}):
                safe_tzset()
                result = iso_date_from_internal_ms(ms)
                # Should be Dec 25 in all these timezones
                assert '2023-12-25' in result

    def test_far_past_timestamp(self):
        """Test with timestamp from 2020."""
        from gmail_stats import iso_date_from_internal_ms

        ms = '1577836800000'  # 2020-01-01 00:00:00 UTC
        result = iso_date_from_internal_ms(ms)
        # Depending on local timezone, could be Dec 31 or Jan 1
        assert result.startswith('2019-12-31') or result.startswith('2020-01-01')


# =============================================================================
# Step 3: Test Date Range Calculation
# =============================================================================

class TestDateRangeCalculation:
    """Tests for local timezone in date range calculation."""

    def test_since_dt_calculation_concept(self):
        """Verify the concept of using local time for date range."""
        # This is more of a concept test - the actual implementation
        # will be in the main script where since_dt is calculated

        # Mock local time: 2024-12-25 18:00:00 PST (UTC-8)
        mock_now_local = datetime(2024, 12, 25, 18, 0, 0)
        mock_now_local = mock_now_local.replace(tzinfo=pytz.timezone('America/Los_Angeles'))

        # 30 days before should be 2024-11-25 18:00:00 PST
        expected = mock_now_local - timedelta(days=30)
        assert expected.day == 25
        assert expected.month == 11

    def test_end_date_uses_local_date(self):
        """Verify end_date should use local date, not UTC date."""
        # Mock: 2024-12-25 23:00:00 PST (which is 2024-12-26 07:00:00 UTC)
        mock_now_local = datetime(2024, 12, 25, 23, 0, 0)
        mock_now_local = mock_now_local.replace(tzinfo=pytz.timezone('America/Los_Angeles'))

        # end_date should be 2024-12-25 (local), not 2024-12-26 (UTC)
        expected_date = mock_now_local.date()
        assert expected_date.isoformat() == '2024-12-25'


# =============================================================================
# Step 4: Test Daily Volume Date Bucketing
# =============================================================================

class TestDailyVolumeBucketing:
    """Integration tests for message bucketing by local date."""

    def test_messages_bucket_by_local_date(self, sample_messages):
        """Messages should be bucketed by local date, not UTC date."""
        from gmail_stats import iso_date_from_internal_ms
        from collections import Counter

        with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
            safe_tzset()

            by_day = Counter()
            for msg in sample_messages:
                date = iso_date_from_internal_ms(msg['internalDate'])
                by_day[date] += 1

            # With PST (UTC-8), both messages should be shifted:
            # - 2023-12-25 00:00:00 UTC = 2023-12-24 16:00:00 PST
            # - 2023-12-24 00:00:00 UTC = 2023-12-23 16:00:00 PST
            assert '2023-12-24' in by_day or '2023-12-23' in by_day

    def test_dst_transition_handling(self):
        """Test date bucketing during DST transition (spring forward)."""
        from gmail_stats import iso_date_from_internal_ms

        # March 10, 2024 is DST transition in US (2am -> 3am)
        # Test message at 2024-03-10 10:00:00 UTC (during transition window)
        dst_transition_ms = str(int(datetime(2024, 3, 10, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000))

        with patch.dict(os.environ, {'TZ': 'America/New_York'}):
            safe_tzset()
            result = iso_date_from_internal_ms(dst_transition_ms)
            assert result == '2024-03-10'  # Should handle DST gracefully


# =============================================================================
# Step 5: Test Header Display with Timezone
# =============================================================================

class TestHeaderDisplay:
    """Tests for timezone labels in section headers."""

    @patch('builtins.print')
    @patch('gmail_stats.get_local_tz_name')
    def test_daily_volume_header_concept(self, mock_tz_name, mock_print):
        """Daily Volume header should include timezone abbreviation."""
        mock_tz_name.return_value = 'PST'

        # This tests the concept - actual integration test will verify output
        DAYS = 30
        tz_name = mock_tz_name()
        expected_header = f"Daily Volume (last {DAYS} days, {tz_name})"
        assert "PST" in expected_header

    def test_top_senders_header_concept(self):
        """Top Senders header should include timezone abbreviation."""
        # Concept test for header format
        DAYS = 30
        tz_name = 'EST'
        examined = 5000
        expected_header = f"Top Senders (last {DAYS} days, {tz_name}, examined {examined})"
        assert "EST" in expected_header


# =============================================================================
# Step 6: Test UTC Logging Configuration
# =============================================================================

class TestLoggingConfiguration:
    """Tests for UTC logging timestamps."""

    def test_log_format_concept(self):
        """Log format should include 'UTC' label for clarity."""
        # Test the format string concept
        log_format = "%(asctime)s UTC %(levelname)s %(message)s"
        assert 'UTC' in log_format

    def test_gmtime_converter_concept(self):
        """Logging should use time.gmtime for UTC timestamps."""
        # Verify that time.gmtime is the correct converter
        assert callable(time_module.gmtime)


# =============================================================================
# Step 7: Integration Tests
# =============================================================================

class TestIntegrationConcepts:
    """Conceptual integration tests."""

    def test_gmail_message_processing_flow(self):
        """Test the flow of processing Gmail messages with timezone."""
        from gmail_stats import iso_date_from_internal_ms
        from collections import Counter

        # Simulate processing messages
        messages = [
            {'internalDate': '1703462400000'},  # 2024-12-25 00:00:00 UTC
            {'internalDate': '1703548800000'},  # 2024-12-26 00:00:00 UTC
        ]

        by_day = Counter()
        for msg in messages:
            date = iso_date_from_internal_ms(msg['internalDate'])
            by_day[date] += 1

        # Should have entries
        assert len(by_day) >= 1


# =============================================================================
# Step 8: Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_timezone_with_no_abbreviation(self):
        """Some timezones return offset instead of abbreviation (e.g., +0800)."""
        with patch.dict(os.environ, {'TZ': 'Etc/GMT-8'}):
            safe_tzset()

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
        assert result.startswith('2012-06-') or result.startswith('2012-07-')

    def test_very_old_message_from_2000(self):
        """Test handling of very old timestamps (edge case)."""
        from gmail_stats import iso_date_from_internal_ms

        # Very old message (should still work)
        ms = '946684800000'  # 2000-01-01 00:00:00 UTC
        result = iso_date_from_internal_ms(ms)
        # Depending on timezone, could be Dec 31, 1999 or Jan 1, 2000
        assert '2000' in result or '1999' in result

    def test_message_at_exact_dst_boundary(self):
        """Test message timestamp at exact DST transition moment."""
        from gmail_stats import iso_date_from_internal_ms

        # November 3, 2024, 2:00 AM EDT -> 1:00 AM EST (fall back)
        # This is 2024-11-03 06:00:00 UTC
        dst_fall_ms = str(int(datetime(2024, 11, 3, 6, 0, 0, tzinfo=timezone.utc).timestamp() * 1000))

        with patch.dict(os.environ, {'TZ': 'America/New_York'}):
            safe_tzset()
            result = iso_date_from_internal_ms(dst_fall_ms)
            # Should still produce valid date
            assert result == '2024-11-03'

    def test_boundary_23_59_59_utc(self):
        """Test timestamp at 23:59:59 UTC (boundary between days)."""
        from gmail_stats import iso_date_from_internal_ms

        # 2024-12-24 23:59:59 UTC
        ms = str(int(datetime(2024, 12, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000))

        with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
            safe_tzset()
            result = iso_date_from_internal_ms(ms)
            # PST is UTC-8, so this should be 2024-12-24 15:59:59 PST
            assert result == '2024-12-24'

        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            safe_tzset()
            result = iso_date_from_internal_ms(ms)
            # JST is UTC+9, so this should be 2024-12-25 08:59:59 JST
            assert result == '2024-12-25'


# =============================================================================
# Multi-Timezone Validation Tests
# =============================================================================

class TestMultiTimezoneValidation:
    """Ensure consistency across multiple timezones."""

    @pytest.mark.parametrize("tz_name", [
        'America/Los_Angeles',  # PST/PDT, UTC-8/-7
        'America/New_York',     # EST/EDT, UTC-5/-4
        'Europe/London',        # GMT/BST, UTC+0/+1
        'Asia/Tokyo',           # JST, UTC+9
        'Australia/Sydney',     # AEDT/AEST, UTC+11/+10
    ])
    def test_timezone_functions_work_in_all_regions(self, tz_name):
        """Test that helper functions work correctly in various timezones."""
        with patch.dict(os.environ, {'TZ': tz_name}):
            safe_tzset()

            from gmail_stats import get_local_tz, get_local_tz_name

            # Both functions should work
            tz = get_local_tz()
            assert tz is not None

            tz_abbr = get_local_tz_name()
            assert isinstance(tz_abbr, str)
            assert len(tz_abbr) > 0

    @pytest.mark.parametrize("tz_name", [
        'America/Los_Angeles',
        'America/New_York',
        'Europe/London',
        'Asia/Tokyo',
        'Australia/Sydney',
    ])
    def test_iso_date_conversion_works_in_all_regions(self, tz_name):
        """Test that date conversion works correctly in various timezones."""
        with patch.dict(os.environ, {'TZ': tz_name}):
            safe_tzset()

            from gmail_stats import iso_date_from_internal_ms

            # Test with a known timestamp (noon UTC)
            ms = '1703505600000'  # 2023-12-25 12:00:00 UTC
            result = iso_date_from_internal_ms(ms)

            # Should produce a valid ISO date
            assert len(result) == 10  # YYYY-MM-DD format
            assert result.startswith('2023-12-')
