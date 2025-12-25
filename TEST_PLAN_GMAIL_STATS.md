# Comprehensive Test Plan for gmail_stats.py

## Executive Summary

This document outlines a comprehensive testing strategy for `gmail_stats.py`, a Gmail statistics dashboard CLI tool. The plan covers unit tests, integration tests, end-to-end tests, performance tests, and security considerations.

**Scope**: All 12 functions, external API interactions, file I/O, error handling, and edge cases
**Framework**: pytest (recommended) with mocking libraries
**Coverage Target**: 85%+ line coverage, 100% critical path coverage
**Estimated Test Count**: 80-100 test cases

## Critical Files
- `/Users/paulbaur/projects/mailbox-stats/gmail_stats.py` - Main script (all logic)
- `/Users/paulbaur/projects/mailbox-stats/TEST_PLAN_GMAIL_STATS.md` - This test plan document

## Test Strategy Overview

### Test Pyramid Distribution
- **Unit Tests**: 70% (~60 tests) - Fast, isolated function tests
- **Integration Tests**: 20% (~20 tests) - Component interaction tests
- **E2E Tests**: 10% (~10 tests) - Full workflow tests

### Testing Framework Recommendations
- **pytest**: Modern, powerful, expressive
- **pytest-mock**: Mocking/patching
- **pytest-cov**: Coverage reporting
- **responses**: HTTP mocking (for Gmail API)
- **freezegun**: Time/date mocking

### Risk-Based Prioritization
**P0 (Critical)**: OAuth, rate limiting, API errors
**P1 (High)**: Data accuracy, pagination, retries
**P2 (Medium)**: Edge cases, logging, validation
**P3 (Low)**: UI formatting, non-critical paths

## Detailed Test Plan

### Phase 1: Unit Tests (Pure Functions)

#### 1.1 extract_email() - 12 test cases
**Priority**: P0 (data accuracy critical)
**File**: `tests/unit/test_email_extraction.py`

```python
def test_extract_email_simple_address():
    """Test extraction from plain email"""
    assert extract_email("john@example.com") == "john@example.com"

def test_extract_email_with_display_name():
    """Test extraction from display name format"""
    assert extract_email("John Doe <john@example.com>") == "john@example.com"

def test_extract_email_uppercase_normalization():
    """Test lowercase conversion"""
    assert extract_email("JOHN@EXAMPLE.COM") == "john@example.com"

def test_extract_email_complex_address():
    """Test plus addressing and subdomains"""
    assert extract_email("user+tag@sub.domain.example.com") == "user+tag@sub.domain.example.com"

def test_extract_email_with_whitespace():
    """Test trimming whitespace"""
    assert extract_email("  john@example.com  ") == "john@example.com"

def test_extract_email_none_input():
    """Test null handling"""
    assert extract_email(None) == "(unknown)"

def test_extract_email_empty_string():
    """Test empty string handling"""
    assert extract_email("") == "(unknown)"

def test_extract_email_invalid_format():
    """Test fallback for no @ sign"""
    result = extract_email("not-an-email")
    assert result == "not-an-email"

def test_extract_email_multiple_addresses():
    """Test first address extraction"""
    assert extract_email("first@test.com and second@test.com") == "first@test.com"

def test_extract_email_special_characters():
    """Test special chars in local part"""
    assert extract_email("user_name.test+label@example.com") == "user_name.test+label@example.com"

def test_extract_email_quoted_display_name():
    """Test quoted strings in display name"""
    assert extract_email('"Doe, John" <john@example.com>') == "john@example.com"

def test_extract_email_international_domain():
    """Test TLD with more than 2 characters"""
    assert extract_email("test@example.info") == "test@example.info"
```

**Edge Cases to Cover**:
- [ ] None input
- [ ] Empty string
- [ ] No @ symbol
- [ ] Multiple @ symbols
- [ ] Unicode characters
- [ ] Very long email (>254 chars)
- [ ] Case sensitivity
- [ ] Plus addressing
- [ ] Subdomain handling

---

#### 1.2 iso_date_from_internal_ms() - 10 test cases
**Priority**: P0 (data accuracy critical)
**File**: `tests/unit/test_date_conversion.py`

```python
def test_iso_date_known_timestamp():
    """Test known timestamp conversion"""
    # 2024-01-01 00:00:00 UTC = 1704067200000 ms
    assert iso_date_from_internal_ms("1704067200000") == "2024-01-01"

def test_iso_date_epoch():
    """Test epoch zero"""
    assert iso_date_from_internal_ms("0") == "1970-01-01"

def test_iso_date_recent():
    """Test recent date"""
    # 2025-12-25 00:00:00 UTC = 1766880000000 ms
    assert iso_date_from_internal_ms("1766880000000") == "2025-12-25"

def test_iso_date_boundary_midnight():
    """Test midnight boundary (23:59:59 vs 00:00:00)"""
    # 2024-01-01 23:59:59 UTC = 1704153599000 ms
    assert iso_date_from_internal_ms("1704153599000") == "2024-01-01"
    # 2024-01-02 00:00:00 UTC = 1704153600000 ms
    assert iso_date_from_internal_ms("1704153600000") == "2024-01-02"

def test_iso_date_leap_year():
    """Test leap year date (Feb 29)"""
    # 2024-02-29 00:00:00 UTC = 1709164800000 ms
    assert iso_date_from_internal_ms("1709164800000") == "2024-02-29"

def test_iso_date_invalid_string():
    """Test non-numeric string"""
    with pytest.raises(ValueError):
        iso_date_from_internal_ms("invalid")

def test_iso_date_negative_timestamp():
    """Test pre-epoch date (if supported)"""
    # -86400000 ms = 1969-12-31
    result = iso_date_from_internal_ms("-86400000")
    assert result == "1969-12-31"

def test_iso_date_very_large_timestamp():
    """Test far future date"""
    # 9999999999999 ms = 2286-11-20
    result = iso_date_from_internal_ms("9999999999999")
    assert "2286" in result

def test_iso_date_timezone_handling():
    """Ensure UTC timezone used"""
    # Timestamp at 11 PM UTC should be same day
    # 2024-01-01 23:00:00 UTC = 1704150000000 ms
    assert iso_date_from_internal_ms("1704150000000") == "2024-01-01"

def test_iso_date_format():
    """Test output format is YYYY-MM-DD"""
    result = iso_date_from_internal_ms("1704067200000")
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"
```

**Edge Cases to Cover**:
- [ ] Epoch (0)
- [ ] Negative timestamps
- [ ] Very large timestamps
- [ ] Invalid string input
- [ ] Leap year boundaries
- [ ] Timezone boundaries (23:59:59 vs 00:00:00)
- [ ] Month boundaries
- [ ] Year boundaries

---

#### 1.3 chunked() - 8 test cases
**Priority**: P1 (critical for batch processing)
**File**: `tests/unit/test_chunked.py`

```python
def test_chunked_empty_list():
    """Test empty input"""
    result = list(chunked([], 2))
    assert result == []

def test_chunked_single_element():
    """Test single element with chunk size > 1"""
    result = list(chunked(["a"], 2))
    assert result == [["a"]]

def test_chunked_exact_division():
    """Test list divides evenly"""
    result = list(chunked(["a", "b", "c", "d"], 2))
    assert result == [["a", "b"], ["c", "d"]]

def test_chunked_uneven_division():
    """Test remainder in last chunk"""
    result = list(chunked(["a", "b", "c"], 2))
    assert result == [["a", "b"], ["c"]]

def test_chunked_size_one():
    """Test chunk size of 1"""
    result = list(chunked(["a", "b", "c"], 1))
    assert result == [["a"], ["b"], ["c"]]

def test_chunked_size_larger_than_list():
    """Test chunk size exceeds list length"""
    result = list(chunked(["a"], 5))
    assert result == [["a"]]

def test_chunked_exact_fit():
    """Test chunk size equals list length"""
    result = list(chunked(["a", "b", "c"], 3))
    assert result == [["a", "b", "c"]]

def test_chunked_large_list():
    """Test performance with large list"""
    large_list = [str(i) for i in range(1000)]
    result = list(chunked(large_list, 10))
    assert len(result) == 100
    assert all(len(chunk) == 10 for chunk in result)
```

**Edge Cases to Cover**:
- [ ] Empty list
- [ ] Single element
- [ ] Chunk size = 1
- [ ] Chunk size > list length
- [ ] Chunk size = list length
- [ ] Uneven division
- [ ] Large lists (performance)
- [ ] Chunk size = 0 (should error or handle)

---

#### 1.4 count_request() & log_request_totals() - 6 test cases
**Priority**: P2 (observability)
**File**: `tests/unit/test_request_tracking.py`

```python
def test_count_request_single():
    """Test single request tracking"""
    # Reset globals
    global REQUEST_TOTAL, REQUESTS_BY_ENDPOINT
    REQUEST_TOTAL = 0
    REQUESTS_BY_ENDPOINT = defaultdict(int)

    count_request("users.messages.get")
    assert REQUEST_TOTAL == 1
    assert REQUESTS_BY_ENDPOINT["users.messages.get"] == 1

def test_count_request_multiple():
    """Test multiple request tracking"""
    REQUEST_TOTAL = 0
    REQUESTS_BY_ENDPOINT = defaultdict(int)

    count_request("users.messages.get", 5)
    assert REQUEST_TOTAL == 5
    assert REQUESTS_BY_ENDPOINT["users.messages.get"] == 5

def test_count_request_multiple_endpoints():
    """Test different endpoints"""
    REQUEST_TOTAL = 0
    REQUESTS_BY_ENDPOINT = defaultdict(int)

    count_request("users.messages.get", 3)
    count_request("users.labels.list", 1)
    assert REQUEST_TOTAL == 4
    assert REQUESTS_BY_ENDPOINT["users.messages.get"] == 3
    assert REQUESTS_BY_ENDPOINT["users.labels.list"] == 1

def test_log_request_totals_zero(caplog):
    """Test logging with zero requests"""
    REQUEST_TOTAL = 0
    REQUESTS_BY_ENDPOINT = defaultdict(int)

    log_request_totals()
    assert "none" in caplog.text

def test_log_request_totals_with_data(caplog):
    """Test logging with request data"""
    REQUEST_TOTAL = 10
    REQUESTS_BY_ENDPOINT = {"endpoint1": 7, "endpoint2": 3}

    log_request_totals()
    assert "10" in caplog.text
    assert "endpoint1=7" in caplog.text

def test_log_request_totals_sorting(caplog):
    """Test endpoints sorted by count descending"""
    REQUEST_TOTAL = 15
    REQUESTS_BY_ENDPOINT = {"low": 2, "high": 10, "medium": 3}

    log_request_totals()
    log_lines = caplog.text.split("\n")
    # "high" should appear before "medium" and "low"
    assert "high=10" in caplog.text
```

**Edge Cases to Cover**:
- [ ] Zero requests
- [ ] Negative count (invalid input)
- [ ] Very large counts
- [ ] Empty endpoint string
- [ ] Sorting correctness

---

#### 1.5 print_header() - 4 test cases
**Priority**: P3 (cosmetic)
**File**: `tests/unit/test_print_header.py`

```python
def test_print_header_normal(capsys):
    """Test normal header printing"""
    print_header("Test")
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert len(lines) == 3
    assert lines[0] == "===="
    assert lines[1] == "Test"
    assert lines[2] == "===="

def test_print_header_empty(capsys):
    """Test empty string"""
    print_header("")
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert len(lines) == 3

def test_print_header_long(capsys):
    """Test long title"""
    title = "Very Long Header Title Here"
    print_header(title)
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert lines[1] == title
    assert len(lines[0]) == len(title)

def test_print_header_special_chars(capsys):
    """Test special characters"""
    print_header("Test (with special) chars!")
    captured = capsys.readouterr()
    assert "Test (with special) chars!" in captured.out
```

---

### Phase 2: Integration Tests (Mocked Dependencies)

#### 2.1 execute_request() - 5 test cases
**Priority**: P0 (API wrapper)
**File**: `tests/integration/test_execute_request.py`

```python
def test_execute_request_success():
    """Test successful request execution"""
    mock_request = Mock()
    mock_request.execute.return_value = {"status": "ok"}

    result = execute_request(mock_request, "test.endpoint")

    assert result == {"status": "ok"}
    assert REQUEST_TOTAL == 1
    mock_request.execute.assert_called_once()

def test_execute_request_http_error_429():
    """Test rate limit error propagation"""
    mock_request = Mock()
    mock_request.execute.side_effect = HttpError(
        resp=Mock(status=429),
        content=b"Rate limit"
    )

    with pytest.raises(HttpError) as exc:
        execute_request(mock_request, "test.endpoint")
    assert exc.value.resp.status == 429

def test_execute_request_http_error_403():
    """Test forbidden error"""
    mock_request = Mock()
    mock_request.execute.side_effect = HttpError(
        resp=Mock(status=403),
        content=b"Forbidden"
    )

    with pytest.raises(HttpError):
        execute_request(mock_request, "test.endpoint")

def test_execute_request_network_error():
    """Test network error propagation"""
    mock_request = Mock()
    mock_request.execute.side_effect = ConnectionError("Network failure")

    with pytest.raises(ConnectionError):
        execute_request(mock_request, "test.endpoint")

def test_execute_request_counts_before_exception():
    """Test request counted even if it fails"""
    mock_request = Mock()
    mock_request.execute.side_effect = HttpError(
        resp=Mock(status=500),
        content=b"Server error"
    )

    REQUEST_TOTAL = 0
    with pytest.raises(HttpError):
        execute_request(mock_request, "test.endpoint")
    assert REQUEST_TOTAL == 1
```

---

#### 2.2 get_creds() - 8 test cases
**Priority**: P0 (authentication critical)
**File**: `tests/integration/test_get_creds.py`

```python
def test_get_creds_from_cache(mocker):
    """Test loading valid cached credentials"""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = True

    mocker.patch("gmail_stats.Credentials.from_authorized_user_file", return_value=mock_creds)

    result = get_creds()

    assert result == mock_creds
    # Should not trigger refresh or OAuth flow

def test_get_creds_expired_with_refresh(mocker):
    """Test refreshing expired token"""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"

    mocker.patch("gmail_stats.Credentials.from_authorized_user_file", return_value=mock_creds)
    mocker.patch("builtins.open", mocker.mock_open())

    result = get_creds()

    mock_creds.refresh.assert_called_once()
    assert result == mock_creds

def test_get_creds_no_cache_runs_oauth(mocker):
    """Test OAuth flow on missing token"""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        side_effect=FileNotFoundError
    )

    mock_flow = Mock()
    mock_creds = Mock(spec=Credentials)
    mock_flow.run_local_server.return_value = mock_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mocker.patch("builtins.open", mocker.mock_open())

    result = get_creds()

    assert result == mock_creds
    mock_flow.run_local_server.assert_called_once()

def test_get_creds_corrupted_token_runs_oauth(mocker):
    """Test OAuth flow on corrupted token"""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        side_effect=ValueError("Invalid JSON")
    )

    mock_flow = Mock()
    mock_creds = Mock(spec=Credentials)
    mock_flow.run_local_server.return_value = mock_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mocker.patch("builtins.open", mocker.mock_open())

    result = get_creds()
    assert result == mock_creds

def test_get_creds_missing_client_secret(mocker):
    """Test error when client_secret.json missing"""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=None
    )
    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        side_effect=FileNotFoundError("client_secret.json not found")
    )

    with pytest.raises(FileNotFoundError):
        get_creds()

def test_get_creds_writes_token_on_refresh(mocker, tmp_path):
    """Test token.json is written on refresh"""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"
    mock_creds.to_json.return_value = '{"token": "data"}'

    mocker.patch("gmail_stats.Credentials.from_authorized_user_file", return_value=mock_creds)

    token_file = tmp_path / "token.json"
    mocker.patch("builtins.open", mocker.mock_open())

    get_creds()

    # Verify write was attempted
    open.assert_called()

def test_get_creds_expired_no_refresh_token(mocker):
    """Test OAuth flow when refresh token missing"""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = None

    mocker.patch("gmail_stats.Credentials.from_authorized_user_file", return_value=mock_creds)

    mock_flow = Mock()
    mock_new_creds = Mock(spec=Credentials)
    mock_flow.run_local_server.return_value = mock_new_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mocker.patch("builtins.open", mocker.mock_open())

    result = get_creds()
    assert result == mock_new_creds

def test_get_creds_timing_logged(mocker, caplog):
    """Test timing is logged"""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = True

    mocker.patch("gmail_stats.Credentials.from_authorized_user_file", return_value=mock_creds)

    get_creds()

    assert "elapsed=" in caplog.text
    assert "source=cache" in caplog.text
```

---

#### 2.3 list_all_message_ids() - 6 test cases
**Priority**: P0 (pagination critical)
**File**: `tests/integration/test_list_all_message_ids.py`

```python
def test_list_all_single_page():
    """Test single page of results"""
    mock_service = Mock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "1"}, {"id": "2"}]
    }

    result = list_all_message_ids(mock_service, "test query", None, 100)

    assert result == ["1", "2"]

def test_list_all_multiple_pages():
    """Test pagination across multiple pages"""
    mock_service = Mock()

    # First page
    first_response = {
        "messages": [{"id": "1"}, {"id": "2"}],
        "nextPageToken": "token1"
    }
    # Second page
    second_response = {
        "messages": [{"id": "3"}, {"id": "4"}]
    }

    mock_service.users().messages().list().execute.side_effect = [
        first_response,
        second_response
    ]

    result = list_all_message_ids(mock_service, "query", None, 100)

    assert result == ["1", "2", "3", "4"]

def test_list_all_max_ids_cap():
    """Test stopping at max_ids"""
    mock_service = Mock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": str(i)} for i in range(10)],
        "nextPageToken": "more"
    }

    result = list_all_message_ids(mock_service, "query", None, max_ids=5)

    assert len(result) == 5

def test_list_all_empty_results():
    """Test no messages returned"""
    mock_service = Mock()
    mock_service.users().messages().list().execute.return_value = {}

    result = list_all_message_ids(mock_service, "query", None, 100)

    assert result == []

def test_list_all_with_label_ids():
    """Test label filtering"""
    mock_service = Mock()
    mock_list = Mock()
    mock_service.users().messages().list = mock_list
    mock_list.return_value.execute.return_value = {
        "messages": [{"id": "1"}]
    }

    result = list_all_message_ids(mock_service, "query", ["INBOX"], 100)

    # Verify labelIds was passed
    mock_list.assert_called_with(
        userId="me",
        q="query",
        labelIds=["INBOX"],
        maxResults=100,
        pageToken=None
    )

def test_list_all_zero_max_ids():
    """Test unlimited results (max_ids=0)"""
    mock_service = Mock()

    responses = [
        {"messages": [{"id": str(i)} for i in range(500)], "nextPageToken": "t1"},
        {"messages": [{"id": str(i)} for i in range(500, 600)]}
    ]

    mock_service.users().messages().list().execute.side_effect = responses

    result = list_all_message_ids(mock_service, "query", None, max_ids=0)

    assert len(result) == 600
```

---

#### 2.4 batch_get_metadata() - 8 test cases
**Priority**: P0 (rate limiting & retry logic)
**File**: `tests/integration/test_batch_get_metadata.py`

```python
def test_batch_get_empty_list():
    """Test empty message list"""
    mock_service = Mock()

    result = batch_get_metadata(mock_service, [])

    assert result == []

def test_batch_get_single_message():
    """Test single message fetch"""
    mock_service = Mock()
    mock_batch = Mock()

    def callback_side_effect(callback):
        # Simulate callback being called
        callback("req1", {"id": "1", "payload": {}}, None)
        return None

    mock_batch.execute.side_effect = callback_side_effect
    mock_service.new_batch_http_request.return_value = mock_batch

    result = batch_get_metadata(mock_service, ["id1"])

    assert len(result) == 1

def test_batch_get_multiple_batches():
    """Test batching across multiple chunks"""
    mock_service = Mock()

    # 25 messages should create 3 batches (10, 10, 5)
    msg_ids = [f"id{i}" for i in range(25)]

    result = batch_get_metadata(mock_service, msg_ids)

    # Should have created 3 batches
    assert mock_service.new_batch_http_request.call_count == 3

def test_batch_get_rate_limit_retry():
    """Test retry on 429 rate limit"""
    mock_service = Mock()
    mock_batch = Mock()

    # First attempt fails with 429, second succeeds
    http_error = HttpError(resp=Mock(status=429), content=b"Rate limit")
    mock_batch.execute.side_effect = [http_error, None]

    mock_service.new_batch_http_request.return_value = mock_batch

    result = batch_get_metadata(mock_service, ["id1"])

    # Should have retried
    assert mock_batch.execute.call_count == 2

def test_batch_get_rate_limit_max_retries():
    """Test max retries exceeded"""
    mock_service = Mock()
    mock_batch = Mock()

    http_error = HttpError(resp=Mock(status=429), content=b"Rate limit")
    mock_batch.execute.side_effect = http_error

    mock_service.new_batch_http_request.return_value = mock_batch

    with pytest.raises(HttpError):
        batch_get_metadata(mock_service, ["id1"])

    # Should have tried MAX_RETRIES times
    assert mock_batch.execute.call_count == MAX_RETRIES

def test_batch_get_403_retry():
    """Test retry on 403 forbidden"""
    mock_service = Mock()
    mock_batch = Mock()

    http_error = HttpError(resp=Mock(status=403), content=b"Forbidden")
    mock_batch.execute.side_effect = [http_error, None]

    mock_service.new_batch_http_request.return_value = mock_batch

    result = batch_get_metadata(mock_service, ["id1"])

    assert mock_batch.execute.call_count == 2

def test_batch_get_other_http_error():
    """Test non-rate-limit error doesn't retry"""
    mock_service = Mock()
    mock_batch = Mock()

    http_error = HttpError(resp=Mock(status=500), content=b"Server error")
    mock_batch.execute.side_effect = http_error

    mock_service.new_batch_http_request.return_value = mock_batch

    with pytest.raises(HttpError):
        batch_get_metadata(mock_service, ["id1"])

    # Should only try once (no retry for 500)
    assert mock_batch.execute.call_count == 1

def test_batch_get_exponential_backoff(mocker):
    """Test exponential backoff timing"""
    mock_service = Mock()
    mock_batch = Mock()
    mock_sleep = mocker.patch("time.sleep")

    http_error = HttpError(resp=Mock(status=429), content=b"Rate limit")
    mock_batch.execute.side_effect = [http_error, http_error, None]

    mock_service.new_batch_http_request.return_value = mock_batch

    result = batch_get_metadata(mock_service, ["id1"])

    # Should have slept twice with exponential backoff
    assert mock_sleep.call_count >= 2
    # Second sleep should be longer than first
    calls = mock_sleep.call_args_list
    assert calls[1][0][0] > calls[0][0][0]
```

---

#### 2.5 label_counts() - 4 test cases
**Priority**: P1
**File**: `tests/integration/test_label_counts.py`

```python
def test_label_counts_multiple_labels():
    """Test fetching multiple labels"""
    mock_service = Mock()

    # List response
    mock_service.users().labels().list().execute.return_value = {
        "labels": [{"id": "INBOX"}, {"id": "SENT"}]
    }

    # Detail responses
    mock_service.users().labels().get().execute.side_effect = [
        {"id": "INBOX", "name": "INBOX", "messagesTotal": 100},
        {"id": "SENT", "name": "SENT", "messagesTotal": 50}
    ]

    result = label_counts(mock_service)

    assert len(result) == 2
    assert result[0]["name"] == "INBOX"

def test_label_counts_empty():
    """Test no labels"""
    mock_service = Mock()
    mock_service.users().labels().list().execute.return_value = {}

    result = label_counts(mock_service)

    assert result == []

def test_label_counts_sorting():
    """Test labels sorted by name"""
    mock_service = Mock()

    mock_service.users().labels().list().execute.return_value = {
        "labels": [{"id": "SENT"}, {"id": "INBOX"}]
    }

    mock_service.users().labels().get().execute.side_effect = [
        {"id": "SENT", "name": "SENT"},
        {"id": "INBOX", "name": "INBOX"}
    ]

    result = label_counts(mock_service)

    # Should be sorted alphabetically
    assert result[0]["name"] == "INBOX"
    assert result[1]["name"] == "SENT"

def test_label_counts_http_error():
    """Test error handling"""
    mock_service = Mock()
    mock_service.users().labels().list().execute.side_effect = HttpError(
        resp=Mock(status=403),
        content=b"Forbidden"
    )

    with pytest.raises(HttpError):
        label_counts(mock_service)
```

---

### Phase 3: End-to-End Tests

#### 3.1 main() Workflow Tests - 10 test cases
**Priority**: P0 (integration of all components)
**File**: `tests/e2e/test_main_workflow.py`

```python
def test_main_happy_path(mocker):
    """Test full successful execution"""
    # Mock all external dependencies
    mock_creds = Mock()
    mocker.patch("gmail_stats.get_creds", return_value=mock_creds)

    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    # Mock API responses
    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 1000,
        "threadsTotal": 500
    }

    mocker.patch("gmail_stats.label_counts", return_value=[
        {"name": "INBOX", "id": "INBOX", "messagesTotal": 50, "messagesUnread": 5}
    ])

    mocker.patch("gmail_stats.list_all_message_ids", return_value=["id1", "id2"])

    mocker.patch("gmail_stats.batch_get_metadata", return_value=[
        {
            "id": "id1",
            "internalDate": "1704067200000",
            "sizeEstimate": 1024,
            "payload": {"headers": [{"name": "From", "value": "sender@test.com"}]}
        },
        {
            "id": "id2",
            "internalDate": "1704067200000",
            "sizeEstimate": 2048,
            "payload": {"headers": [{"name": "From", "value": "sender@test.com"}]}
        }
    ])

    # Capture stdout
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        main()
        output = mock_stdout.getvalue()

    assert "test@example.com" in output
    assert "Total messages: 1000" in output
    assert "sender@test.com" in output

def test_main_no_messages_in_window(mocker, capsys):
    """Test early return when no messages found"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mocker.patch("gmail_stats.build", return_value=Mock())
    mocker.patch("gmail_stats.execute_request", return_value={"emailAddress": "test@example.com"})
    mocker.patch("gmail_stats.label_counts", return_value=[])
    mocker.patch("gmail_stats.list_all_message_ids", return_value=[])

    main()

    captured = capsys.readouterr()
    assert "No messages found" in captured.out

def test_main_oauth_failure(mocker):
    """Test failure in OAuth"""
    mocker.patch("gmail_stats.get_creds", side_effect=FileNotFoundError("client_secret.json"))

    with pytest.raises(FileNotFoundError):
        main()

def test_main_api_rate_limit(mocker):
    """Test graceful handling of API rate limits"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mocker.patch("gmail_stats.build", return_value=Mock())

    # Simulate rate limit that eventually succeeds
    mocker.patch("gmail_stats.batch_get_metadata", return_value=[])

    # Should not raise
    # (actual rate limit retry tested in batch_get_metadata tests)

def test_main_missing_inbox_label(mocker, capsys):
    """Test when INBOX label not found"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 100
    }

    # No INBOX in labels
    mocker.patch("gmail_stats.label_counts", return_value=[
        {"name": "SENT", "id": "SENT"}
    ])

    mocker.patch("gmail_stats.list_all_message_ids", return_value=[])

    main()

    captured = capsys.readouterr()
    # Should complete without error, no unread section
    assert "test@example.com" in captured.out

def test_main_configuration_used(mocker, monkeypatch):
    """Test environment config is applied"""
    monkeypatch.setenv("DAYS", "7")
    monkeypatch.setenv("SAMPLE_MAX_IDS", "100")

    # Reload module to pick up env vars
    # (In real test, would use importlib.reload or subprocess)

    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mocker.patch("gmail_stats.build", return_value=Mock())
    mocker.patch("gmail_stats.label_counts", return_value=[])

    mock_list_ids = mocker.patch("gmail_stats.list_all_message_ids", return_value=[])

    main()

    # Verify config was used (check query contains "7d")
    # (Implementation detail - may need adjustment)

def test_main_large_mailbox(mocker):
    """Test handling of large mailbox (5000+ messages)"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 100000
    }

    mocker.patch("gmail_stats.label_counts", return_value=[])

    # Return 5000 IDs (max cap)
    mocker.patch("gmail_stats.list_all_message_ids", return_value=[f"id{i}" for i in range(5000)])

    # Mock batch metadata (would be slow for real)
    mocker.patch("gmail_stats.batch_get_metadata", return_value=[])

    # Should complete without issues
    main()

def test_main_message_missing_headers(mocker, capsys):
    """Test graceful handling of missing headers"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 10
    }

    mocker.patch("gmail_stats.label_counts", return_value=[])
    mocker.patch("gmail_stats.list_all_message_ids", return_value=["id1"])

    # Message with missing/malformed payload
    mocker.patch("gmail_stats.batch_get_metadata", return_value=[
        {"id": "id1", "internalDate": "1704067200000", "sizeEstimate": 100}
        # Missing "payload" field
    ])

    # Should handle gracefully
    main()

    captured = capsys.readouterr()
    assert "test@example.com" in captured.out

def test_main_top_senders_limit(mocker, capsys):
    """Test top 25 senders limit"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 100
    }

    mocker.patch("gmail_stats.label_counts", return_value=[])
    mocker.patch("gmail_stats.list_all_message_ids", return_value=[f"id{i}" for i in range(50)])

    # 50 unique senders
    messages = [
        {
            "id": f"id{i}",
            "internalDate": "1704067200000",
            "sizeEstimate": 100,
            "payload": {"headers": [{"name": "From", "value": f"sender{i}@test.com"}]}
        }
        for i in range(50)
    ]

    mocker.patch("gmail_stats.batch_get_metadata", return_value=messages)

    main()

    captured = capsys.readouterr()
    # Should only show top 25
    lines = [l for l in captured.out.split("\n") if "@test.com" in l]
    assert len(lines) <= 25

def test_main_logging_output(mocker, caplog):
    """Test logging is generated"""
    mocker.patch("gmail_stats.get_creds", return_value=Mock())
    mock_service = Mock()
    mocker.patch("gmail_stats.build", return_value=mock_service)

    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 10
    }

    mocker.patch("gmail_stats.label_counts", return_value=[])
    mocker.patch("gmail_stats.list_all_message_ids", return_value=[])

    main()

    # Verify configuration was logged
    assert "Configuration:" in caplog.text
    assert "DAYS=" in caplog.text
```

---

### Phase 4: Performance & Load Tests

#### 4.1 Performance Tests - 5 test cases
**Priority**: P2
**File**: `tests/performance/test_performance.py`

```python
@pytest.mark.slow
def test_chunked_performance_large_list():
    """Test chunked() with 100k items"""
    large_list = [str(i) for i in range(100000)]

    start = time.perf_counter()
    result = list(chunked(large_list, 100))
    elapsed = time.perf_counter() - start

    assert len(result) == 1000
    assert elapsed < 1.0  # Should be very fast

@pytest.mark.slow
def test_email_extraction_performance():
    """Test extract_email() throughput"""
    emails = [f"User {i} <user{i}@example.com>" for i in range(10000)]

    start = time.perf_counter()
    results = [extract_email(e) for e in emails]
    elapsed = time.perf_counter() - start

    assert len(results) == 10000
    assert elapsed < 1.0  # 10k/sec minimum

@pytest.mark.slow
def test_date_conversion_performance():
    """Test iso_date_from_internal_ms() throughput"""
    timestamps = [str(1704067200000 + i * 86400000) for i in range(10000)]

    start = time.perf_counter()
    results = [iso_date_from_internal_ms(ts) for ts in timestamps]
    elapsed = time.perf_counter() - start

    assert len(results) == 10000
    assert elapsed < 2.0

@pytest.mark.slow
def test_batch_processing_throughput(mocker):
    """Test batch_get_metadata() with 5000 messages"""
    mock_service = Mock()
    mock_batch = Mock()
    mock_service.new_batch_http_request.return_value = mock_batch

    # Simulate fast batch execution
    mock_batch.execute.return_value = None

    msg_ids = [f"id{i}" for i in range(5000)]

    start = time.perf_counter()
    result = batch_get_metadata(mock_service, msg_ids)
    elapsed = time.perf_counter() - start

    # With BATCH_DELAY=0.25, 500 batches = ~125s minimum
    # Test should complete faster with mocks
    assert elapsed < 200.0

@pytest.mark.slow
def test_memory_usage_large_dataset():
    """Test memory efficiency with large data"""
    import tracemalloc

    tracemalloc.start()

    # Simulate processing 10k messages
    messages = [
        {
            "id": f"id{i}",
            "internalDate": str(1704067200000 + i * 1000),
            "sizeEstimate": 1024,
            "payload": {"headers": [{"name": "From", "value": f"user{i}@test.com"}]}
        }
        for i in range(10000)
    ]

    by_day = Counter()
    by_sender = Counter()

    for msg in messages:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        from_email = extract_email(headers.get("From"))
        iso_date = iso_date_from_internal_ms(msg["internalDate"])

        by_day[iso_date] += 1
        by_sender[from_email] += 1

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Peak memory should be reasonable (< 100MB)
    assert peak < 100 * 1024 * 1024
```

---

### Phase 5: Edge Case & Error Tests

#### 5.1 Configuration Edge Cases - 6 test cases
**Priority**: P1
**File**: `tests/edge_cases/test_config_edge_cases.py`

```python
def test_zero_days_config(monkeypatch):
    """Test DAYS=0 edge case"""
    monkeypatch.setenv("DAYS", "0")
    # Reload config
    # Test behavior - should it error or handle gracefully?

def test_negative_days_config(monkeypatch):
    """Test DAYS=-1 invalid input"""
    monkeypatch.setenv("DAYS", "-1")
    # Should handle or error

def test_zero_sample_max_ids(monkeypatch):
    """Test unlimited sampling (SAMPLE_MAX_IDS=0)"""
    monkeypatch.setenv("SAMPLE_MAX_IDS", "0")
    # Should fetch all messages

def test_invalid_log_level(monkeypatch, caplog):
    """Test invalid LOG_LEVEL"""
    monkeypatch.setenv("LOG_LEVEL", "INVALID")
    # Should error or use default

def test_zero_max_retries(monkeypatch):
    """Test MAX_RETRIES=0"""
    monkeypatch.setenv("MAX_RETRIES", "0")
    # Should fail immediately on rate limit

def test_negative_batch_delay(monkeypatch):
    """Test BATCH_DELAY=-0.5"""
    monkeypatch.setenv("BATCH_DELAY", "-0.5")
    # Should error or treat as 0
```

#### 5.2 Data Edge Cases - 8 test cases
**Priority**: P1
**File**: `tests/edge_cases/test_data_edge_cases.py`

```python
def test_empty_from_header():
    """Test message with no From header"""
    result = extract_email("")
    assert result == "(unknown)"

def test_unicode_email():
    """Test unicode characters in email"""
    # IDN (Internationalized Domain Names)
    result = extract_email("user@münchen.de")
    # May or may not match depending on regex

def test_very_long_email():
    """Test email > 254 characters"""
    long_email = "a" * 300 + "@example.com"
    result = extract_email(long_email)
    # Should handle without crashing

def test_timestamp_zero():
    """Test epoch timestamp"""
    result = iso_date_from_internal_ms("0")
    assert result == "1970-01-01"

def test_timestamp_far_future():
    """Test year 2100 timestamp"""
    # 4102444800000 ms = 2100-01-01
    result = iso_date_from_internal_ms("4102444800000")
    assert "2100" in result

def test_message_missing_size_estimate():
    """Test message without sizeEstimate"""
    msg = {"id": "1", "internalDate": "1704067200000"}
    size = int(msg.get("sizeEstimate", 0))
    assert size == 0

def test_all_messages_same_sender():
    """Test statistics with single sender"""
    # by_sender will have only 1 entry
    # Should still display correctly

def test_all_messages_same_day():
    """Test all messages on one day"""
    # by_day will have only 1 entry
    # Daily volume chart should still work
```

---

### Phase 6: Security & Reliability Tests

#### 6.1 Security Tests - 4 test cases
**Priority**: P0
**File**: `tests/security/test_security.py`

```python
def test_token_file_permissions(tmp_path):
    """Test token.json has restrictive permissions"""
    # After writing token.json, verify permissions
    # Should be 600 (owner read/write only)

def test_no_credentials_in_logs(mocker, caplog):
    """Test credentials not logged"""
    # Run full workflow
    # Verify no tokens/secrets in log output

def test_client_secret_not_required_when_cached(mocker):
    """Test client_secret.json not accessed if token cached"""
    # With valid token.json, should not read client_secret.json

def test_oauth_scope_readonly():
    """Test OAuth scope is read-only"""
    assert SCOPES == ["https://www.googleapis.com/auth/gmail.readonly"]
```

#### 6.2 Reliability Tests - 6 test cases
**Priority**: P1
**File**: `tests/reliability/test_reliability.py`

```python
def test_partial_batch_failure():
    """Test handling when some messages in batch fail"""
    # Individual message errors should be logged but not crash

def test_network_interruption_recovery(mocker):
    """Test retry on transient network errors"""
    # ConnectionError should trigger retry logic

def test_malformed_api_response():
    """Test handling of unexpected API response structure"""
    # Missing fields should be handled gracefully

def test_disk_full_on_token_write(mocker):
    """Test handling when disk full during token write"""
    mocker.patch("builtins.open", side_effect=OSError("Disk full"))
    # Should raise or handle gracefully

def test_log_file_write_failure(mocker):
    """Test handling when log file cannot be written"""
    # Logger should handle or fallback to console only

def test_concurrent_token_refresh():
    """Test token refresh is safe (not concurrent)"""
    # If multiple instances run, token.json shouldn't corrupt
```

---

## Test Execution Plan

### Test Organization
```
tests/
├── unit/
│   ├── test_email_extraction.py
│   ├── test_date_conversion.py
│   ├── test_chunked.py
│   ├── test_request_tracking.py
│   └── test_print_header.py
├── integration/
│   ├── test_execute_request.py
│   ├── test_get_creds.py
│   ├── test_list_all_message_ids.py
│   ├── test_batch_get_metadata.py
│   └── test_label_counts.py
├── e2e/
│   └── test_main_workflow.py
├── performance/
│   └── test_performance.py
├── edge_cases/
│   ├── test_config_edge_cases.py
│   └── test_data_edge_cases.py
├── security/
│   └── test_security.py
├── reliability/
│   └── test_reliability.py
└── conftest.py  # Shared fixtures
```

### Fixtures & Test Data
**File**: `tests/conftest.py`

```python
@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service"""
    return Mock()

@pytest.fixture
def sample_messages():
    """Sample message metadata"""
    return [
        {
            "id": "1",
            "internalDate": "1704067200000",
            "sizeEstimate": 1024,
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender1@test.com"},
                    {"name": "Subject", "value": "Test 1"}
                ]
            }
        },
        # ... more samples
    ]

@pytest.fixture
def sample_labels():
    """Sample label data"""
    return [
        {
            "id": "INBOX",
            "name": "INBOX",
            "messagesTotal": 100,
            "messagesUnread": 5,
            "threadsTotal": 50
        },
        # ... more labels
    ]

@pytest.fixture
def mock_credentials():
    """Mock OAuth credentials"""
    creds = Mock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "refresh_token"
    return creds
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific category
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with coverage
pytest --cov=gmail_stats --cov-report=html

# Run specific priority
pytest -m p0  # Critical tests only
pytest -m "not slow"  # Skip performance tests

# Run with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_email_extraction.py::test_extract_email_simple_address

# Run with logging
pytest -v --log-cli-level=DEBUG
```

### Test Markers
**File**: `pytest.ini`

```ini
[pytest]
markers =
    p0: Critical priority tests
    p1: High priority tests
    p2: Medium priority tests
    p3: Low priority tests
    slow: Slow-running tests (performance)
    integration: Integration tests requiring mocks
    e2e: End-to-end tests
    security: Security-focused tests
```

---

## Continuous Integration

### CI Pipeline Stages

**Stage 1: Fast Tests (< 2 minutes)**
- All unit tests
- Linting (flake8, black, mypy)
- Coverage check (minimum 85%)

**Stage 2: Integration Tests (< 5 minutes)**
- All integration tests
- Security tests

**Stage 3: Full Suite (< 10 minutes)**
- E2E tests
- Performance tests
- Reliability tests

### GitHub Actions Example
**File**: `.github/workflows/test.yml`

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-mock responses freezegun

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run E2E tests
        run: pytest tests/e2e/ -v

      - name: Generate coverage report
        run: pytest --cov=gmail_stats --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Coverage Goals

### Target Coverage
- **Overall**: 85%+ line coverage
- **Critical functions**: 100% coverage
  - get_creds()
  - batch_get_metadata()
  - list_all_message_ids()
  - extract_email()
  - iso_date_from_internal_ms()

### Coverage Exclusions
- Logging statements (cosmetic)
- Print statements (UI only)
- Debug code (if any)

---

## Test Maintenance

### When to Update Tests
1. **Feature additions**: Add corresponding tests
2. **Bug fixes**: Add regression tests
3. **API changes**: Update mock responses
4. **Config changes**: Update edge case tests

### Test Review Checklist
- [ ] All new code has tests
- [ ] Edge cases documented and tested
- [ ] Mocks updated for API changes
- [ ] Performance impacts measured
- [ ] Security implications reviewed
- [ ] Documentation updated

---

## Post-Implementation Checklist

After implementing this test plan:

- [ ] Create tests/ directory structure
- [ ] Install test dependencies
- [ ] Implement all unit tests (60+ tests)
- [ ] Implement integration tests (20+ tests)
- [ ] Implement E2E tests (10+ tests)
- [ ] Set up pytest configuration
- [ ] Configure CI/CD pipeline
- [ ] Generate initial coverage report
- [ ] Document test execution in README
- [ ] Add test badges to repository

---

## Estimated Effort

| Phase | Tests | Effort | Priority |
|-------|-------|--------|----------|
| Unit tests | 60 | 2-3 days | P0 |
| Integration tests | 20 | 2 days | P0 |
| E2E tests | 10 | 1 day | P1 |
| Performance tests | 5 | 1 day | P2 |
| Edge cases | 14 | 1 day | P1 |
| Security/Reliability | 10 | 1 day | P1 |
| CI/CD setup | - | 0.5 day | P0 |
| **Total** | **~120** | **8-9 days** | - |

---

## Success Criteria

Test plan is successful when:
1. ✅ 85%+ code coverage achieved
2. ✅ All critical paths (P0) have tests
3. ✅ CI pipeline passes consistently
4. ✅ No regressions in production
5. ✅ New features ship with tests
6. ✅ Test execution time < 10 minutes

---

## Summary

This comprehensive test plan covers:
- **12 functions** with 120+ test cases
- **Unit, integration, E2E, performance, security, and reliability** testing
- **Risk-based prioritization** (P0-P3)
- **Mocking strategy** for Gmail API, OAuth, file I/O
- **CI/CD integration** with coverage tracking
- **Clear organization** and execution plan

The plan balances thoroughness with practicality, focusing first on critical paths (OAuth, rate limiting, data accuracy) while providing comprehensive coverage of edge cases and error conditions.
