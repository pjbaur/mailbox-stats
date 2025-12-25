"""Integration tests for label_counts() function."""

import pytest
from unittest.mock import Mock
from googleapiclient.errors import HttpError
import gmail_stats


def test_label_counts_multiple_labels():
    """Test fetching multiple labels."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_labels_api = Mock()
    mock_list_obj = Mock()
    mock_get_obj = Mock()

    mock_service.users.return_value.labels.return_value = mock_labels_api
    mock_labels_api.list.return_value = mock_list_obj
    mock_labels_api.get.return_value = mock_get_obj

    # List response
    mock_list_obj.execute.return_value = {
        "labels": [{"id": "INBOX"}, {"id": "SENT"}]
    }

    # Detail responses
    mock_get_obj.execute.side_effect = [
        {"id": "INBOX", "name": "INBOX", "messagesTotal": 100},
        {"id": "SENT", "name": "SENT", "messagesTotal": 50}
    ]

    result = gmail_stats.label_counts(mock_service)

    assert len(result) == 2
    assert result[0]["name"] == "INBOX"
    assert result[0]["messagesTotal"] == 100
    assert result[1]["name"] == "SENT"
    assert result[1]["messagesTotal"] == 50


def test_label_counts_empty():
    """Test no labels."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_labels_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.labels.return_value = mock_labels_api
    mock_labels_api.list.return_value = mock_list_obj
    mock_list_obj.execute.return_value = {}

    result = gmail_stats.label_counts(mock_service)

    assert result == []


def test_label_counts_sorting():
    """Test labels sorted by name."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_labels_api = Mock()
    mock_list_obj = Mock()
    mock_get_obj = Mock()

    mock_service.users.return_value.labels.return_value = mock_labels_api
    mock_labels_api.list.return_value = mock_list_obj
    mock_labels_api.get.return_value = mock_get_obj

    # List response with labels in non-alphabetical order
    mock_list_obj.execute.return_value = {
        "labels": [{"id": "SENT"}, {"id": "INBOX"}]
    }

    # Detail responses
    mock_get_obj.execute.side_effect = [
        {"id": "SENT", "name": "SENT"},
        {"id": "INBOX", "name": "INBOX"}
    ]

    result = gmail_stats.label_counts(mock_service)

    # Should be sorted alphabetically
    assert len(result) == 2
    assert result[0]["name"] == "INBOX"
    assert result[1]["name"] == "SENT"


def test_label_counts_http_error():
    """Test error handling."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_labels_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.labels.return_value = mock_labels_api
    mock_labels_api.list.return_value = mock_list_obj

    mock_resp = Mock(status=403)
    mock_list_obj.execute.side_effect = HttpError(
        resp=mock_resp,
        content=b"Forbidden"
    )

    with pytest.raises(HttpError):
        gmail_stats.label_counts(mock_service)
