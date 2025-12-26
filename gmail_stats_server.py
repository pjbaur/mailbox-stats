"""FastAPI server for gmail_stats web UI."""

import argparse
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse


DB_PATH = Path("gmail_stats.db")

app = FastAPI(title="Gmail Stats API", version="1.0.0")


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/summary")
def get_summary():
    """Get summary of the most recent run."""
    conn = get_db()
    try:
        cursor = conn.cursor()

        # Get the most recent run
        cursor.execute("""
            SELECT run_id, timestamp, account_email, days_analyzed, sample_size,
                   sampling_method, messages_examined, total_mailbox_messages
            FROM runs
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        run = cursor.fetchone()

        if not run:
            return {"error": "No runs found"}

        run_id = run["run_id"]

        # Get aggregate stats for this run
        cursor.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN aggregation_level = 'domain' THEN sender END) as unique_domains,
                COUNT(DISTINCT CASE WHEN aggregation_level = 'email' THEN sender END) as unique_emails,
                SUM(CASE WHEN aggregation_level = 'domain' THEN total_size_bytes ELSE 0 END) as total_bytes
            FROM sender_stats
            WHERE run_id = ?
        """, (run_id,))
        stats = cursor.fetchone()

        return {
            "run_id": run["run_id"],
            "timestamp": run["timestamp"],
            "account_email": run["account_email"],
            "days_analyzed": run["days_analyzed"],
            "sample_size": run["sample_size"],
            "sampling_method": run["sampling_method"],
            "messages_examined": run["messages_examined"],
            "total_mailbox_messages": run["total_mailbox_messages"],
            "unique_domains": stats["unique_domains"] or 0,
            "unique_emails": stats["unique_emails"] or 0,
            "total_bytes": stats["total_bytes"] or 0,
            "total_mb": round((stats["total_bytes"] or 0) / (1024 * 1024), 2)
        }

    finally:
        conn.close()


@app.get("/api/top")
def get_top_senders(
    metric: str = Query("count", pattern="^(count|size)$"),
    level: str = Query("domain", pattern="^(domain|email)$"),
    limit: int = Query(50, ge=1, le=500)
):
    """Get top senders by count or size.

    Args:
        metric: 'count' or 'size' - what to rank by
        level: 'domain' or 'email' - aggregation level
        limit: Number of results (1-500)

    Returns:
        List of senders with stats
    """
    conn = get_db()
    try:
        cursor = conn.cursor()

        # Get the most recent run
        cursor.execute("SELECT run_id FROM runs ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return {"error": "No runs found", "senders": []}

        run_id = row["run_id"]

        # Get total for percentage calculation
        cursor.execute("""
            SELECT SUM(message_count) as total_count, SUM(total_size_bytes) as total_size
            FROM sender_stats
            WHERE run_id = ? AND aggregation_level = ?
        """, (run_id, level))
        totals = cursor.fetchone()
        total_count = totals["total_count"] or 1
        total_size = totals["total_size"] or 1

        # Order by the requested metric
        order_col = "message_count" if metric == "count" else "total_size_bytes"

        cursor.execute(f"""
            SELECT sender, message_count, total_size_bytes, messages_with_attachments
            FROM sender_stats
            WHERE run_id = ? AND aggregation_level = ?
            ORDER BY {order_col} DESC
            LIMIT ?
        """, (run_id, level, limit))

        senders = []
        for row in cursor.fetchall():
            size_mb = row["total_size_bytes"] / (1024 * 1024)
            senders.append({
                "sender": row["sender"],
                "message_count": row["message_count"],
                "total_size_mb": round(size_mb, 2),
                "messages_with_attachments": row["messages_with_attachments"],
                "count_pct": round(row["message_count"] / total_count * 100, 1),
                "size_pct": round(row["total_size_bytes"] / total_size * 100, 1)
            })

        return {
            "metric": metric,
            "level": level,
            "limit": limit,
            "senders": senders
        }

    finally:
        conn.close()


@app.get("/api/runs")
def get_runs(limit: int = Query(10, ge=1, le=100)):
    """Get list of recent runs."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT run_id, timestamp, account_email, days_analyzed, sample_size,
                   sampling_method, messages_examined, total_mailbox_messages
            FROM runs
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return {
            "runs": [dict(row) for row in cursor.fetchall()]
        }

    finally:
        conn.close()


# Embedded HTML for the web UI
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gmail Stats Dashboard</title>
    <style>
        :root {
            --primary: #1a73e8;
            --primary-light: #e8f0fe;
            --success: #34a853;
            --gray-50: #f8f9fa;
            --gray-100: #f1f3f4;
            --gray-200: #e8eaed;
            --gray-600: #5f6368;
            --gray-900: #202124;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--gray-50);
            color: var(--gray-900);
            line-height: 1.5;
            padding: 2rem;
        }

        .container { max-width: 1200px; margin: 0 auto; }

        h1 { font-size: 1.75rem; font-weight: 500; margin-bottom: 0.5rem; }

        .subtitle { color: var(--gray-600); font-size: 0.9rem; margin-bottom: 1.5rem; }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .card-label {
            font-size: 0.75rem;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-value { font-size: 1.5rem; font-weight: 500; }

        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        select, input {
            padding: 0.5rem 1rem;
            border: 1px solid var(--gray-200);
            border-radius: 4px;
            font-size: 0.9rem;
        }

        .section {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        table { width: 100%; border-collapse: collapse; }

        th {
            text-align: left;
            font-weight: 500;
            font-size: 0.75rem;
            color: var(--gray-600);
            text-transform: uppercase;
            padding: 0.75rem 0.5rem;
            border-bottom: 2px solid var(--gray-200);
        }

        td {
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--gray-100);
        }

        tr:hover { background: var(--gray-50); }

        .mono { font-family: monospace; font-size: 0.9rem; }
        .right { text-align: right; }

        .bar-cell { width: 150px; }

        .bar {
            height: 12px;
            background: var(--primary);
            border-radius: 2px;
            min-width: 2px;
        }

        .loading { color: var(--gray-600); padding: 2rem; text-align: center; }

        @media (max-width: 768px) {
            body { padding: 1rem; }
            .bar-cell { display: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gmail Stats Dashboard</h1>
        <p class="subtitle" id="subtitle">Loading...</p>

        <div class="cards" id="cards">
            <div class="card"><div class="card-label">Messages</div><div class="card-value" id="stat-messages">-</div></div>
            <div class="card"><div class="card-label">Total Size</div><div class="card-value" id="stat-size">-</div></div>
            <div class="card"><div class="card-label">Domains</div><div class="card-value" id="stat-domains">-</div></div>
            <div class="card"><div class="card-label">Senders</div><div class="card-value" id="stat-senders">-</div></div>
        </div>

        <div class="controls">
            <select id="metric">
                <option value="count">Sort by Count</option>
                <option value="size">Sort by Size</option>
            </select>
            <select id="level">
                <option value="domain">Domains</option>
                <option value="email">Email Addresses</option>
            </select>
            <input type="number" id="limit" value="50" min="1" max="500" style="width: 80px;">
        </div>

        <div class="section">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Sender</th>
                        <th class="right">Count</th>
                        <th class="right">Size</th>
                        <th class="right">Share</th>
                        <th class="bar-cell"></th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    <tr><td colspan="6" class="loading">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function loadSummary() {
            try {
                const res = await fetch('/api/summary');
                const data = await res.json();

                if (data.error) {
                    document.getElementById('subtitle').textContent = data.error;
                    return;
                }

                document.getElementById('subtitle').textContent =
                    `${data.account_email} | ${data.timestamp}`;
                document.getElementById('stat-messages').textContent =
                    data.messages_examined.toLocaleString();
                document.getElementById('stat-size').textContent =
                    `${data.total_mb.toFixed(1)} MB`;
                document.getElementById('stat-domains').textContent =
                    data.unique_domains.toLocaleString();
                document.getElementById('stat-senders').textContent =
                    data.unique_emails.toLocaleString();
            } catch (e) {
                document.getElementById('subtitle').textContent = 'Error loading summary';
            }
        }

        async function loadTable() {
            const metric = document.getElementById('metric').value;
            const level = document.getElementById('level').value;
            const limit = document.getElementById('limit').value;

            try {
                const res = await fetch(`/api/top?metric=${metric}&level=${level}&limit=${limit}`);
                const data = await res.json();

                const tbody = document.getElementById('table-body');

                if (data.error || !data.senders.length) {
                    tbody.innerHTML = '<tr><td colspan="6" class="loading">No data</td></tr>';
                    return;
                }

                const maxVal = metric === 'count'
                    ? data.senders[0].message_count
                    : data.senders[0].total_size_mb;

                tbody.innerHTML = data.senders.map((s, i) => {
                    const val = metric === 'count' ? s.message_count : s.total_size_mb;
                    const pct = metric === 'count' ? s.count_pct : s.size_pct;
                    const barPct = (val / maxVal * 100).toFixed(1);

                    return `<tr>
                        <td>${i + 1}</td>
                        <td class="mono">${s.sender}</td>
                        <td class="right mono">${s.message_count.toLocaleString()}</td>
                        <td class="right mono">${s.total_size_mb.toFixed(1)} MB</td>
                        <td class="right">${pct}%</td>
                        <td class="bar-cell"><div class="bar" style="width: ${barPct}%"></div></td>
                    </tr>`;
                }).join('');
            } catch (e) {
                document.getElementById('table-body').innerHTML =
                    '<tr><td colspan="6" class="loading">Error loading data</td></tr>';
            }
        }

        // Event listeners
        document.getElementById('metric').addEventListener('change', loadTable);
        document.getElementById('level').addEventListener('change', loadTable);
        document.getElementById('limit').addEventListener('change', loadTable);

        // Initial load
        loadSummary();
        loadTable();
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main dashboard page."""
    return HTML_PAGE


def parse_args():
    """Parse command-line arguments for standalone mode."""
    parser = argparse.ArgumentParser(description="Gmail Stats Web Server")
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to run the server on (default: 8000)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='gmail_stats.db',
        help='Path to SQLite database (default: gmail_stats.db)'
    )
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()
    DB_PATH = Path(args.db)

    print(f"Starting Gmail Stats server at http://{args.host}:{args.port}")
    print(f"Using database: {DB_PATH}")
    uvicorn.run(app, host=args.host, port=args.port)
