"""Phase 4: Performance & Load Tests

Priority: P2
File: tests/performance/test_performance.py

These tests verify performance characteristics and throughput of core functions
when processing large datasets. All tests are marked as @pytest.mark.slow and
should be run separately from the main test suite.
"""

import time
import pytest
from collections import Counter
from unittest.mock import Mock
from gmail_stats import (
    chunked,
    extract_email,
    iso_date_from_internal_ms,
    batch_get_metadata,
)


@pytest.mark.slow
def test_chunked_performance_large_list():
    """Test chunked() with 100k items.

    Verifies that chunked() can handle large lists efficiently without
    performance degradation.
    """
    large_list = [str(i) for i in range(100000)]

    start = time.perf_counter()
    result = list(chunked(large_list, 100))
    elapsed = time.perf_counter() - start

    assert len(result) == 1000
    assert all(len(chunk) == 100 for chunk in result)
    assert elapsed < 1.0  # Should be very fast


@pytest.mark.slow
def test_email_extraction_performance():
    """Test extract_email() throughput.

    Verifies that email extraction can process at least 10k emails per second.
    """
    emails = [f"User {i} <user{i}@example.com>" for i in range(10000)]

    start = time.perf_counter()
    results = [extract_email(e) for e in emails]
    elapsed = time.perf_counter() - start

    assert len(results) == 10000
    assert elapsed < 1.0  # 10k/sec minimum

    # Verify correctness of first few
    assert results[0] == "user0@example.com"
    assert results[100] == "user100@example.com"
    assert results[-1] == "user9999@example.com"


@pytest.mark.slow
def test_date_conversion_performance():
    """Test iso_date_from_internal_ms() throughput (now uses local timezone).

    Verifies that date conversion can process 10k timestamps in under 2 seconds.
    """
    timestamps = [str(1704067200000 + i * 86400000) for i in range(10000)]

    start = time.perf_counter()
    results = [iso_date_from_internal_ms(ts) for ts in timestamps]
    elapsed = time.perf_counter() - start

    assert len(results) == 10000
    assert elapsed < 2.0

    # Verify correctness (date depends on local timezone)
    assert results[0] in ["2023-12-31", "2024-01-01", "2024-01-02"]
    # Results should be valid ISO dates
    assert all(len(r) == 10 and r[4] == '-' and r[7] == '-' for r in results)


@pytest.mark.slow
def test_batch_processing_throughput(mocker):
    """Test batch_get_metadata() with 5000 messages.

    Verifies batch processing can handle large volumes with proper
    batching and rate limiting.
    """
    mock_service = Mock()
    mock_batch = Mock()

    # Track how many batches were created
    batches_created = []

    def new_batch_side_effect(callback=None):
        batch = Mock()
        batches_created.append(batch)

        # Simulate batch execution
        def execute_side_effect():
            # Simulate callback being called for each message in the batch
            # The actual callback is stored and called
            if callback:
                for i in range(10):  # SAFE_BATCH_SIZE = 10 in the code
                    callback(
                        f"req{i}",
                        {
                            "id": f"id{i}",
                            "internalDate": "1704067200000",
                            "sizeEstimate": 1024,
                            "payload": {"headers": [{"name": "From", "value": "test@example.com"}]}
                        },
                        None
                    )
            return None

        batch.execute.side_effect = execute_side_effect
        batch.add = Mock()
        return batch

    mock_service.new_batch_http_request.side_effect = new_batch_side_effect
    mock_service.users().messages().get.return_value = Mock()

    msg_ids = [f"id{i}" for i in range(5000)]

    # Patch BATCH_DELAY to 0 for faster testing
    mocker.patch("gmail_stats.BATCH_DELAY", 0.0)

    start = time.perf_counter()
    result = batch_get_metadata(mock_service, msg_ids)
    elapsed = time.perf_counter() - start

    # Should have created 500 batches (5000 messages / 10 per batch)
    assert len(batches_created) == 500

    # Should complete reasonably fast with mocks (no actual delays)
    # Original plan estimated ~125s with delays, much faster with mocks
    assert elapsed < 10.0  # Very generous, should be well under this

    # Verify all batches were executed
    for batch in batches_created:
        batch.execute.assert_called_once()


@pytest.mark.slow
def test_memory_usage_large_dataset():
    """Test memory efficiency with large data.

    Verifies that processing 10k messages doesn't consume excessive memory.
    Peak memory usage should be under 100MB.
    """
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

    # Verify processing was correct
    assert len(by_sender) == 10000  # 10k unique senders
    assert sum(by_day.values()) == 10000  # Total count matches
    assert sum(by_sender.values()) == 10000  # Total count matches
