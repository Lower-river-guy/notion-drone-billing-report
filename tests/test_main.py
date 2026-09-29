from drone_billing.main import run


def test_run_does_not_email_when_generation_fails(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "test-token")
    monkeypatch.setenv("REPORT_EMAIL_ENABLED", "true")
    sent = []

    class BoomClient:
        def validate_schema(self):
            raise RuntimeError("schema mismatch")

        def query_flights(self):
            return []

        def close(self):
            return None

    monkeypatch.setattr("drone_billing.main.NotionClient", lambda token: BoomClient())
    monkeypatch.setattr(
        "drone_billing.main.send_report_email",
        lambda *args, **kwargs: sent.append((args, kwargs)) or "sent",
    )

    assert run() == 1
    assert sent == []


def test_run_does_not_email_when_gcs_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTION_TOKEN", "test-token")
    monkeypatch.setenv("GCS_BUCKET", "trimble-data-bucket-rk")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("BILLING_MONTH", "2026-09")
    monkeypatch.setenv("REPORT_EMAIL_ENABLED", "true")
    sent = []

    class EmptyClient:
        def validate_schema(self):
            return None

        def query_flights(self):
            return []

        def close(self):
            return None

    class FailedUpload:
        gcs_status = "failed"
        gcs_uri = None

    monkeypatch.setattr("drone_billing.main.NotionClient", lambda token: EmptyClient())
    monkeypatch.setattr(
        "drone_billing.main.upload_report",
        lambda path, filename: FailedUpload(),
    )
    monkeypatch.setattr(
        "drone_billing.main.send_report_email",
        lambda *args, **kwargs: sent.append(True) or "sent",
    )

    assert run() == 1
    assert sent == []
