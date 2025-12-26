"""CSV export functionality for gmail_stats."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple


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
