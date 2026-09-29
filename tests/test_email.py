from datetime import date
from pathlib import Path

from drone_billing.email_delivery import (
    build_body,
    build_subject,
    email_enabled,
    load_email_config,
    send_report_email,
)
from drone_billing.report import validate_workbook
from tests.test_report import test_workbook_generation


def test_subject_and_body():
    assert build_subject("2026-09") == "Drone Billing Report - September 2026"
    body = build_body("2026-09", date(2026, 9, 1), date(2026, 9, 30))
    assert "Please see attached Drone Billing Report for September 2026." in body
    assert "September 1, 2026 through September 30, 2026" in body
    assert "Status = In Process or Completed" in body
    assert "SUKUT GPS Automation Team" in body
    assert "Sukut Drone Automation" not in body
    assert "><(((º>   ><(((º>   RK   ><(((º>" in body
    assert "><(((º>            ><(((º>          RK               ><(((º>" not in body
    assert body.endswith(
        "SUKUT GPS Automation Team\n"
        "><(((º>   ><(((º>   RK   ><(((º>\n"
    )


def test_email_disabled(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("REPORT_EMAIL_ENABLED", "false")
    assert email_enabled() is False
    called = []
    report = tmp_path / "Drone_Billing_Report_2026-09.xlsx"
    report.write_bytes(b"fake-xlsx")
    status = send_report_email(
        report,
        "2026-09",
        date(2026, 9, 1),
        date(2026, 9, 30),
        smtp_send=lambda *args: called.append(args),
    )
    assert status == "skipped (REPORT_EMAIL_ENABLED=false)"
    assert called == []


def test_send_report_email_uses_attachment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REPORT_EMAIL_ENABLED", "true")
    monkeypatch.setenv("REPORT_EMAIL_TO", "rkolt@sukut.com")
    monkeypatch.setenv("GMAIL_EMAIL", "sukut.rtk.bases@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    report = tmp_path / "Drone_Billing_Report_2026-09.xlsx"
    report.write_bytes(b"fake-xlsx")
    captured = {}

    def fake_send(config, message):
        captured["to"] = config.to_address
        captured["from"] = config.from_address
        captured["subject"] = message["Subject"]
        captured["body"] = message.get_body(preferencelist=("plain",)).get_content()
        captured["filename"] = message.get_payload()[1].get_filename()

    status = send_report_email(
        report,
        "2026-09",
        date(2026, 9, 1),
        date(2026, 9, 30),
        smtp_send=fake_send,
    )
    assert status == "sent to rkolt@sukut.com"
    assert captured["to"] == "rkolt@sukut.com"
    assert captured["subject"] == "Drone Billing Report - September 2026"
    assert captured["filename"] == "Drone_Billing_Report_2026-09.xlsx"
    assert captured["body"].endswith(
        "SUKUT GPS Automation Team\n"
        "><(((º>   ><(((º>   RK   ><(((º>\n"
    )


def test_load_email_config_smtp_aliases(monkeypatch):
    monkeypatch.delenv("GMAIL_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("REPORT_EMAIL_TO", "rkolt@sukut.com")
    monkeypatch.setenv("SMTP_USER", "sukut.rtk.bases@gmail.com")
    monkeypatch.setenv("SMTP_PASS", "app-password")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    config = load_email_config()
    assert config.to_address == "rkolt@sukut.com"
    assert config.smtp_user == "sukut.rtk.bases@gmail.com"
    assert config.smtp_host == "smtp.gmail.com"
    assert config.smtp_port == 587


def test_load_email_config_requires_secrets(monkeypatch):
    monkeypatch.delenv("GMAIL_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    try:
        load_email_config()
        raise AssertionError("expected missing SMTP credentials")
    except RuntimeError as exc:
        assert "SMTP credentials are missing" in str(exc)


def test_validate_workbook(tmp_path: Path):
    test_workbook_generation(tmp_path)
    validate_workbook(tmp_path / "Drone_Billing_Report_2026-09.xlsx")
