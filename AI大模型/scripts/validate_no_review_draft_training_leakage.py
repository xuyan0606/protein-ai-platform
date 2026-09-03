#!/usr/bin/env python3
"""Validate that review-draft artifacts do not leak into training/intake paths."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "no_review_draft_training_leakage_validation_report.json"

SCANNED_JSONL = {
    "strict_supervised_training": "datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl",
    "claim_eligible_supervised": "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
    "strict_msa_site_features": "datasets/curated/enzyme_mutation_strict_msa_site_features.jsonl",
    "wet_lab_feedback_preflight": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
    "wet_lab_feedback_apply_plan": "datasets/feedback/wet_lab_mutant_library_feedback_intake_apply_plan.jsonl",
    "fireprot_reviewed_import_candidates": "datasets/curation/fireprot_reviewed_import_candidates.jsonl",
}

REQUIRED_REPORTS = {
    "review_draft_formal_boundary": "reports/review_draft_formal_boundary_validation_report.json",
    "repaired_supervised": "reports/repaired_supervised_table_report.json",
    "label_provenance": "reports/label_provenance_audit_report.json",
    "strict_msa": "reports/strict_msa_site_feature_report.json",
    "wet_lab_preflight": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "wet_lab_apply_plan": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
    "fireprot_reviewed_import": "reports/fireprot_reviewed_import_candidate_report.json",
}

LEAK_MARKERS = ("review_draft", "draft_policy", ".review_draft", "REVIEW_DRAFT")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL row: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(row)
    return rows


def contains_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(marker in value for marker in LEAK_MARKERS) or any(contains_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_marker(item) for item in value)
    if isinstance(value, str):
        return any(marker in value for marker in LEAK_MARKERS)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate no review-draft leakage into training/intake rows")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    scanned_files: dict[str, dict[str, Any]] = {}
    reports = {name: load_json(AI_ROOT / rel) for name, rel in REQUIRED_REPORTS.items()}

    boundary = reports["review_draft_formal_boundary"]
    if boundary.get("success") is not True:
        failures.append({"check": "review_draft_formal_boundary_success", "observed": boundary.get("success"), "expected": True})
    if boundary.get("draft_rows_counted_as_formal_decisions") != 0:
        failures.append({
            "check": "draft_rows_counted_as_formal_decisions_zero",
            "observed": boundary.get("draft_rows_counted_as_formal_decisions"),
            "expected": 0,
        })

    for name, rel_path in SCANNED_JSONL.items():
        path = AI_ROOT / rel_path
        rows = load_jsonl(path)
        leak_rows = []
        for idx, row in enumerate(rows, start=1):
            if contains_marker(row):
                leak_rows.append(idx)
        if leak_rows:
            failures.append({"check": "no_review_draft_markers_in_training_or_intake_rows", "file": rel_path, "leak_rows": leak_rows[:50], "leak_row_count": len(leak_rows)})
        scanned_files[name] = {
            "path": rel_path,
            "exists": path.exists(),
            "rows": len(rows),
            "leak_row_count": len(leak_rows),
        }

    repaired = reports["repaired_supervised"]
    provenance = reports["label_provenance"]
    strict_msa = reports["strict_msa"]
    wet_lab_preflight = reports["wet_lab_preflight"]
    wet_lab_apply_plan = reports["wet_lab_apply_plan"]
    fireprot_reviewed_import = reports["fireprot_reviewed_import"]

    strict_rows = int(repaired.get("supervised_rows") or 0)
    claim_eligible_rows = int(provenance.get("claim_eligible_rows") or 0)
    strict_msa_rows = int(strict_msa.get("feature_rows") or 0)
    wet_lab_preflight_ready_rows = int(wet_lab_preflight.get("ready_for_feedback_intake_rows") or 0)
    wet_lab_applied_rows = int(wet_lab_apply_plan.get("applied_rows") or 0)
    fireprot_ready_rows = int(fireprot_reviewed_import.get("ready_for_training_import_rows") or 0)

    expected_zero_counts = {
        "strict_rows": strict_rows,
        "claim_eligible_rows": claim_eligible_rows,
        "strict_msa_site_feature_rows": strict_msa_rows,
        "wet_lab_preflight_ready_rows": wet_lab_preflight_ready_rows,
        "wet_lab_applied_rows": wet_lab_applied_rows,
        "fireprot_ready_for_training_import_rows": fireprot_ready_rows,
    }
    for key, observed in expected_zero_counts.items():
        if observed != 0:
            failures.append({"check": f"{key}_remains_zero_without_formal_human_gate", "observed": observed, "expected": 0})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "scanned_files": scanned_files,
        "checked_reports": REQUIRED_REPORTS,
        **expected_zero_counts,
        "review_draft_rows": boundary.get("total_review_draft_rows"),
        "formal_decision_rows": boundary.get("total_formal_decision_rows"),
        "draft_rows_counted_as_formal_decisions": boundary.get("draft_rows_counted_as_formal_decisions"),
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "No .review_draft artifact may feed strict supervised rows, claim-eligible rows, MSA strict rows, wet-lab preflight/apply rows, or external reviewed import rows. Non-zero training intake requires formal human-reviewed gates first.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "strict_rows": strict_rows,
        "claim_eligible_rows": claim_eligible_rows,
        "review_draft_rows": report["review_draft_rows"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
