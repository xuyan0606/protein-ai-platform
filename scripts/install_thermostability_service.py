#!/usr/bin/env python3
"""Install private stdlib HTTP wrapper after official scientific provisioning.

Run on the app host. Does not change production containers or database.
Runtime source root must contain model_services/thermostability/*.py.
No secret is printed or copied into the source tree.
"""
from __future__ import annotations

import argparse
import grp
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess

BASE = Path("/opt/protein-ai-platform/model-services/thermostability")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--bind", required=True)
    args = parser.parse_args()
    if args.bind != "172.18.0.1":
        raise SystemExit("Review unit IPAddressAllow before changing Docker gateway")
    source = args.source.resolve()
    modules = source / "model_services"
    if not (modules / "thermostability/service.py").is_file():
        raise SystemExit("Missing reviewed service source")
    try:
        user = pwd.getpwnam("protein-models")
    except KeyError:
        subprocess.run(["useradd", "--system", "--no-create-home", "--shell", "/sbin/nologin", "protein-models"], check=True)
        user = pwd.getpwnam("protein-models")
    subprocess.run(["setfacl", "-m", "u:protein-models:--x", str(BASE.parent.parent)], check=True)
    runtime = BASE / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    shutil.copytree(modules, runtime / "model_services", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
    runtime.chmod(0o755)
    for entry in (runtime / "model_services").rglob("*"):
        entry.chmod(0o755 if entry.is_dir() else 0o644)
    (runtime / "model_services").chmod(0o755)
    runs = BASE / "runs"
    runs.mkdir(mode=0o700, exist_ok=True)
    # Keep operator-only provisioning logs private; service has a dedicated subtree.
    service_runs = runs / "service"
    service_runs.mkdir(mode=0o700, exist_ok=True)
    os.chown(service_runs, user.pw_uid, user.pw_gid)
    for name in ("numba-cache", "cache", "matplotlib"):
        cache = service_runs / name
        cache.mkdir(mode=0o700, exist_ok=True)
        os.chown(cache, user.pw_uid, user.pw_gid)
    # The service user needs traverse but not write permissions on installed assets.
    os.chmod(BASE, 0o751)
    os.chmod(runs, 0o711)
    env_path = BASE / "service.env"
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                existing[key] = value
    values = {
        "MODEL_SERVICE_BIND": args.bind, "MODEL_SERVICE_PORT": "4270",
        "MODEL_SERVICE_TOKEN": existing.get("MODEL_SERVICE_TOKEN") or secrets.token_urlsafe(48),
        "MODEL_SERVICE_RUN_ROOT": str(service_runs), "MODEL_SERVICE_TIMEOUT_SECONDS": "7200",
        "DDGUN_RUNNER_PYTHON": "/usr/bin/python3.11",
        "COLABFOLD_RUNNER_PYTHON": str(BASE / "colabfold-venv/bin/python"),
        "EVCOUPLINGS_RUNNER_PYTHON": str(BASE / "evcouplings-venv/bin/python"),
    }
    for config in ("ddgun-runtime.env", "colabfold-runtime.env", "evcouplings-runtime.env"):
        path = BASE / config
        if path.exists():
            for line in path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    if not key.replace("_", "").isalnum() or any(c in value for c in "\n\r\x00"):
                        raise SystemExit("Invalid runtime configuration")
                    values[key] = value
    if any(key.endswith("ALLOW_VALIDATION_DATABASE") and value == "1" for key, value in values.items()):
        raise SystemExit("Refuse production service with validation database override")
    values.update({"NUMBA_CACHE_DIR": str(service_runs / "numba-cache"),
                   "XDG_CACHE_HOME": str(service_runs / "cache"),
                   "MPLCONFIGDIR": str(service_runs / "matplotlib")})
    # Longer HTTP wrapper budget than individual runners allows their own cleanup.
    env_path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    env_path.chmod(0o600)
    unit = Path("/etc/systemd/system/protein-thermostability.service")
    shutil.copyfile(modules / "thermostability/protein-thermostability.service", unit)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "protein-thermostability.service"], check=True)
    subprocess.run(["systemctl", "restart", "protein-thermostability.service"], check=True)
    print("Private model HTTP service installed; model readiness requires real authenticated smoke.")


if __name__ == "__main__":
    main()
