#!/usr/bin/env bash
# Deploy Notion Drone Billing Report as a Cloud Run Job + monthly scheduler.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-work-projects-486912}"
REGION="${GCP_REGION:-us-west1}"
JOB_NAME="${JOB_NAME:-notion-drone-billing-report}"
SCHEDULER_NAME="${SCHEDULER_NAME:-notion-drone-billing-report-monthly}"
GCS_BUCKET="${GCS_BUCKET:-trimble-data-bucket-rk}"
GCS_PREFIX="${GCS_PREFIX:-notion-drone-billing-report/}"
NOTION_SECRET="${NOTION_SECRET:-Notion_Google_Cloud_Sync}"
# Project number from existing Cloud Run service tcc-work-order-builder-564809734796
PROJECT_NUMBER="${GCP_PROJECT_NUMBER:-564809734796}"
SCHEDULER_SA="${SCHEDULER_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
JOB_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"

echo "Deploying Cloud Run Job ${JOB_NAME} from source..."
gcloud run jobs deploy "${JOB_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --set-secrets="NOTION_TOKEN=${NOTION_SECRET}:latest" \
  --set-env-vars="GCS_BUCKET=${GCS_BUCKET},GCS_PREFIX=${GCS_PREFIX}" \
  --max-retries=1 \
  --task-timeout=30m \
  --memory=512Mi \
  --cpu=1 \
  --tasks=1

echo "Granting Cloud Scheduler invoker on job..."
gcloud run jobs add-iam-policy-binding "${JOB_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker" \
  --quiet || true

echo "Creating/updating Cloud Scheduler ${SCHEDULER_NAME}..."
# 02:00 on the 2nd of each month, America/Los_Angeles (bills previous calendar month).
if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="0 2 2 * *" \
    --time-zone="America/Los_Angeles" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA}"
else
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="0 2 2 * *" \
    --time-zone="America/Los_Angeles" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA}"
fi

echo "Done. Manual run:"
echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION} --project ${PROJECT_ID}"
