#!/usr/bin/env python3
"""Verify OSS/MinIO E2E readiness.

By default this is a contract check only: it validates endpoint and credential
shape, but does not create buckets, upload objects, download objects, or contact
a live storage service. With --require-live it performs a guarded write/read/
delete round-trip under the drills/oss-minio-e2e/ prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass
class ContractItem:
    name: str
    status: str
    detail: str


def _load_env_file(path: str) -> None:
    """Load simple KEY=VALUE pairs without evaluating shell syntax."""
    env_path = path.strip()
    if not env_path:
        return
    try:
        lines = open(env_path, "r", encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _storage_config() -> dict[str, str | bool | None]:
    endpoint = _first_env("MINIO_ENDPOINT", "ALIYUN_OSS_ENDPOINT", default="localhost:9000")
    secure = _truthy(_first_env("MINIO_SECURE", "ALIYUN_OSS_SECURE", default="false"))
    region = _first_env("MINIO_REGION", "ALIYUN_OSS_REGION")
    bucket = _first_env("MINIO_BUCKET", "ALIYUN_OSS_BUCKET", default="protein-files")
    access_key = _first_env("MINIO_ACCESS_KEY", "ALIYUN_OSS_ACCESS_KEY_ID")
    secret_key = _first_env("MINIO_SECRET_KEY", "ALIYUN_OSS_ACCESS_KEY_SECRET")
    parsed = urlparse(endpoint if "://" in endpoint else f"//{endpoint}", scheme="http")
    if parsed.scheme in {"http", "https"} and "://" in endpoint:
        secure = parsed.scheme == "https"
    return {
        "endpoint": endpoint,
        "endpoint_host": parsed.netloc or parsed.path,
        "secure": secure,
        "region": region or None,
        "bucket": bucket,
        "access_key": access_key,
        "secret_key": secret_key,
    }


def _collect(require_live: bool) -> tuple[list[ContractItem], int, dict[str, str | bool | None]]:
    config = _storage_config()
    endpoint = str(config["endpoint"] or "")
    endpoint_host = str(config["endpoint_host"] or "")
    secure = bool(config["secure"])
    region = str(config["region"] or "")
    bucket = str(config["bucket"] or "")
    access_key = str(config["access_key"] or "")
    secret_key = str(config["secret_key"] or "")
    results: list[ContractItem] = []

    endpoint_ok = bool(endpoint and endpoint_host)
    results.append(
        ContractItem(
            "oss_minio_endpoint",
            "passed" if endpoint_ok else "blocked",
            f"endpoint={endpoint or '<empty>'}",
        )
    )
    results.append(
        ContractItem(
            "oss_minio_bucket",
            "passed" if bucket else "blocked",
            f"bucket={bucket or '<empty>'}",
        )
    )
    credentials_ok = bool(access_key and secret_key)
    credential_status = "passed" if credentials_ok else ("blocked" if require_live else "planned")
    results.append(
        ContractItem(
            "oss_minio_credentials",
            credential_status,
            "object storage access key and secret are set"
            if credentials_ok
            else "credentials not set; live object round-trip remains plan-only; accepts MINIO_* or ALIYUN_OSS_* aliases",
        )
    )

    tls_region_ok = not (secure and region and any(char.isspace() for char in region))
    results.append(
        ContractItem(
            "oss_minio_tls_region",
            "passed" if tls_region_ok else "blocked",
            f"secure={secure}; region={region or '<unset>'}",
        )
    )

    if require_live and not all(item.status == "passed" for item in results):
        return results, 1, config
    return results, 0, config


def _make_client(config: dict[str, str | bool | None]):
    from minio import Minio

    return Minio(
        str(config["endpoint_host"]),
        access_key=str(config["access_key"]),
        secret_key=str(config["secret_key"]),
        secure=bool(config["secure"]),
        region=str(config["region"]) if config["region"] else None,
    )


def _object_bytes() -> bytes:
    payload = {
        "purpose": "oss-minio-e2e-live-gate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "nonce": secrets.token_hex(8),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_object(client, bucket: str, object_name: str) -> bytes:
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def _live_round_trip(config: dict[str, str | bool | None]) -> tuple[list[ContractItem], int]:
    from minio.error import S3Error

    bucket = str(config["bucket"])
    object_name = (
        "drills/oss-minio-e2e/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{secrets.token_hex(6)}.json"
    )
    data = _object_bytes()
    expected_hash = _sha256_bytes(data)
    client = _make_client(config)
    results: list[ContractItem] = []
    uploaded = False
    try:
        client.put_object(
            bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type="application/json",
            metadata={"sha256": expected_hash, "drill": "oss-minio-e2e"},
        )
        uploaded = True
        results.append(
            ContractItem(
                "oss_minio_live_upload",
                "passed",
                f"uploaded {len(data)} bytes to {object_name}",
            )
        )

        downloaded = _read_object(client, bucket, object_name)
        actual_hash = _sha256_bytes(downloaded)
        if actual_hash != expected_hash:
            results.append(
                ContractItem(
                    "oss_minio_live_download",
                    "failed",
                    "downloaded object hash did not match uploaded payload",
                )
            )
            return results, 1
        results.append(
            ContractItem(
                "oss_minio_live_download",
                "passed",
                f"readback bytes={len(downloaded)} sha256={actual_hash}",
            )
        )

        client.remove_object(bucket, object_name)
        uploaded = False
        results.append(ContractItem("oss_minio_live_cleanup", "passed", f"removed {object_name}"))
        return results, 0
    except S3Error as exc:
        results.append(ContractItem("oss_minio_live_round_trip", "failed", f"{exc.code}: {exc.message}"))
        return results, 1
    except Exception as exc:
        results.append(ContractItem("oss_minio_live_round_trip", "failed", f"{type(exc).__name__}: {exc}"))
        return results, 1
    finally:
        if uploaded:
            try:
                client.remove_object(bucket, object_name)
                results.append(ContractItem("oss_minio_live_cleanup", "passed", f"removed {object_name} after failure"))
            except Exception as exc:
                results.append(
                    ContractItem(
                        "oss_minio_live_cleanup",
                        "failed",
                        f"cleanup failed for {object_name}: {type(exc).__name__}",
                    )
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--require-live", action="store_true", help="Return non-zero unless live E2E config is complete")
    parser.add_argument("--env-file", help="Load KEY=VALUE storage settings without shell evaluation")
    args = parser.parse_args()

    _load_env_file(args.env_file or "")
    results, exit_code, config = _collect(require_live=args.require_live)
    network_io = "not_executed"
    if args.require_live and exit_code == 0:
        live_results, live_exit = _live_round_trip(config)
        results.extend(live_results)
        exit_code = live_exit
        network_io = "executed"
    blocked = sum(1 for item in results if item.status == "blocked")
    failed = sum(1 for item in results if item.status == "failed")
    planned = sum(1 for item in results if item.status == "planned")
    status = (
        "failed"
        if failed
        else "blocked"
        if blocked and args.require_live
        else "planned"
        if planned
        else "blocked"
        if blocked
        else "passed"
    )
    payload = {
        "summary": {
            "status": status,
            "failed": failed,
            "blocked": blocked,
            "planned": planned,
            "total": len(results),
            "network_io": network_io,
            "passwords_printed": False,
        },
        "results": [asdict(item) for item in results],
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for item in results:
            print(f"{item.name}\t{item.status}\t{item.detail}")
        print(
            "summary\t"
            f"{status}\t"
            f"{blocked} blocked / {planned} planned / {len(results)} total; network_io={network_io}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
