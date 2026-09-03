#!/usr/bin/env python3
"""Initialize deployment env files with safe generated defaults.

This script copies project env templates into runtime env files and replaces
known placeholder secrets with random values. It never overwrites existing
files unless --force is provided.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import secrets
import string
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class InitTarget:
    label: str
    template: Path
    output: Path
    replacements: dict[str, str]
    append_missing: dict[str, str]


def _random_token(bytes_len: int = 32) -> str:
    return secrets.token_urlsafe(bytes_len)


def _random_hex(bytes_len: int = 32) -> str:
    return secrets.token_hex(bytes_len)


def _random_password(length: int = 28) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _replace_env_values(content: str, replacements: dict[str, str], append_missing: dict[str, str]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        key, _value = line.split("=", 1)
        if key in replacements:
            lines.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            lines.append(line)
            seen.add(key)

    missing = {key: value for key, value in append_missing.items() if key not in seen}
    if missing:
        lines.extend(["", "# Generated deployment secrets"])
        lines.extend(f"{key}={value}" for key, value in missing.items())
    lines.append("")
    return "\n".join(lines)


def _render_target(target: InitTarget) -> str:
    content = target.template.read_text(encoding="utf-8")
    return _replace_env_values(content, target.replacements, target.append_missing)


def _write_target(target: InitTarget, *, force: bool, dry_run: bool) -> str:
    rel_output = target.output.relative_to(PROJECT_ROOT)
    if target.output.exists() and not force:
        return f"skip\t{target.label}\t{rel_output}\texists"
    rendered = _render_target(target)
    if dry_run:
        action = "overwrite" if target.output.exists() else "create"
        return f"dry-run\t{target.label}\t{rel_output}\t{action}"
    target.output.parent.mkdir(parents=True, exist_ok=True)
    target.output.write_text(rendered, encoding="utf-8")
    return f"write\t{target.label}\t{rel_output}"


def _local_targets(public_base_url: str, backend_env: bool) -> list[InitTarget]:
    secret_key = _random_token(48)
    postgres_password = _random_password()
    minio_password = _random_password()
    oidc_secret = _random_token(32)
    outline_secret = _random_hex(32)
    outline_utils_secret = _random_hex(32)
    targets = [
        InitTarget(
            label="docker.local",
            template=PROJECT_ROOT / "docker" / ".env.example",
            output=PROJECT_ROOT / "docker" / ".env",
            replacements={
                "SECRET_KEY": secret_key,
                "POSTGRES_PASSWORD": postgres_password,
                "MINIO_ROOT_PASSWORD": minio_password,
                "MINIO_SECRET_KEY": minio_password,
                "DEEPSEEK_API_KEY": "",
            },
            append_missing={
                "PUBLIC_BASE_URL": public_base_url,
                "OUTLINE_PUBLIC_URL": f"{public_base_url.rstrip('/')}/wiki",
                "OIDC_CLIENT_SECRET": oidc_secret,
                "OUTLINE_SECRET_KEY": outline_secret,
                "OUTLINE_UTILS_SECRET": outline_utils_secret,
            },
        )
    ]
    if backend_env:
        targets.append(
            InitTarget(
                label="backend.local",
                template=PROJECT_ROOT / "backend" / ".env.example",
                output=PROJECT_ROOT / "backend" / ".env",
                replacements={
                    "SECRET_KEY": secret_key,
                    "PUBLIC_BASE_URL": public_base_url,
                    "OUTLINE_PUBLIC_URL": f"{public_base_url.rstrip('/')}/wiki",
                    "POSTGRES_PASSWORD": postgres_password,
                    "MINIO_SECRET_KEY": minio_password,
                    "DEEPSEEK_API_KEY": "",
                    "DASHSCOPE_API_KEY": "",
                },
                append_missing={},
            )
        )
    return targets


def _aliyun_app_targets(public_base_url: str) -> list[InitTarget]:
    return [
        InitTarget(
            label="aliyun.app",
            template=PROJECT_ROOT / "docker" / ".env.aliyun.app.example",
            output=PROJECT_ROOT / "docker" / ".env.aliyun.app",
            replacements={
                "PUBLIC_BASE_URL": public_base_url,
                "OUTLINE_PUBLIC_URL": f"{public_base_url.rstrip('/')}/wiki",
                "CORS_ORIGINS": f'["{public_base_url.rstrip("/")}"]',
                "SECRET_KEY": _random_token(48),
                "OIDC_CLIENT_SECRET": _random_token(32),
                "OUTLINE_SECRET_KEY": _random_hex(32),
                "OUTLINE_UTILS_SECRET": _random_hex(32),
            },
            append_missing={},
        )
    ]


def _aliyun_gpu_targets(shared_secret: str | None) -> list[InitTarget]:
    return [
        InitTarget(
            label="aliyun.gpu",
            template=PROJECT_ROOT / "docker" / ".env.aliyun.gpu.example",
            output=PROJECT_ROOT / "docker" / ".env.aliyun.gpu",
            replacements={
                "SECRET_KEY": shared_secret or _random_token(48),
            },
            append_missing={},
        )
    ]


def _targets_for_profiles(profiles: Iterable[str], public_base_url: str, backend_env: bool) -> list[InitTarget]:
    targets: list[InitTarget] = []
    shared_aliyun_secret = _random_token(48)
    for profile in profiles:
        if profile == "local":
            targets.extend(_local_targets(public_base_url, backend_env))
        elif profile == "aliyun-app":
            app_targets = _aliyun_app_targets(public_base_url)
            app_target = app_targets[0]
            replacements = dict(app_target.replacements)
            replacements["SECRET_KEY"] = shared_aliyun_secret
            targets.append(
                InitTarget(
                    label=app_target.label,
                    template=app_target.template,
                    output=app_target.output,
                    replacements=replacements,
                    append_missing=app_target.append_missing,
                )
            )
        elif profile == "aliyun-gpu":
            targets.extend(_aliyun_gpu_targets(shared_aliyun_secret))
        else:
            raise ValueError(f"Unsupported profile: {profile}")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=["local", "aliyun-app", "aliyun-gpu", "all"],
        default="local",
        help="Which deployment env files to initialize.",
    )
    parser.add_argument("--public-base-url", default="http://localhost:4200", help="Public platform URL.")
    parser.add_argument("--backend-env", action="store_true", help="Also create backend/.env for direct backend dev.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    args = parser.parse_args()

    profiles = ["local", "aliyun-app", "aliyun-gpu"] if args.profile == "all" else [args.profile]
    targets = _targets_for_profiles(profiles, args.public_base_url, args.backend_env)

    for target in targets:
        if not target.template.exists():
            print(f"missing\t{target.label}\t{target.template.relative_to(PROJECT_ROOT)}")
            return 1
        print(_write_target(target, force=args.force, dry_run=args.dry_run))

    if "local" in profiles and not args.dry_run:
        print("next\tlocal\tmake write-deploy-env && make package-preflight && make docker-up")
    if any(profile.startswith("aliyun") for profile in profiles) and not args.dry_run:
        print("next\taliyun\tfill RDS/Redis/OSS/LLM values, then ./deploy-aliyun.sh app config")
    print("summary\tok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
