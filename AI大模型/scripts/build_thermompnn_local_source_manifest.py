#!/usr/bin/env python3
"""Build local source/model-weight manifest for ThermoMPNN."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "cache" / "external" / "ThermoMPNN"
REPORT_OUT = AI_ROOT / "reports" / "thermompnn_local_source_report.json"
MANIFEST_OUT = AI_ROOT / "reports" / "thermompnn_local_source_manifest.json"
VENV_PYTHON = AI_ROOT / ".venv-thermompnn" / "bin" / "python"

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "environment.yaml",
    "local.yaml",
    "analysis/custom_inference.py",
    "analysis/SSM.py",
    "analysis/thermompnn_benchmarking.py",
    "models/thermoMPNN_default.pt",
    "examples/2OCJ.pdb",
]
RUNTIME_MODULES = [
    "torch",
    "pandas",
    "numpy",
    "tqdm",
    "omegaconf",
    "Bio",
    "pytorch_lightning",
    "torchmetrics",
    "wandb",
    "joblib",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def module_available_in_python(python_path: Path, name: str) -> bool:
    if not python_path.exists():
        return False
    result = subprocess.run(
        [
            str(python_path),
            "-c",
            "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) is not None else 1)",
            name,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0


def git_commit(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def file_manifest(source_dir: Path) -> list[dict[str, Any]]:
    rows = []
    if not source_dir.exists():
        return rows
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and ".git/" not in str(path.relative_to(source_dir)):
            rel = str(path.relative_to(source_dir))
            rows.append({
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ThermoMPNN local source manifest")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--venv-python", type=Path, default=VENV_PYTHON)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    args = parser.parse_args()

    source_present = args.source_dir.exists()
    files = file_manifest(args.source_dir)
    by_path = {row["path"]: row for row in files}
    missing_required = [rel for rel in REQUIRED_FILES if rel not in by_path]
    license_text = (args.source_dir / "LICENSE").read_text(encoding="utf-8", errors="replace") if source_present and (args.source_dir / "LICENSE").exists() else ""
    readme_text = (args.source_dir / "README.md").read_text(encoding="utf-8", errors="replace") if source_present and (args.source_dir / "README.md").exists() else ""
    model_weight_rows = [
        row for row in files
        if row["path"].startswith("models/") or row["path"].startswith("vanilla_model_weights/")
    ]
    runtime_modules_current_python = {name: module_available(name) for name in RUNTIME_MODULES}
    runtime_modules_venv = {name: module_available_in_python(args.venv_python, name) for name in RUNTIME_MODULES}
    runtime_modules = runtime_modules_venv if args.venv_python.exists() else runtime_modules_current_python
    missing_runtime_modules = [name for name, present in runtime_modules.items() if not present]
    source_ready = source_present and not missing_required
    license_ready = "MIT License" in license_text and "Kuhlman-Lab" in license_text
    model_weight_ready = any(row["path"] == "models/thermoMPNN_default.pt" for row in model_weight_rows)
    inference_entry_ready = "analysis/custom_inference.py" in by_path and "From a PDB" in readme_text
    runtime_dependency_ready = not missing_runtime_modules
    ready_for_local_inference = all([
        source_ready,
        license_ready,
        model_weight_ready,
        inference_entry_ready,
        runtime_dependency_ready,
    ])
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(args.source_dir),
        "git_commit": git_commit(args.source_dir) if source_present else None,
        "file_count": len(files),
        "files": files,
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_dir": str(args.source_dir),
        "source_present": source_present,
        "git_commit": manifest["git_commit"],
        "file_count": len(files),
        "required_files": REQUIRED_FILES,
        "missing_required_files": missing_required,
        "source_ready": source_ready,
        "license_type": "MIT" if license_ready else None,
        "license_ready": license_ready,
        "license_file": "cache/external/ThermoMPNN/LICENSE" if license_ready else None,
        "readme_present": "README.md" in by_path,
        "inference_entry_ready": inference_entry_ready,
        "model_weight_ready": model_weight_ready,
        "model_weight_rows": model_weight_rows,
        "runtime_modules": runtime_modules,
        "runtime_python": str(args.venv_python if args.venv_python.exists() else Path(sys.executable)),
        "runtime_modules_current_python": runtime_modules_current_python,
        "runtime_modules_venv": runtime_modules_venv,
        "runtime_dependency_ready": runtime_dependency_ready,
        "missing_runtime_modules": missing_runtime_modules,
        "ready_for_local_inference": ready_for_local_inference,
        "ready_as_ddg_proxy_backend": ready_for_local_inference,
        "source_license_model_ready": bool(source_ready and license_ready and model_weight_ready and inference_entry_ready),
        "safe_for_model_claim": False,
        "policy": "ThermoMPNN is a predicted stability/ddG-proxy backend; it is not a wet-lab stability label and not Rosetta/FoldX physics ddG.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_license_model_ready": report["source_license_model_ready"],
        "runtime_dependency_ready": report["runtime_dependency_ready"],
        "ready_for_local_inference": report["ready_for_local_inference"],
        "missing_runtime_modules": report["missing_runtime_modules"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
