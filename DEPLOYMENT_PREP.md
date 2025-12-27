Alright, Day 6: we take your mail-scooper and give it a nice little GCP home with a doorbell 🔔

Below is a clean deployment path that matches what you said earlier: **infrequent, on-demand/triggered**, **Python**, **metadata-only**, **us-central1**. I’m going to steer you toward **Cloud Run Jobs** (best fit for “run this batch when I ask”), with an optional HTTP trigger if you want a big red “RUN” button.

---

## Deploy option I recommend: Cloud Run Job (on-demand batch)

### What you get

* **No server running** between runs
* **Pay mostly only while it runs**
* Easy to rerun, easy to version, easy to bump CPU/memory for speed
* Works great with your existing “process N messages” approach

### Step 0: Prep your repo for container deploy

Make sure you have:

* `main.py` (or similar) entry point that can run end-to-end
* `requirements.txt` (or `pyproject.toml`, but `requirements.txt` is the least fussy)
* Config pulled from env vars (no hardcoding)

Suggested env vars:

* `GMAIL_USER=me`
* `MAX_MESSAGES=0` (0 meaning “all”, or omit)
* `BATCH_SIZE=500` (or whatever you tuned)
* `OUTPUT_BUCKET=...` (if you write results somewhere)

### Step 1: Add a Dockerfile

Typical minimal Dockerfile for Python batch jobs:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "main"]
```

If your entry file is `gmail_stats.py`, change the CMD accordingly.

### Step 2: Decide where the OAuth tokens live (important)

For “run in Cloud Run Job” you want **non-interactive auth**.

**Best practice** for Gmail API on GCP:

* Use a **Workspace domain-wide delegation** service account (if this is Google Workspace and allowed), **or**
* Use an **installed-app OAuth token** that you already generated locally, then store it securely and mount it at runtime.

For a dev project, the pragmatic approach is:

* Put your `token.json` (refresh token) in **Secret Manager**
* At runtime, write it to disk (or read from env) and use it

Do **not** bake `token.json` into the container image.

### Step 3: Build + push image (Artifact Registry)

From your project root:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region us-central1

gcloud artifacts repositories create mailbox-stats \
  --repository-format=docker \
  --location=us-central1

gcloud auth configure-docker us-central1-docker.pkg.dev

IMAGE="us-central1-docker.pkg.dev/YOUR_PROJECT_ID/mailbox-stats/mailbox-stats:$(git rev-parse --short HEAD)"
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

### Step 4: Create the Cloud Run Job

```bash
gcloud run jobs create mailbox-stats \
  --image "$IMAGE" \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 3600 \
  --max-retries 0
```

Then set environment variables:

```bash
gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --set-env-vars "BATCH_SIZE=500,MAX_MESSAGES=0"
```

### Step 5: Add secrets (token, creds, etc.)

Example pattern (you can mount as env vars or files). If you store the OAuth token as a secret:

```bash
gcloud secrets create gmail-token-json --data-file=token.json
```

Then wire it to the job:

```bash
gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --set-secrets "GMAIL_TOKEN_JSON=gmail-token-json:latest"
```

In code, you can read `os.environ["GMAIL_TOKEN_JSON"]` and write it to a temp file if your Gmail library expects a file.

### Step 6: Run it

```bash
gcloud run jobs execute mailbox-stats --region us-central1
```

Tail logs:

```bash
gcloud logs read --region us-central1 --limit 100 --format="value(textPayload)"
```

---

## Optional: make it “push-button” triggered

If you want HTTP-triggered:

* Create a tiny **Cloud Run Service** (or Cloud Function) that calls `run.jobs.execute` on your Job.
* Lock it down to your Google account (IAM) so it’s not a public “summon the API goblin” endpoint.

---

## Deployment checklist (the “did we forget a banana peel?” list)

* [ ] No client secrets committed (ever)
* [ ] Token/refresh token stored in Secret Manager
* [ ] Output has a home (Cloud Storage bucket is easiest)
* [ ] Logging emits progress checkpoints (you already wanted this, and Cloud Logging will love it)
* [ ] Job timeout high enough for ~78k messages
* [ ] Batching and retry behavior set (and idempotent writes, ideally)

---

## My default “fast enough” job sizing for your workload

Start with:

* **2 CPU / 2Gi RAM**
* If you see the Gmail API becoming the bottleneck: CPU won’t help much, but concurrency tuning will.
* If your parsing/aggregation is heavier than expected: bump to **4 CPU**.

---

If you tell me what you want as the deployed output (CSV? JSON? BigQuery table? a simple HTML report in a bucket?), I’ll snap the last pieces into place so Day 7 becomes “press button, admire stats.” 📬📈


Got it. Option A = **“Cloud Run with no args should do the real run.”** Your CLI flags still work for local/dev, but the default path becomes “run the job.”

Below is a clean pattern that keeps your existing `--random-sample / --sample-size / --export-csv` vibe, while adding sane defaults and Cloud Run-friendly env config.

## Assumptions

* Your entry script is `gmail_stats.py`.
* Today, “no args” prints help and exits.
* You already have a `main()`-ish function (or can add one) that does the work.

---

## Goal behavior

* **No args** ⇒ full mailbox scan (or a “default scan” you choose)
* `--random-sample` ⇒ sample mode
* `--export-csv` ⇒ export results (works with default scan or sample, your choice)
* Cloud Run configuration comes from **env vars**, but CLI flags can override

---

## Step 1: Adjust argparse to support “default run”

Instead of treating “no flags” as “do nothing,” define an explicit **mode** with a default.

### Recommended approach: `--mode {full,sample}`

This is the least ambiguous and easiest to maintain.

```python
# gmail_stats.py
from __future__ import annotations

import argparse
import os
import sys
import logging

logger = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mailbox Stats")

    p.add_argument(
        "--mode",
        choices=["full", "sample"],
        default=os.getenv("MODE", "full"),
        help="Run mode. Default: full (or env MODE).",
    )

    p.add_argument(
        "--sample-size",
        type=int,
        default=int(os.getenv("SAMPLE_SIZE", "5000")),
        metavar="N",
        help="Sample size for --mode sample. Default: 5000 (or env SAMPLE_SIZE).",
    )

    p.add_argument(
        "--export-csv",
        action="store_true",
        default=os.getenv("EXPORT_CSV", "").lower() in ("1", "true", "yes", "y"),
        help="Export results to CSV (or env EXPORT_CSV=1).",
    )

    # Optional: make cloud run configurable without flags
    p.add_argument(
        "--max-messages",
        type=int,
        default=int(os.getenv("MAX_MESSAGES", "0")),
        help="0 means all messages. Default: 0 (or env MAX_MESSAGES).",
    )

    p.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("BATCH_SIZE", "500")),
        help="Gmail list/get batch size. Default: 500 (or env BATCH_SIZE).",
    )

    return p.parse_args(argv)
```

This alone eliminates the “prints usage and exits” failure mode.

---

## Step 2: Route execution based on mode

Now implement a real `main()` that always runs something.

```python
def run_full_scan(*, max_messages: int, batch_size: int, export_csv: bool) -> int:
    logger.info("Mode=full max_messages=%s batch_size=%s export_csv=%s",
                max_messages, batch_size, export_csv)

    # TODO: call your existing logic here
    # stats = compute_stats_full(max_messages=max_messages, batch_size=batch_size)
    # if export_csv: write_csv(stats)
    return 0


def run_sample(*, sample_size: int, batch_size: int, export_csv: bool) -> int:
    logger.info("Mode=sample sample_size=%s batch_size=%s export_csv=%s",
                sample_size, batch_size, export_csv)

    # TODO: call your existing logic here
    # stats = compute_stats_sample(sample_size=sample_size, batch_size=batch_size)
    # if export_csv: write_csv(stats)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    # Optional: guardrails
    if args.mode == "sample" and args.sample_size <= 0:
        raise SystemExit("--sample-size must be > 0 in sample mode")

    if args.mode == "full":
        return run_full_scan(
            max_messages=args.max_messages,
            batch_size=args.batch_size,
            export_csv=args.export_csv,
        )

    return run_sample(
        sample_size=args.sample_size,
        batch_size=args.batch_size,
        export_csv=args.export_csv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

That’s the core of Option A.

---

## Step 3: Keep backward compatibility (optional)

If you really want to keep `--random-sample` working (so your old commands don’t break), you can accept it but map it into `mode`.

Add this arg:

```python
p.add_argument("--random-sample", action="store_true", help=argparse.SUPPRESS)
```

Then after parsing:

```python
if getattr(args, "random_sample", False):
    args.mode = "sample"
```

This lets:

* Old: `--random-sample --sample-size 5000`
* New: `--mode sample --sample-size 5000`

Both work.

---

## Step 4: Set Cloud Run defaults via env vars

Now your Cloud Run Job can run with **no args**, configured by env vars.

Example:

```bash
gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --set-env-vars "MODE=full,BATCH_SIZE=500,MAX_MESSAGES=0,EXPORT_CSV=1"
```

Then execute:

```bash
gcloud run jobs execute mailbox-stats --region us-central1
```

---

## Step 5: Add “this is alive” logging checkpoints

You already saw how valuable a single line was. Add a few more:

* On startup (mode + settings)
* Every N batches/messages processed
* On completion (duration + API totals)

Even simple counters + timestamps make Cloud Runs feel less like a black box.

---

## My recommendation

Use `--mode` with `default=full` (env override). It makes the system **predictable** and future-proof (later you might add `--mode daily` or `--mode top-senders`).

---
