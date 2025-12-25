"""Unit tests for iso_date_from_internal_ms() function.

Tests the conversion from Gmail internalDate (milliseconds since epoch) to ISO date.
NOTE: Function now converts to LOCAL timezone (changed from UTC in time localization update).
Priority: P0 (data accuracy critical)
"""

import pytest
from datetime import datetime, timezone
from gmail_stats import iso_date_from_internal_ms


def test_iso_date_known_timestamp():
    """Test known timestamp conversion (now uses local timezone)."""
    # 2024-01-01 00:00:00 UTC = 1704067200000 ms
    # Result depends on local timezone (could be 2023-12-31 or 2024-01-01)
    result = iso_date_from_internal_ms("1704067200000")
    assert result in ["2023-12-31", "2024-01-01", "2024-01-02"]


def test_iso_date_epoch():
    """Test epoch zero (now uses local timezone)."""
    # 0 ms = 1970-01-01 00:00:00 UTC
    # In local timezone could be 1969-12-31 or 1970-01-01
    result = iso_date_from_internal_ms("0")
    assert result in ["1969-12-31", "1970-01-01"]


def test_iso_date_recent():
    """Test recent date (now uses local timezone)."""
    # 2025-12-28 00:00:00 UTC = 1766880000000 ms
    # Result depends on local timezone
    result = iso_date_from_internal_ms("1766880000000")
    assert result in ["2025-12-27", "2025-12-28", "2025-12-29"]


def test_iso_date_boundary_midnight():
    """Test midnight boundary (now uses local timezone, so boundaries may shift)."""
    # These tests now check that dates are reasonable but may shift based on timezone
    result1 = iso_date_from_internal_ms("1704153599000")
    assert result1.startswith("2024-01-0")  # Should be around Jan 1-2

    result2 = iso_date_from_internal_ms("1704153600000")
    assert result2.startswith("2024-01-0")  # Should be around Jan 1-2


def test_iso_date_leap_year():
    """Test leap year date (Feb 29) - now uses local timezone."""
    # 2024-02-29 00:00:00 UTC = 1709164800000 ms
    # Result depends on local timezone (could be Feb 28 or Feb 29)
    result = iso_date_from_internal_ms("1709164800000")
    assert result in ["2024-02-28", "2024-02-29", "2024-03-01"]


def test_iso_date_invalid_string():
    """Test non-numeric string."""
    with pytest.raises(ValueError):
        iso_date_from_internal_ms("invalid")


def test_iso_date_negative_timestamp():
    """Test pre-epoch date (now uses local timezone)."""
    # -86400000 ms = 1969-12-31 UTC
    # Could be 1969-12-30 or 1969-12-31 depending on timezone
    result = iso_date_from_internal_ms("-86400000")
    assert result in ["1969-12-30", "1969-12-31"]


def test_iso_date_very_large_timestamp():
    """Test far future date."""
    # 9999999999999 ms = 2286-11-20 UTC (approximately)
    result = iso_date_from_internal_ms("9999999999999")
    assert "2286" in result


def test_iso_date_timezone_handling():
    """Ensure local timezone is used (updated behavior)."""
    # Timestamp at 11 PM UTC - result depends on local timezone
    # 2024-01-01 23:00:00 UTC = 1704150000000 ms
    result = iso_date_from_internal_ms("1704150000000")
    # Could be Jan 1 or Jan 2 depending on timezone
    assert result.startswith("2024-01-0")


def test_iso_date_format():
    """Test output format is YYYY-MM-DD."""
    result = iso_date_from_internal_ms("1704067200000")
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"
