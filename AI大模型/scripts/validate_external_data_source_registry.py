#!/usr/bin/env python3
"""Validate external data-source registry readiness without approving sources."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = AI_ROOT / "config" / "external_data_source_registry.local.example.json"
REPORT_OUT = AI_ROOT / "reports" / "external_data_source_registry_validation_report.json"

REQUIRED_FIELDS = {
    "source_name",
    "source_type",
    "url",
    "license",
    "commercial_use_status",
    "redistribution_status",
    "attribution_required",
    "version",
    "retrieved_at",
    "allowed_uses",
    "forbidden_uses",
}
READY_COMMERCIAL = {"commercial_use_allowed", "public_domain"}
READY_REDISTRIBUTION = {"redistribution_allowed", "public_domain", "internal_use_only"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_source(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    blockers: list[str] = []
    for field in sorted(REQUIRED_FIELDS):
        if field not in row:
            errors.append(f"missing_{field}")
    if not isinstance(row.get("allowed_uses"), list) or not row.get("allowed_uses"):
        errors.append("allowed_uses_missing_or_empty")
    if not isinstance(row.get("forbidden_uses"), list) or not row.get("forbidden_uses"):
        errors.append("forbidden_uses_missing_or_empty")
    if row.get("commercial_use_status") not in READY_COMMERCIAL:
        blockers.append("commercial_use_not_cleared")
    if row.get("redistribution_status") not in READY_REDISTRIBUTION:
        blockers.append("redistribution_not_cleared")
    if row.get("version") in {None, "", "not_configured"}:
        blockers.append("source_version_not_configured")
    if not row.get("retrieved_at"):
        blockers.append("retrieved_at_missing")
    if row.get("attribution_required") is True and not row.get("license"):
        errors.append("attribution_required_but_license_missing")
    return errors, blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external data-source registry")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    registry = load_json(args.registry)
    rows = registry.get("sources", [])
    records = []
    error_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    for row in rows:
        errors, blockers = validate_source(row)
        error_counts.update(errors)
        blocker_counts.update(blockers)
        records.append({
            "source_name": row.get("source_name"),
            "valid": not errors,
            "ready_for_training_or_delivery": not errors and not blockers,
            "errors": errors,
            "blockers": blockers,
        })
    report = {
        "local_only": True,
        "registry": str(args.registry),
        "source_rows": len(rows),
        "valid_rows": sum(1 for item in records if item["valid"]),
        "invalid_rows": sum(1 for item in records if not item["valid"]),
        "ready_sources": sum(1 for item in records if item["ready_for_training_or_delivery"]),
        "ready": bool(rows) and all(item["ready_for_training_or_delivery"] for item in records),
        "error_counts": dict(error_counts),
        "blocker_counts": dict(blocker_counts),
        "records": records,
        "policy": "Registry validation never grants license clearance; version, retrieval date, commercial use, and redistribution must be reviewed per source.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_rows": report["source_rows"],
        "valid_rows": report["valid_rows"],
        "ready_sources": report["ready_sources"],
        "ready": report["ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
