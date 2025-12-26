## Day 5: Minimal UI or Output (pick “tiny but useful”)

Here are 3 solid Day 5 targets, ordered from fastest-to-value to slightly fancier:

### Option A: “One Command, Two Files” (my default pick)

**Outputs**

* `top_senders_by_count.csv`
* `top_senders_by_size.csv`
* plus a small `summary.json` (totals, date run, messages scanned)

**Also print** a clean console report:

* Top 10 by count
* Top 10 by size
* “Top 10 share of total size” (%)
* “Attachments: X% of messages” (if you tracked it)

This gets you shareable artifacts immediately.

### Option B: Static HTML Report (zero server, open in browser)

Generate a single `report.html` with:

* Tables: top senders by count/size
* Little “sparkline-lite” bars (just CSS width percentages)
* Footer: run metadata

Feels like a dashboard without becoming a dashboard.

### Option C: Minimal Local Web UI (FastAPI)

A couple endpoints:

* `/api/top?metric=size&limit=50`
* `/api/summary`
  And a barebones page that fetches and renders tables.

More moving parts, but it sets you up for Day 6/7 polish.

---

## What “Shipped” means for Day 5 ✅

* You can run one command and get **human-friendly output** someone else could understand in 30 seconds.
* Output is stable and versionable (CSV/JSON/HTML).
* Includes run metadata (timestamp, message count scanned, filters applied).

---

## Suggested “Next” checklist for Day 5

* [ ] Add `--out ./out` and create dated subfolders: `out/2025-12-25_2210/`
* [ ] Write CSVs with consistent columns:

  * sender, message_count, total_bytes, total_mb, messages_with_attachments
* [ ] Add `summary.json`:

  * total_messages, total_bytes, unique_senders, run_started, run_finished, filters
* [ ] Print a short console report (top 10 + totals)

---
