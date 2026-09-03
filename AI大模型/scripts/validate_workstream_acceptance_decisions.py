#!/usr/bin/env python3
"""Validate human workstream acceptance decisions fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "workstream_acceptance_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "workstream_acceptance_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json"

VALID_STREAMS = {
    "external_data_sources",
    "structure_chain_mapping",
    "msa_conservation",
    "plate_feedback",
    "biosecurity_customer_delivery",
    "active_learning",
}
VALID_DECISIONS = {"accepted", "rejected", "blocked", "needs_more_info"}
VALID_SCOPES = {
    "local_feature_production",
    "model_training",
    "model_claim",
    "customer_delivery",
    "experiment_submission",
}

TEMPLATE_ROW = {
    "stream": "external_data_sources",
    "acceptance_decision": "needs_more_info",
    "reviewer": "human-workstream-owner",
    "reviewed_at": "2026-07-27T00:00:00+08:00",
    "evidence_artifacts": ["datasets/governance/external_license_review_decisions.jsonl"],
    "validation_reports": ["reports/external_license_review_decision_validation_report.json"],
    "acceptance_scope": "model_training",
    "accepted_for_model_claim": False,
    "accepted_for_customer_delivery": False,
    "accepted_for_experiment_submission": False,
    "acceptance_note": "template only; copy after the stream is technically ready and human accepted",
    "residual_risks": [],
    "next_action": "complete missing workstream evidence",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def exists_rel(rel: str) -> bool:
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def missing(value: Any) -> bool:
    return value is None or value == ""


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in [
        "stream",
        "acceptance_decision",
        "reviewer",
        "reviewed_at",
        "evidence_artifacts",
        "validation_reports",
        "acceptance_scope",
        "acceptance_note",
    ]:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")
    if row.get("stream") not in VALID_STREAMS:
        errors.append("invalid_stream")
    if row.get("acceptance_decision") not in VALID_DECISIONS:
        errors.append("invalid_acceptance_decision")
    if row.get("acceptance_scope") not in VALID_SCOPES:
        errors.append("invalid_acceptance_scope")
    for field in ["accepted_for_model_claim", "accepted_for_customer_delivery", "accepted_for_experiment_submission"]:
        if field in row and not isinstance(row.get(field), bool):
            errors.append(f"invalid_{field}")
    for field in ["evidence_artifacts", "validation_reports"]:
        value = row.get(field)
        if not isinstance(value, list):
            errors.append(f"invalid_{field}")
            continue
        missing_paths = [path for path in value if not isinstance(path, str) or not exists_rel(path)]
        if missing_paths:
            errors.append(f"missing_{field}_paths")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")
    acceptance_flags = [
        bool(row.get("accepted_for_model_claim")),
        bool(row.get("accepted_for_customer_delivery")),
        bool(row.get("accepted_for_experiment_submission")),
    ]
    if any(acceptance_flags) and row.get("acceptance_decision") != "accepted":
        errors.append("acceptance_flag_without_accepted_decision")
    if row.get("acceptance_decision") == "accepted":
        if not row.get("evidence_artifacts"):
            errors.append("accepted_without_evidence_artifacts")
        if not row.get("validation_reports"):
            errors.append("accepted_without_validation_reports")
        if row.get("residual_risks"):
            errors.append("accepted_with_residual_risks")
    return errors


def stream_decision_sets(records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    decided = sorted(str(item["stream"]) for item in records if item.get("valid"))
    accepted = sorted(str(item["stream"]) for item in records if item.get("accepted"))
    return decided, accepted


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workstream acceptance decisions")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    decisions = load_jsonl(args.input)
    records = []
    errors = Counter()
    seen = set()
    duplicates = set()
    for row in decisions:
        stream = str(row.get("stream"))
        if stream in seen:
            duplicates.add(stream)
        seen.add(stream)
        row_errors = validate(row)
        errors.update(row_errors)
        records.append({
            "stream": row.get("stream"),
            "acceptance_decision": row.get("acceptance_decision"),
            "valid": not row_errors,
            "accepted": row.get("acceptance_decision") == "accepted" and not row_errors,
            "accepted_for_model_claim": bool(row.get("accepted_for_model_claim")) and not row_errors,
            "accepted_for_customer_delivery": bool(row.get("accepted_for_customer_delivery")) and not row_errors,
            "accepted_for_experiment_submission": bool(row.get("accepted_for_experiment_submission")) and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_stream": len(duplicates)})
        for record in records:
            if record["stream"] in duplicates:
                record["valid"] = False
                record["accepted"] = False
                record["accepted_for_model_claim"] = False
                record["accepted_for_customer_delivery"] = False
                record["accepted_for_experiment_submission"] = False
                record["errors"].append("duplicate_stream")

    valid_rows = sum(1 for item in records if item["valid"])
    decided_streams, accepted_streams = stream_decision_sets(records)
    missing_stream_decisions = sorted(VALID_STREAMS - set(decided_streams))
    unaccepted_streams = sorted(VALID_STREAMS - set(accepted_streams))
    report = {
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "expected_streams": sorted(VALID_STREAMS),
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "invalid_rows": len(records) - valid_rows,
        "decided_streams": len(decided_streams),
        "decided_stream_ids": decided_streams,
        "all_streams_decided": len(decided_streams) == len(VALID_STREAMS) and not errors,
        "accepted_streams": len(accepted_streams),
        "accepted_stream_ids": accepted_streams,
        "accepted_for_model_claim_streams": [
            item["stream"] for item in records if item["accepted_for_model_claim"]
        ],
        "accepted_for_customer_delivery_streams": [
            item["stream"] for item in records if item["accepted_for_customer_delivery"]
        ],
        "accepted_for_experiment_submission_streams": [
            item["stream"] for item in records if item["accepted_for_experiment_submission"]
        ],
        "all_streams_accepted": len(accepted_streams) == len(VALID_STREAMS) and not errors,
        "missing_stream_decisions": missing_stream_decisions,
        "unaccepted_streams": unaccepted_streams,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Workstream acceptance requires explicit human acceptance with evidence; technical readiness alone is not acceptance.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "accepted_streams": len(accepted_streams),
        "all_streams_accepted": report["all_streams_accepted"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
