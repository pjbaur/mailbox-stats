"""HTML report generation for gmail_stats."""

from datetime import datetime
from pathlib import Path
from typing import Dict


def generate_html_report(
    domain_stats: Dict,
    email_stats: Dict,
    run_metadata: Dict,
    output_dir: Path
) -> Path:
    """Generate a simple HTML report (1998 style).

    Creates a single report.html file with inline CSS, no external dependencies.
    Simple tables only, no JavaScript, no fancy visualizations.

    Args:
        domain_stats: Domain-level aggregation (Dict[str, SenderStats])
        email_stats: Email-level aggregation (Dict[str, SenderStats])
        run_metadata: Dict with account_email, days, sample_size, etc.
        output_dir: Directory to write the HTML file

    Returns:
        Path to the created HTML file
    """
    # Extract metadata
    account_email = run_metadata.get("account_email", "Unknown")
    run_started = run_metadata.get("run_started", "")
    days_analyzed = run_metadata.get("days_analyzed", 0)
    sample_size = run_metadata.get("sample_size", 0)
    sampling_method = run_metadata.get("sampling_method", "unknown")
    messages_examined = run_metadata.get("messages_examined", 0)
    total_mailbox_messages = run_metadata.get("total_mailbox_messages", 0)
    total_bytes = run_metadata.get("total_bytes", 0)
    total_mb = total_bytes / (1024 * 1024)

    # Sort stats for tables
    sorted_by_count = sorted(
        domain_stats.items(),
        key=lambda x: x[1].message_count,
        reverse=True
    )[:20]

    sorted_by_size = sorted(
        domain_stats.items(),
        key=lambda x: x[1].total_size_bytes,
        reverse=True
    )[:20]

    # Format run timestamp for display
    try:
        dt = datetime.fromisoformat(run_started.replace('Z', '+00:00'))
        run_display = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        run_display = run_started

    # Build table rows for count
    count_rows = []
    for i, (domain, stats) in enumerate(sorted_by_count, 1):
        total_pct = (stats.message_count / messages_examined * 100) if messages_examined > 0 else 0
        count_rows.append(f"""
            <tr>
                <td>{i}</td>
                <td>{_escape(domain)}</td>
                <td class="right">{stats.message_count:,}</td>
                <td class="right">{total_pct:.1f}%</td>
            </tr>""")

    # Build table rows for size
    size_rows = []
    for i, (domain, stats) in enumerate(sorted_by_size, 1):
        total_pct = (stats.total_size_bytes / total_bytes * 100) if total_bytes > 0 else 0
        size_mb = stats.total_size_bytes / (1024 * 1024)
        size_display = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
        size_rows.append(f"""
            <tr>
                <td>{i}</td>
                <td>{_escape(domain)}</td>
                <td class="right">{size_display}</td>
                <td class="right">{total_pct:.1f}%</td>
            </tr>""")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gmail Stats Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
        }}
        .summary {{
            margin: 20px 0;
            background: white;
            padding: 15px;
            border: 1px solid #ccc;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            background: white;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background: #f0f0f0;
        }}
        .right {{
            text-align: right;
        }}
    </style>
</head>
<body>
    <h1>Gmail Stats Report</h1>

    <div class="summary">
        <p><strong>Account:</strong> {_escape(account_email)}</p>
        <p><strong>Generated:</strong> {run_display}</p>
        <p><strong>Total messages:</strong> {messages_examined:,}</p>
        <p><strong>Time window:</strong> Last {days_analyzed} days</p>
    </div>

    <h2>Top Senders by Message Count</h2>
    <table>
        <tr>
            <th>#</th>
            <th>Sender</th>
            <th>Count</th>
            <th>Share</th>
        </tr>
        {''.join(count_rows)}
    </table>

    <h2>Top Senders by Total Size</h2>
    <table>
        <tr>
            <th>#</th>
            <th>Sender</th>
            <th>Size</th>
            <th>Share</th>
        </tr>
        {''.join(size_rows)}
    </table>

    <div class="summary">
        <p><strong>Days Analyzed:</strong> {days_analyzed}</p>
        <p><strong>Sample Size:</strong> {sample_size if sample_size > 0 else 'unlimited'}</p>
        <p><strong>Sampling Method:</strong> {sampling_method}</p>
        <p><strong>Total Mailbox Messages:</strong> {total_mailbox_messages:,}</p>
    </div>
</body>
</html>"""

    html_path = output_dir / "report.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return html_path


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
