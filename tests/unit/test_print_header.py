"""Unit tests for print_header() function.

Tests the CLI header printing utility.
Priority: P3 (cosmetic)
"""

import pytest
from gmail_stats import print_header


def test_print_header_normal(capsys):
    """Test normal header printing."""
    print_header("Test")
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert len(lines) == 3
    assert lines[0] == "=" * len("Test")
    assert lines[1] == "Test"
    assert lines[2] == "=" * len("Test")


def test_print_header_empty(capsys):
    """Test empty string."""
    print_header("")
    captured = capsys.readouterr()
    # Empty title produces empty equals lines, resulting in just newlines
    assert "\n\n\n" in captured.out


def test_print_header_long(capsys):
    """Test long title."""
    title = "Very Long Header Title Here"
    print_header(title)
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert lines[1] == title
    assert len(lines[0]) == len(title)


def test_print_header_special_chars(capsys):
    """Test special characters."""
    print_header("Test (with special) chars!")
    captured = capsys.readouterr()
    assert "Test (with special) chars!" in captured.out
