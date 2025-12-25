"""Edge case tests for data processing.

Tests various edge cases in data handling including unusual email formats,
extreme timestamps, missing fields, and edge cases in statistics aggregation.
"""

from collections import Counter

import pytest

from gmail_stats import extract_email, iso_date_from_internal_ms


def test_empty_from_header():
    """Test message with no From header.

    When the From header is empty or None, extract_email should
    return "(unknown)" as a safe fallback.
    """
    # None input
    result = extract_email(None)
    assert result == "(unknown)"

    # Empty string
    result = extract_email("")
    assert result == "(unknown)"

    # Whitespace only
    result = extract_email("   ")
    # Will return stripped/lowercased whitespace or match attempt
    assert isinstance(result, str)


def test_unicode_email():
    """Test unicode characters in email.

    Email addresses with internationalized domain names (IDN) or
    unicode characters may or may not match the EMAIL_RE pattern.
    The conservative regex may not match these, falling back to
    the original input (stripped and lowercased).
    """
    # Unicode domain (IDN)
    unicode_email = "user@münchen.de"
    result = extract_email(unicode_email)

    # EMAIL_RE is [A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}
    # This won't match "ü" so it will fall back to original input
    assert isinstance(result, str)
    assert result == unicode_email.lower()

    # Unicode in local part
    unicode_local = "müller@example.com"
    result = extract_email(unicode_local)
    assert isinstance(result, str)

    # Emoji in email (pathological case)
    emoji_email = "test😀@example.com"
    result = extract_email(emoji_email)
    assert isinstance(result, str)


def test_very_long_email():
    """Test email > 254 characters.

    Email addresses have a maximum length of 254 characters per RFC.
    Very long emails should be handled without crashing, though they
    may not match the regex pattern.
    """
    # Generate an email that's too long
    long_local_part = "a" * 300
    long_email = f"{long_local_part}@example.com"

    result = extract_email(long_email)

    # Should not crash
    assert isinstance(result, str)
    assert len(result) > 254

    # Very long domain
    long_domain = "a" * 250 + ".com"
    long_email2 = f"user@{long_domain}"
    result2 = extract_email(long_email2)
    assert isinstance(result2, str)


def test_timestamp_zero():
    """Test epoch timestamp (now uses local timezone).

    Timestamp 0 represents the Unix epoch: 1970-01-01 00:00:00 UTC.
    In local timezone, could be 1969-12-31 or 1970-01-01 depending on offset.
    """
    result = iso_date_from_internal_ms("0")
    assert result in ["1969-12-31", "1970-01-01"]


def test_timestamp_far_future():
    """Test year 2100 timestamp (now uses local timezone).

    Test a timestamp far in the future to ensure the date conversion
    handles large values correctly.
    """
    # 4102444800000 ms = 2100-01-01 00:00:00 UTC
    # Could be 2099-12-31, 2100-01-01, or 2100-01-02 in local timezone
    result = iso_date_from_internal_ms("4102444800000")
    assert "2099-12-31" in result or "2100-01-01" in result or "2100-01-02" in result

    # Test year 2286 (from test plan example)
    # 9999999999999 ms ≈ 2286-11-20
    result2 = iso_date_from_internal_ms("9999999999999")
    assert "2286" in result2


def test_message_missing_size_estimate():
    """Test message without sizeEstimate field.

    Gmail messages should have a sizeEstimate field, but if it's missing,
    the code should handle it gracefully using .get() with a default.
    """
    # Simulate message without sizeEstimate
    msg = {
        "id": "123",
        "internalDate": "1704067200000"
    }

    # Access pattern from main()
    size = int(msg.get("sizeEstimate", 0))
    assert size == 0

    # Message with sizeEstimate
    msg_with_size = {
        "id": "456",
        "internalDate": "1704067200000",
        "sizeEstimate": 1024
    }
    size2 = int(msg_with_size.get("sizeEstimate", 0))
    assert size2 == 1024


def test_all_messages_same_sender():
    """Test statistics with single sender.

    When all messages come from the same sender, the by_sender Counter
    should have only one entry. This tests that the statistics display
    handles this edge case correctly.
    """
    # Simulate processing messages from single sender
    by_sender = Counter()

    messages = [
        {
            "id": f"id{i}",
            "internalDate": "1704067200000",
            "sizeEstimate": 100,
            "payload": {
                "headers": [{"name": "From", "value": "single@example.com"}]
            }
        }
        for i in range(100)
    ]

    # Process messages
    for msg in messages:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        from_email = extract_email(headers.get("From"))
        by_sender[from_email] += 1

    # Should have exactly one sender
    assert len(by_sender) == 1
    assert by_sender["single@example.com"] == 100

    # Top 25 senders should still work
    top_senders = by_sender.most_common(25)
    assert len(top_senders) == 1
    assert top_senders[0] == ("single@example.com", 100)


def test_all_messages_same_day():
    """Test all messages on one day (now uses local timezone).

    When all messages are from the same day, the by_day Counter
    should have only one entry. This tests that the daily volume
    chart displays correctly for this edge case.
    """
    # Simulate processing messages from same day
    by_day = Counter()

    # All messages at same timestamp
    timestamp = "1704067200000"  # 2024-01-01 00:00:00 UTC

    messages = [
        {
            "id": f"id{i}",
            "internalDate": timestamp,
            "sizeEstimate": 100,
            "payload": {"headers": [{"name": "From", "value": f"sender{i}@test.com"}]}
        }
        for i in range(50)
    ]

    # Process messages
    for msg in messages:
        iso_date = iso_date_from_internal_ms(msg["internalDate"])
        by_day[iso_date] += 1

    # Should have exactly one day (date depends on local timezone)
    assert len(by_day) == 1
    # First (and only) date should have all 50 messages
    assert list(by_day.values())[0] == 50

    # Daily volume display should still work
    for day, count in sorted(by_day.items()):
        # Formatting from main()
        line = f"{day}  {count:5d}"
        assert "2024" in line or "2023" in line  # Could be either year depending on timezone
        assert "50" in line


def test_message_missing_payload():
    """Test message with missing or malformed payload.

    If a message is missing the payload field entirely, accessing
    headers should be handled gracefully.
    """
    # Message without payload
    msg_no_payload = {
        "id": "123",
        "internalDate": "1704067200000",
        "sizeEstimate": 100
    }

    # Safe access pattern
    payload = msg_no_payload.get("payload", {})
    headers_list = payload.get("headers", [])
    headers = {h["name"]: h["value"] for h in headers_list}

    # Should be empty dict
    assert headers == {}
    assert headers.get("From") is None

    # extract_email on None should return "(unknown)"
    from_email = extract_email(headers.get("From"))
    assert from_email == "(unknown)"


def test_message_headers_empty():
    """Test message with empty headers list.

    Some messages might have a payload but an empty headers list.
    """
    msg = {
        "id": "123",
        "internalDate": "1704067200000",
        "sizeEstimate": 100,
        "payload": {
            "headers": []
        }
    }

    # Process headers
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    assert headers == {}

    # Extract email from missing From header
    from_email = extract_email(headers.get("From"))
    assert from_email == "(unknown)"


def test_negative_timestamp():
    """Test pre-epoch timestamp (now uses local timezone).

    Timestamps before 1970-01-01 are represented as negative values.
    The code should handle these correctly.
    """
    # -86400000 ms = 1969-12-31 00:00:00 UTC
    # Could be 1969-12-30 or 1969-12-31 in local timezone
    result = iso_date_from_internal_ms("-86400000")
    assert result in ["1969-12-30", "1969-12-31"]

    # Pre-1970 date
    # -31536000000 ms = 1969-01-01 00:00:00 UTC
    result2 = iso_date_from_internal_ms("-31536000000")
    assert "1969" in result2 or "1968" in result2


def test_malformed_email_patterns():
    """Test various malformed or unusual email patterns.

    Tests that extract_email handles edge cases gracefully.
    """
    # Multiple @ symbols
    result = extract_email("user@@example.com")
    assert isinstance(result, str)

    # No domain
    result = extract_email("justtext")
    assert result == "justtext"

    # Missing TLD
    result = extract_email("user@localhost")
    # Regex requires [A-Z]{2,} TLD, so won't match
    assert result == "user@localhost"

    # Dots in wrong places
    result = extract_email(".user@example.com")
    assert isinstance(result, str)

    # Comma-separated list (common in CC headers)
    result = extract_email("user1@test.com, user2@test.com")
    # Should extract first match
    assert "@" in result
