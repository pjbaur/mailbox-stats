"""Integration tests for batch_get_metadata() function."""

import pytest
from unittest.mock import Mock, MagicMock, call
from googleapiclient.errors import HttpError
import gmail_stats


def test_batch_get_empty_list():
    """Test empty message list."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()

    result = gmail_stats.batch_get_metadata(mock_service, [])

    assert result == []


def test_batch_get_single_message():
    """Test single message fetch."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()

    # Store callback for later invocation
    callback_store = {}

    def mock_batch_execute():
        # Simulate the batch executing and calling the callback
        if 'callback' in callback_store:
            callback_store['callback']("req1", {"id": "1", "payload": {"headers": []}}, None)

    def mock_new_batch(callback=None):
        if callback:
            callback_store['callback'] = callback
        return mock_batch

    mock_service.new_batch_http_request = mock_new_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.add = Mock()
    mock_batch.execute = mock_batch_execute

    result = gmail_stats.batch_get_metadata(mock_service, ["id1"])

    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_batch_get_multiple_batches():
    """Test batching across multiple chunks."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()

    # 25 messages should create 3 batches (10, 10, 5)
    msg_ids = [f"id{i}" for i in range(25)]

    batch_count = [0]
    results = []

    def mock_batch_execute():
        batch_count[0] += 1

    def mock_new_batch(callback=None):
        mock_batch = Mock()
        mock_batch.execute = mock_batch_execute
        return mock_batch

    mock_service.new_batch_http_request = mock_new_batch
    mock_messages_api = Mock()
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()

    result = gmail_stats.batch_get_metadata(mock_service, msg_ids)

    # Should have created 3 batches (25 / 10 = 3)
    assert batch_count[0] == 3


def test_batch_get_rate_limit_retry(mocker):
    """Test retry on 429 rate limit."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()

    # First attempt fails with 429, second succeeds
    mock_resp = Mock(status=429)
    http_error = HttpError(resp=mock_resp, content=b"Rate limit")

    attempt_count = [0]

    def mock_batch_execute():
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            raise http_error
        # Second attempt succeeds

    mock_service.new_batch_http_request.return_value = mock_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.execute = mock_batch_execute
    mock_batch.add = Mock()

    # Mock time.sleep to speed up test
    mocker.patch("time.sleep")

    result = gmail_stats.batch_get_metadata(mock_service, ["id1"])

    # Should have retried (2 attempts)
    assert attempt_count[0] == 2


def test_batch_get_rate_limit_max_retries(mocker):
    """Test max retries exceeded."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()

    mock_resp = Mock(status=429)
    http_error = HttpError(resp=mock_resp, content=b"Rate limit")

    attempt_count = [0]

    def mock_batch_execute():
        attempt_count[0] += 1
        raise http_error

    mock_service.new_batch_http_request.return_value = mock_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.execute = mock_batch_execute
    mock_batch.add = Mock()

    # Mock time.sleep to speed up test
    mocker.patch("time.sleep")

    with pytest.raises(HttpError):
        gmail_stats.batch_get_metadata(mock_service, ["id1"])

    # Should have tried MAX_RETRIES times
    assert attempt_count[0] == gmail_stats.MAX_RETRIES


def test_batch_get_403_retry(mocker):
    """Test retry on 403 forbidden."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()

    mock_resp = Mock(status=403)
    http_error = HttpError(resp=mock_resp, content=b"Forbidden")

    attempt_count = [0]

    def mock_batch_execute():
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            raise http_error
        # Second attempt succeeds

    mock_service.new_batch_http_request.return_value = mock_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.execute = mock_batch_execute
    mock_batch.add = Mock()

    # Mock time.sleep to speed up test
    mocker.patch("time.sleep")

    result = gmail_stats.batch_get_metadata(mock_service, ["id1"])

    # Should have retried
    assert attempt_count[0] == 2


def test_batch_get_other_http_error(mocker):
    """Test non-rate-limit error doesn't retry."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()

    mock_resp = Mock(status=500)
    http_error = HttpError(resp=mock_resp, content=b"Server error")

    attempt_count = [0]

    def mock_batch_execute():
        attempt_count[0] += 1
        raise http_error

    mock_service.new_batch_http_request.return_value = mock_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.execute = mock_batch_execute
    mock_batch.add = Mock()

    # Mock time.sleep to speed up test
    mocker.patch("time.sleep")

    with pytest.raises(HttpError):
        gmail_stats.batch_get_metadata(mock_service, ["id1"])

    # Should only try once (no retry for 500)
    assert attempt_count[0] == 1


def test_batch_get_exponential_backoff(mocker):
    """Test exponential backoff timing."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_batch = Mock()
    mock_messages_api = Mock()
    mock_sleep = mocker.patch("time.sleep")

    mock_resp = Mock(status=429)
    http_error = HttpError(resp=mock_resp, content=b"Rate limit")

    attempt_count = [0]

    def mock_batch_execute():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise http_error
        # Third attempt succeeds

    mock_service.new_batch_http_request.return_value = mock_batch
    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.get.return_value = Mock()
    mock_batch.execute = mock_batch_execute
    mock_batch.add = Mock()

    result = gmail_stats.batch_get_metadata(mock_service, ["id1"])

    # Should have slept at least twice for retries (plus BATCH_DELAY)
    assert mock_sleep.call_count >= 2

    # Get the sleep calls (excluding BATCH_DELAY which is constant)
    sleep_calls = [call_args[0][0] for call_args in mock_sleep.call_args_list]

    # Filter out BATCH_DELAY calls (0.25)
    retry_sleeps = [s for s in sleep_calls if s > gmail_stats.BATCH_DELAY]

    # Should have exponential backoff: second sleep > first sleep
    if len(retry_sleeps) >= 2:
        assert retry_sleeps[1] > retry_sleeps[0]
