"""Unit tests for iso_date_from_internal_ms() function.

Tests the conversion from Gmail internalDate (milliseconds since epoch) to ISO date.
Priority: P0 (data accuracy critical)
"""

import pytest
from gmail_stats import iso_date_from_internal_ms


def test_iso_date_known_timestamp():
    """Test known timestamp conversion."""
    # 2024-01-01 00:00:00 UTC = 1704067200000 ms
    assert iso_date_from_internal_ms("1704067200000") == "2024-01-01"


def test_iso_date_epoch():
    """Test epoch zero."""
    assert iso_date_from_internal_ms("0") == "1970-01-01"


def test_iso_date_recent():
    """Test recent date."""
    # 2025-12-28 00:00:00 UTC = 1766880000000 ms
    assert iso_date_from_internal_ms("1766880000000") == "2025-12-28"


def test_iso_date_boundary_midnight():
    """Test midnight boundary (23:59:59 vs 00:00:00)."""
    # 2024-01-01 23:59:59 UTC = 1704153599000 ms
    assert iso_date_from_internal_ms("1704153599000") == "2024-01-01"
    # 2024-01-02 00:00:00 UTC = 1704153600000 ms
    assert iso_date_from_internal_ms("1704153600000") == "2024-01-02"


def test_iso_date_leap_year():
    """Test leap year date (Feb 29)."""
    # 2024-02-29 00:00:00 UTC = 1709164800000 ms
    assert iso_date_from_internal_ms("1709164800000") == "2024-02-29"


def test_iso_date_invalid_string():
    """Test non-numeric string."""
    with pytest.raises(ValueError):
        iso_date_from_internal_ms("invalid")


def test_iso_date_negative_timestamp():
    """Test pre-epoch date (if supported)."""
    # -86400000 ms = 1969-12-31
    result = iso_date_from_internal_ms("-86400000")
    assert result == "1969-12-31"


def test_iso_date_very_large_timestamp():
    """Test far future date."""
    # 9999999999999 ms = 2286-11-20
    result = iso_date_from_internal_ms("9999999999999")
    assert "2286" in result


def test_iso_date_timezone_handling():
    """Ensure UTC timezone used."""
    # Timestamp at 11 PM UTC should be same day
    # 2024-01-01 23:00:00 UTC = 1704150000000 ms
    assert iso_date_from_internal_ms("1704150000000") == "2024-01-01"


def test_iso_date_format():
    """Test output format is YYYY-MM-DD."""
    result = iso_date_from_internal_ms("1704067200000")
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"
