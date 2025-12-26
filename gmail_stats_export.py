"""CSV and JSON export functionality for gmail_stats."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple


def create_dated_output_dir(base_dir: str) -> Path:
    """Create a dated output subdirectory.

    Args:
        base_dir: Base output directory (e.g., './out')

    Returns:
        Path to the created dated subdirectory (e.g., './out/2025-12-26_1430/')
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = Path(base_dir) / timestamp
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def export_top_senders_csv(
    domain_stats: Dict,
    email_stats: Dict,
    output_dir: Path
) -> Tuple[Path, Path]:
    """Export top senders CSVs split by count and size.

    Creates two files:
    - top_senders_by_count.csv: Sorted by message count
    - top_senders_by_size.csv: Sorted by total size

    Each file includes both domain and email-level rows.

    Args:
        domain_stats: Domain-level aggregation (Dict[str, SenderStats])
        email_stats: Email-level aggregation (Dict[str, SenderStats])
        output_dir: Directory to write CSV files

    Returns:
        Tuple of (count_csv_path, size_csv_path)
    """
    headers = [
        'level', 'sender', 'message_count', 'total_size_mb',
        'messages_with_attachments', 'attachment_rate_pct'
    ]

    def make_row(level: str, sender: str, stats) -> list:
        attach_rate = (
            (stats.messages_with_attachments / stats.message_count * 100)
            if stats.message_count > 0 else 0
        )
        return [
            level,
            sender,
            stats.message_count,
            round(stats.total_size_bytes / (1024 * 1024), 2),
            stats.messages_with_attachments if stats.messages_with_attachments > 0 else '',
            round(attach_rate, 1) if stats.messages_with_attachments > 0 else ''
        ]

    # Combine domain and email stats into a unified list
    all_rows = []
    for domain, stats in domain_stats.items():
        all_rows.append(('domain', domain, stats))
    for email, stats in email_stats.items():
        all_rows.append(('email', email, stats))

    # Sort by count and write
    count_path = output_dir / "top_senders_by_count.csv"
    sorted_by_count = sorted(all_rows, key=lambda x: x[2].message_count, reverse=True)
    with open(count_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for level, sender, stats in sorted_by_count:
            writer.writerow(make_row(level, sender, stats))

    # Sort by size and write
    size_path = output_dir / "top_senders_by_size.csv"
    sorted_by_size = sorted(all_rows, key=lambda x: x[2].total_size_bytes, reverse=True)
    with open(size_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for level, sender, stats in sorted_by_size:
            writer.writerow(make_row(level, sender, stats))

    return count_path, size_path


def export_summary_json(
    run_metadata: Dict,
    domain_stats: Dict,
    email_stats: Dict,
    output_dir: Path
) -> Path:
    """Export a summary JSON file with run metadata and aggregate stats.

    Args:
        run_metadata: Dict with account_email, days, sample_size, etc.
        domain_stats: Domain-level aggregation
        email_stats: Email-level aggregation
        output_dir: Directory to write JSON file

    Returns:
        Path to the created JSON file
    """
    summary = {
        "account_email": run_metadata.get("account_email"),
        "run_started": run_metadata.get("run_started"),
        "run_finished": run_metadata.get("run_finished"),
        "filters": {
            "days_analyzed": run_metadata.get("days_analyzed"),
            "sample_size": run_metadata.get("sample_size"),
            "sampling_method": run_metadata.get("sampling_method")
        },
        "totals": {
            "messages_examined": run_metadata.get("messages_examined"),
            "total_mailbox_messages": run_metadata.get("total_mailbox_messages"),
            "total_bytes": run_metadata.get("total_bytes"),
            "total_mb": round(run_metadata.get("total_bytes", 0) / (1024 * 1024), 2)
        },
        "unique_senders": {
            "domains": len(domain_stats),
            "emails": len(email_stats)
        }
    }

    json_path = output_dir / "summary.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return json_path


def export_to_csv(
    domain_stats: Dict,
    email_stats: Dict,
    run_metadata: Dict,
    output_dir: Path = Path(".")
) -> Tuple[Path, Path, Path]:
    """Export statistics to CSV files.

    Args:
        domain_stats: Domain-level aggregation (Dict[str, SenderStats])
        email_stats: Email-level aggregation (Dict[str, SenderStats])
        run_metadata: Dict with account_email, days, sample_size, etc.
        output_dir: Directory to write CSV files

    Returns:
        Tuple of (domain_csv_path, email_csv_path, metadata_csv_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Export domain stats
    domain_path = output_dir / f"sender_stats_domain_{timestamp}.csv"
    with open(domain_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'domain', 'message_count', 'total_size_mb', 'messages_with_attachments',
            'attachment_rate_pct', 'unique_email_addresses'
        ])

        for domain, stats in sorted(
            domain_stats.items(),
            key=lambda x: x[1].total_size_bytes,
            reverse=True
        ):
            attach_rate = (stats.messages_with_attachments / stats.message_count * 100) if stats.message_count > 0 else 0
            writer.writerow([
                domain,
                stats.message_count,
                round(stats.total_size_bytes / (1024 * 1024), 2),
                stats.messages_with_attachments if stats.messages_with_attachments > 0 else '',
                round(attach_rate, 1) if stats.messages_with_attachments > 0 else '',
                len(stats.emails)
            ])

    # Export email stats
    email_path = output_dir / f"sender_stats_email_{timestamp}.csv"
    with open(email_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'email', 'domain', 'message_count', 'total_size_mb', 'messages_with_attachments',
            'attachment_rate_pct'
        ])

        for email, stats in sorted(
            email_stats.items(),
            key=lambda x: x[1].total_size_bytes,
            reverse=True
        ):
            domain = email.split('@')[1] if '@' in email else '(unknown)'
            attach_rate = (stats.messages_with_attachments / stats.message_count * 100) if stats.message_count > 0 else 0
            writer.writerow([
                email,
                domain,
                stats.message_count,
                round(stats.total_size_bytes / (1024 * 1024), 2),
                stats.messages_with_attachments if stats.messages_with_attachments > 0 else '',
                round(attach_rate, 1) if stats.messages_with_attachments > 0 else ''
            ])

    # Export run metadata
    metadata_path = output_dir / f"run_metadata_{timestamp}.csv"
    with open(metadata_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['key', 'value'])
        for key, value in run_metadata.items():
            writer.writerow([key, value])

    return domain_path, email_path, metadata_path
