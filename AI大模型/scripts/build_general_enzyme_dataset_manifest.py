#!/usr/bin/env python3
"""Build a research-only dataset manifest; never starts model training."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(audit_path: Path, source_receipt: Optional[Path] = None, normalized_path: Optional[Path] = None) -> Dict[str, Any]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    blocked = audit.get("status") != "passed" or audit.get("training_import_allowed") is not True
    files: List[Dict[str, Any]] = [{"path": str(audit_path), "sha256": sha256_file(audit_path), "kind": "audit"}]
    for path, kind in ((source_receipt, "source_receipt"), (normalized_path, "normalized_records")):
        if path is not None and path.is_file():
            files.append({"path": str(path), "sha256": sha256_file(path), "kind": kind})
    return {
        "schema_version": "general-enzyme-training-manifest.v1",
        "status": "blocked" if blocked else "research_ready",
        "execution_scope": "research_only",
        "production_registration": "forbidden",
        "training_import_allowed": not blocked,
        "safe_for_model_claim": False,
        "release_ready": False,
        "audit_status": audit.get("status"),
        "row_count": audit.get("row_count", 0),
        "metric_counts": audit.get("metric_counts", {}),
        "files": files,
        "blockers": (["dataset_audit_not_passed"] if blocked else []),
        "policy": "This manifest describes research data readiness only and never authorizes production registration.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path)
    parser.add_argument("--normalized", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_manifest(args.audit, args.source_receipt, args.normalized)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "research_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
