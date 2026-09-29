"""SMTP email delivery for the monthly drone billing workbook."""

from __future__ import annotations

import os
import smtplib
from calendar import month_name
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

DEFAULT_RECIPIENT = "rkolt@sukut.com"
DEFAULT_CC = "meklund@sukut.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587


@dataclass(frozen=True)
class EmailConfig:
    to_address: str
    cc_address: str
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str


def email_enabled() -> bool:
    raw = os.environ.get("REPORT_EMAIL_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def load_email_config() -> EmailConfig:
    to_address = (os.environ.get("REPORT_EMAIL_TO") or DEFAULT_RECIPIENT).strip()
    cc_address = (os.environ.get("REPORT_EMAIL_CC", DEFAULT_CC) or "").strip()
    smtp_user = (
        os.environ.get("GMAIL_EMAIL")
        or os.environ.get("SMTP_USER")
        or os.environ.get("EMAIL_FROM")
        or ""
    ).strip()
    smtp_password = (
        os.environ.get("GMAIL_APP_PASSWORD")
        or os.environ.get("SMTP_PASS")
        or os.environ.get("SMTP_PASSWORD")
        or ""
    ).strip()
    from_address = (os.environ.get("EMAIL_FROM") or smtp_user).strip()
    smtp_host = (
        os.environ.get("GMAIL_SMTP_SERVER")
        or os.environ.get("SMTP_HOST")
        or DEFAULT_SMTP_HOST
    ).strip()
    port_raw = os.environ.get("GMAIL_SMTP_PORT") or os.environ.get("SMTP_PORT") or str(DEFAULT_SMTP_PORT)
    try:
        smtp_port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid SMTP port: {port_raw!r}") from exc
    if not to_address:
        raise RuntimeError("REPORT_EMAIL_TO is empty")
    if not smtp_user or not smtp_password or not from_address:
        raise RuntimeError(
            "SMTP credentials are missing. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD "
            "(or SMTP_USER / SMTP_PASS) from Secret Manager."
        )
    return EmailConfig(
        to_address=to_address,
        cc_address=cc_address,
        from_address=from_address,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )


def month_year_label(billing_month: str) -> str:
    year_s, month_s = billing_month.split("-", 1)
    return f"{month_name[int(month_s)]} {year_s}"


def billing_period_text(start: date, end: date) -> str:
    return (
        f"{month_name[start.month]} {start.day}, {start.year} through "
        f"{month_name[end.month]} {end.day}, {end.year}"
    )


def build_subject(billing_month: str) -> str:
    return f"Drone Billing Report - {month_year_label(billing_month)}"


def build_body(billing_month: str, start: date, end: date) -> str:
    label = month_year_label(billing_month)
    return (
        f"Please see attached Drone Billing Report for {label}.\n"
        f"\n"
        f"Billing Period:\n"
        f"{billing_period_text(start, end)}\n"
        f"\n"
        f"The report includes drone flights with:\n"
        f"- Status = In Process or Completed\n"
        f"- Flight Date within the billing period\n"
        f"\n"
        f"SUKUT GPS Automation Team\n"
    )


def send_report_email(
    report_path: Path,
    billing_month: str,
    start: date,
    end: date,
    *,
    smtp_send=None,
) -> str:
    """Email the workbook. smtp_send is injectable for tests."""
    if not email_enabled():
        return "skipped (REPORT_EMAIL_ENABLED=false)"

    config = load_email_config()
    message = EmailMessage()
    message["To"] = config.to_address
    if config.cc_address:
        message["Cc"] = config.cc_address
    message["From"] = config.from_address
    message["Subject"] = build_subject(billing_month)
    message.set_content(build_body(billing_month, start, end))

    filename = report_path.name
    message.add_attachment(
        report_path.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

    sender = smtp_send or _smtp_send
    sender(config, message)
    if config.cc_address:
        return f"sent to {config.to_address} (cc: {config.cc_address})"
    return f"sent to {config.to_address}"


def _smtp_send(config: EmailConfig, message: EmailMessage) -> None:
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=60) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)
