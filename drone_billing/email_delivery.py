"""Email delivery stub — not enabled in v0.01.00."""

from __future__ import annotations

from pathlib import Path


def send_report_email(report_path: Path, billing_month: str) -> None:
    """Placeholder for future email delivery. No-op in v0.01.00."""
    _ = (report_path, billing_month)
