# Notion Drone Billing Report

**Version 0.01.01** — Python 3.12 Cloud Run **Job** that reads drone flights from Notion, applies tiered internal billing costs from project acreage rollups, writes a monthly Excel report to local disk or Google Cloud Storage, and emails the workbook after successful generation.

## Purpose

Automate monthly internal drone billing by:

1. Querying the Notion **Drone Flight Schedule** database via the official REST API (rollup **Acres** requires REST, not Notion SQL).
2. Selecting flights with **Status = In Process or Completed** and **Flight Date** in the target calendar month (default: previous month in `America/Los_Angeles`).
3. Billing flights with **Status = In Process or Completed** when Flight Date is in the billing month and acres/project/date are valid. Templates and Scheduled flights are not billed. Valid In Process rows appear on the main **Billing Report** (they are not review-only).
4. Grouping flights by project number (then flight date) in an Excel workbook with Billing Report, Flight Detail, and Review Required sheets.
5. Uploading to GCS when configured.
6. Emailing `rkolt@sukut.com` after Notion query, month filter, Excel generation, workbook validation, and GCS upload (when GCS is enabled) all succeed.

If generation fails, the job logs the failure, **does not** send a billing-report email, and exits non-zero.

## Architecture

```
Cloud Scheduler (2nd of month, 2:00 AM PT)
        │
        ▼
Cloud Run Job (notion-drone-billing-report)
        │
        ├── Notion REST API ──► Drone Flight Schedule DB
        │                       Status = In Process OR Completed
        │                       Flight Date in previous calendar month
        │
        ├── Excel report ──► GCS (trimble-data-bucket-rk)
        │
        └── Email ──► rkolt@sukut.com (SMTP after validation)
```

- **GCP project:** `work-projects-486912`
- **Region:** `us-west1`
- **Job name:** `notion-drone-billing-report`
- **Scheduler:** `notion-drone-billing-report-monthly` — cron `0 2 2 * *`, timezone `America/Los_Angeles` (2:00 AM on the 2nd; bills the **previous** calendar month)
- **Example:** Oct 2 2026 2:00 AM PT → September 1–30 2026, attachment `Drone_Billing_Report_2026-09.xlsx`

## Notion source database

- **Title:** Drone Flight Schedule
- **URL:** https://app.notion.com/p/16f9d45a816849cf9436ed2a566312b3
- **Default database ID:** `16f9d45a816849cf9436ed2a566312b3`

### Required properties (by name)

| Property | Type | Notes |
|----------|------|--------|
| Project Number | title | Parsed for project number / name |
| Project | relation | Projects DB |
| Flight Date | date | Month filter |
| Flight Type | select | Detail sheet |
| Drone Equipment | select | Detail sheet |
| Acres | rollup (number) | **Source of truth** for tier |
| Status | select | Query `In Process` or `Completed`. Both are billed when acres, date, and project are valid. |

At startup the job retrieves the live database schema and **fails** if any required property name is missing.

### Excel workbook

**Billing Report** (accounting-facing; no Notion page ID/URL):

- Centered title merged across the report width, e.g. `DRONE BILLINGS - September 2026`
- Blank row under the title, then bold column headers
- Columns: `PROJECT #`, `PROJECT DESCRIPTION`, `FLIGHT DATE`, `FLIGHT TYPE`, `DRONE`, `ACRES`, `STATUS`, `COST TIER`, `$ BILLED AMOUNT`
- Sorted and grouped by Project Number, then Flight Date, with one blank row between project groups
- Dates `MM/DD/YYYY`, acres as a number, dollars with commas and two decimals
- Landscape print, one page wide, header row repeated on subsequent pages
- Bold total row: `TOTAL DRONE BILLING` + month total

**Flight Detail** keeps Notion Page ID and URL plus Status.

**Review Required** lists only records that cannot be billed reliably.

### Review required (not billed)

- Title starts with `TEMPLATE` (case-insensitive)
- Title contains `PLACEHOLDER`
- Missing Acres, Project, or Flight Date
- Acres > 800 → custom estimate (`CUSTOM ESTIMATE REQUIRED`)
- Multiple Project relations

Valid **In Process** flights (acres, date, and project present, acres ≤ 800) **are billed** on Billing Report. Scheduled and other non-reportable statuses are excluded from the Notion query and are not billed.

## Cost tiers

All amounts live in `drone_billing/cost_config.py` (billed totals and line-item breakdown).

| Acres | Total |
|-------|-------|
| 0–200 | $2,500.00 |
| 201–300 | $2,930.68 |
| 301–500 | $3,805.99 |
| 501–800 | $6,233.02 |
| > 800 | Custom estimate (review) |
| Missing | Review required |

Tier 1 is billed at **$2,500.00** per flight. That is the authoritative charge even though the underlying cost-component line items still sum to $2,442.94.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_TOKEN` | Yes | Notion integration token (Secret Manager in Cloud Run) |
| `NOTION_DATABASE_ID` | No | Default: Drone Flight Schedule ID |
| `NOTION_VERSION` | No | Default: `2022-06-28` |
| `BILLING_MONTH` | No | Override `YYYY-MM` (default: previous month, LA) |
| `OUTPUT_DIR` | No | Local output when GCS unset (default: `./output`) |
| `GCS_BUCKET` | No | If set, upload report (example: `trimble-data-bucket-rk`) |
| `GCS_PREFIX` | No | Default: `notion-drone-billing-report/` |
| `REPORT_EMAIL_TO` | No | Default production recipient: `rkolt@sukut.com` |
| `REPORT_EMAIL_CC` | No | Default CC: `meklund@sukut.com`. Set empty to omit CC. |
| `REPORT_EMAIL_ENABLED` | No | Default `true`. Set `false` to skip sending. |
| `GMAIL_EMAIL` | Yes if email enabled | SMTP username (Secret Manager). Alias: `SMTP_USER` |
| `GMAIL_APP_PASSWORD` | Yes if email enabled | SMTP password (Secret Manager). Alias: `SMTP_PASS` |
| `EMAIL_FROM` | No | Defaults to `GMAIL_EMAIL` |
| `GMAIL_SMTP_SERVER` / `SMTP_HOST` | No | Default `smtp.gmail.com` |
| `GMAIL_SMTP_PORT` / `SMTP_PORT` | No | Default `587` STARTTLS |

SMTP credentials are **never** hard-coded. Do not commit app passwords.

## Email delivery

After a successful, validated report (and GCS upload when enabled), the job emails:

- **To:** `rkolt@sukut.com` (override with `REPORT_EMAIL_TO`)
- **Cc:** `meklund@sukut.com` (override with `REPORT_EMAIL_CC`; set empty to omit)
- **Subject:** `Drone Billing Report - {Month} {Year}` (e.g. `Drone Billing Report - September 2026`)
- **Attachment:** `Drone_Billing_Report_YYYY-MM.xlsx`
- **Body:** billing period plus “Status = In Process or Completed”, signed `SUKUT GPS Automation Team`

Failure during Notion query, month filtering, Excel generation, validation, or GCS upload (when GCS is enabled) skips the normal billing email and exits non-zero.

**Secrets:** Never commit `NOTION_TOKEN` or Gmail app passwords. In GCP the expected Secret Manager secrets are:

- **Name:** `Notion_Google_Cloud_Sync` → Cloud Run `NOTION_TOKEN`
- **Name:** `GMAIL_EMAIL` → Cloud Run `GMAIL_EMAIL` (if the secret exists)
- **Name:** `GMAIL_APP_PASSWORD` → Cloud Run `GMAIL_APP_PASSWORD` (if the secret exists)

```
--set-secrets=NOTION_TOKEN=Notion_Google_Cloud_Sync:latest,GMAIL_EMAIL=GMAIL_EMAIL:latest,GMAIL_APP_PASSWORD=GMAIL_APP_PASSWORD:latest
--set-env-vars=GCS_BUCKET=trimble-data-bucket-rk,GCS_PREFIX=notion-drone-billing-report/,REPORT_EMAIL_TO=rkolt@sukut.com,REPORT_EMAIL_CC=meklund@sukut.com
```

## Local testing

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
cp .env.example .env   # add NOTION_TOKEN; for a live send, add Gmail secrets
./scripts/run_local.sh
```

Without `GCS_BUCKET`, reports are written to `./output/Drone_Billing_Report_YYYY-MM.xlsx`.

Set `REPORT_EMAIL_ENABLED=false` for a local run that should not send mail.

## Cloud Run Job deployment

```bash
chmod +x scripts/deploy_cloud_run_job.sh
./scripts/deploy_cloud_run_job.sh
```

The deploy script maps `NOTION_TOKEN` from `Notion_Google_Cloud_Sync` and, when present, maps `GMAIL_EMAIL` / `GMAIL_APP_PASSWORD` from Secret Manager. It does not hard-code SMTP passwords. Scheduler is created or updated to cron `0 2 2 * *` in `America/Los_Angeles` and is **not** fired by the script.

Equivalent manual steps:

```bash
export PROJECT_ID=work-projects-486912
export REGION=us-west1
export JOB_NAME=notion-drone-billing-report

gcloud run jobs deploy "${JOB_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --set-secrets="NOTION_TOKEN=Notion_Google_Cloud_Sync:latest,GMAIL_EMAIL=GMAIL_EMAIL:latest,GMAIL_APP_PASSWORD=GMAIL_APP_PASSWORD:latest" \
  --set-env-vars="GCS_BUCKET=trimble-data-bucket-rk,GCS_PREFIX=notion-drone-billing-report/,REPORT_EMAIL_TO=rkolt@sukut.com,REPORT_EMAIL_CC=meklund@sukut.com" \
  --max-retries=1 \
  --task-timeout=30m
```

The scheduler uses cron `0 2 2 * *` in `America/Los_Angeles` and triggers:

`https://run.googleapis.com/v2/projects/work-projects-486912/locations/us-west1/jobs/notion-drone-billing-report:run`

OAuth service account: `564809734796-compute@developer.gserviceaccount.com`

### Manual execution

Do **not** run the production scheduler to test. Execute the Cloud Run Job directly, with a billing-month override when needed:

```bash
gcloud run jobs execute notion-drone-billing-report \
  --region us-west1 \
  --project work-projects-486912 \
  --update-env-vars BILLING_MONTH=2026-09 \
  --wait
```

On a date in September, the default previous-month window would be August; pass `BILLING_MONTH=2026-09` for a September report.

## GCS output

When `GCS_BUCKET` is set (example: `trimble-data-bucket-rk`), the job uploads:

`gs://<bucket>/notion-drone-billing-report/Drone_Billing_Report_YYYY-MM.xlsx`

Buckets are not made public.

## Logging

On startup the job logs `SUKUT GPS Automation Team`, then JSON structured logs including version, billing month, completed vs In Process counts, billable vs review, month total, output path, GCS status, and email delivery status.

## Troubleshooting

| Issue | Check |
|-------|--------|
| Schema validation error | Property **names** in Notion must match exactly (including `Acres` rollup). |
| Empty report | Confirm `BILLING_MONTH` and flights’ **Flight Date** in that month. |
| Valid In Process not on Billing Report | In Process with acres, date, and project **is billed**. Review Required is only for rows that cannot be billed reliably. |
| Missing acreage | Rollup must return a number via REST API; fix Project relation / project acreage. |
| 401 from Notion | `NOTION_TOKEN` / `Notion_Google_Cloud_Sync` secret and integration access to the database. |
| GCS upload failed | Job service account needs `storage.objects.create` on the bucket. Email is not sent. |
| Email not sent | Confirm `REPORT_EMAIL_ENABLED`, `GMAIL_EMAIL` / `GMAIL_APP_PASSWORD` secrets, and that generation + validation + GCS succeeded. |
| SMTP credentials missing | Set Secret Manager `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD`; never hard-code them. |

## License

Internal use — Lower River / RK workflows.
