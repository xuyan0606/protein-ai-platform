#!/usr/bin/env python3
"""Run a guarded OSS offsite/shadow restore drill.

The script intentionally only writes to object keys that contain a ``drills/``
path segment. It never changes application storage configuration or production
prefixes.
"""

import argparse
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).absolute().parent.parent


class DrillStep:
    def __init__(self, name, status, detail):
        self.name = name
        self.status = status
        self.detail = detail

    def as_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


def _load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _first_env(*names, **kwargs):
    default = kwargs.get("default", "")
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def _truthy(value):
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_oss_uri(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "oss" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"expected oss://bucket/key-or-prefix, got {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def _safe_drill_key(key):
    normalized = key.strip("/")
    parts = [part for part in normalized.split("/") if part]
    return "drills" in parts and ".." not in parts


def _require_safe_uri(uri):
    bucket, key = _parse_oss_uri(uri)
    if not _safe_drill_key(key):
        raise ValueError(f"refusing non-drill object path: oss://{bucket}/{key}")
    return bucket, key


def _sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_object(client, bucket, key):
    h = hashlib.sha256()
    total = 0
    response = client.get_object(bucket, key)
    try:
        for chunk in response.stream(1024 * 1024):
            h.update(chunk)
            total += len(chunk)
    finally:
        response.close()
        response.release_conn()
    return h.hexdigest(), total


def _client():
    from minio import Minio

    endpoint = _first_env("MINIO_ENDPOINT", "ALIYUN_OSS_ENDPOINT")
    access_key = _first_env("MINIO_ACCESS_KEY", "ALIYUN_OSS_ACCESS_KEY_ID")
    secret_key = _first_env("MINIO_SECRET_KEY", "ALIYUN_OSS_ACCESS_KEY_SECRET")
    secure = _truthy(_first_env("MINIO_SECURE", "ALIYUN_OSS_SECURE", default="true"))
    region = _first_env("MINIO_REGION", "ALIYUN_OSS_REGION") or None
    if not endpoint or not access_key or not secret_key:
        missing = [
            label
            for label, value in {
                "MINIO_ENDPOINT/ALIYUN_OSS_ENDPOINT": endpoint,
                "MINIO_ACCESS_KEY/ALIYUN_OSS_ACCESS_KEY_ID": access_key,
                "MINIO_SECRET_KEY/ALIYUN_OSS_ACCESS_KEY_SECRET": secret_key,
            }.items()
            if not value
        ]
        raise RuntimeError(f"missing object storage config: {', '.join(missing)}")
    parsed = urlparse(endpoint)
    endpoint_host = parsed.netloc or parsed.path
    if parsed.scheme:
        secure = parsed.scheme == "https"
    return Minio(endpoint_host, access_key=access_key, secret_key=secret_key, secure=secure, region=region)


def _copy_object(client, source_bucket, source_key, target_bucket, target_key):
    from minio.commonconfig import CopySource

    client.copy_object(target_bucket, target_key, CopySource(source_bucket, source_key))


def run(args):
    for env_file in args.env_file:
        _load_env_file(Path(env_file).expanduser())

    steps = []
    backup_file = Path(args.backup_file).expanduser()
    if not backup_file.exists():
        raise FileNotFoundError(f"backup file not found: {backup_file}")

    offsite_bucket, offsite_key = _require_safe_uri(args.offsite_backup_target)
    backup_ref_bucket, backup_ref_key = _require_safe_uri(args.external_storage_backup_ref)
    restore_bucket, restore_prefix = _require_safe_uri(args.external_storage_restore_target)
    if not restore_prefix.endswith("/"):
        restore_prefix += "/"

    local_hash = _sha256_file(backup_file)
    backup_size = backup_file.stat().st_size
    marker_key = backup_ref_key.rstrip("/") + "/restore-drill-source-marker.json"
    restored_marker_key = restore_prefix + "restore-drill-source-marker.json"
    marker_payload = {
        "drill_id": args.maintenance_window_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "external-storage-shadow-restore-validation",
        "source": f"oss://{backup_ref_bucket}/{marker_key}",
        "restore_target": f"oss://{restore_bucket}/{restored_marker_key}",
    }
    marker_bytes = json.dumps(marker_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    marker_hash = hashlib.sha256(marker_bytes).hexdigest()

    if not args.execute:
        return {
            "summary": {"status": "planned", "network_io": "not_executed", "destructive_actions": "not_executed"},
            "maintenance_window_id": args.maintenance_window_id,
            "offsite_backup_target": f"oss://{offsite_bucket}/{offsite_key}",
            "external_storage_backup_ref": f"oss://{backup_ref_bucket}/{backup_ref_key}",
            "external_storage_restore_target": f"oss://{restore_bucket}/{restore_prefix}",
            "planned_objects": [
                {"key": offsite_key, "size": backup_size, "sha256": local_hash},
                {"key": offsite_key + ".sha256", "size": len(local_hash) + 3},
                {"key": marker_key, "size": len(marker_bytes), "sha256": marker_hash},
                {"key": restored_marker_key, "size": len(marker_bytes), "sha256": marker_hash},
            ],
        }

    client = _client()
    steps.append(DrillStep("storage_auth", "planned", "object-level write/read operations will validate access"))

    client.fput_object(
        offsite_bucket,
        offsite_key,
        str(backup_file),
        content_type="application/octet-stream",
        metadata={"sha256": local_hash, "drill-id": args.maintenance_window_id},
    )
    steps.append(DrillStep("offsite_backup_upload", "passed", f"uploaded {backup_size} bytes to oss://{offsite_bucket}/{offsite_key}"))

    checksum_bytes = f"{local_hash}  {backup_file.name}\n".encode("utf-8")
    client.put_object(
        offsite_bucket,
        offsite_key + ".sha256",
        io.BytesIO(checksum_bytes),
        length=len(checksum_bytes),
        content_type="text/plain",
    )
    steps.append(DrillStep("offsite_checksum_upload", "passed", f"uploaded checksum sidecar to oss://{offsite_bucket}/{offsite_key}.sha256"))

    remote_hash, remote_size = _sha256_object(client, offsite_bucket, offsite_key)
    if remote_hash != local_hash or remote_size != backup_size:
        raise RuntimeError("offsite backup hash/size mismatch after readback")
    steps.append(DrillStep("offsite_backup_readback", "passed", f"size={remote_size}; sha256={remote_hash}"))

    client.put_object(
        backup_ref_bucket,
        marker_key,
        io.BytesIO(marker_bytes),
        length=len(marker_bytes),
        content_type="application/json",
        metadata={"sha256": marker_hash, "drill-id": args.maintenance_window_id},
    )
    steps.append(DrillStep("shadow_source_marker_create", "passed", f"created oss://{backup_ref_bucket}/{marker_key}"))

    _copy_object(client, backup_ref_bucket, marker_key, restore_bucket, restored_marker_key)
    steps.append(DrillStep("shadow_restore_copy", "passed", f"copied marker to oss://{restore_bucket}/{restored_marker_key}"))

    restored_hash, restored_size = _sha256_object(client, restore_bucket, restored_marker_key)
    if restored_hash != marker_hash or restored_size != len(marker_bytes):
        raise RuntimeError("shadow restored marker hash/size mismatch")
    steps.append(DrillStep("shadow_restore_readback", "passed", f"size={restored_size}; sha256={restored_hash}"))

    if args.cleanup_shadow_markers:
        client.remove_object(backup_ref_bucket, marker_key)
        client.remove_object(restore_bucket, restored_marker_key)
        steps.append(DrillStep("shadow_marker_cleanup", "passed", "source and restored marker objects removed"))

    return {
        "summary": {
            "status": "passed",
            "network_io": "executed",
            "destructive_actions": "not_executed",
            "production_paths_changed": False,
            "objects_written_under_drills_prefix_only": True,
        },
        "maintenance_window_id": args.maintenance_window_id,
        "backup_file": str(backup_file),
        "backup_size": backup_size,
        "backup_sha256": local_hash,
        "offsite_backup_target": f"oss://{offsite_bucket}/{offsite_key}",
        "external_storage_backup_ref": f"oss://{backup_ref_bucket}/{backup_ref_key}",
        "external_storage_restore_target": f"oss://{restore_bucket}/{restore_prefix}",
        "steps": [step.as_dict() for step in steps],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", action="append", default=[], help="Env file to load without printing secrets")
    parser.add_argument(
        "--credentials-from-stdin",
        action="store_true",
        help="Read access key id and secret access key from stdin before loading env files",
    )
    parser.add_argument("--maintenance-window-id", required=True)
    parser.add_argument("--backup-file", required=True)
    parser.add_argument("--offsite-backup-target", required=True)
    parser.add_argument("--external-storage-backup-ref", required=True)
    parser.add_argument("--external-storage-restore-target", required=True)
    parser.add_argument("--execute", action="store_true", help="Actually upload/read/copy objects under guarded drills/ paths")
    parser.add_argument("--cleanup-shadow-markers", action="store_true", help="Remove marker objects after readback verification")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.credentials_from_stdin:
        access_key = input().strip()
        secret_key = input().strip()
        if access_key:
            os.environ["ALIYUN_OSS_ACCESS_KEY_ID"] = access_key
            os.environ["MINIO_ACCESS_KEY"] = access_key
        if secret_key:
            os.environ["ALIYUN_OSS_ACCESS_KEY_SECRET"] = secret_key
            os.environ["MINIO_SECRET_KEY"] = secret_key

    try:
        payload = run(args)
    except Exception as exc:
        payload = {
            "summary": {
                "status": "failed",
                "network_io": "partially_executed" if args.execute else "not_executed",
                "destructive_actions": "not_executed",
            },
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"summary\tfailed\t{exc}")
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(f"summary\t{summary['status']}\tnetwork_io={summary['network_io']}; destructive_actions={summary['destructive_actions']}")
        for step in payload.get("steps", []):
            print(f"{step['name']}\t{step['status']}\t{step['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
