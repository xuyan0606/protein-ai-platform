#!/usr/bin/env python3
"""Apply local benchmark score cache intake rows to a fail-closed manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.template.jsonl"
MANIFEST_OUT = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "benchmark_score_cache_intake_report.json"
HEX_DIGITS = set("0123456789abcdefABCDEF")
APPROVED_LICENSE_STATUSES = {
    "approved_for_benchmark_only",
    "approved_for_model_evaluation",
    "approved_for_training",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def key(row: dict[str, Any]) -> str:
    return f"{row.get('head')}::{row.get('benchmark_name')}"


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in HEX_DIGITS for char in text)


def build_template(plan_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in plan_rows:
        head = row.get("head")
        benchmark_name = row.get("benchmark_name")
        slug = str(benchmark_name or "benchmark").lower().replace("/", "_").replace(" ", "_").replace("-", "_")
        rows.append({
            "head": head,
            "benchmark_name": benchmark_name,
            "dataset_version": "",
            "license_review_status": "not_reviewed",
            "local_dataset_uri": f"cache/advanced_features/benchmarks/{slug}/dataset.jsonl",
            "dataset_sha256": "",
            "split_definition_uri": f"cache/advanced_features/benchmarks/{slug}/split_definition.json",
            "split_sha256": "",
            "scorecard_uri": f"cache/advanced_features/benchmarks/{slug}/scorecard.json",
            "scorecard_sha256": "",
            "metric_report_uri": f"cache/advanced_features/benchmarks/{slug}/metric_report.json",
            "metric_sha256": "",
            "leakage_check_status": "not_run",
            "reviewer": "",
            "reviewed_at": "",
            "notes": "Fill only with real local benchmark dataset/split/scorecard/metric artifacts. Do not use benchmark rows as KWB wet-lab labels.",
        })
    return rows


def validate_artifact(row: dict[str, Any], path_key: str, hash_key: str) -> list[str]:
    errors = []
    path = resolve_path(row.get(path_key))
    expected_hash = row.get(hash_key)
    if not path or not path.exists():
        errors.append(f"{path_key}_missing")
    if not is_sha256_hex(expected_hash):
        errors.append(f"{hash_key}_missing_or_invalid")
    elif path and path.exists() and sha256(path) != str(expected_hash).lower():
        errors.append(f"{hash_key}_mismatch")
    return errors


def validate_intake_row(row: dict[str, Any], expected_keys: set[str]) -> list[str]:
    errors: list[str] = []
    if key(row) not in expected_keys:
        errors.append("benchmark_not_in_acquisition_plan")
    if not row.get("dataset_version"):
        errors.append("dataset_version_missing")
    if row.get("license_review_status") not in APPROVED_LICENSE_STATUSES:
        errors.append("license_review_not_approved")
    if row.get("leakage_check_status") != "passed":
        errors.append("leakage_check_not_passed")
    if not row.get("reviewer"):
        errors.append("reviewer_missing")
    if not row.get("reviewed_at"):
        errors.append("reviewed_at_missing")
    errors.extend(validate_artifact(row, "local_dataset_uri", "dataset_sha256"))
    errors.extend(validate_artifact(row, "split_definition_uri", "split_sha256"))
    errors.extend(validate_artifact(row, "scorecard_uri", "scorecard_sha256"))
    errors.extend(validate_artifact(row, "metric_report_uri", "metric_sha256"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply benchmark score cache intake")
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    plan_rows = load_jsonl(args.plan)
    intake_rows = load_jsonl(args.intake)
    expected_keys = {key(row) for row in plan_rows}
    if not args.template.exists():
        write_jsonl(args.template, build_template(plan_rows))
    if not args.intake.exists():
        write_jsonl(args.intake, [])

    accepted: dict[str, dict[str, Any]] = {}
    rejected = []
    counts: Counter[str] = Counter()
    seen = set()
    for row in intake_rows:
        row_key = key(row)
        errors = []
        if row_key in seen:
            errors.append("duplicate_benchmark_row")
        seen.add(row_key)
        errors.extend(validate_intake_row(row, expected_keys))
        if errors:
            counts.update(errors)
            rejected.append({"head": row.get("head"), "benchmark_name": row.get("benchmark_name"), "errors": errors})
            continue
        accepted[row_key] = row

    manifest_rows = []
    for plan_row in plan_rows:
        row_key = key(plan_row)
        intake = accepted.get(row_key)
        if intake:
            manifest_rows.append({
                "head": plan_row.get("head"),
                "benchmark_name": plan_row.get("benchmark_name"),
                "status": "present",
                "dataset_version": intake.get("dataset_version"),
                "license_review_status": intake.get("license_review_status"),
                "local_dataset_uri": intake.get("local_dataset_uri"),
                "dataset_sha256": str(intake.get("dataset_sha256")).lower(),
                "split_definition_uri": intake.get("split_definition_uri"),
                "split_sha256": str(intake.get("split_sha256")).lower(),
                "scorecard_uri": intake.get("scorecard_uri"),
                "scorecard_sha256": str(intake.get("scorecard_sha256")).lower(),
                "metric_report_uri": intake.get("metric_report_uri"),
                "metric_sha256": str(intake.get("metric_sha256")).lower(),
                "leakage_check_status": intake.get("leakage_check_status"),
            })
        else:
            manifest_rows.append({
                "head": plan_row.get("head"),
                "benchmark_name": plan_row.get("benchmark_name"),
                "status": "missing",
            })

    ready = bool(plan_rows) and len(accepted) == len(plan_rows) and not rejected
    manifest = {
        "manifest_id": "kwb_benchmark_score_cache_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "ready" if ready else "not_configured",
        "expected_benchmarks": len(plan_rows),
        "accepted_benchmarks": len(accepted),
        "rows": manifest_rows,
        "safe_for_model_claim": False,
        "policy": "Benchmark cache accepts only local dataset/split/scorecard/metric artifacts with checksums and license review. Benchmark data must not be used as KWB wet-lab labels.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "plan_rows": len(plan_rows),
        "intake_rows": len(intake_rows),
        "accepted_rows": len(accepted),
        "rejected_rows": len(rejected),
        "missing_rows": len(plan_rows) - len(accepted),
        "ready_to_validate_cache": ready,
        "template": str(args.template.relative_to(AI_ROOT) if args.template.is_absolute() else args.template),
        "intake": str(args.intake.relative_to(AI_ROOT) if args.intake.is_absolute() else args.intake),
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "error_counts": dict(counts),
        "rejected": rejected[:200],
        "safe_for_model_claim": False,
        "policy": manifest["policy"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "accepted_rows": report["accepted_rows"],
        "rejected_rows": report["rejected_rows"],
        "missing_rows": report["missing_rows"],
        "ready_to_validate_cache": report["ready_to_validate_cache"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
