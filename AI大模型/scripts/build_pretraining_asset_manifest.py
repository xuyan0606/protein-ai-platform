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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local pretraining asset manifest")
    parser.add_argument("--asset", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()
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
