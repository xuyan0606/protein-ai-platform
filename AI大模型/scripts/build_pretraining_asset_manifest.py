#!/usr/bin/env python3
"""Build and verify a hash-bound manifest for local pretraining assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(paths: list[Path]) -> dict[str, Any]:
    assets = []
    for path in paths:
        resolved = path.resolve()
        assets.append({
            "path": str(resolved),
            "exists": resolved.is_file(),
            "size": resolved.stat().st_size if resolved.is_file() else None,
            "sha256": file_sha256(resolved) if resolved.is_file() else None,
        })
    return {
        "artifact_kind": "local_unlabeled_pretraining_asset_manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "asset_count": len(assets),
        "assets": assets,
        "local_only": True,
        "release_ready": False,
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }


def verify_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    missing = 0
    mismatched = 0
    for asset in manifest.get("assets", []):
        path = Path(str(asset.get("path", "")))
        if not path.is_file():
            missing += 1
        elif file_sha256(path) != asset.get("sha256") or path.stat().st_size != asset.get("size"):
            mismatched += 1
    boundary_ok = (
        manifest.get("local_only") is True
        and manifest.get("release_ready") is False
        and manifest.get("safe_for_supervised_training") is False
        and manifest.get("safe_for_model_claim") is False
    )
    return {
        "success": missing == 0 and mismatched == 0 and boundary_ok,
        "asset_count": len(manifest.get("assets", [])),
        "missing_count": missing,
        "hash_mismatch_count": mismatched,
        "boundary_ok": boundary_ok,
        "release_ready": False,
    }


def build_continuous_selection(report_path: Path, superseded: str) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checkpoint = Path(str(report.get("checkpoint_path", "")))
    if report.get("status") != "completed_pretraining_only" or int(report.get("sequence_count", 0)) != 12830 or not checkpoint.is_file():
        raise ValueError("continuous pretraining report is incomplete")
    return {
        "artifact_kind": "continuous_unlabeled_pretraining_selection",
        "selection_rule": "continuous_full_dataset_coverage",
        "selected_batch": "continuous_full",
        "sequence_count": int(report["sequence_count"]),
        "training_report": str(report_path.resolve()),
        "training_report_sha256": file_sha256(report_path),
        "selected_checkpoint": str(checkpoint.resolve()),
        "selected_checkpoint_sha256": file_sha256(checkpoint),
        "integrity_pass": True,
        "supersedes": superseded,
        "release_status": "pretraining_only_not_for_production",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local pretraining asset manifest")
    parser.add_argument("--asset", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    parser.add_argument("--continuous-report", type=Path)
    parser.add_argument("--selection-output", type=Path)
    args = parser.parse_args()
    if args.continuous_report and args.selection_output:
        selection = build_continuous_selection(args.continuous_report, "sequence_pretraining_checkpoint_selection.json")
        args.selection_output.parent.mkdir(parents=True, exist_ok=True)
        args.selection_output.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.asset = [args.selection_output if p.name == "sequence_pretraining_checkpoint_selection.json" else p for p in args.asset]
    manifest = build_manifest(args.asset)
    validation = verify_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation["manifest"] = str(args.output.resolve())
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
