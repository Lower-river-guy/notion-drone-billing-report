# Notion Drone Billing Report

**Version 0.01.00** — Python 3.12 Cloud Run **Job** that reads completed drone flights from Notion, applies tiered internal billing costs from project acreage rollups, and writes a monthly Excel report to local disk or Google Cloud Storage.

## Purpose

Automate monthly internal drone billing by:

1. Querying the Notion **Drone Flight Schedule** database via the official REST API (rollup **Acres** requires REST, not Notion SQL).
2. Billing only **Completed** flights in the target calendar month (default: previous month in `America/Los_Angeles`).
3. Grouping results by project in an Excel workbook with summary, detail, and review sheets.
4. Uploading to GCS when configured.

Email delivery is stubbed for a future release; report generation does not depend on email.

## Architecture

```
Cloud Scheduler (monthly)
        │
        ▼
Cloud Run Job (notion-drone-billing-report)
        │
        ├── Notion REST API ──► Drone Flight Schedule DB
        │
        └── Excel report ──► GCS (or ./output locally)
```

- **GCP project:** `work-projects-486912`
- **Region:** `us-west1`
- **Job name:** `notion-drone-billing-report`
- **Scheduler:** `notion-drone-billing-report-monthly` — cron `0 2 2 * *`, timezone `America/Los_Angeles` (2:00 AM on the 2nd; bills the **previous** calendar month)

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
| Status | select | Only `Completed` is billable |

At startup the job retrieves the live database schema and **fails** if any required property name is missing.

### Review required (not billed)

- Status ≠ Completed
- Title starts with `TEMPLATE` (case-insensitive)
- Title contains `PLACEHOLDER`
- Missing Acres, Project, or Flight Date
- Acres > 800 → custom estimate
- Multiple Project relations

## Cost tiers

All amounts live in `drone_billing/cost_config.py` (totals and line-item breakdown).

| Acres | Total |
|-------|-------|
| 0–200 | $2,442.94 |
| 201–300 | $2,930.68 |
| 301–500 | $3,805.99 |
| 501–800 | $6,233.02 |
| > 800 | Custom estimate (review) |
| Missing | Review required |

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

**Secrets:** Never commit `NOTION_TOKEN`. In GCP the existing Secret Manager secret is:

- **Name:** `Notion_Google_Cloud_Sync`
- **Cloud Run:** `--set-secrets=NOTION_TOKEN=Notion_Google_Cloud_Sync:latest`

## Local testing

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
cp .env.example .env   # add NOTION_TOKEN for live runs
./scripts/run_local.sh
```

Without `GCS_BUCKET`, reports are written to `./output/Drone_Billing_Report_YYYY-MM.xlsx`.

## Cloud Run Job deployment

```bash
chmod +x scripts/deploy_cloud_run_job.sh
./scripts/deploy_cloud_run_job.sh
```

Equivalent manual steps:

```bash
export PROJECT_ID=work-projects-486912
export REGION=us-west1
export JOB_NAME=notion-drone-billing-report
export IMAGE=gcr.io/${PROJECT_ID}/${JOB_NAME}:0.01.00

gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

gcloud run jobs deploy "${JOB_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --set-secrets="NOTION_TOKEN=Notion_Google_Cloud_Sync:latest" \
  --set-env-vars="GCS_BUCKET=trimble-data-bucket-rk,GCS_PREFIX=notion-drone-billing-report/" \
  --max-retries=1 \
  --task-timeout=30m
```

### Manual execution

```bash
gcloud run jobs execute notion-drone-billing-report \
  --region us-west1 \
  --project work-projects-486912
```

Optional billing month override for a single run (if your job template allows env overrides):

```bash
gcloud run jobs execute notion-drone-billing-report \
  --region us-west1 \
  --project work-projects-486912 \
  --update-env-vars BILLING_MONTH=2026-09
```

## GCS output

When `GCS_BUCKET` is set (example: `trimble-data-bucket-rk`), the job uploads:

`gs://<bucket>/notion-drone-billing-report/Drone_Billing_Report_YYYY-MM.xlsx`

Buckets are not made public.

## Logging

On startup the job prints the RK fish banner, then JSON structured logs including version, billing month, flight counts, output path, and GCS status.

## Troubleshooting

| Issue | Check |
|-------|--------|
| Schema validation error | Property **names** in Notion must match exactly (including `Acres` rollup). |
| Empty report | Confirm `BILLING_MONTH` and flights’ **Flight Date** in that month. |
| Missing acreage | Rollup must return a number via REST API; fix Project relation / project acreage. |
| 401 from Notion | `NOTION_TOKEN` / `Notion_Google_Cloud_Sync` secret and integration access to the database. |
| GCS upload failed | Job service account needs `storage.objects.create` on the bucket. |

## License

Internal use — Lower River / RK workflows.
