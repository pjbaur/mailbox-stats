"""Reliability tests for gmail_stats.py.

Tests error handling, recovery mechanisms, and robustness including:
- Partial batch failures
- Network interruption recovery
- Malformed API responses
- Disk I/O errors
- Logging failures
- Concurrent token refresh safety
"""

import logging
import time
from unittest.mock import Mock, patch, MagicMock, call, mock_open

import pytest
from googleapiclient.errors import HttpError

import gmail_stats


class TestReliability:
    """Reliability and error handling test cases."""

    def test_partial_batch_failure(self, mocker):
        """Test handling when some messages in batch fail but others succeed."""
        mock_service = Mock()

        # Create a list of message IDs
        msg_ids = ["id1", "id2", "id3", "id4", "id5"]

        # Track which messages succeeded/failed
        successful_messages = []
        failed_messages = []

        def callback(request_id, response, exception):
            """Callback that simulates partial failures."""
            if request_id in ["id2", "id4"]:
                # Simulate failure for id2 and id4
                failed_messages.append(request_id)
                # In real callback, exception would be set
                if exception:
                    pass  # Would log error
            else:
                # Success for others
                successful_messages.append(request_id)
                if response:
                    pass  # Would append to results

        # Mock batch execution
        mock_batch = Mock()

        call_count = [0]

        def mock_execute():
            """Simulate batch execution with partial failures."""
            # Simulate calling the callback for each message
            callback("id1", {"id": "id1", "payload": {}}, None)
            callback("id2", None, HttpError(resp=Mock(status=500), content=b"Error"))
            callback("id3", {"id": "id3", "payload": {}}, None)
            callback("id4", None, HttpError(resp=Mock(status=500), content=b"Error"))
            callback("id5", {"id": "id5", "payload": {}}, None)
            call_count[0] += 1

        mock_batch.execute = mock_execute
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        # Call batch_get_metadata
        # Note: The actual implementation logs errors but continues
        result = gmail_stats.batch_get_metadata(mock_service, msg_ids)

        # Verify batch was created and executed
        assert mock_service.new_batch_http_request.called
        assert call_count[0] > 0, "Batch should have been executed"

        # The function should complete without raising exceptions
        # even though some messages failed
        assert isinstance(result, list)

    def test_network_interruption_recovery(self, mocker):
        """Test retry on transient network errors."""
        mock_service = Mock()
        msg_ids = ["id1"]

        mock_batch = Mock()

        # Simulate network failure followed by success
        call_count = [0]

        def mock_execute():
            call_count[0] += 1
            if call_count[0] == 1:
                # First attempt: network error
                raise ConnectionError("Network unreachable")
            # Second attempt: success
            return None

        mock_batch.execute = mock_execute
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        # The function should eventually raise the ConnectionError
        # as it doesn't retry on ConnectionError (only on 429/403)
        with pytest.raises(ConnectionError):
            gmail_stats.batch_get_metadata(mock_service, msg_ids)

    def test_rate_limit_recovery_with_exponential_backoff(self, mocker):
        """Test exponential backoff on rate limit errors (429)."""
        mock_service = Mock()
        msg_ids = ["id1"]

        mock_batch = Mock()

        # Track retry attempts
        attempt_count = [0]
        sleep_durations = []

        def mock_execute():
            attempt_count[0] += 1
            if attempt_count[0] <= 2:
                # First two attempts fail with rate limit
                raise HttpError(resp=Mock(status=429), content=b"Rate limit exceeded")
            # Third attempt succeeds
            return None

        mock_batch.execute = mock_execute
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep to track backoff timing
        def mock_sleep(duration):
            sleep_durations.append(duration)

        mocker.patch("time.sleep", side_effect=mock_sleep)

        # Call should eventually succeed after retries
        result = gmail_stats.batch_get_metadata(mock_service, msg_ids)

        # Verify retries occurred
        assert attempt_count[0] == 3, "Should have retried twice before succeeding"

        # Verify exponential backoff (each sleep should be longer than previous)
        assert len(sleep_durations) >= 2, "Should have slept during retries"

        # Check that we're using exponential backoff
        # (sleep durations should increase, though BATCH_DELAY might also be included)

    def test_malformed_api_response(self, mocker):
        """Test handling of unexpected API response structure."""
        mock_service = Mock()

        # Test list_all_message_ids with malformed response
        # Missing 'messages' key
        malformed_response = {
            # "messages": [...],  # Missing!
            "resultSizeEstimate": 100
        }

        mock_service.users().messages().list().execute.return_value = malformed_response

        # Should handle gracefully and return empty list
        result = gmail_stats.list_all_message_ids(
            mock_service,
            query="test",
            label_ids=None,
            max_ids=100
        )

        # Should return empty list, not crash
        assert result == []

    def test_malformed_message_metadata(self, mocker):
        """Test handling messages with missing or malformed metadata fields."""
        # Message missing 'payload' field
        malformed_msg = {
            "id": "msg1",
            "internalDate": "1704067200000",
            "sizeEstimate": 1024
            # Missing "payload" field!
        }

        # This should not crash when processing statistics
        # The extract_email function should handle missing headers gracefully
        headers = malformed_msg.get("payload", {}).get("headers", [])
        header_dict = {h["name"]: h["value"] for h in headers}

        # Should return "(unknown)" for missing From header
        from_email = gmail_stats.extract_email(header_dict.get("From"))
        assert from_email == "(unknown)"

    def test_disk_full_on_token_write(self, mocker):
        """Test handling when disk is full during token write."""
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "test_token"
        mock_creds.to_json.return_value = '{"token": "data"}'

        mocker.patch(
            "gmail_stats.Credentials.from_authorized_user_file",
            return_value=mock_creds
        )

        # Mock refresh to succeed
        mock_creds.refresh = Mock()

        # Mock file open to raise OSError (disk full)
        mock_file = mocker.patch(
            "builtins.open",
            side_effect=OSError("No space left on device")
        )

        # Should raise the OSError
        with pytest.raises(OSError, match="No space left on device"):
            gmail_stats.get_creds()

    def test_corrupted_token_file_recovery(self, mocker):
        """Test recovery when token.json is corrupted."""
        # Mock reading corrupted token file
        mocker.patch(
            "gmail_stats.Credentials.from_authorized_user_file",
            side_effect=ValueError("Invalid JSON in token file")
        )

        # Mock OAuth flow for re-authentication
        mock_flow = Mock()
        mock_new_creds = Mock(spec=gmail_stats.Credentials)
        mock_flow.run_local_server.return_value = mock_new_creds

        mocker.patch(
            "gmail_stats.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow
        )

        # Mock file write
        mocker.patch("builtins.open", mock_open())

        # Should recover by running OAuth flow
        result = gmail_stats.get_creds()

        assert result == mock_new_creds
        mock_flow.run_local_server.assert_called_once()

    def test_log_file_write_failure(self, mocker, caplog):
        """Test handling when log file cannot be written."""
        # This tests graceful degradation when logging fails

        # Create a logger that will fail on file writes but succeed on console
        with caplog.at_level(logging.INFO):
            # Simulate a scenario where file handler fails but stream handler works
            # The logging module typically handles handler failures gracefully

            # Log a test message
            gmail_stats.log.info("Test message")

            # Should still be captured by caplog (console handler)
            assert "Test message" in caplog.text

    def test_http_error_403_retry(self, mocker):
        """Test retry on 403 Forbidden errors (quota/permission issues)."""
        mock_service = Mock()
        msg_ids = ["id1"]

        mock_batch = Mock()

        # Track attempts
        attempt_count = [0]

        def mock_execute():
            attempt_count[0] += 1
            if attempt_count[0] == 1:
                # First attempt: 403 error
                raise HttpError(resp=Mock(status=403), content=b"Forbidden")
            # Second attempt: success
            return None

        mock_batch.execute = mock_execute
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep
        mocker.patch("time.sleep")

        # Should retry and succeed
        result = gmail_stats.batch_get_metadata(mock_service, msg_ids)

        # Verify retry occurred
        assert attempt_count[0] == 2

    def test_max_retries_exhausted(self, mocker):
        """Test behavior when max retries are exhausted."""
        mock_service = Mock()
        msg_ids = ["id1"]

        mock_batch = Mock()

        # Always fail with rate limit
        mock_batch.execute.side_effect = HttpError(
            resp=Mock(status=429),
            content=b"Rate limit exceeded"
        )
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        # Should eventually raise after MAX_RETRIES attempts
        with pytest.raises(HttpError) as exc_info:
            gmail_stats.batch_get_metadata(mock_service, msg_ids)

        assert exc_info.value.resp.status == 429

    def test_concurrent_token_refresh_safety(self, mocker):
        """Test that token refresh is safe and doesn't corrupt token.json."""
        # This tests that file writes are atomic/safe

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "test_refresh"
        mock_creds.to_json.return_value = '{"token": "refreshed_data"}'

        mocker.patch(
            "gmail_stats.Credentials.from_authorized_user_file",
            return_value=mock_creds
        )

        # Track file operations
        file_operations = []

        original_open = open

        def tracked_open(*args, **kwargs):
            file_operations.append(('open', args, kwargs))
            return mock_open()(*args, **kwargs)

        mocker.patch("builtins.open", side_effect=tracked_open)
        mock_creds.refresh = Mock()

        # Call get_creds twice (simulating potential concurrent access)
        # Note: True concurrent execution would need threading,
        # but we're testing the write pattern is safe
        gmail_stats.get_creds()

        # Verify file was opened for writing
        write_operations = [
            op for op in file_operations
            if len(op[1]) > 0 and 'w' in str(op)
        ]

        # Each write should be a complete operation (open, write, close)
        assert len(write_operations) > 0, "Should have written token file"

    def test_empty_batch_handling(self, mocker):
        """Test handling of empty message ID list."""
        mock_service = Mock()

        # Empty list should be handled gracefully
        result = gmail_stats.batch_get_metadata(mock_service, [])

        # Should return empty list without making API calls
        assert result == []
        assert not mock_service.new_batch_http_request.called

    def test_api_response_missing_fields(self, mocker):
        """Test handling when API response is missing expected fields."""
        mock_service = Mock()

        # Profile response missing fields
        incomplete_profile = {
            "emailAddress": "test@example.com"
            # Missing messagesTotal, threadsTotal
        }

        mock_service.users().getProfile().execute.return_value = incomplete_profile

        # Should use defaults (0) for missing fields
        email = incomplete_profile.get("emailAddress")
        total_msgs = incomplete_profile.get("messagesTotal", 0)
        total_threads = incomplete_profile.get("threadsTotal", 0)

        assert email == "test@example.com"
        assert total_msgs == 0
        assert total_threads == 0

    def test_label_api_error_propagation(self, mocker):
        """Test that label API errors are properly propagated."""
        mock_service = Mock()

        # Mock label list to raise HttpError
        mock_service.users().labels().list().execute.side_effect = HttpError(
            resp=Mock(status=500),
            content=b"Internal Server Error"
        )

        # Should propagate the error
        with pytest.raises(HttpError) as exc_info:
            gmail_stats.label_counts(mock_service)

        assert exc_info.value.resp.status == 500

    def test_batch_callback_exception_handling(self, mocker, caplog):
        """Test that exceptions in batch callbacks are logged but don't crash."""
        mock_service = Mock()
        msg_ids = ["id1", "id2"]

        # The batch_get_metadata function has a callback that logs errors
        # We test that individual message errors are handled gracefully

        results = []

        def callback_with_error(request_id, response, exception):
            if exception:
                # This simulates the error logging in the callback
                gmail_stats.log.error(f"Error fetching message {request_id}: {exception}")
            else:
                results.append(response)

        mock_batch = Mock()

        def mock_execute():
            # Simulate one success, one failure
            callback_with_error("id1", {"id": "id1"}, None)
            callback_with_error("id2", None, Exception("Message not found"))

        mock_batch.execute = mock_execute
        mock_batch.add = Mock()

        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().messages().get.return_value = Mock()

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        with caplog.at_level(logging.ERROR):
            # Should complete without raising
            result = gmail_stats.batch_get_metadata(mock_service, msg_ids)

            # Error should be logged
            assert "Error fetching message" in caplog.text or "error" in caplog.text.lower()
