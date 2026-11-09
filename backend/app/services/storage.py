"""S3-compatible object storage with local-filesystem fallback.

In production (Docker):    MinIO at minio:9000
In development (no Docker): local ./storage/ directory
"""

from __future__ import annotations

import io
import logging
from urllib.parse import quote
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None  # Minio client or None
_fallback = False  # True if we fell back to local storage
_local_root: Path | None = None


def _public_download_url(object_name: str, filename: str | None = None) -> str:
    """Return a browser-safe download URL via the backend API."""
    url = f"/api/files/{object_name}/download"
    if filename:
        return f"{url}?filename={quote(filename)}"
    return url


def _get_minio_client():
    """Try to connect to an S3-compatible object store. Returns client or raises on failure."""
    global _client, _fallback
    if _client is not None:
        return _client

    try:
        from minio import Minio
        import urllib3

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION or None,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=3, read=10), retries=False,
            ),
        )
        # Bucket-scoped credentials need no account-wide ListAllMyBuckets grant.
        client.bucket_exists(settings.MINIO_BUCKET)
        logger.info("Connected to object storage endpoint %s", settings.MINIO_ENDPOINT)
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


def _mark_minio_runtime_unavailable(operation: str, error: Exception) -> None:
    global _client, _fallback
    _client = None
    _fallback = True
    logger.warning("MinIO %s failed (%s), using local filesystem fallback", operation, error)


def _is_missing_object_error(error: Exception) -> bool:
    return getattr(error, "code", None) == "NoSuchKey"


def _local_path_for(object_name: str) -> Path:
    return _get_local_root() / object_name


def _save_local_file(object_name: str, data: bytes) -> None:
    local_path = _local_path_for(object_name)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    logger.info("Local file saved: %s (%d bytes)", local_path, len(data))


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
        try:
            _ensure_bucket(client, settings.MINIO_BUCKET)
            client.put_object(
                settings.MINIO_BUCKET,
                object_name,
                io.BytesIO(data),
                length=size,
                content_type=content_type,
            )
            return {
                "object_name": object_name,
                "bucket": settings.MINIO_BUCKET,
                "size": size,
                "download_url": _public_download_url(object_name),
                "storage": "minio",
            }
        except Exception as e:
            _mark_minio_runtime_unavailable("upload", e)

    # Local filesystem fallback
    _save_local_file(object_name, data)

    return {
        "object_name": object_name,
        "bucket": "local",
        "size": size,
        "download_url": _public_download_url(object_name),
        "storage": "local",
    }


async def download_file(object_name: str) -> bytes:
    """Download file content."""
    # Always give the configured object store a chance. A single missing key
    # or transient operation error must not permanently poison this process
    # into reading unrelated objects from the local fallback directory.
    client = _get_minio_client()

    if client is not None:
        try:
            response = client.get_object(settings.MINIO_BUCKET, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            if _is_missing_object_error(e):
                logger.warning("Object not found in object storage: %s", object_name)
            else:
                _mark_minio_runtime_unavailable("download", e)

    # Local filesystem fallback
    local_path = _local_path_for(object_name)
    if not local_path.exists():
        raise RuntimeError(f"File not found: {object_name}")
    return local_path.read_bytes()


async def delete_file(object_name: str) -> bool:
    """Delete a file. Returns True if deleted."""
    client = _get_minio_client()
    deleted = False

    if client is not None:
        try:
            client.remove_object(settings.MINIO_BUCKET, object_name)
            deleted = True
        except Exception as e:
            if _is_missing_object_error(e):
                pass
            else:
                _mark_minio_runtime_unavailable("delete", e)

    # Local filesystem fallback
    local_path = _local_path_for(object_name)
    if local_path.exists():
        local_path.unlink()
        return True
    return deleted


async def get_presigned_url(object_name: str, expires_hours: int = 24) -> str:
    """Generate a browser-safe download URL."""
    return _public_download_url(object_name)

def is_minio_available() -> bool:
    """Check if MinIO is connected."""
    return _get_minio_client() is not None and not _fallback
