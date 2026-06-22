"""MinIO / S3-compatible object storage with local-filesystem fallback.

In production (Docker):    MinIO at minio:9000
In development (no Docker): local ./storage/ directory
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None  # Minio client or None
_fallback = False  # True if we fell back to local storage
_local_root: Path | None = None


def _get_minio_client():
    """Try to connect to MinIO. Returns client or raises on failure."""
    global _client, _fallback
    if _client is not None:
        return _client

    try:
        from minio import Minio
        from minio.error import S3Error

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        # Quick connectivity check
        client.list_buckets()
        logger.info("Connected to MinIO at %s", settings.MINIO_ENDPOINT)
        _client = client
        _fallback = False
        return client
    except Exception as e:
        logger.warning("MinIO unavailable (%s), using local filesystem fallback", e)
        _fallback = True
        return None


def _get_local_root() -> Path:
    global _local_root
    if _local_root is None:
        _local_root = Path(settings.STORAGE_LOCAL_PATH)
        _local_root.mkdir(parents=True, exist_ok=True)
    return _local_root


def _ensure_bucket(client, bucket: str) -> None:
    try:
        from minio.error import S3Error
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
    except Exception as e:
        logger.warning("MinIO bucket check failed: %s", e)


async def upload_file(
    data: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    folder: str = "uploads",
) -> dict:
    """Upload file content. Uses MinIO if available, otherwise local disk."""
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    object_name = f"{folder}/{uuid.uuid4().hex}.{ext}"
    size = len(data)

    client = _get_minio_client()

    if client is not None:
        from minio.error import S3Error
        try:
            _ensure_bucket(client, settings.MINIO_BUCKET)
            client.put_object(
                settings.MINIO_BUCKET,
                object_name,
                io.BytesIO(data),
                length=size,
                content_type=content_type,
            )
            presigned = client.presigned_get_object(
                settings.MINIO_BUCKET, object_name,
                expires=timedelta(hours=24),
            )
            return {
                "object_name": object_name,
                "bucket": settings.MINIO_BUCKET,
                "size": size,
                "download_url": presigned,
                "storage": "minio",
            }
        except S3Error as e:
            logger.exception("MinIO upload failed")
            raise RuntimeError(f"Storage upload failed: {e}") from e

    # Local filesystem fallback
    local_path = _get_local_root() / object_name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    logger.info("Local file saved: %s (%d bytes)", local_path, size)

    return {
        "object_name": object_name,
        "bucket": "local",
        "size": size,
        "download_url": f"/api/files/{object_name}/download",
        "storage": "local",
    }


async def download_file(object_name: str) -> bytes:
    """Download file content."""
    client = _get_minio_client() if not _fallback else None

    if client is not None:
        from minio.error import S3Error
        try:
            response = client.get_object(settings.MINIO_BUCKET, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise RuntimeError(f"Storage download failed: {e}") from e

    # Local filesystem fallback
    local_path = _get_local_root() / object_name
    if not local_path.exists():
        raise RuntimeError(f"File not found: {object_name}")
    return local_path.read_bytes()


async def delete_file(object_name: str) -> bool:
    """Delete a file. Returns True if deleted."""
    client = _get_minio_client() if not _fallback else None

    if client is not None:
        from minio.error import S3Error
        try:
            client.remove_object(settings.MINIO_BUCKET, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise RuntimeError(f"Storage delete failed: {e}") from e

    # Local filesystem fallback
    local_path = _get_local_root() / object_name
    if local_path.exists():
        local_path.unlink()
        return True
    return False


async def get_presigned_url(object_name: str, expires_hours: int = 24) -> str:
    """Generate a download URL."""
    client = _get_minio_client() if not _fallback else None

    if client is not None:
        return client.presigned_get_object(
            settings.MINIO_BUCKET, object_name,
            expires=timedelta(hours=expires_hours),
        )

    # Local filesystem: return API download endpoint
    return f"/api/files/{object_name}/download"

def is_minio_available() -> bool:
    """Check if MinIO is connected."""
    return not _fallback and _get_minio_client() is not None
