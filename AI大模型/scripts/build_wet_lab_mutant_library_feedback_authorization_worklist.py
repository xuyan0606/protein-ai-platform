#!/usr/bin/env python3
"""Build QC-aware authorization worklist for wet-lab mutant-library feedback."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
QC_MATRIX = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_qc_matrix.jsonl"
AUTH_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
AUTH_DECISIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def qc_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for qc_row in rows:
        for metric in qc_row.get("metric_rows") or []:
            cid = str(metric.get("feedback_candidate_id") or "")
            if not cid:
                continue
            result[cid] = {
                "qc_matrix_id": qc_row.get("qc_matrix_id"),
                "property_call": qc_row.get("property_call"),
                "review_priority": qc_row.get("review_priority"),
                "conflicting_property_signal": qc_row.get("conflicting_property_signal"),
                "variant_outcome_counts": qc_row.get("outcome_counts"),
                "variant_metric_classes": qc_row.get("metric_classes"),
                "variant_ratio_min": qc_row.get("ratio_min"),
                "variant_ratio_max": qc_row.get("ratio_max"),
                "variant_ratio_range": qc_row.get("ratio_range"),
                "metric_class": metric.get("metric_class"),
            }
    return result


def validation_records_by_candidate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in report.get("records") or []
        if isinstance(row, dict) and row.get("feedback_candidate_id")
    }


def decision_by_candidate(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in decisions
        if row.get("feedback_candidate_id")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization worklist")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--qc-matrix", type=Path, default=QC_MATRIX)
    parser.add_argument("--authorization-template", type=Path, default=AUTH_TEMPLATE)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-report", type=Path, default=AUTH_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    numeric_candidates = [row for row in candidates if row.get("numeric_training_candidate") is True]
    qc_lookup = qc_by_candidate(load_jsonl(args.qc_matrix))
    template_lookup = {
        str(row.get("feedback_candidate_id")): row
        for row in load_jsonl(args.authorization_template)
        if row.get("feedback_candidate_id")
    }
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    auth_report = load_json(args.authorization_report)
    validation_lookup = validation_records_by_candidate(auth_report)

    rows: list[dict[str, Any]] = []
    for candidate in sorted(
        numeric_candidates,
        key=lambda row: (str(row.get("variant")), str(row.get("metric_name")), str(row.get("feedback_candidate_id"))),
    ):
        cid = str(candidate.get("feedback_candidate_id"))
        qc = qc_lookup.get(cid, {})
        template = template_lookup.get(cid, {})
        decision = decisions.get(cid)
        validation = validation_lookup.get(cid, {})
        authorized = bool(validation.get("authorized_for_feedback_intake"))
        decision_present = decision is not None
        worklist_status = "authorized_ready_for_preflight" if authorized else "blocked_waiting_for_authorization"
        if decision_present and not authorized:
            worklist_status = "decision_present_but_not_authorized"
        rows.append({
            "authorization_worklist_id": f"wetlab-mutlib-auth-worklist-{cid.replace('wetlab-mutlib-', '')}",
            "feedback_candidate_id": cid,
            "authorization_template_id": template.get("authorization_id"),
            "source_project": candidate.get("source_project"),
            "variant": candidate.get("variant"),
            "mutation_set": candidate.get("mutation_set"),
            "metric_name": candidate.get("metric_name"),
            "metric_class": qc.get("metric_class"),
            "assay_type": candidate.get("assay_type"),
            "raw_value_numeric": candidate.get("raw_value_numeric"),
            "control_value_numeric": candidate.get("control_value_numeric"),
            "vs_control_ratio": candidate.get("vs_control_ratio"),
            "outcome_candidate": candidate.get("outcome_candidate"),
            "confidence_tier": candidate.get("confidence_tier"),
            "batch_id": candidate.get("batch_id"),
            "sample_id": candidate.get("sample_id"),
            "source_file": candidate.get("source_file"),
            "source_row_index": candidate.get("source_row_index"),
            "qc_context": {
                "qc_matrix_id": qc.get("qc_matrix_id"),
                "property_call": qc.get("property_call"),
                "review_priority": qc.get("review_priority"),
                "conflicting_property_signal": bool(qc.get("conflicting_property_signal")),
                "variant_outcome_counts": qc.get("variant_outcome_counts"),
                "variant_metric_classes": qc.get("variant_metric_classes"),
                "variant_ratio_min": qc.get("variant_ratio_min"),
                "variant_ratio_max": qc.get("variant_ratio_max"),
                "variant_ratio_range": qc.get("variant_ratio_range"),
            },
            "authorization_decision_present": decision_present,
            "authorization_decision": decision.get("authorization_decision") if decision else None,
            "authorization_valid": bool(validation.get("valid")),
            "authorized_for_feedback_intake": authorized,
            "authorization_errors": validation.get("errors") or [],
            "worklist_status": worklist_status,
            "required_human_actions": [
                "copy the matching template row into wet_lab_mutant_library_feedback_authorizations.jsonl",
                "review source trace, numbering, unit/condition, batch/control and replicate/QC policy",
                "authorize/reject this metric row independently from other properties of the same variant",
                "rerun validate_wet_lab_mutant_library_feedback_authorizations.py",
            ],
            "ready_for_feedback_intake": False,
            "claim_eligible_now": False,
            "policy": "Authorization worklist only; not an authorization, not preflight, and not a training label.",
        })

    priority_counts = Counter((row.get("qc_context") or {}).get("review_priority") for row in rows)
    status_counts = Counter(row["worklist_status"] for row in rows)
    critical_rows = [row for row in rows if (row.get("qc_context") or {}).get("review_priority") == "critical_tradeoff_review"]
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "numeric_training_candidate_rows": len(numeric_candidates),
        "authorization_worklist_rows": len(rows),
        "decision_present_rows": sum(1 for row in rows if row["authorization_decision_present"]),
        "authorized_rows": sum(1 for row in rows if row["authorized_for_feedback_intake"]),
        "blocked_waiting_for_authorization_rows": status_counts.get("blocked_waiting_for_authorization", 0),
        "critical_tradeoff_worklist_rows": len(critical_rows),
        "critical_tradeoff_feedback_candidate_ids": [row["feedback_candidate_id"] for row in critical_rows],
        "priority_counts": dict(sorted(priority_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "output": str(args.output),
        "policy": "QC-aware worklist makes review priority explicit but never grants authorization or writes feedback intake.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorization_worklist_rows": report["authorization_worklist_rows"],
        "authorized_rows": report["authorized_rows"],
        "critical_tradeoff_worklist_rows": report["critical_tradeoff_worklist_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
