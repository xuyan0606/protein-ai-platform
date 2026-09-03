#!/usr/bin/env python3
"""Update Aliyun OSS credentials in an env file without printing secrets."""

import argparse
from pathlib import Path


def _read_credentials_from_stdin():
    access_key = input().strip()
    secret_key = input().strip()
    if not access_key or not secret_key:
        raise ValueError("access key id and secret access key are required")
    return access_key, secret_key


def _upsert_env(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []
    seen = set()
    output = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in values:
            output.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return sorted(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--credentials-from-stdin", action="store_true", required=True)
    parser.add_argument("--endpoint", default="oss-cn-beijing.aliyuncs.com")
    parser.add_argument("--region", default="cn-beijing")
    parser.add_argument("--bucket", default="crvab")
    parser.add_argument("--secure", default="true")
    args = parser.parse_args()

    access_key, secret_key = _read_credentials_from_stdin()
    updated = _upsert_env(
        Path(args.env_file).expanduser(),
        {
            "ALIYUN_OSS_ENDPOINT": args.endpoint,
            "ALIYUN_OSS_REGION": args.region,
            "ALIYUN_OSS_SECURE": args.secure,
            "ALIYUN_OSS_ACCESS_KEY_ID": access_key,
            "ALIYUN_OSS_ACCESS_KEY_SECRET": secret_key,
            "ALIYUN_OSS_BUCKET": args.bucket,
            "ALIYUN_OSS_OUTLINE_BUCKET": args.bucket,
            "ALIYUN_OSS_OUTLINE_BUCKET_URL": f"https://{args.bucket}.{args.endpoint}",
            "ALIYUN_OSS_FORCE_PATH_STYLE": "false",
        },
    )
    print(f"updated {Path(args.env_file).name}: {', '.join(updated)}")
    print("secrets redacted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
