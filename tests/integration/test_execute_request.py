"""Integration tests for execute_request() function."""

import pytest
from unittest.mock import Mock
from googleapiclient.errors import HttpError
import gmail_stats


def test_execute_request_success():
    """Test successful request execution."""
    # Reset global counters
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_request = Mock()
    mock_request.execute.return_value = {"status": "ok"}

    result = gmail_stats.execute_request(mock_request, "test.endpoint")

    assert result == {"status": "ok"}
    assert gmail_stats.REQUEST_TOTAL == 1
    assert gmail_stats.REQUESTS_BY_ENDPOINT["test.endpoint"] == 1
    mock_request.execute.assert_called_once()


def test_execute_request_http_error_429():
    """Test rate limit error propagation."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_request = Mock()
    mock_resp = Mock(status=429)
    mock_request.execute.side_effect = HttpError(
        resp=mock_resp,
        content=b"Rate limit"
    )

    with pytest.raises(HttpError) as exc:
        gmail_stats.execute_request(mock_request, "test.endpoint")
    assert exc.value.resp.status == 429
    # Request should still be counted
    assert gmail_stats.REQUEST_TOTAL == 1


def test_execute_request_http_error_403():
    """Test forbidden error."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_request = Mock()
    mock_resp = Mock(status=403)
    mock_request.execute.side_effect = HttpError(
        resp=mock_resp,
        content=b"Forbidden"
    )

    with pytest.raises(HttpError) as exc:
        gmail_stats.execute_request(mock_request, "test.endpoint")
    assert exc.value.resp.status == 403


def test_execute_request_network_error():
    """Test network error propagation."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_request = Mock()
    mock_request.execute.side_effect = ConnectionError("Network failure")

    with pytest.raises(ConnectionError):
        gmail_stats.execute_request(mock_request, "test.endpoint")


def test_execute_request_counts_before_exception():
    """Test request counted even if it fails."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_request = Mock()
    mock_resp = Mock(status=500)
    mock_request.execute.side_effect = HttpError(
        resp=mock_resp,
        content=b"Server error"
    )

    with pytest.raises(HttpError):
        gmail_stats.execute_request(mock_request, "test.endpoint")

    # Request should be counted before the exception
    assert gmail_stats.REQUEST_TOTAL == 1
    assert gmail_stats.REQUESTS_BY_ENDPOINT["test.endpoint"] == 1
