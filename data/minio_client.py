"""
MinIO client — S3-compatible object storage for participant documents.

Local dev:
  docker run -p 9000:9000 -p 9001:9001 \\
    minio/minio server /data --console-address ":9001"

Env vars (see .env.example):
  MINIO_ENDPOINT    — host:port, default localhost:9000
  MINIO_ACCESS_KEY  — default minioadmin
  MINIO_SECRET_KEY  — default minioadmin
  MINIO_BUCKET      — default aldergate-docs
  MINIO_SECURE      — "true" for HTTPS, default false

If MinIO is not reachable, all functions raise — callers should catch and
fall back to text-only storage (object_key stays empty in document_store).
"""

import io
import os
import uuid
from datetime import timedelta
from pathlib import Path

# Lazy import so the package is optional at import time
_minio = None


def _get_minio():
    global _minio
    if _minio is None:
        from minio import Minio  # noqa: PLC0415
        _minio = Minio
    return _minio


MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT",  "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET",    "aldergate-docs")
MINIO_SECURE    = os.getenv("MINIO_SECURE",    "false").lower() == "true"


def _client():
    Minio = _get_minio()
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def _ensure_bucket(client) -> None:
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def upload_document(
    participant_id: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload raw file bytes to MinIO.

    Returns the object key (e.g. "documents/PART-008/a3b2c1d4.pdf").
    Raises on any connection / auth failure — caller should catch and fall back.
    """
    ext = Path(filename).suffix.lower() or ".bin"
    object_key = f"documents/{participant_id}/{uuid.uuid4().hex[:8]}{ext}"

    client = _client()
    _ensure_bucket(client)
    client.put_object(
        MINIO_BUCKET,
        object_key,
        io.BytesIO(content),
        length=len(content),
        content_type=content_type,
    )
    return object_key


def get_presigned_url(object_key: str, expires_days: int = 7) -> str:
    """
    Return a pre-signed GET URL for the given object key.
    Valid for `expires_days` (default 7).
    Raises if MinIO is not reachable.
    """
    client = _client()
    return client.presigned_get_object(
        MINIO_BUCKET,
        object_key,
        expires=timedelta(days=expires_days),
    )


def is_available() -> bool:
    """Return True if MinIO responds — used for health checks and graceful fallback."""
    try:
        _client().list_buckets()
        return True
    except Exception:
        return False
