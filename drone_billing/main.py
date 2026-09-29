"""Notion Drone Billing Report job entrypoint."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal

from drone_billing import VERSION
from drone_billing.billing import process_flights, resolve_billing_month
from drone_billing.email_delivery import email_enabled, send_report_email
from drone_billing.logging_utils import configure_logging, log_structured, print_banner
from drone_billing.notion_client import NotionClient
from drone_billing.report import build_workbook, report_filename, save_workbook, validate_workbook
from drone_billing.storage import output_dir, upload_report


def run(now: datetime | None = None) -> int:
    logger = configure_logging()
    print_banner(logger)

    generation_complete = False
    try:
        token = os.environ.get("NOTION_TOKEN")
        if not token:
            raise RuntimeError("NOTION_TOKEN environment variable is required")

        billing_month, start, end = resolve_billing_month(
            now=now,
            override=os.environ.get("BILLING_MONTH"),
        )

        client = NotionClient(token=token)
        try:
            client.validate_schema()
            flights = client.query_flights()
        finally:
            client.close()

        processed = process_flights(flights, start, end)
        wb = build_workbook(billing_month, processed.billable, processed.review)

        filename = report_filename(billing_month)
        out_path = output_dir() / filename
        save_workbook(wb, out_path)
        validate_workbook(out_path)

        upload = upload_report(out_path, filename)
        gcs_enabled = bool(os.environ.get("GCS_BUCKET", "").strip())
        if gcs_enabled and upload.gcs_status != "uploaded":
            raise RuntimeError(f"GCS upload did not succeed: {upload.gcs_status}")

        generation_complete = True
        month_total = sum(
            (b.cost.total for b in processed.billable if b.cost.total is not None),
            start=Decimal("0"),
        )
        email_status = "not attempted"
        if email_enabled():
            email_status = send_report_email(out_path, billing_month, start, end)
        else:
            email_status = "skipped (REPORT_EMAIL_ENABLED=false)"

        log_structured(
            logger,
            {
                "message": "Notion Drone Billing Report",
                "version": VERSION,
                "billing_month": billing_month,
                "flights_found": processed.flights_found,
                "completed_flights": processed.completed_in_month,
                "in_process_flights": processed.in_process_in_month,
                "billable_flights": len(processed.billable),
                "review_required": len(processed.review),
                "month_total": str(month_total),
                "output_file": str(out_path),
                "gcs_upload_status": upload.gcs_status,
                "gcs_uri": upload.gcs_uri,
                "email_status": email_status,
            },
        )
        return 0
    except Exception as exc:
        if generation_complete:
            logger.error("Email delivery failed after successful report generation: %s", exc)
        else:
            logger.error("Report generation failed; email was not sent: %s", exc)
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
