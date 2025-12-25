"""Shared pytest fixtures and configuration for gmail_stats tests."""

from collections import defaultdict
from unittest.mock import Mock

import pytest
from google.oauth2.credentials import Credentials


@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service."""
    return Mock()


@pytest.fixture
def sample_messages():
    """Sample message metadata for testing."""
    return [
        {
            "id": "1",
            "internalDate": "1704067200000",  # 2024-01-01 00:00:00 UTC
            "sizeEstimate": 1024,
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender1@test.com"},
                    {"name": "Subject", "value": "Test 1"}
                ]
            }
        },
        {
            "id": "2",
            "internalDate": "1704153600000",  # 2024-01-02 00:00:00 UTC
            "sizeEstimate": 2048,
            "payload": {
                "headers": [
                    {"name": "From", "value": "John Doe <sender2@test.com>"},
                    {"name": "Subject", "value": "Test 2"}
                ]
            }
        },
        {
            "id": "3",
            "internalDate": "1704240000000",  # 2024-01-03 00:00:00 UTC
            "sizeEstimate": 512,
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender1@test.com"},
                    {"name": "Subject", "value": "Test 3"}
                ]
            }
        }
    ]


@pytest.fixture
def sample_labels():
    """Sample label data for testing."""
    return [
        {
            "id": "INBOX",
            "name": "INBOX",
            "type": "system",
            "messagesTotal": 100,
            "messagesUnread": 5,
            "threadsTotal": 50,
            "threadsUnread": 3
        },
        {
            "id": "SENT",
            "name": "SENT",
            "type": "system",
            "messagesTotal": 200,
            "messagesUnread": 0,
            "threadsTotal": 150,
            "threadsUnread": 0
        },
        {
            "id": "DRAFT",
            "name": "DRAFT",
            "type": "system",
            "messagesTotal": 5,
            "messagesUnread": 0,
            "threadsTotal": 5,
            "threadsUnread": 0
        },
        {
            "id": "SPAM",
            "name": "SPAM",
            "type": "system",
            "messagesTotal": 50,
            "messagesUnread": 10,
            "threadsTotal": 40,
            "threadsUnread": 8
        },
        {
            "id": "TRASH",
            "name": "TRASH",
            "type": "system",
            "messagesTotal": 30,
            "messagesUnread": 0,
            "threadsTotal": 25,
            "threadsUnread": 0
        },
        {
            "id": "IMPORTANT",
            "name": "IMPORTANT",
            "type": "system",
            "messagesTotal": 25,
            "messagesUnread": 2,
            "threadsTotal": 20,
            "threadsUnread": 2
        },
        {
            "id": "STARRED",
            "name": "STARRED",
            "type": "system",
            "messagesTotal": 15,
            "messagesUnread": 1,
            "threadsTotal": 12,
            "threadsUnread": 1
        }
    ]


@pytest.fixture
def mock_credentials():
    """Mock OAuth credentials."""
    creds = Mock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "refresh_token"
    creds.token = "access_token"
    creds.to_json.return_value = '{"token": "test_token"}'
    return creds


@pytest.fixture
def sample_profile():
    """Sample Gmail profile data."""
    return {
        "emailAddress": "test@example.com",
        "messagesTotal": 1000,
        "threadsTotal": 500,
        "historyId": "12345"
    }


@pytest.fixture(autouse=True)
def reset_request_tracking():
    """Reset global request tracking variables before each test."""
    import gmail_stats
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)
    yield
    # Reset again after test
    gmail_stats.REQUEST_TOTAL = 0
    gmail_stats.REQUESTS_BY_ENDPOINT = defaultdict(int)
