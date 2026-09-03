#!/usr/bin/env python3
"""Validate the shared governance review bundle fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = AI_ROOT / "datasets" / "governance" / "governance_review_bundle.jsonl"
STATUS_OUT = AI_ROOT / "datasets" / "governance" / "governance_review_bundle_status.jsonl"
REPORT = AI_ROOT / "reports" / "governance_review_bundle_report.json"
REPORT_OUT = AI_ROOT / "reports" / "governance_review_bundle_validation_report.json"

LICENSE_PACKETS = AI_ROOT / "datasets" / "governance" / "external_license_review_packets.jsonl"
BIOSECURITY_DRAFTS = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_drafts.jsonl"
SEQUENCE_PACKET_DIR = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets"
OPERATOR_QUEUE = AI_ROOT / "datasets" / "governance" / "operator_review_action_queue.jsonl"
WORKSTREAM_GATES = AI_ROOT / "reports" / "workstream_acceptance_gates.json"

EXPECTED_WORKSTREAMS = {
    "external_license_review",
    "biosecurity_screening",
    "sequence_ip_fto",
    "operator_review_actions",
    "workstream_acceptance",
}
VALID_STATUSES = {
    "open_blocked_waiting_for_human_decision",
    "blocked_invalid_human_decision",
    "reviewed_valid_but_not_approved",
    "reviewed_completion_ready",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def expected_counts() -> dict[str, int]:
    sequence_rows = 0
    if SEQUENCE_PACKET_DIR.exists():
        for path in sorted(SEQUENCE_PACKET_DIR.glob("*.jsonl")):
            sequence_rows += len(load_jsonl(path))
    return {
        "external_license_review": len(load_jsonl(LICENSE_PACKETS)),
        "biosecurity_screening": len(load_jsonl(BIOSECURITY_DRAFTS)),
        "sequence_ip_fto": sequence_rows,
        "operator_review_actions": len(load_jsonl(OPERATOR_QUEUE)),
        "workstream_acceptance": len(load_json(WORKSTREAM_GATES).get("gates", [])),
    }


def path_exists(rel_path: Any) -> bool:
    if not isinstance(rel_path, str) or not rel_path:
        return False
    path = Path(rel_path)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def missing(value: Any) -> bool:
    return value is None or value == ""


def validate_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "bundle_id",
        "workstream",
        "priority",
        "review_order",
        "source_artifact",
        "source_row_id",
        "decision_input",
        "template",
        "validator_command",
        "validator_report",
        "reviewer_role",
        "required_human_decision",
        "required_fields",
        "current_status",
        "human_review_required",
        "no_auto_approval",
        "completion_ready",
        "blocking_claims",
        "operator_next_step",
        "policy",
    ]
    for field in required:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")
    if row.get("workstream") not in EXPECTED_WORKSTREAMS:
        errors.append("invalid_workstream")
    if row.get("current_status") not in VALID_STATUSES:
        errors.append("invalid_current_status")
    if row.get("human_review_required") is not True:
        errors.append("human_review_required_not_true")
    if row.get("no_auto_approval") is not True:
        errors.append("no_auto_approval_not_true")
    if not isinstance(row.get("required_fields"), list) or not row.get("required_fields"):
        errors.append("invalid_required_fields")
    if not isinstance(row.get("blocking_claims"), list) or not row.get("blocking_claims"):
        errors.append("invalid_blocking_claims")
    if not path_exists(row.get("source_artifact")):
        errors.append("missing_source_artifact")
    if not path_exists(row.get("decision_input")):
        errors.append("missing_decision_input")
    if not path_exists(row.get("template")):
        errors.append("missing_template")
    if not path_exists(row.get("validator_report")):
        errors.append("missing_validator_report")
    if row.get("completion_ready") != (row.get("current_status") == "reviewed_completion_ready"):
        errors.append("completion_ready_status_mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate governance review bundle")
    parser.add_argument("--bundle", type=Path, default=BUNDLE)
    parser.add_argument("--status", type=Path, default=STATUS_OUT)
    parser.add_argument("--bundle-report", type=Path, default=REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.bundle)
    bundle_report = load_json(args.bundle_report)
    expected = expected_counts()
    counts = Counter(str(row.get("workstream")) for row in rows)
    errors = Counter()
    status_rows = []
    seen = set()
    duplicates = set()
    for row in rows:
        bundle_id = str(row.get("bundle_id"))
        if bundle_id in seen:
            duplicates.add(bundle_id)
        seen.add(bundle_id)
        row_errors = validate_row(row)
        errors.update(row_errors)
        status_rows.append({
            "bundle_id": row.get("bundle_id"),
            "workstream": row.get("workstream"),
            "source_row_id": row.get("source_row_id"),
            "current_status": row.get("current_status"),
            "valid": not row_errors,
            "completion_ready": bool(row.get("completion_ready")) and not row_errors,
            "errors": row_errors,
            "policy": "Status only; not a human approval.",
        })
    if duplicates:
        errors.update({"duplicate_bundle_id": len(duplicates)})
        for row in status_rows:
            if row["bundle_id"] in duplicates:
                row["valid"] = False
                row["completion_ready"] = False
                row["errors"].append("duplicate_bundle_id")
    for workstream, expected_count in expected.items():
        if counts.get(workstream, 0) != expected_count:
            errors.update({f"{workstream}_count_mismatch": 1})
    if set(counts) - EXPECTED_WORKSTREAMS:
        errors.update({"unexpected_workstream": len(set(counts) - EXPECTED_WORKSTREAMS)})
    if bundle_report.get("bundle_rows") != len(rows):
        errors.update({"report_bundle_rows_mismatch": 1})
    if bundle_report.get("open_rows") != sum(1 for row in rows if not row.get("completion_ready")):
        errors.update({"report_open_rows_mismatch": 1})
    if bundle_report.get("safe_for_model_claim") is not False:
        errors.update({"bundle_report_safe_for_model_claim_not_false": 1})
    if bundle_report.get("release_ready") is not False:
        errors.update({"bundle_report_release_ready_not_false": 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    completion_ready_rows = sum(1 for row in status_rows if row["completion_ready"])
    open_rows = len(rows) - completion_ready_rows
    report = {
        "local_only": True,
        "online_deployment": False,
        "bundle": rel(args.bundle),
        "status": rel(args.status),
        "source_bundle_report": rel(args.bundle_report),
        "bundle_rows": len(rows),
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "completion_ready_rows": completion_ready_rows,
        "open_rows": open_rows,
        "expected_counts": expected,
        "observed_counts": dict(sorted(counts.items())),
        "all_source_rows_covered": all(counts.get(workstream, 0) == count for workstream, count in expected.items()),
        "all_rows_valid": valid_rows == len(rows) and bool(rows) and not errors,
        "ready": open_rows == 0 and valid_rows == len(rows) and bool(rows) and not errors,
        "safe_for_model_claim": False,
        "release_ready": False,
        "error_counts": dict(errors),
        "records": status_rows[:200],
        "policy": "Validation proves the governance review queue is internally consistent only. It does not approve legal use, FTO, biosecurity ordering, operator completion, workstream acceptance, model claims, release, deployment, or customer delivery.",
    }
    write_jsonl(args.status, status_rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "bundle_rows": report["bundle_rows"],
        "valid_rows": report["valid_rows"],
        "open_rows": report["open_rows"],
        "all_source_rows_covered": report["all_source_rows_covered"],
        "ready": report["ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
