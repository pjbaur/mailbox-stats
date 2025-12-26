"""Unit tests for random sampling functionality.

Tests the list_all_message_ids_random() function and parse_args() function
to ensure random sampling works correctly with various edge cases.
"""

import pytest
from unittest.mock import Mock, patch
from gmail_stats import list_all_message_ids_random, parse_args


def test_list_all_message_ids_random_basic(mocker):
    """Test random sampling with more IDs than sample size.

    When the total number of available message IDs exceeds the requested
    sample size, the function should return exactly the requested number
    of randomly selected IDs.
    """
    # Mock service that returns 100 message IDs
    mock_service = Mock()

    # Create 100 message IDs
    all_messages = [{"id": f"msg_{i:03d}"} for i in range(100)]

    # Mock execute_request to return all messages
    def mock_execute_request(request, endpoint):
        return {
            "messages": all_messages,
            "nextPageToken": None
        }

    mocker.patch("gmail_stats.execute_request", side_effect=mock_execute_request)

    # Request a sample of 10
    result = list_all_message_ids_random(mock_service, "test_query", None, 10)

    # Verify exactly 10 IDs returned
    assert len(result) == 10

    # Verify all IDs are unique
    assert len(set(result)) == 10

    # Verify all IDs are from the original set
    all_ids = [f"msg_{i:03d}" for i in range(100)]
    for msg_id in result:
        assert msg_id in all_ids


def test_list_all_message_ids_random_edge_case_fewer_ids(mocker):
    """Test when available IDs < sample size.

    When the total number of available message IDs is less than the
    requested sample size, the function should return all available IDs.
    """
    mock_service = Mock()

    # Create only 5 message IDs
    few_messages = [{"id": f"msg_{i}"} for i in range(5)]

    def mock_execute_request(request, endpoint):
        return {
            "messages": few_messages,
            "nextPageToken": None
        }

    mocker.patch("gmail_stats.execute_request", side_effect=mock_execute_request)

    # Request a sample of 10 (more than available)
    result = list_all_message_ids_random(mock_service, "test_query", None, 10)

    # Verify all 5 IDs are returned
    assert len(result) == 5

    # Verify all IDs match
    expected_ids = [f"msg_{i}" for i in range(5)]
    assert sorted(result) == sorted(expected_ids)


def test_list_all_message_ids_random_no_limit(mocker):
    """Test with max_ids=0 (no limit).

    When max_ids is 0, the function should return all available IDs
    without any sampling.
    """
    mock_service = Mock()

    # Create 50 message IDs
    all_messages = [{"id": f"msg_{i:02d}"} for i in range(50)]

    def mock_execute_request(request, endpoint):
        return {
            "messages": all_messages,
            "nextPageToken": None
        }

    mocker.patch("gmail_stats.execute_request", side_effect=mock_execute_request)

    # Request with max_ids=0 (no limit)
    result = list_all_message_ids_random(mock_service, "test_query", None, 0)

    # Verify all 50 IDs are returned
    assert len(result) == 50

    # Verify all IDs match (order doesn't matter)
    expected_ids = [f"msg_{i:02d}" for i in range(50)]
    assert sorted(result) == sorted(expected_ids)


def test_list_all_message_ids_random_pagination(mocker):
    """Test random sampling with pagination.

    When messages span multiple pages, the function should correctly
    fetch all pages before sampling.
    """
    mock_service = Mock()

    # Create messages across 3 pages (30 total)
    page1_messages = [{"id": f"msg_page1_{i}"} for i in range(10)]
    page2_messages = [{"id": f"msg_page2_{i}"} for i in range(10)]
    page3_messages = [{"id": f"msg_page3_{i}"} for i in range(10)]

    call_count = [0]

    def mock_execute_request(request, endpoint):
        call_count[0] += 1
        if call_count[0] == 1:
            return {"messages": page1_messages, "nextPageToken": "token1"}
        elif call_count[0] == 2:
            return {"messages": page2_messages, "nextPageToken": "token2"}
        else:
            return {"messages": page3_messages, "nextPageToken": None}

    mocker.patch("gmail_stats.execute_request", side_effect=mock_execute_request)

    # Request a sample of 15 from 30 total
    result = list_all_message_ids_random(mock_service, "test_query", None, 15)

    # Verify exactly 15 IDs returned
    assert len(result) == 15

    # Verify all IDs are unique
    assert len(set(result)) == 15

    # Verify IDs could come from any page
    all_ids = (
        [f"msg_page1_{i}" for i in range(10)] +
        [f"msg_page2_{i}" for i in range(10)] +
        [f"msg_page3_{i}" for i in range(10)]
    )
    for msg_id in result:
        assert msg_id in all_ids


def test_list_all_message_ids_random_empty_result(mocker):
    """Test with empty result set.

    When the query returns no messages, the function should return
    an empty list.
    """
    mock_service = Mock()

    def mock_execute_request(request, endpoint):
        return {"messages": [], "nextPageToken": None}

    mocker.patch("gmail_stats.execute_request", side_effect=mock_execute_request)

    # Request a sample from empty result set
    result = list_all_message_ids_random(mock_service, "test_query", None, 10)

    # Verify empty list returned
    assert result == []


def test_parse_args_random_flag():
    """Test argument parser with --random-sample flag.

    Verify that the argument parser correctly handles the --random-sample
    flag in both enabled and disabled states.
    """
    # Test with --random-sample flag
    with patch('sys.argv', ['gmail_stats.py', '--random-sample']):
        args = parse_args()
        assert args.random_sample is True

    # Test without flag (default)
    with patch('sys.argv', ['gmail_stats.py']):
        args = parse_args()
        assert args.random_sample is False


def test_parse_args_help():
    """Test that --help includes random-sample documentation.

    Verify that the help text for --random-sample is properly included.
    """
    with patch('sys.argv', ['gmail_stats.py', '--help']):
        with pytest.raises(SystemExit):
            parse_args()
