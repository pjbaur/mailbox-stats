"""Integration tests for gmail_stats_server.py (Day 5 features).

Tests for FastAPI endpoints:
- GET /
- GET /api/summary
- GET /api/top
- GET /api/runs
"""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Import the app after patching DB_PATH
import gmail_stats_server


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    try:
        # Create schema
        conn.executescript("""
            CREATE TABLE runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                account_email TEXT NOT NULL,
                days_analyzed INTEGER NOT NULL,
                sample_size INTEGER NOT NULL,
                sampling_method TEXT NOT NULL,
                messages_examined INTEGER NOT NULL,
                total_mailbox_messages INTEGER NOT NULL
            );

            CREATE TABLE sender_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                aggregation_level TEXT NOT NULL,
                sender TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL,
                messages_with_attachments INTEGER,
                parent_domain TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
        """)

        # Insert test runs
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO runs (timestamp, account_email, days_analyzed, sample_size,
                            sampling_method, messages_examined, total_mailbox_messages)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            "test@example.com",
            30,
            5000,
            "random",
            1000,
            50000
        ))
        run_id = cursor.lastrowid

        # Insert domain stats
        domain_data = [
            (run_id, 'domain', 'example.com', 500, 1024 * 1024 * 50, 100, None),
            (run_id, 'domain', 'test.org', 300, 1024 * 1024 * 30, 50, None),
            (run_id, 'domain', 'small.net', 200, 1024 * 1024 * 20, 25, None),
        ]
        cursor.executemany("""
            INSERT INTO sender_stats (run_id, aggregation_level, sender, message_count,
                                     total_size_bytes, messages_with_attachments, parent_domain)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, domain_data)

        # Insert email stats
        email_data = [
            (run_id, 'email', 'user@example.com', 300, 1024 * 1024 * 30, 60, 'example.com'),
            (run_id, 'email', 'admin@example.com', 200, 1024 * 1024 * 20, 40, 'example.com'),
            (run_id, 'email', 'info@test.org', 300, 1024 * 1024 * 30, 50, 'test.org'),
            (run_id, 'email', 'contact@small.net', 200, 1024 * 1024 * 20, 25, 'small.net'),
        ]
        cursor.executemany("""
            INSERT INTO sender_stats (run_id, aggregation_level, sender, message_count,
                                     total_size_bytes, messages_with_attachments, parent_domain)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, email_data)

        conn.commit()
    finally:
        conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def client(test_db):
    """Create test client with mocked database path."""
    with patch.object(gmail_stats_server, 'DB_PATH', test_db):
        yield TestClient(gmail_stats_server.app)


@pytest.fixture
def empty_db():
    """Create an empty test database (no data)."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                account_email TEXT NOT NULL,
                days_analyzed INTEGER NOT NULL,
                sample_size INTEGER NOT NULL,
                sampling_method TEXT NOT NULL,
                messages_examined INTEGER NOT NULL,
                total_mailbox_messages INTEGER NOT NULL
            );

            CREATE TABLE sender_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                aggregation_level TEXT NOT NULL,
                sender TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL,
                messages_with_attachments INTEGER,
                parent_domain TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def empty_client(empty_db):
    """Create test client with empty database."""
    with patch.object(gmail_stats_server, 'DB_PATH', empty_db):
        yield TestClient(gmail_stats_server.app)


class TestIndexEndpoint:
    """Tests for GET / endpoint."""

    def test_returns_html(self, client):
        """Test that / returns HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_html_has_dashboard_title(self, client):
        """Test HTML has dashboard title."""
        response = client.get("/")
        assert "Gmail Stats Dashboard" in response.text

    def test_html_has_api_fetch(self, client):
        """Test HTML has JavaScript to fetch from API."""
        response = client.get("/")
        assert "fetch('/api/" in response.text

    def test_html_has_controls(self, client):
        """Test HTML has metric/level controls."""
        response = client.get("/")
        assert 'id="metric"' in response.text
        assert 'id="level"' in response.text


class TestApiSummaryEndpoint:
    """Tests for GET /api/summary endpoint."""

    def test_returns_json(self, client):
        """Test that /api/summary returns JSON."""
        response = client.get("/api/summary")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_summary_structure(self, client):
        """Test summary response has expected fields."""
        response = client.get("/api/summary")
        data = response.json()

        expected_fields = [
            'run_id', 'timestamp', 'account_email', 'days_analyzed',
            'sample_size', 'sampling_method', 'messages_examined',
            'total_mailbox_messages', 'unique_domains', 'unique_emails',
            'total_bytes', 'total_mb'
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_summary_values(self, client):
        """Test summary has correct values from test data."""
        response = client.get("/api/summary")
        data = response.json()

        assert data['account_email'] == "test@example.com"
        assert data['days_analyzed'] == 30
        assert data['sample_size'] == 5000
        assert data['sampling_method'] == "random"
        assert data['messages_examined'] == 1000
        assert data['unique_domains'] == 3
        assert data['unique_emails'] == 4

    def test_summary_empty_db(self, empty_client):
        """Test summary returns error for empty database."""
        response = empty_client.get("/api/summary")
        data = response.json()
        assert "error" in data


class TestApiTopEndpoint:
    """Tests for GET /api/top endpoint."""

    def test_returns_json(self, client):
        """Test that /api/top returns JSON."""
        response = client.get("/api/top")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_default_parameters(self, client):
        """Test default parameters (count, domain, 50)."""
        response = client.get("/api/top")
        data = response.json()

        assert data['metric'] == 'count'
        assert data['level'] == 'domain'
        assert data['limit'] == 50

    def test_metric_count(self, client):
        """Test sorting by count."""
        response = client.get("/api/top?metric=count&level=domain")
        data = response.json()

        senders = data['senders']
        counts = [s['message_count'] for s in senders]
        assert counts == sorted(counts, reverse=True)

    def test_metric_size(self, client):
        """Test sorting by size."""
        response = client.get("/api/top?metric=size&level=domain")
        data = response.json()

        senders = data['senders']
        sizes = [s['total_size_mb'] for s in senders]
        assert sizes == sorted(sizes, reverse=True)

    def test_level_domain(self, client):
        """Test domain level aggregation."""
        response = client.get("/api/top?level=domain")
        data = response.json()

        senders = data['senders']
        assert len(senders) == 3  # 3 domains in test data
        assert all('@' not in s['sender'] for s in senders)

    def test_level_email(self, client):
        """Test email level aggregation."""
        response = client.get("/api/top?level=email")
        data = response.json()

        senders = data['senders']
        assert len(senders) == 4  # 4 emails in test data
        assert all('@' in s['sender'] for s in senders)

    def test_limit_parameter(self, client):
        """Test limit parameter."""
        response = client.get("/api/top?level=domain&limit=2")
        data = response.json()

        assert len(data['senders']) == 2

    def test_sender_fields(self, client):
        """Test sender objects have expected fields."""
        response = client.get("/api/top")
        data = response.json()

        sender = data['senders'][0]
        expected_fields = [
            'sender', 'message_count', 'total_size_mb',
            'messages_with_attachments', 'count_pct', 'size_pct'
        ]
        for field in expected_fields:
            assert field in sender, f"Missing field: {field}"

    def test_invalid_metric(self, client):
        """Test invalid metric returns 422."""
        response = client.get("/api/top?metric=invalid")
        assert response.status_code == 422

    def test_invalid_level(self, client):
        """Test invalid level returns 422."""
        response = client.get("/api/top?level=invalid")
        assert response.status_code == 422

    def test_limit_bounds(self, client):
        """Test limit parameter bounds (1-500)."""
        # Below minimum
        response = client.get("/api/top?limit=0")
        assert response.status_code == 422

        # Above maximum
        response = client.get("/api/top?limit=501")
        assert response.status_code == 422

        # Valid bounds
        response = client.get("/api/top?limit=1")
        assert response.status_code == 200

        response = client.get("/api/top?limit=500")
        assert response.status_code == 200

    def test_empty_db(self, empty_client):
        """Test /api/top with empty database."""
        response = empty_client.get("/api/top")
        data = response.json()
        assert "error" in data or len(data.get('senders', [])) == 0


class TestApiRunsEndpoint:
    """Tests for GET /api/runs endpoint."""

    def test_returns_json(self, client):
        """Test that /api/runs returns JSON."""
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_runs_structure(self, client):
        """Test runs response structure."""
        response = client.get("/api/runs")
        data = response.json()

        assert 'runs' in data
        assert isinstance(data['runs'], list)

    def test_runs_fields(self, client):
        """Test run objects have expected fields."""
        response = client.get("/api/runs")
        data = response.json()

        run = data['runs'][0]
        expected_fields = [
            'run_id', 'timestamp', 'account_email', 'days_analyzed',
            'sample_size', 'sampling_method', 'messages_examined',
            'total_mailbox_messages'
        ]
        for field in expected_fields:
            assert field in run, f"Missing field: {field}"

    def test_limit_parameter(self, client):
        """Test limit parameter."""
        response = client.get("/api/runs?limit=5")
        data = response.json()

        # We only have 1 run in test data
        assert len(data['runs']) <= 5

    def test_empty_db(self, empty_client):
        """Test /api/runs with empty database."""
        response = empty_client.get("/api/runs")
        data = response.json()
        assert data['runs'] == []
