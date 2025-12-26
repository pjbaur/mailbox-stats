"""Unit tests for gmail_stats_export.py (Day 5 features).

Tests for:
- create_dated_output_dir()
- export_top_senders_csv()
- export_summary_json()
"""

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from gmail_stats import SenderStats
from gmail_stats_export import (
    create_dated_output_dir,
    export_top_senders_csv,
    export_summary_json,
)


class TestCreateDatedOutputDir:
    """Tests for create_dated_output_dir()."""

    def test_creates_directory(self):
        """Test that directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_dated_output_dir(tmpdir)
            assert result.exists()
            assert result.is_dir()

    def test_directory_name_format(self):
        """Test directory name matches YYYY-MM-DD_HHMM format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_dated_output_dir(tmpdir)
            # Name should be like "2025-12-26_1430"
            name = result.name
            assert len(name) == 15  # YYYY-MM-DD_HHMM
            assert name[4] == '-'
            assert name[7] == '-'
            assert name[10] == '_'

    def test_creates_nested_directories(self):
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "path")
            result = create_dated_output_dir(nested_path)
            assert result.exists()
            assert "nested" in str(result)

    def test_idempotent_creation(self):
        """Test that calling twice with same timestamp doesn't fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock datetime to ensure same timestamp
            with patch('gmail_stats_export.datetime') as mock_dt:
                mock_dt.now.return_value.strftime.return_value = "2025-12-26_1430"
                result1 = create_dated_output_dir(tmpdir)
                result2 = create_dated_output_dir(tmpdir)
                assert result1 == result2


class TestExportTopSendersCsv:
    """Tests for export_top_senders_csv()."""

    @pytest.fixture
    def sample_stats(self):
        """Sample domain and email stats for testing."""
        domain_stats = {
            "example.com": SenderStats(
                message_count=100,
                total_size_bytes=1024 * 1024 * 10,  # 10 MB
                messages_with_attachments=25,
            ),
            "test.org": SenderStats(
                message_count=50,
                total_size_bytes=1024 * 1024 * 5,  # 5 MB
                messages_with_attachments=10,
            ),
        }
        email_stats = {
            "user@example.com": SenderStats(
                message_count=60,
                total_size_bytes=1024 * 1024 * 6,  # 6 MB
                messages_with_attachments=15,
            ),
            "admin@example.com": SenderStats(
                message_count=40,
                total_size_bytes=1024 * 1024 * 4,  # 4 MB
                messages_with_attachments=10,
            ),
            "info@test.org": SenderStats(
                message_count=50,
                total_size_bytes=1024 * 1024 * 5,  # 5 MB
                messages_with_attachments=10,
            ),
        }
        return domain_stats, email_stats

    def test_creates_count_csv(self, sample_stats):
        """Test that top_senders_by_count.csv is created."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)
            assert count_path.exists()
            assert count_path.name == "top_senders_by_count.csv"

    def test_creates_size_csv(self, sample_stats):
        """Test that top_senders_by_size.csv is created."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _, size_path = export_top_senders_csv(domain_stats, email_stats, output_dir)
            assert size_path.exists()
            assert size_path.name == "top_senders_by_size.csv"

    def test_count_csv_headers(self, sample_stats):
        """Test CSV headers are correct."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                expected = ['level', 'sender', 'message_count', 'total_size_mb',
                           'messages_with_attachments', 'attachment_rate_pct']
                assert headers == expected

    def test_count_csv_sorted_by_count(self, sample_stats):
        """Test that count CSV is sorted by message_count descending."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                counts = [int(row['message_count']) for row in rows]
                assert counts == sorted(counts, reverse=True)

    def test_size_csv_sorted_by_size(self, sample_stats):
        """Test that size CSV is sorted by total_size_mb descending."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _, size_path = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(size_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                sizes = [float(row['total_size_mb']) for row in rows]
                assert sizes == sorted(sizes, reverse=True)

    def test_includes_both_domain_and_email(self, sample_stats):
        """Test that both domain and email level rows are included."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                levels = {row['level'] for row in rows}
                assert 'domain' in levels
                assert 'email' in levels

    def test_row_count_matches_input(self, sample_stats):
        """Test that row count equals domain + email entries."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                expected_count = len(domain_stats) + len(email_stats)
                assert len(rows) == expected_count

    def test_attachment_rate_calculation(self, sample_stats):
        """Test that attachment_rate_pct is calculated correctly."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, _ = export_top_senders_csv(domain_stats, email_stats, output_dir)

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['sender'] == 'example.com':
                        # 25/100 = 25%
                        assert row['attachment_rate_pct'] == '25.0'
                        break

    def test_empty_stats(self):
        """Test handling of empty stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            count_path, size_path = export_top_senders_csv({}, {}, output_dir)

            # Files should still be created with headers
            assert count_path.exists()
            assert size_path.exists()

            with open(count_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert len(rows) == 1  # Just headers


class TestExportSummaryJson:
    """Tests for export_summary_json()."""

    @pytest.fixture
    def sample_metadata(self):
        """Sample run metadata for testing."""
        return {
            'account_email': 'test@example.com',
            'run_started': '2025-12-26T10:00:00+00:00',
            'run_finished': '2025-12-26T10:05:00+00:00',
            'days_analyzed': 30,
            'sample_size': 5000,
            'sampling_method': 'random',
            'messages_examined': 4500,
            'total_mailbox_messages': 50000,
            'total_bytes': 1024 * 1024 * 100,  # 100 MB
        }

    @pytest.fixture
    def sample_stats(self):
        """Sample stats for testing."""
        domain_stats = {
            "example.com": SenderStats(message_count=100),
            "test.org": SenderStats(message_count=50),
        }
        email_stats = {
            "user@example.com": SenderStats(message_count=60),
            "admin@example.com": SenderStats(message_count=40),
            "info@test.org": SenderStats(message_count=50),
        }
        return domain_stats, email_stats

    def test_creates_summary_json(self, sample_metadata, sample_stats):
        """Test that summary.json is created."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)
            assert json_path.exists()
            assert json_path.name == "summary.json"

    def test_json_is_valid(self, sample_metadata, sample_stats):
        """Test that output is valid JSON."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)  # Should not raise
                assert isinstance(data, dict)

    def test_json_structure(self, sample_metadata, sample_stats):
        """Test JSON has expected top-level keys."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            expected_keys = ['account_email', 'run_started', 'run_finished',
                           'filters', 'totals', 'unique_senders']
            assert all(key in data for key in expected_keys)

    def test_filters_section(self, sample_metadata, sample_stats):
        """Test filters section has correct values."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert data['filters']['days_analyzed'] == 30
            assert data['filters']['sample_size'] == 5000
            assert data['filters']['sampling_method'] == 'random'

    def test_totals_section(self, sample_metadata, sample_stats):
        """Test totals section has correct values."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert data['totals']['messages_examined'] == 4500
            assert data['totals']['total_mailbox_messages'] == 50000
            assert data['totals']['total_bytes'] == 1024 * 1024 * 100
            assert data['totals']['total_mb'] == 100.0

    def test_unique_senders_count(self, sample_metadata, sample_stats):
        """Test unique_senders counts are correct."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert data['unique_senders']['domains'] == 2
            assert data['unique_senders']['emails'] == 3

    def test_json_is_formatted(self, sample_metadata, sample_stats):
        """Test that JSON is pretty-printed (has indentation)."""
        domain_stats, email_stats = sample_stats
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path = export_summary_json(sample_metadata, domain_stats, email_stats, output_dir)

            with open(json_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pretty-printed JSON should have newlines
            assert '\n' in content
            # And indentation
            assert '  ' in content
