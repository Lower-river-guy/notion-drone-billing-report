"""Notion Drone Billing Report job entrypoint."""

from __future__ import annotations

import os
import sys
from datetime import datetime

from drone_billing import VERSION
from drone_billing.billing import build_monthly_summary, process_flights, resolve_billing_month
from drone_billing.logging_utils import configure_logging, log_structured, print_banner
from drone_billing.notion_client import NotionClient
from drone_billing.report import build_workbook, report_filename, save_workbook
from drone_billing.storage import output_dir, upload_report


def run(now: datetime | None = None) -> int:
    logger = configure_logging()
    print_banner(logger)

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        logger.error("NOTION_TOKEN environment variable is required")
        return 1

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

    billable, review, completed_in_month, flights_in_month = process_flights(
        flights, start, end
    )

    summary = build_monthly_summary(billing_month, billable, review)
    wb = build_workbook(billing_month, summary, billable, review)

    filename = report_filename(billing_month)
    out_path = output_dir() / filename
    save_workbook(wb, out_path)
    upload = upload_report(out_path, filename)

    log_structured(
        logger,
        {
            "message": "Notion Drone Billing Report",
            "version": VERSION,
            "billing_month": billing_month,
            "flights_found": flights_in_month,
            "completed_flights": completed_in_month,
            "billable_flights": len(billable),
            "review_required": len(review),
            "output_file": str(out_path),
            "gcs_upload_status": upload.gcs_status,
            "gcs_uri": upload.gcs_uri,
        },
    )
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
