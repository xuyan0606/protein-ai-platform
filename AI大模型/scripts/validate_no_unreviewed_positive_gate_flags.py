#!/usr/bin/env python3
"""Validate that generated datasets contain no unreviewed positive gate flags."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "no_unreviewed_positive_gate_flags_validation_report.json"

POSITIVE_GATE_FIELDS = {
    "approved_for_plate_intake",
    "approved_for_feedback_intake",
    "allow_append_to_experiment_feedback_local",
    "authorized_for_feedback_intake",
    "claim_eligible",
    "claim_eligible_now",
    "completion_ready",
    "ready_for_ddg_execution",
    "ready_for_feedback_intake",
    "ready_for_model_claim",
    "ready_for_training_import",
    "release_ready",
    "safe_for_customer_delivery",
    "safe_for_model_claim",
    "safe_for_training_import",
    "training_eligible",
}

ALLOWED_TRUE_FIELDS: dict[str, set[str]] = {
    "datasets/feedback/wet_lab_mutant_library_feedback_authorization_gap_matrix.jsonl": {
        "authorized_for_feedback_intake"
    },
    "datasets/feedback/wet_lab_mutant_library_feedback_authorization_operator_receipts.jsonl": {
        "authorized_for_feedback_intake"
    },
    "datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl": {
        "authorized_for_feedback_intake"
    },
    "datasets/feedback/activity_risk_label_replicate_decisions.jsonl": {
        "ready_for_training_import",
        "safe_for_training_import",
    },
    "datasets/training/activity_risk_training_import_labels.jsonl": {
        "ready_for_training_import",
        "safe_for_training_import",
    },
    "datasets/governance/ddg_local_runtime_discovery_candidates.jsonl": {
        "ready_for_ddg_execution"
    },
    "datasets/governance/next_unlock_completion_status.jsonl": {"completion_ready"},
    "datasets/governance/next_unlock_operator_index.jsonl": {"completion_ready"},
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def row_id(row: dict[str, Any]) -> Any:
    for field in (
        "record_id",
        "backlog_id",
        "authorization_id",
        "feedback_candidate_id",
        "candidate_id",
        "workstream_id",
        "packet_id",
        "id",
    ):
        if row.get(field) not in (None, ""):
            return row.get(field)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate no positive gate flags in generated datasets")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    scanned_files: dict[str, dict[str, Any]] = {}
    true_field_counts: dict[str, int] = {}
    allowlisted_true_field_counts: dict[str, int] = {}

    for path in sorted((AI_ROOT / "datasets").rglob("*.jsonl")):
        rel_path = str(path.relative_to(AI_ROOT))
        rows = load_jsonl(path)
        allowed_fields = ALLOWED_TRUE_FIELDS.get(rel_path, set())
        file_true_rows = 0
        file_true_fields: dict[str, int] = {}
        for idx, row in enumerate(rows, start=1):
            for field in sorted(POSITIVE_GATE_FIELDS & row.keys()):
                if row.get(field) is True:
                    true_field_counts[field] = true_field_counts.get(field, 0) + 1
                    file_true_fields[field] = file_true_fields.get(field, 0) + 1
                    file_true_rows += 1
                    if field in allowed_fields:
                        allowlisted_true_field_counts[field] = allowlisted_true_field_counts.get(field, 0) + 1
                    else:
                        failures.append({
                            "check": "no_unreviewed_positive_gate_flags",
                            "file": rel_path,
                            "row": idx,
                            "row_id": row_id(row),
                            "field": field,
                            "observed": True,
                            "expected": "false unless explicitly allowlisted after formal human gate",
                        })
        scanned_files[rel_path] = {
            "rows": len(rows),
            "positive_gate_true_rows": file_true_rows,
            "positive_gate_true_fields": file_true_fields,
            "allowlisted_true_fields": sorted(allowed_fields),
        }

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "scanned_file_count": len(scanned_files),
        "scanned_files": scanned_files,
        "positive_gate_fields": sorted(POSITIVE_GATE_FIELDS),
        "allowlisted_true_fields": {path: sorted(fields) for path, fields in ALLOWED_TRUE_FIELDS.items()},
        "true_field_counts": dict(sorted(true_field_counts.items())),
        "allowlisted_true_field_counts": dict(sorted(allowlisted_true_field_counts.items())),
        "positive_gate_true_count": sum(true_field_counts.values()),
        "disallowed_positive_gate_true_count": len(failures),
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Generated datasets may not carry positive gate booleans unless a file/field allowlist is added after formal human-reviewed evidence is validated.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "scanned_file_count": report["scanned_file_count"],
        "positive_gate_true_count": report["positive_gate_true_count"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
