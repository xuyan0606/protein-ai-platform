#!/usr/bin/env python3
"""Download and verify one guarded OSS object for a restore drill."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse


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


def _parse_safe_uri(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "oss" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("expected oss://bucket/key")
    key = parsed.path.lstrip("/")
    parts = [part for part in key.split("/") if part]
    if "drills" not in parts or ".." in parts:
        raise ValueError("refusing non-drill object path")
    return parsed.netloc, key


def _client():
    from minio import Minio

    endpoint = os.environ.get("MINIO_ENDPOINT") or os.environ.get("ALIYUN_OSS_ENDPOINT")
    access_key = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("ALIYUN_OSS_ACCESS_KEY_ID")
    secret_key = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("ALIYUN_OSS_ACCESS_KEY_SECRET")
    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("missing object storage configuration")
    parsed = urlparse(endpoint)
    secure = os.environ.get("MINIO_SECURE") or os.environ.get("ALIYUN_OSS_SECURE", "true")
    if parsed.scheme:
        secure = parsed.scheme == "https"
    else:
        secure = str(secure).lower() in {"1", "true", "yes", "on"}
    return Minio(
        parsed.netloc or parsed.path,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        region=os.environ.get("MINIO_REGION") or os.environ.get("ALIYUN_OSS_REGION") or None,
    )


def _download(client, bucket, key, output):
    digest = hashlib.sha256()
    total = 0
    response = client.get_object(bucket, key)
    try:
        with output.open("wb") as target:
            for chunk in response.stream(1024 * 1024):
                target.write(chunk)
                digest.update(chunk)
                total += len(chunk)
    finally:
        response.close()
        response.release_conn()
    return total, digest.hexdigest()


def run(args):
    for env_file in args.env_file:
        _load_env_file(Path(env_file).expanduser())
    bucket, key = _parse_safe_uri(args.source)
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    client = _client()
    size, sha256 = _download(client, bucket, key, output)

    sidecar = None
    if args.verify_sidecar:
        sidecar_response = client.get_object(bucket, key + ".sha256")
        try:
            sidecar = sidecar_response.read().decode("utf-8", errors="replace")
        finally:
            sidecar_response.close()
            sidecar_response.release_conn()
        expected = sidecar.split()[0] if sidecar.split() else ""
        if not expected or expected != sha256:
            raise RuntimeError("downloaded object does not match OSS checksum sidecar")

    return {
        "summary": {"status": "passed"},
        "source": "oss://{}/{}".format(bucket, key),
        "output": str(output),
        "size": size,
        "sha256": sha256,
        "sidecar_verified": bool(args.verify_sidecar),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", action="append", default=[])
    parser.add_argument("--source", required=True, help="Guarded oss://bucket/drills/... object")
    parser.add_argument("--output", required=True)
    parser.add_argument("--verify-sidecar", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        payload = run(args)
        code = 0
    except Exception as exc:
        payload = {"summary": {"status": "failed"}, "error": str(exc)}
        code = 1
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("summary\t{}\t{}".format(payload["summary"]["status"], payload.get("error", "")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
