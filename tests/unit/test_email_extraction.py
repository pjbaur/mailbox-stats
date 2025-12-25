"""Unit tests for extract_email() function.

Tests the email extraction and normalization logic from From headers.
Priority: P0 (data accuracy critical)
"""

import pytest
from gmail_stats import extract_email


def test_extract_email_simple_address():
    """Test extraction from plain email."""
    assert extract_email("john@example.com") == "john@example.com"


def test_extract_email_with_display_name():
    """Test extraction from display name format."""
    assert extract_email("John Doe <john@example.com>") == "john@example.com"


def test_extract_email_uppercase_normalization():
    """Test lowercase conversion."""
    assert extract_email("JOHN@EXAMPLE.COM") == "john@example.com"


def test_extract_email_complex_address():
    """Test plus addressing and subdomains."""
    assert extract_email("user+tag@sub.domain.example.com") == "user+tag@sub.domain.example.com"


def test_extract_email_with_whitespace():
    """Test trimming whitespace."""
    assert extract_email("  john@example.com  ") == "john@example.com"


def test_extract_email_none_input():
    """Test null handling."""
    assert extract_email(None) == "(unknown)"


def test_extract_email_empty_string():
    """Test empty string handling."""
    assert extract_email("") == "(unknown)"


def test_extract_email_invalid_format():
    """Test fallback for no @ sign."""
    result = extract_email("not-an-email")
    assert result == "not-an-email"


def test_extract_email_multiple_addresses():
    """Test first address extraction."""
    assert extract_email("first@test.com and second@test.com") == "first@test.com"


def test_extract_email_special_characters():
    """Test special chars in local part."""
    assert extract_email("user_name.test+label@example.com") == "user_name.test+label@example.com"


def test_extract_email_quoted_display_name():
    """Test quoted strings in display name."""
    assert extract_email('"Doe, John" <john@example.com>') == "john@example.com"


def test_extract_email_international_domain():
    """Test TLD with more than 2 characters."""
    assert extract_email("test@example.info") == "test@example.info"
