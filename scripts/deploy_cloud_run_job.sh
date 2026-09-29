#!/usr/bin/env bash
# Deploy Notion Drone Billing Report as a Cloud Run Job + monthly scheduler.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-work-projects-486912}"
REGION="${GCP_REGION:-us-west1}"
JOB_NAME="${JOB_NAME:-notion-drone-billing-report}"
SCHEDULER_NAME="${SCHEDULER_NAME:-notion-drone-billing-report-monthly}"
IMAGE="${IMAGE:-gcr.io/${PROJECT_ID}/${JOB_NAME}:0.01.00}"
GCS_BUCKET="${GCS_BUCKET:-trimble-data-bucket-rk}"
GCS_PREFIX="${GCS_PREFIX:-notion-drone-billing-report/}"
NOTION_SECRET="${NOTION_SECRET:-Notion_Google_Cloud_Sync}"

echo "Building image ${IMAGE}..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

echo "Deploying Cloud Run Job ${JOB_NAME}..."
gcloud run jobs deploy "${JOB_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --set-secrets="NOTION_TOKEN=${NOTION_SECRET}:latest" \
  --set-env-vars="GCS_BUCKET=${GCS_BUCKET},GCS_PREFIX=${GCS_PREFIX}" \
  --max-retries=1 \
  --task-timeout=30m

echo "Creating/updating Cloud Scheduler ${SCHEDULER_NAME}..."
# Runs at 02:00 on the 2nd of each month in America/Los_Angeles (previous calendar month billing).
if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="0 2 2 * *" \
    --time-zone="America/Los_Angeles" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
else
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="0 2 2 * *" \
    --time-zone="America/Los_Angeles" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
fi

echo "Done. Manual run:"
echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION} --project ${PROJECT_ID}"
