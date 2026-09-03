#!/usr/bin/env python3
"""Build wet-lab feedback preflight rows from validated human authorizations."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def assay_condition(candidate: dict[str, Any]) -> dict[str, Any]:
    metric = str(candidate.get("metric_name") or "")
    condition: dict[str, Any] = {
        "metric": metric,
        "batch_id": candidate.get("batch_id"),
        "sample_id": candidate.get("sample_id"),
        "control_sample_id": candidate.get("control_sample_id"),
        "source_project": candidate.get("source_project"),
    }
    if "pH6.0" in metric or "pH6" in metric:
        condition["ph"] = 6.0
    elif "pH4.8" in metric:
        condition["ph"] = 4.8
    if "85C" in metric or "85°C" in metric:
        condition["temperature_c"] = 85
        condition["duration_min"] = 3
    if "pH4.8/pH6.0" in metric:
        condition["comparison_condition"] = {"ph": 6.0}
    return condition


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab mutant library feedback preflight")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--authorization-report", type=Path, default=AUTH_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    auth_report = load_json(args.authorization_report)
    candidate_by_id = {str(row.get("feedback_candidate_id")): row for row in candidates}
    authorized_ids = set(auth_report.get("authorized_feedback_candidate_ids") or [])

    rows: list[dict[str, Any]] = []
    skipped_missing = 0
    for cid in sorted(authorized_ids):
        candidate = candidate_by_id.get(cid)
        if not candidate:
            skipped_missing += 1
            continue
        mutation = "+".join(candidate.get("mutation_set") or [])
        if not mutation:
            skipped_missing += 1
            continue
        assay_type = candidate.get("assay_type")
        row = {
            "preflight_feedback_id": f"wetlab-mutlib-preflight-{cid.replace('wetlab-mutlib-', '')}",
            "feedback_candidate_id": cid,
            "proposed_feedback_id": f"wetlab-mutlib-{candidate.get('source_project', '').lower()}-{mutation.lower()}-{candidate.get('measurement_id')}",
            "enzyme_id": "Venus-15B-alpha-amylase-AAP-noCa" if candidate.get("source_project") == "15B" else None,
            "project_id": f"wetlab-mutlib-{str(candidate.get('source_project')).lower()}",
            "mutation": mutation,
            "mutation_set": candidate.get("mutation_set"),
            "canonical_position": int(str(candidate["mutation_set"][0])[1:-1]) if len(candidate.get("mutation_set") or []) == 1 else None,
            "numbering_verified": bool(candidate.get("numbering_verified")),
            "numbering_verification_basis": candidate.get("numbering_verification_basis"),
            "assay_type": assay_type,
            "assay_condition": assay_condition(candidate),
            "outcome": candidate.get("outcome_candidate"),
            "data_granularity": candidate.get("data_granularity"),
            "quantitative_assay_available": True,
            "plate_level_available": False,
            "activity_relative_to_wt": candidate.get("activity_relative_to_wt") if assay_type == "activity" else None,
            "stability_relative_to_wt": candidate.get("stability_relative_to_wt") if assay_type == "stability" else None,
            "raw_value_numeric": candidate.get("raw_value_numeric"),
            "control_value_numeric": candidate.get("control_value_numeric"),
            "vs_control_ratio": candidate.get("vs_control_ratio"),
            "vs_control_delta": candidate.get("vs_control_delta"),
            "vs_control_pct_change": candidate.get("vs_control_pct_change"),
            "source": "kwb_wet_lab",
            "source_project": candidate.get("source_project"),
            "source_file": candidate.get("source_file"),
            "source_file_sha256": candidate.get("source_file_sha256"),
            "source_row_index": candidate.get("source_row_index"),
            "measurement_id": candidate.get("measurement_id"),
            "batch_id": candidate.get("batch_id"),
            "sample_id": candidate.get("sample_id"),
            "control_sample_id": candidate.get("control_sample_id"),
            "ready_for_feedback_intake": False,
            "ready_for_training_import": False,
            "claim_eligible_now": False,
            "remaining_blockers": [
                "separate_apply_to_experiment_feedback_local_not_executed",
                "plate_or_replicate_level_qc_not_integrated",
                "model_quality_release_gate_not_approved",
            ],
            "policy": "Preflight only; not appended to experiment_feedback.local.jsonl and not a training label.",
        }
        rows.append(row)

    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "authorization_report": str(args.authorization_report),
        "output": str(args.output),
        "candidate_rows": len(candidates),
        "authorized_candidate_rows": len(authorized_ids),
        "preflight_rows": len(rows),
        "skipped_authorized_candidate_rows": skipped_missing,
        "ready_for_feedback_intake_rows": 0,
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "policy": "Preflight rows preserve approved wet-lab evidence mapping but never modify training or feedback intake tables automatically.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorized_candidate_rows": report["authorized_candidate_rows"],
        "preflight_rows": report["preflight_rows"],
        "ready_for_feedback_intake_rows": report["ready_for_feedback_intake_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
