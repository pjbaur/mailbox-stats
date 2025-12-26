"""Unit tests for gmail_stats_html.py (Day 5 features).

Tests for:
- generate_html_report()
- _escape() helper function
"""

import tempfile
from pathlib import Path

import pytest

from gmail_stats import SenderStats
from gmail_stats_html import generate_html_report, _escape


class TestEscape:
    """Tests for the HTML escape helper function."""

    def test_escape_ampersand(self):
        """Test & is escaped."""
        assert _escape("Tom & Jerry") == "Tom &amp; Jerry"

    def test_escape_less_than(self):
        """Test < is escaped."""
        assert _escape("a < b") == "a &lt; b"

    def test_escape_greater_than(self):
        """Test > is escaped."""
        assert _escape("a > b") == "a &gt; b"

    def test_escape_double_quote(self):
        """Test " is escaped."""
        assert _escape('say "hello"') == "say &quot;hello&quot;"

    def test_escape_single_quote(self):
        """Test ' is escaped."""
        assert _escape("it's") == "it&#39;s"

    def test_escape_multiple_chars(self):
        """Test multiple special chars are all escaped."""
        result = _escape('<script>alert("XSS")</script>')
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result
        assert "<" not in result
        assert ">" not in result

    def test_escape_no_special_chars(self):
        """Test plain text passes through unchanged."""
        assert _escape("hello world") == "hello world"

    def test_escape_empty_string(self):
        """Test empty string returns empty."""
        assert _escape("") == ""

    def test_escape_non_string(self):
        """Test that non-strings are converted."""
        assert _escape(123) == "123"


class TestGenerateHtmlReport:
    """Tests for generate_html_report()."""

    @pytest.fixture
    def sample_data(self):
        """Sample data for HTML report generation."""
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
            "small.net": SenderStats(
                message_count=10,
                total_size_bytes=1024 * 100,  # 100 KB
                messages_with_attachments=0,
            ),
        }
        email_stats = {
            "user@example.com": SenderStats(
                message_count=60,
                total_size_bytes=1024 * 1024 * 6,
                messages_with_attachments=15,
            ),
            "admin@example.com": SenderStats(
                message_count=40,
                total_size_bytes=1024 * 1024 * 4,
                messages_with_attachments=10,
            ),
            "info@test.org": SenderStats(
                message_count=50,
                total_size_bytes=1024 * 1024 * 5,
                messages_with_attachments=10,
            ),
        }
        run_metadata = {
            'account_email': 'test@example.com',
            'run_started': '2025-12-26T10:00:00+00:00',
            'run_finished': '2025-12-26T10:05:00+00:00',
            'days_analyzed': 30,
            'sample_size': 5000,
            'sampling_method': 'random',
            'messages_examined': 160,
            'total_mailbox_messages': 50000,
            'total_bytes': 1024 * 1024 * 15,  # 15 MB
        }
        return domain_stats, email_stats, run_metadata

    def test_creates_report_html(self, sample_data):
        """Test that report.html is created."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )
            assert html_path.exists()
            assert html_path.name == "report.html"

    def test_html_is_valid_structure(self, sample_data):
        """Test HTML has basic structure."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "<!DOCTYPE html>" in content
            assert "<html" in content
            assert "</html>" in content
            assert "<head>" in content
            assert "</head>" in content
            assert "<body>" in content
            assert "</body>" in content

    def test_html_has_title(self, sample_data):
        """Test HTML has title with account email."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "<title>" in content
            assert "test@example.com" in content

    def test_html_has_inline_css(self, sample_data):
        """Test HTML has inline CSS (no external stylesheets)."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "<style>" in content
            assert "</style>" in content
            # Should not have external stylesheet links
            assert 'rel="stylesheet"' not in content

    def test_html_has_summary_section(self, sample_data):
        """Test HTML has summary section with metadata."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "Total messages:" in content
            assert "Time window:" in content
            assert "Account:" in content
            assert "Generated:" in content

    def test_html_has_count_table(self, sample_data):
        """Test HTML has top senders by count table."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "Top Senders by Message Count" in content
            assert "example.com" in content

    def test_html_has_size_table(self, sample_data):
        """Test HTML has top senders by size table."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "Top Senders by Total Size" in content

    def test_html_has_footer_metadata(self, sample_data):
        """Test HTML has footer with run metadata."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            # Check for metadata section (using div.summary instead of footer)
            assert "Days Analyzed" in content
            assert "Sample Size" in content
            assert "Sampling Method" in content
            assert "Total Mailbox Messages" in content

    def test_html_shows_correct_counts(self, sample_data):
        """Test HTML displays correct message counts."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            # example.com has 100 messages
            assert "100" in content
            # test.org has 50 messages
            assert "50" in content

    def test_html_escapes_special_chars(self):
        """Test HTML properly escapes special characters in data."""
        domain_stats = {
            "<script>alert('xss')</script>": SenderStats(
                message_count=10,
                total_size_bytes=1024,
            ),
        }
        email_stats = {}
        run_metadata = {
            'account_email': 'test@example.com',
            'run_started': '2025-12-26T10:00:00+00:00',
            'days_analyzed': 30,
            'sample_size': 5000,
            'sampling_method': 'random',
            'messages_examined': 10,
            'total_mailbox_messages': 100,
            'total_bytes': 1024,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            # Raw script tag should not appear
            assert "<script>alert" not in content
            # Escaped version should appear
            assert "&lt;script&gt;" in content

    def test_html_no_javascript(self, sample_data):
        """Test HTML has no JavaScript (static report)."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert "<script>" not in content

    def test_html_charset_utf8(self, sample_data):
        """Test HTML specifies UTF-8 charset."""
        domain_stats, email_stats, run_metadata = sample_data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report(
                domain_stats, email_stats, run_metadata, output_dir
            )

            content = html_path.read_text(encoding='utf-8')
            assert 'charset="UTF-8"' in content

    def test_empty_stats(self):
        """Test handling of empty stats."""
        run_metadata = {
            'account_email': 'test@example.com',
            'run_started': '2025-12-26T10:00:00+00:00',
            'days_analyzed': 30,
            'sample_size': 5000,
            'sampling_method': 'random',
            'messages_examined': 0,
            'total_mailbox_messages': 0,
            'total_bytes': 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            html_path = generate_html_report({}, {}, run_metadata, output_dir)
            assert html_path.exists()
            # Should still be valid HTML
            content = html_path.read_text(encoding='utf-8')
            assert "<!DOCTYPE html>" in content
