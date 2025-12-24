# GMail statistics

## What it does

I wanted to clean up my GMail, and wanted to find the senders with the most/largest emails

## What stats it will show

- Senders with the most email
- Senders with the largest email (include attachments)

## Tech stack

- Python 3.12
- GCP
- GMail API

## Claude code notes

⏺ I've created a CLAUDE.md file for this repository. Since this is an early-stage project with no code yet, I've kept it minimal and focused on the essential information:

  1. Project Overview: Describes what the tool does - analyzing Gmail data to find top senders by count and size
  2. Tech Stack: Documents the key technologies (Python 3.12, GCP, Gmail API)
  3. Project Status: Notes that this is early-stage, so future Claude instances understand the context

  As you develop the project and add code, build scripts, tests, and establish architectural patterns, you can expand this file with:
  - Build/test/lint commands
  - Authentication setup for Gmail API
  - GCP configuration details
  - Code architecture and module organization
  - Any specific development workflows you establish

## Design decisions

Before deploying, we need to decide on an authentication approach:
Option A: Service Account (simpler, if you only need to access YOUR Gmail)

Best for personal automation
No OAuth flow needed once set up

Option B: Web OAuth Flow (if you want other users to authorize access to their Gmail)

Proper for multi-user apps
Stores tokens in Cloud Storage or Secret Manager

I went with **Option A**.

