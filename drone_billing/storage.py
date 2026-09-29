"""Local and GCS output storage."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UploadResult:
    local_path: Path
    gcs_uri: str | None
    gcs_status: str


def output_dir() -> Path:
    return Path(os.environ.get("OUTPUT_DIR", "output"))


def gcs_prefix() -> str:
    p = os.environ.get("GCS_PREFIX", "notion-drone-billing-report/")
    return p if p.endswith("/") else f"{p}/"


def upload_report(local_path: Path, filename: str) -> UploadResult:
    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        return UploadResult(
            local_path=local_path,
            gcs_uri=None,
            gcs_status="skipped (GCS_BUCKET not set)",
        )

    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_path = f"{gcs_prefix()}{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(local_path))
    return UploadResult(
        local_path=local_path,
        gcs_uri=f"gs://{bucket_name}/{blob_path}",
        gcs_status="uploaded",
    )
