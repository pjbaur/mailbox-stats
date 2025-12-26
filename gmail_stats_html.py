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
    """Generate a self-contained HTML report.

    Creates a single report.html file with inline CSS, no external dependencies.

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

    # Calculate max values for bar widths
    max_count = sorted_by_count[0][1].message_count if sorted_by_count else 1
    max_size = sorted_by_size[0][1].total_size_bytes if sorted_by_size else 1

    # Format run timestamp for display
    try:
        dt = datetime.fromisoformat(run_started.replace('Z', '+00:00'))
        run_display = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        run_display = run_started

    # Build table rows for count
    count_rows = []
    for i, (domain, stats) in enumerate(sorted_by_count, 1):
        pct = (stats.message_count / max_count * 100) if max_count > 0 else 0
        total_pct = (stats.message_count / messages_examined * 100) if messages_examined > 0 else 0
        count_rows.append(f"""
            <tr>
                <td class="rank">{i}</td>
                <td class="domain">{_escape(domain)}</td>
                <td class="count">{stats.message_count:,}</td>
                <td class="pct">{total_pct:.1f}%</td>
                <td class="bar-cell">
                    <div class="bar" style="width: {pct:.1f}%"></div>
                </td>
            </tr>""")

    # Build table rows for size
    size_rows = []
    for i, (domain, stats) in enumerate(sorted_by_size, 1):
        pct = (stats.total_size_bytes / max_size * 100) if max_size > 0 else 0
        total_pct = (stats.total_size_bytes / total_bytes * 100) if total_bytes > 0 else 0
        size_mb = stats.total_size_bytes / (1024 * 1024)
        size_display = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
        size_rows.append(f"""
            <tr>
                <td class="rank">{i}</td>
                <td class="domain">{_escape(domain)}</td>
                <td class="size">{size_display}</td>
                <td class="pct">{total_pct:.1f}%</td>
                <td class="bar-cell">
                    <div class="bar bar-size" style="width: {pct:.1f}%"></div>
                </td>
            </tr>""")

    # Top 10 share calculations
    top_10_count = sum(stats.message_count for _, stats in sorted_by_count[:10])
    top_10_count_pct = (top_10_count / messages_examined * 100) if messages_examined > 0 else 0
    top_10_size = sum(stats.total_size_bytes for _, stats in sorted_by_size[:10])
    top_10_size_pct = (top_10_size / total_bytes * 100) if total_bytes > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gmail Stats Report - {_escape(account_email)}</title>
    <style>
        :root {{
            --primary: #1a73e8;
            --primary-light: #e8f0fe;
            --success: #34a853;
            --warning: #fbbc04;
            --danger: #ea4335;
            --gray-50: #f8f9fa;
            --gray-100: #f1f3f4;
            --gray-200: #e8eaed;
            --gray-600: #5f6368;
            --gray-900: #202124;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--gray-50);
            color: var(--gray-900);
            line-height: 1.5;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2rem;
        }}

        h1 {{
            font-size: 1.75rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: var(--gray-600);
            font-size: 0.9rem;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .card {{
            background: white;
            border-radius: 8px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .card-label {{
            font-size: 0.8rem;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.25rem;
        }}

        .card-value {{
            font-size: 1.75rem;
            font-weight: 500;
        }}

        .section {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .section-title {{
            font-size: 1.1rem;
            font-weight: 500;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--gray-200);
        }}

        .summary-note {{
            color: var(--gray-600);
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            text-align: left;
            font-weight: 500;
            font-size: 0.8rem;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 0.75rem 0.5rem;
            border-bottom: 2px solid var(--gray-200);
        }}

        td {{
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--gray-100);
        }}

        tr:hover {{
            background: var(--gray-50);
        }}

        .rank {{
            width: 40px;
            color: var(--gray-600);
        }}

        .domain {{
            font-family: monospace;
            font-size: 0.9rem;
        }}

        .count, .size {{
            text-align: right;
            font-family: monospace;
            width: 100px;
        }}

        .pct {{
            text-align: right;
            width: 60px;
            color: var(--gray-600);
        }}

        .bar-cell {{
            width: 200px;
            padding-left: 1rem;
        }}

        .bar {{
            height: 12px;
            background: var(--primary);
            border-radius: 2px;
            min-width: 2px;
        }}

        .bar-size {{
            background: var(--success);
        }}

        footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--gray-200);
            color: var(--gray-600);
            font-size: 0.8rem;
        }}

        footer dl {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.5rem 2rem;
        }}

        footer dt {{
            font-weight: 500;
        }}

        footer dd {{
            margin-left: 0;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}

            .bar-cell {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Gmail Stats Report</h1>
            <p class="subtitle">{_escape(account_email)} &bull; {run_display}</p>
        </header>

        <div class="cards">
            <div class="card">
                <div class="card-label">Messages Examined</div>
                <div class="card-value">{messages_examined:,}</div>
            </div>
            <div class="card">
                <div class="card-label">Total Size</div>
                <div class="card-value">{total_mb:.1f} MB</div>
            </div>
            <div class="card">
                <div class="card-label">Unique Domains</div>
                <div class="card-value">{len(domain_stats):,}</div>
            </div>
            <div class="card">
                <div class="card-label">Unique Senders</div>
                <div class="card-value">{len(email_stats):,}</div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Top Senders by Message Count</h2>
            <p class="summary-note">Top 10 domains account for {top_10_count_pct:.1f}% of messages</p>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Domain</th>
                        <th>Count</th>
                        <th>Share</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(count_rows)}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2 class="section-title">Top Senders by Storage Size</h2>
            <p class="summary-note">Top 10 domains account for {top_10_size_pct:.1f}% of storage</p>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Domain</th>
                        <th>Size</th>
                        <th>Share</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(size_rows)}
                </tbody>
            </table>
        </div>

        <footer>
            <dl>
                <dt>Days Analyzed</dt>
                <dd>{days_analyzed}</dd>

                <dt>Sample Size</dt>
                <dd>{sample_size if sample_size > 0 else 'unlimited'}</dd>

                <dt>Sampling Method</dt>
                <dd>{sampling_method}</dd>

                <dt>Total Mailbox Messages</dt>
                <dd>{total_mailbox_messages:,}</dd>
            </dl>
        </footer>
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
