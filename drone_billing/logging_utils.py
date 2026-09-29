"""Logging helpers and startup banner."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

BANNER = r"><(((º>            ><(((º>          RK               ><(((º>"


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("drone_billing")


def print_banner(logger: logging.Logger) -> None:
    logger.info(BANNER)


def log_structured(logger: logging.Logger, fields: dict[str, Any]) -> None:
    logger.info("Notion Drone Billing Report")
    logger.info("Version: %s", fields.get("version", ""))
    logger.info("Billing Month: %s", fields.get("billing_month", ""))
    logger.info("Flights Found: %s", fields.get("flights_found", ""))
    logger.info("Completed Flights: %s", fields.get("completed_flights", ""))
    logger.info("In Process Flights: %s", fields.get("in_process_flights", ""))
    logger.info("Billable Flights: %s", fields.get("billable_flights", ""))
    logger.info("Review Required: %s", fields.get("review_required", ""))
    logger.info("Month Total: %s", fields.get("month_total", ""))
    logger.info("Output File: %s", fields.get("output_file", ""))
    logger.info("GCS Upload Status: %s", fields.get("gcs_upload_status", ""))
    if fields.get("gcs_uri"):
        logger.info("GCS URI: %s", fields["gcs_uri"])
    logger.info("Email Status: %s", fields.get("email_status", ""))
    logger.info(json.dumps(fields, default=str))
