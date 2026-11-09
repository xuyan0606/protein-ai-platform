#!/usr/bin/env python3
"""Validate production-facing configuration without printing secrets."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).absolute().parent.parent


WEAK_VALUES = {
    "",
    "change-me",
    "change-me-to-a-random-string-at-least-32-chars",
    "change-me-oidc-client-secret",
    "change-me-strong-password",
    "change-me-minio-password",
    "dev-secret-change-in-production",
    "oidc-secret-change-me-in-production",
    "minioadmin",
    "postgres",
    "password",
    "root",
    "your-deepseek-api-key",
}

PLACEHOLDER_MARKERS = (
    "change_me",
    "change-me",
    "changeme",
    "<",
    "your-",
)


def _read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_values(env_files):
    values = {}
    for env_file in env_files:
        values.update(_read_env_file(Path(env_file).expanduser()))
    values.update({k: v for k, v in os.environ.items() if v is not None})
    return values


def _first(values, *names):
    for name in names:
        value = str(values.get(name) or "").strip()
        if value:
            return value
    return ""


def _is_weak_secret(value, min_length=32):
    normalized = str(value or "").strip()
    return _has_placeholder(value) or normalized in WEAK_VALUES or len(normalized) < min_length


def _has_placeholder(value):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _public_base_url(values):
    return _first(values, "PUBLIC_BASE_URL", "FRONTEND_URL", "OIDC_ISSUER").rstrip("/")


def _mode(values, explicit_mode):
    if explicit_mode:
        return explicit_mode
    for name in ("APP_ENV", "ENVIRONMENT", "NODE_ENV"):
        value = str(values.get(name) or "").strip().lower()
        if value in {"prod", "production"}:
            return "production"
    debug = str(values.get("DEBUG") or "").strip().lower()
    if debug in {"false", "0", "no", "off"}:
        return "production"
    return "development"


def _check_secret(results, values, key, min_length=32, aliases=()):
    value = _first(values, key, *aliases)
    if _is_weak_secret(value, min_length=min_length):
        results.append({
            "name": key,
            "status": "critical",
            "detail": "%s is missing, too short, or still set to a known default" % key,
        })
    else:
        results.append({"name": key, "status": "ok", "detail": "%s is configured" % key})


def collect_checks(values, mode, skip_domain_https=False):
    results = []
    production = mode == "production"

    if production:
        debug = str(values.get("DEBUG") or "").strip().lower()
        if debug in {"true", "1", "yes", "on"}:
            results.append({"name": "DEBUG", "status": "critical", "detail": "DEBUG must be false in production mode"})
        else:
            results.append({"name": "DEBUG", "status": "ok", "detail": "DEBUG is not enabled"})

    _check_secret(results, values, "SECRET_KEY", min_length=32)
    _check_secret(results, values, "OIDC_CLIENT_SECRET", min_length=24)

    database_url = _first(values, "DATABASE_URL", "ALIYUN_APP_DATABASE_URL")
    if not database_url:
        results.append({"name": "DATABASE_URL", "status": "critical", "detail": "DATABASE_URL/ALIYUN_APP_DATABASE_URL is missing"})
    elif production and _has_placeholder(database_url):
        results.append({"name": "DATABASE_URL", "status": "critical", "detail": "database URL contains placeholder values"})
    elif production and any(token in database_url for token in ("localhost", "127.0.0.1", "sqlite")):
        results.append({"name": "DATABASE_URL", "status": "critical", "detail": "production database points to local/sqlite storage"})
    else:
        results.append({"name": "DATABASE_URL", "status": "ok", "detail": "database URL is configured"})

    redis_url = _first(values, "REDIS_URL", "ALIYUN_REDIS_APP_URL")
    redis_host = _first(values, "REDIS_HOST", "ALIYUN_REDIS_HOST")
    if not redis_url and not redis_host:
        results.append({"name": "REDIS", "status": "critical", "detail": "Redis URL or host is missing"})
    elif production and (_has_placeholder(redis_url) or _has_placeholder(redis_host)):
        results.append({"name": "REDIS", "status": "critical", "detail": "Redis endpoint contains placeholder values"})
    elif production and (redis_url.startswith("redis://localhost") or redis_host in {"localhost", "127.0.0.1"}):
        results.append({"name": "REDIS", "status": "critical", "detail": "production Redis points to localhost"})
    else:
        results.append({"name": "REDIS", "status": "ok", "detail": "Redis endpoint is configured"})

    # Managed Alibaba deployments keep development MinIO defaults in the
    # shared env file while compose maps ALIYUN_OSS_* into the runtime's
    # MINIO_* names. Prefer the managed values when present so the gate checks
    # the effective production configuration instead of a shadowed example.
    oss_endpoint = _first(values, "ALIYUN_OSS_ENDPOINT", "MINIO_ENDPOINT")
    oss_bucket = _first(values, "ALIYUN_OSS_BUCKET", "MINIO_BUCKET")
    oss_access = _first(values, "ALIYUN_OSS_ACCESS_KEY_ID", "MINIO_ACCESS_KEY")
    oss_secret = _first(values, "ALIYUN_OSS_ACCESS_KEY_SECRET", "MINIO_SECRET_KEY")
    if not all([oss_endpoint, oss_bucket, oss_access, oss_secret]):
        results.append({"name": "OBJECT_STORAGE", "status": "critical", "detail": "object storage endpoint/bucket/access key/secret key are not all configured"})
    elif production and any(_has_placeholder(value) for value in (oss_endpoint, oss_bucket, oss_access, oss_secret)):
        results.append({"name": "OBJECT_STORAGE", "status": "critical", "detail": "object storage config contains placeholder values"})
    elif production and (_is_weak_secret(oss_secret, min_length=16) or oss_access in WEAK_VALUES):
        results.append({"name": "OBJECT_STORAGE", "status": "critical", "detail": "object storage credentials are weak or default"})
    else:
        results.append({"name": "OBJECT_STORAGE", "status": "ok", "detail": "object storage config is present"})

    provider = _first(values, "LLM_PROVIDER").lower()
    provider_keys = {
        "openai": _first(values, "OPENAI_API_KEY"),
        "deepseek": _first(values, "DEEPSEEK_API_KEY"),
        "kuapao": _first(values, "KUAPAO_API_KEY"),
        "dashscope": _first(values, "DASHSCOPE_API_KEY"),
        "minimax": _first(values, "MINIMAX_API_KEY"),
    }
    if provider and _has_placeholder(provider_keys.get(provider, "")):
        results.append({"name": "LLM_PROVIDER_KEY", "status": "critical", "detail": "selected LLM provider key contains placeholder values"})
    elif provider and not provider_keys.get(provider, ""):
        results.append({"name": "LLM_PROVIDER_KEY", "status": "critical", "detail": "selected LLM provider key is missing"})
    elif not any(provider_keys.values()):
        results.append({"name": "LLM_PROVIDER_KEY", "status": "warning", "detail": "no LLM provider key detected; chat will rely on deterministic fallbacks only"})
    else:
        results.append({"name": "LLM_PROVIDER_KEY", "status": "ok", "detail": "at least one LLM provider key is configured"})

    public_url = _public_base_url(values)
    if public_url:
        parsed = urlparse(public_url)
        is_https = parsed.scheme == "https"
        is_local = parsed.hostname in {"localhost", "127.0.0.1"}
        if production and not is_https and not skip_domain_https and not is_local:
            results.append({"name": "PUBLIC_BASE_URL_HTTPS", "status": "critical", "detail": "production public URL must use HTTPS; provide a formal domain and certificate or explicitly use --skip-domain-https for non-production preparation"})
        else:
            results.append({"name": "PUBLIC_BASE_URL", "status": "ok", "detail": "public base URL is configured"})
    else:
        results.append({"name": "PUBLIC_BASE_URL", "status": "warning", "detail": "PUBLIC_BASE_URL is missing"})

    oidc_private = _first(values, "OIDC_PRIVATE_KEY_PATH")
    oidc_public = _first(values, "OIDC_PUBLIC_KEY_PATH")
    oidc_private_host = _first(values, "OIDC_PRIVATE_KEY_HOST_PATH")
    oidc_public_host = _first(values, "OIDC_PUBLIC_KEY_HOST_PATH")
    missing_keys = [p for p in (oidc_private, oidc_public) if p and not Path(p).expanduser().exists()]
    if missing_keys:
        results.append({"name": "OIDC_SIGNING_KEYS", "status": "critical", "detail": "configured OIDC signing key path does not exist"})
    elif oidc_private and oidc_public:
        results.append({"name": "OIDC_SIGNING_KEYS", "status": "ok", "detail": "OIDC signing key paths are present or mounted at runtime"})
    elif oidc_private_host and oidc_public_host:
        results.append({"name": "OIDC_SIGNING_KEYS", "status": "ok", "detail": "OIDC signing key host paths are configured for Docker secret mounting"})
    else:
        results.append({"name": "OIDC_SIGNING_KEYS", "status": "warning", "detail": "OIDC signing key paths are not configured in this environment"})

    outline_token = _first(values, "OUTLINE_API_TOKEN")
    outline_api_url = _first(values, "OUTLINE_API_URL") or "http://outline:3001/api"
    if not outline_token:
        results.append({
            "name": "OUTLINE_API_TOKEN",
            "status": "critical" if production else "warning",
            "detail": "OUTLINE_API_TOKEN is missing; Wiki collection listing and publish will fail",
        })
    elif not outline_token.startswith("ol_api_") or len(outline_token) < 40:
        results.append({
            "name": "OUTLINE_API_TOKEN",
            "status": "critical",
            "detail": "OUTLINE_API_TOKEN is present but does not look like a valid Outline API key",
        })
    else:
        results.append({"name": "OUTLINE_API_TOKEN", "status": "ok", "detail": "Outline API token is configured"})

    parsed_outline_api = urlparse(outline_api_url)
    if not parsed_outline_api.scheme or not parsed_outline_api.netloc:
        results.append({"name": "OUTLINE_API_URL", "status": "critical", "detail": "OUTLINE_API_URL is not a valid URL"})
    else:
        results.append({"name": "OUTLINE_API_URL", "status": "ok", "detail": "Outline API URL is configured"})

    return results


def summarize(checks, require_production_safe):
    critical = [item for item in checks if item["status"] == "critical"]
    warning = [item for item in checks if item["status"] == "warning"]
    if critical and require_production_safe:
        return {"status": "blocked", "critical": len(critical), "warning": len(warning)}
    if critical:
        return {"status": "needs-attention", "critical": len(critical), "warning": len(warning)}
    if warning:
        return {"status": "ready-with-warnings", "critical": 0, "warning": len(warning)}
    return {"status": "ready", "critical": 0, "warning": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--env-file", action="append", default=[], help="Read key=value config from an env file; can be repeated")
    parser.add_argument("--mode", choices=["development", "production"])
    parser.add_argument("--require-production-safe", action="store_true", help="Exit non-zero on critical production config issues")
    parser.add_argument("--skip-domain-https", action="store_true", help="Do not warn/block on missing formal HTTPS domain")
    args = parser.parse_args()

    env_files = args.env_file or [str(PROJECT_ROOT / "docker" / ".env")]
    values = _load_values(env_files)
    mode = _mode(values, args.mode)
    checks = collect_checks(values, mode, skip_domain_https=args.skip_domain_https)
    summary = summarize(checks, args.require_production_safe)
    payload = {
        "project_root": str(PROJECT_ROOT),
        "mode": mode,
        "env_files_checked": [str(Path(path).expanduser()) for path in env_files],
        "checks": checks,
        "summary": summary,
        "secrets_printed": False,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in checks:
            print("%s\t%s\t%s" % (check["name"], check["status"], check["detail"]))
        print("summary\t%s\tcritical=%s warning=%s" % (summary["status"], summary["critical"], summary["warning"]))
    return 1 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
