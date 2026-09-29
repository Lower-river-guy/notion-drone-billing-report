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
    logger.info(json.dumps(fields, default=str))
