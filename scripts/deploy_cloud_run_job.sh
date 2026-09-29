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
REPORT_EMAIL_TO="${REPORT_EMAIL_TO:-rkolt@sukut.com}"
# Project number from existing Cloud Run service tcc-work-order-builder-564809734796
PROJECT_NUMBER="${GCP_PROJECT_NUMBER:-564809734796}"
SCHEDULER_SA="${SCHEDULER_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
JOB_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"

secret_exists() {
  local name="$1"
  gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1
}

resolve_secret_flag() {
  local env_name="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if secret_exists "${candidate}"; then
      echo "${env_name}=${candidate}:latest"
      return 0
    fi
  done
  return 1
}

if ! secret_exists "${NOTION_SECRET}"; then
  echo "ERROR: Notion Secret Manager secret '${NOTION_SECRET}' was not found in ${PROJECT_ID}." >&2
  echo "Refusing to deploy with an unidentifiable Notion secret." >&2
  exit 1
fi

SECRET_FLAGS="NOTION_TOKEN=${NOTION_SECRET}:latest"

if GMAIL_EMAIL_FLAG="$(resolve_secret_flag GMAIL_EMAIL GMAIL_EMAIL gmail-email SMTP_USER)"; then
  SECRET_FLAGS="${SECRET_FLAGS},${GMAIL_EMAIL_FLAG}"
  echo "Using Secret Manager mapping ${GMAIL_EMAIL_FLAG}"
else
  echo "WARNING: No GMAIL_EMAIL (or alias) secret found. Job email will fail unless credentials are provided another way." >&2
fi

if GMAIL_PASS_FLAG="$(resolve_secret_flag GMAIL_APP_PASSWORD GMAIL_APP_PASSWORD gmail-app-password SMTP_PASS SMTP_PASSWORD)"; then
  SECRET_FLAGS="${SECRET_FLAGS},${GMAIL_PASS_FLAG}"
  echo "Using Secret Manager mapping ${GMAIL_PASS_FLAG}"
else
  echo "WARNING: No GMAIL_APP_PASSWORD (or alias) secret found. Job email will fail unless credentials are provided another way." >&2
fi

ENV_VARS="GCS_BUCKET=${GCS_BUCKET},GCS_PREFIX=${GCS_PREFIX},REPORT_EMAIL_TO=${REPORT_EMAIL_TO}"

echo "Deploying Cloud Run Job ${JOB_NAME} from source..."
gcloud run jobs deploy "${JOB_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --set-secrets="${SECRET_FLAGS}" \
  --set-env-vars="${ENV_VARS}" \
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
# Do not pass --attempt-deadline / --force-run; this must not fire production.
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

echo "Verifying scheduler cron and timezone (no run triggered)..."
gcloud scheduler jobs describe "${SCHEDULER_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="yaml(name,schedule,timeZone,httpTarget.uri,httpTarget.httpMethod,state)"

echo "Done. Manual run (does not fire the scheduler):"
echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION} --project ${PROJECT_ID} --update-env-vars BILLING_MONTH=2026-09 --wait"
