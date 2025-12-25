"""Unit tests for count_request() and log_request_totals() functions.

Tests the API request tracking and logging functionality.
Priority: P2 (observability)
"""

from collections import defaultdict

import pytest
import gmail_stats


def test_count_request_single():
    """Test single request tracking."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)

    gmail_stats.count_request("users.messages.get")
    assert gmail_stats.REQUEST_TOTAL == 1
    assert gmail_stats.REQUESTS_BY_ENDPOINT["users.messages.get"] == 1


def test_count_request_multiple():
    """Test multiple request tracking."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)

    gmail_stats.count_request("users.messages.get", 5)
    assert gmail_stats.REQUEST_TOTAL == 5
    assert gmail_stats.REQUESTS_BY_ENDPOINT["users.messages.get"] == 5


def test_count_request_multiple_endpoints():
    """Test different endpoints."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)

    gmail_stats.count_request("users.messages.get", 3)
    gmail_stats.count_request("users.labels.list", 1)
    assert gmail_stats.REQUEST_TOTAL == 4
    assert gmail_stats.REQUESTS_BY_ENDPOINT["users.messages.get"] == 3
    assert gmail_stats.REQUESTS_BY_ENDPOINT["users.labels.list"] == 1


def test_log_request_totals_zero(caplog):
    """Test logging with zero requests."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)

    with caplog.at_level("INFO", logger="gmail_stats"):
        gmail_stats.log_request_totals()
    assert "none" in caplog.text.lower()


def test_log_request_totals_with_data(caplog):
    """Test logging with request data."""
    gmail_stats.REQUEST_TOTAL = 10
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int, {"endpoint1": 7, "endpoint2": 3})

    with caplog.at_level("INFO", logger="gmail_stats"):
        gmail_stats.log_request_totals()
    assert "10" in caplog.text
    assert "endpoint1=7" in caplog.text


def test_log_request_totals_sorting(caplog):
    """Test endpoints sorted by count descending."""
    gmail_stats.REQUEST_TOTAL = 15
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int, {"low": 2, "high": 10, "medium": 3})

    with caplog.at_level("INFO", logger="gmail_stats"):
        gmail_stats.log_request_totals()
    # "high" should appear before "medium" and "low"
    assert "high=10" in caplog.text

    # Verify sorting by finding positions in log text
    high_pos = caplog.text.find("high=10")
    medium_pos = caplog.text.find("medium=3")
    low_pos = caplog.text.find("low=2")

    assert high_pos < medium_pos < low_pos
