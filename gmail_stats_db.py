"""SQLite persistence for gmail_stats historical tracking."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


# DB path configurable via environment variable for deployment flexibility
DB_PATH = Path(os.getenv("DB_PATH", "gmail_stats.db"))


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize database schema if not exists."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                account_email TEXT NOT NULL,
                days_analyzed INTEGER NOT NULL,
                sample_size INTEGER NOT NULL,
                sampling_method TEXT NOT NULL,
                messages_examined INTEGER NOT NULL,
                total_mailbox_messages INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sender_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                aggregation_level TEXT NOT NULL,
                sender TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL,
                messages_with_attachments INTEGER,
                parent_domain TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                UNIQUE(run_id, aggregation_level, sender)
            );

            CREATE INDEX IF NOT EXISTS idx_sender_stats_run
                ON sender_stats(run_id);
            CREATE INDEX IF NOT EXISTS idx_sender_stats_sender
                ON sender_stats(sender);
            CREATE INDEX IF NOT EXISTS idx_sender_stats_size
                ON sender_stats(total_size_bytes DESC);
        """)
        conn.commit()
    finally:
        conn.close()


def save_run(
    account_email: str,
    days_analyzed: int,
    sample_size: int,
    sampling_method: str,
    messages_examined: int,
    total_mailbox_messages: int,
    domain_stats: Dict,
    email_stats: Dict,
    db_path: Path = DB_PATH
) -> int:
    """Save a complete run to the database.

    Args:
        account_email: Gmail account email address
        days_analyzed: Number of days in the analysis window
        sample_size: Maximum number of messages sampled (0 = unlimited)
        sampling_method: 'chronological' or 'random'
        messages_examined: Actual number of messages examined
        total_mailbox_messages: Total messages in mailbox
        domain_stats: Dict[str, SenderStats] - domain-level aggregation
        email_stats: Dict[str, SenderStats] - email-level aggregation
        db_path: Path to SQLite database file

    Returns:
        run_id of the inserted run
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # Insert run metadata
        cursor.execute("""
            INSERT INTO runs (
                timestamp, account_email, days_analyzed, sample_size,
                sampling_method, messages_examined, total_mailbox_messages
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            account_email,
            days_analyzed,
            sample_size,
            sampling_method,
            messages_examined,
            total_mailbox_messages
        ))

        run_id = cursor.lastrowid

        # Insert domain-level stats
        for domain, stats in domain_stats.items():
            cursor.execute("""
                INSERT INTO sender_stats (
                    run_id, aggregation_level, sender, message_count,
                    total_size_bytes, messages_with_attachments, parent_domain
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, 'domain', domain, stats.message_count,
                stats.total_size_bytes,
                stats.messages_with_attachments if stats.messages_with_attachments > 0 else None,
                None
            ))

        # Insert email-level stats
        for email, stats in email_stats.items():
            domain = email.split('@')[1] if '@' in email else None
            cursor.execute("""
                INSERT INTO sender_stats (
                    run_id, aggregation_level, sender, message_count,
                    total_size_bytes, messages_with_attachments, parent_domain
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, 'email', email, stats.message_count,
                stats.total_size_bytes,
                stats.messages_with_attachments if stats.messages_with_attachments > 0 else None,
                domain
            ))

        conn.commit()
        return run_id

    finally:
        conn.close()


def get_historical_growth(sender: str, limit: int = 10, db_path: Path = DB_PATH) -> List[Dict]:
    """Get historical size growth for a sender (domain or email).

    Args:
        sender: Sender email address or domain
        limit: Maximum number of historical records to return
        db_path: Path to SQLite database file

    Returns:
        List of {timestamp, message_count, total_size_bytes} dicts,
        ordered by timestamp (most recent first)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.timestamp, s.message_count, s.total_size_bytes
            FROM sender_stats s
            JOIN runs r ON s.run_id = r.run_id
            WHERE s.sender = ?
            ORDER BY r.timestamp DESC
            LIMIT ?
        """, (sender, limit))

        return [dict(row) for row in cursor.fetchall()]

    finally:
        conn.close()
