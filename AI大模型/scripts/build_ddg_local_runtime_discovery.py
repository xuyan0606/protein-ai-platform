#!/usr/bin/env python3
"""Discover local physical ddG runtime candidates without enabling them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import module_probe_row


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "datasets" / "governance" / "ddg_local_runtime_discovery_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json"

EXECUTABLE_NAMES = {
    "rosetta": {
        "cartesian_ddg",
        "cartesian_ddg.cxx11threadserialization.macosclangrelease",
        "cartesian_ddg.default.macosclangrelease",
        "cartesian_ddg.default.linuxgccrelease",
        "rosetta_scripts",
        "rosetta_scripts.cxx11threadserialization.macosclangrelease",
        "rosetta_scripts_jd3",
        "rosetta_scripts_jd3.cxx11threadserialization.macosclangrelease",
        "rosetta_scripts.default.macosclangrelease",
        "rosetta_scripts.default.linuxgccrelease",
    },
    "foldx": {"foldx", "FoldX"},
}
PYTHON_MODULES = {"pyrosetta": "pyrosetta"}
SCAN_ROOTS = [
    AI_ROOT / "cache" / "external",
    AI_ROOT / "cache",
    AI_ROOT,
    Path.home() / "foldx",
    Path.home() / "FoldX",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path("/Applications"),
    Path.home() / "Applications",
]
MAX_DEPTH_BY_ROOT = {
    str(AI_ROOT): 3,
    str(AI_ROOT / "cache"): 5,
    str(AI_ROOT / "cache" / "external"): 6,
    "/Applications": 4,
}
MAX_FILES_PER_ROOT = 25000


def sha256(path: Path, max_bytes: int = 64 * 1024 * 1024) -> str | None:
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def max_depth(root: Path) -> int:
    return MAX_DEPTH_BY_ROOT.get(str(root), 2)


def executable_bit(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def scan_root(root: Path, names_by_backend: dict[str, set[str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stats = {
        "root": str(root),
        "exists": root.exists(),
        "files_scanned": 0,
        "dirs_scanned": 0,
        "max_depth": max_depth(root),
        "truncated": False,
        "errors": [],
    }
    if not root.exists():
        return rows, stats
    root = root.resolve()
    for current, dirnames, filenames in os.walk(root, topdown=True):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            depth = 0
        stats["dirs_scanned"] += 1
        if depth >= stats["max_depth"]:
            dirnames[:] = []
        skip_names = {".git", "__pycache__", "node_modules", ".venv", ".venv-thermompnn"}
        dirnames[:] = [name for name in dirnames if name not in skip_names and not name.startswith(".Trash")]
        for filename in filenames:
            stats["files_scanned"] += 1
            if stats["files_scanned"] > MAX_FILES_PER_ROOT:
                stats["truncated"] = True
                dirnames[:] = []
                break
            for backend, names in names_by_backend.items():
                if filename not in names:
                    continue
                path = current_path / filename
                rows.append({
                    "candidate_id": f"ddg-runtime-discovery-{backend}-{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:16]}",
                    "backend": backend,
                    "candidate_type": "local_executable_path",
                    "path": rel_or_abs(path),
                    "source_root": str(root),
                    "file_name": filename,
                    "exists": path.exists(),
                    "is_file": path.is_file(),
                    "executable_bit": executable_bit(path),
                    "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
                    "sha256": sha256(path) if path.exists() and path.is_file() else None,
                    "version_probe_attempted": False,
                    "version_probe_succeeded": False,
                    "ddg_job_executed": False,
                    "ready_for_runtime_receipt": False,
                    "blockers": [
                        reason
                        for reason, blocked in [
                            ("not_executable", not executable_bit(path)),
                            ("license_receipt_not_validated", True),
                            ("runtime_receipt_not_approved", True),
                            ("ddg_smoke_not_executed", True),
                        ]
                        if blocked
                    ],
                    "policy": "Discovery candidate only; not license approval, not runtime receipt, and not ddG execution.",
                })
        if stats["truncated"]:
            break
    return rows, stats


def path_candidates() -> list[dict[str, Any]]:
    rows = []
    for backend, names in EXECUTABLE_NAMES.items():
        for name in sorted(names):
            path = None
            if backend == "foldx" and name.lower() == "foldx":
                path = os.environ.get("FOLDX_BINARY") or shutil.which(name)
            else:
                path = shutil.which(name)
            rows.append({
                "candidate_id": f"ddg-runtime-path-{backend}-{name}",
                "backend": backend,
                "candidate_type": "path_lookup",
                "path": path,
                "file_name": name,
                "exists": bool(path),
                "is_file": Path(path).is_file() if path else False,
                "executable_bit": executable_bit(Path(path)) if path else False,
                "size_bytes": Path(path).stat().st_size if path and Path(path).is_file() else None,
                "sha256": sha256(Path(path)) if path and Path(path).is_file() else None,
                "version_probe_attempted": False,
                "version_probe_succeeded": False,
                "ddg_job_executed": False,
                "ready_for_runtime_receipt": False,
                "blockers": [
                    reason
                    for reason, blocked in [
                        ("not_found_on_path", not path),
                        ("license_receipt_not_validated", True),
                        ("runtime_receipt_not_approved", True),
                        ("ddg_smoke_not_executed", True),
                    ]
                    if blocked
                ],
                "policy": "PATH discovery only; not license approval, not runtime receipt, and not ddG execution.",
            })
    return rows


def module_candidates() -> list[dict[str, Any]]:
    rows = []
    for backend, module in PYTHON_MODULES.items():
        probe = module_probe_row(module)
        technical_ready = bool(probe["available"])
        rows.append({
            "candidate_id": f"ddg-runtime-module-{backend}-{module}",
            "backend": backend,
            "candidate_type": "python_module",
            "module": module,
            "available": probe["available"],
            "origin": probe["origin"],
            "discovered_via": probe["discovered_via"],
            "local_search_paths": probe["local_search_paths"],
            "error": probe["error"],
            "python_executable": sys.executable,
            "module_imported": probe["module_imported"],
            "ddg_protocol_executed": probe["ddg_protocol_executed"],
            "ready_for_runtime_receipt": technical_ready,
            "ready_for_ddg_execution": technical_ready,
            "blockers": [
                reason
                for reason, blocked in [
                    ("module_not_available", not probe["available"]),
                ]
                if blocked
            ],
            "policy": "Module discovery only. ready flags mean technically discoverable; license approval, runtime receipt and smoke artifacts remain separate gates.",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG local runtime discovery")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = path_candidates()
    scan_stats = []
    seen = {(row.get("backend"), row.get("candidate_type"), row.get("path"), row.get("file_name")) for row in rows}
    for root in SCAN_ROOTS:
        found, stats = scan_root(root, EXECUTABLE_NAMES)
        scan_stats.append(stats)
        for row in found:
            key = (row.get("backend"), row.get("candidate_type"), row.get("path"), row.get("file_name"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    rows.extend(module_candidates())

    executable_candidate_rows = [
        row for row in rows
        if row.get("candidate_type") in {"path_lookup", "local_executable_path"} and row.get("exists")
    ]
    executable_with_xbit_rows = [row for row in executable_candidate_rows if row.get("executable_bit")]
    module_available_rows = [row for row in rows if row.get("candidate_type") == "python_module" and row.get("available")]
    ready_for_runtime_receipt_rows = [row for row in rows if row.get("ready_for_runtime_receipt")]
    ready_for_ddg_execution_rows = [row for row in rows if row.get("ready_for_ddg_execution")]
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "output": str(args.output),
        "candidate_rows": len(rows),
        "executable_candidate_rows": len(executable_candidate_rows),
        "executable_with_xbit_rows": len(executable_with_xbit_rows),
        "python_module_available_rows": len(module_available_rows),
        "rosetta_candidate_rows": sum(1 for row in rows if row.get("backend") == "rosetta" and row.get("exists")),
        "foldx_candidate_rows": sum(1 for row in rows if row.get("backend") == "foldx" and row.get("exists")),
        "pyrosetta_module_available": any(row.get("backend") == "pyrosetta" and row.get("available") for row in rows),
        "scan_stats": scan_stats,
        "ready_for_runtime_receipt_rows": len(ready_for_runtime_receipt_rows),
        "ready_for_ddg_execution_rows": len(ready_for_ddg_execution_rows),
        "version_probe_succeeded_rows": 0,
        "ddg_smoke_job_executed": False,
        "physics_ddg_ready": False,
        "runtime_discovery_scope": "PATH lookup, bounded local file-name scan and Python module spec discovery only; no imports, no license acceptance, no ddG execution.",
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Local runtime discovery is evidence gathering only; license review, runtime receipt, config enable and ddG smoke remain separate gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "executable_candidate_rows": report["executable_candidate_rows"],
        "python_module_available_rows": report["python_module_available_rows"],
        "ready_for_ddg_execution_rows": report["ready_for_ddg_execution_rows"],
        "physics_ddg_ready": report["physics_ddg_ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
