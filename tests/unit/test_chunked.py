"""Unit tests for chunked() function.

Tests the list chunking utility used for batch processing.
Priority: P1 (critical for batch processing)
"""

import pytest
from gmail_stats import chunked


def test_chunked_empty_list():
    """Test empty input."""
    result = list(chunked([], 2))
    assert result == []


def test_chunked_single_element():
    """Test single element with chunk size > 1."""
    result = list(chunked(["a"], 2))
    assert result == [["a"]]


def test_chunked_exact_division():
    """Test list divides evenly."""
    result = list(chunked(["a", "b", "c", "d"], 2))
    assert result == [["a", "b"], ["c", "d"]]


def test_chunked_uneven_division():
    """Test remainder in last chunk."""
    result = list(chunked(["a", "b", "c"], 2))
    assert result == [["a", "b"], ["c"]]


def test_chunked_size_one():
    """Test chunk size of 1."""
    result = list(chunked(["a", "b", "c"], 1))
    assert result == [["a"], ["b"], ["c"]]


def test_chunked_size_larger_than_list():
    """Test chunk size exceeds list length."""
    result = list(chunked(["a"], 5))
    assert result == [["a"]]


def test_chunked_exact_fit():
    """Test chunk size equals list length."""
    result = list(chunked(["a", "b", "c"], 3))
    assert result == [["a", "b", "c"]]


def test_chunked_large_list():
    """Test performance with large list."""
    large_list = [str(i) for i in range(1000)]
    result = list(chunked(large_list, 10))
    assert len(result) == 100
    assert all(len(chunk) == 10 for chunk in result)
