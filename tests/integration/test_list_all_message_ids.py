"""Integration tests for list_all_message_ids() function."""

import pytest
from unittest.mock import Mock, MagicMock
import gmail_stats


def test_list_all_single_page():
    """Test single page of results."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj
    mock_list_obj.execute.return_value = {
        "messages": [{"id": "1"}, {"id": "2"}]
    }

    result = gmail_stats.list_all_message_ids(mock_service, "test query", None, 100)

    assert result == ["1", "2"]


def test_list_all_multiple_pages():
    """Test pagination across multiple pages."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj

    # First page has nextPageToken, second page doesn't
    mock_list_obj.execute.side_effect = [
        {
            "messages": [{"id": "1"}, {"id": "2"}],
            "nextPageToken": "token1"
        },
        {
            "messages": [{"id": "3"}, {"id": "4"}]
        }
    ]

    result = gmail_stats.list_all_message_ids(mock_service, "query", None, 100)

    assert result == ["1", "2", "3", "4"]


def test_list_all_max_ids_cap():
    """Test stopping at max_ids."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj
    mock_list_obj.execute.return_value = {
        "messages": [{"id": str(i)} for i in range(10)],
        "nextPageToken": "more"
    }

    result = gmail_stats.list_all_message_ids(mock_service, "query", None, max_ids=5)

    assert len(result) == 5
    assert result == ["0", "1", "2", "3", "4"]


def test_list_all_empty_results():
    """Test no messages returned."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj
    mock_list_obj.execute.return_value = {}

    result = gmail_stats.list_all_message_ids(mock_service, "query", None, 100)

    assert result == []


def test_list_all_with_label_ids():
    """Test label filtering."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj
    mock_list_obj.execute.return_value = {
        "messages": [{"id": "1"}]
    }

    result = gmail_stats.list_all_message_ids(mock_service, "query", ["INBOX"], 100)

    # Verify labelIds was passed
    mock_messages_api.list.assert_called()
    call_args = mock_messages_api.list.call_args
    assert call_args[1]["userId"] == "me"
    assert call_args[1]["q"] == "query"
    assert call_args[1]["labelIds"] == ["INBOX"]
    assert result == ["1"]


def test_list_all_zero_max_ids():
    """Test unlimited results (max_ids=0)."""
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT.clear()

    mock_service = Mock()
    mock_messages_api = Mock()
    mock_list_obj = Mock()

    mock_service.users.return_value.messages.return_value = mock_messages_api
    mock_messages_api.list.return_value = mock_list_obj

    responses = [
        {"messages": [{"id": str(i)} for i in range(500)], "nextPageToken": "t1"},
        {"messages": [{"id": str(i)} for i in range(500, 600)]}
    ]

    mock_list_obj.execute.side_effect = responses

    result = gmail_stats.list_all_message_ids(mock_service, "query", None, max_ids=0)

    assert len(result) == 600
