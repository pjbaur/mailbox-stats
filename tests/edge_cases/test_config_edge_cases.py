"""Edge case tests for configuration parameters.

Tests various edge cases and invalid configurations to ensure the
application handles them gracefully or raises appropriate errors.
"""

import importlib
import logging
import os
import sys
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment fixture that removes all config env vars."""
    env_vars = [
        "DAYS",
        "SAMPLE_MAX_IDS",
        "BATCH_DELAY",
        "BATCH_SIZE",
        "SLEEP_BETWEEN_BATCHES",
        "SLEEP_EVERY_N_BATCHES",
        "SLEEP_LONG_DURATION",
        "MAX_RETRIES",
        "INITIAL_RETRY_DELAY",
        "MAX_RETRY_DELAY",
        "LOG_LEVEL",
        "LOG_EVERY",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    yield


def reload_gmail_stats():
    """Reload gmail_stats module to pick up env changes."""
    if "gmail_stats" in sys.modules:
        return importlib.reload(sys.modules["gmail_stats"])
    else:
        import gmail_stats
        return gmail_stats


def test_zero_days_config(monkeypatch, clean_env):
    """Test DAYS=0 edge case.

    With DAYS=0, the Gmail query will be 'newer_than:0d' which should
    match all messages (not just recent ones). This is a valid configuration
    but may result in many messages being examined.
    """
    monkeypatch.setenv("DAYS", "0")

    # Reload to pick up new config
    gmail_stats = reload_gmail_stats()

    # Verify config was loaded
    assert gmail_stats.DAYS == 0

    # The application should handle this, though it may be slow
    # No error should be raised during configuration


def test_negative_days_config(monkeypatch, clean_env):
    """Test DAYS=-1 invalid input.

    Negative days doesn't make logical sense. The application will load it
    but the Gmail query 'newer_than:-1d' may behave unexpectedly.
    Ideally this should be validated at startup.
    """
    monkeypatch.setenv("DAYS", "-1")

    # Reload to pick up new config
    gmail_stats = reload_gmail_stats()

    # Config loads but value is negative
    assert gmail_stats.DAYS == -1

    # Note: In production, this should probably raise a ValueError
    # during validation. For now, we document the behavior.


def test_zero_sample_max_ids(monkeypatch, clean_env):
    """Test unlimited sampling (SAMPLE_MAX_IDS=0).

    SAMPLE_MAX_IDS=0 means "no limit" - fetch all matching messages.
    This is a valid configuration for small mailboxes or when you want
    complete data regardless of runtime.
    """
    monkeypatch.setenv("SAMPLE_MAX_IDS", "0")

    # Reload to pick up new config
    gmail_stats = reload_gmail_stats()

    # Verify config was loaded
    assert gmail_stats.SAMPLE_MAX_IDS == 0

    # Test that list_all_message_ids respects max_ids=0 (unlimited)
    mock_service = Mock()

    # Mock paginated responses
    first_response = {
        "messages": [{"id": str(i)} for i in range(500)],
        "nextPageToken": "token1"
    }
    second_response = {
        "messages": [{"id": str(i)} for i in range(500, 1000)]
    }

    mock_service.users().messages().list().execute.side_effect = [
        first_response,
        second_response
    ]

    # With max_ids=0, should fetch all pages
    result = gmail_stats.list_all_message_ids(mock_service, "test query", None, max_ids=0)

    assert len(result) == 1000


def test_invalid_log_level(monkeypatch, clean_env, caplog):
    """Test invalid LOG_LEVEL.

    If LOG_LEVEL is set to an invalid value, logging.getLogger()
    should raise an AttributeError when trying to get the level.
    """
    monkeypatch.setenv("LOG_LEVEL", "INVALID")

    # Attempting to reload with invalid log level should raise
    with pytest.raises(AttributeError):
        # This will fail when trying to do getattr(logging, "INVALID")
        gmail_stats = reload_gmail_stats()


def test_zero_max_retries(monkeypatch, clean_env):
    """Test MAX_RETRIES=0.

    With MAX_RETRIES=0, the retry loop (range(0)) will not execute at all,
    so the function returns an empty list without making any API calls.
    This is a degenerate edge case where the configuration prevents any work.
    """
    monkeypatch.setenv("MAX_RETRIES", "0")

    # Reload to pick up new config
    gmail_stats = reload_gmail_stats()

    # Verify config was loaded
    assert gmail_stats.MAX_RETRIES == 0

    # Test batch_get_metadata with MAX_RETRIES=0
    mock_service = Mock()

    # With MAX_RETRIES=0, the loop `for attempt in range(0)` doesn't execute
    # So the function should return an empty list without any API calls
    result = gmail_stats.batch_get_metadata(mock_service, ["id1", "id2"])

    # Should return empty list since loop never executes
    assert result == []

    # No batch should have been created
    mock_service.new_batch_http_request.assert_not_called()

    # Clean up: Restore default value
    monkeypatch.setenv("MAX_RETRIES", "5")
    reload_gmail_stats()


def test_negative_batch_delay(monkeypatch, clean_env):
    """Test BATCH_DELAY=-0.5.

    Negative delay doesn't make sense. The time.sleep() function will
    raise ValueError if given a negative value.
    """
    monkeypatch.setenv("BATCH_DELAY", "-0.5")

    # Reload to pick up new config
    gmail_stats = reload_gmail_stats()

    # Config loads with negative value
    assert gmail_stats.BATCH_DELAY == -0.5

    # However, if code actually calls time.sleep(BATCH_DELAY),
    # it will raise ValueError
    import time

    with pytest.raises(ValueError):
        time.sleep(gmail_stats.BATCH_DELAY)

    # Note: In production, configuration should validate that
    # BATCH_DELAY >= 0

    # Clean up: Restore default value to prevent test pollution
    monkeypatch.setenv("BATCH_DELAY", "0.25")
    reload_gmail_stats()
