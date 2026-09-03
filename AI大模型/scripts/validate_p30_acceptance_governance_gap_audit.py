#!/usr/bin/env python3
"""Validate the P30 acceptance and governance gap audit."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKSTREAM = AI_ROOT / "reports" / "workstream_acceptance_gates.json"
LICENSE = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
BIOSECURITY = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"
IP_FTO = AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p30_acceptance_governance_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p30_acceptance_governance_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p30_acceptance_governance_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    workstream = load_json(WORKSTREAM)
    license_report = load_json(LICENSE)
    bio_report = load_json(BIOSECURITY)
    ip_report = load_json(IP_FTO)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(workstream.get("gates") or []) + len(license_report.get("missing_packet_decisions") or [])
    expected_rows += sum(
        1 for record in license_report.get("records") or []
        if record.get("verification_required") is True and record.get("verification_status") != "verified"
    )
    expected_rows += len(bio_report.get("missing_draft_decisions") or [])
    expected_rows += len(ip_report.get("missing_delivery_decisions") or [])

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("workstream_count") != len(workstream.get("gates") or []), failures, "workstream_count_bound", report.get("workstream_count"), len(workstream.get("gates") or []))
    fail_if(report.get("workstream_accepted_count") != 0, failures, "workstream_accepted_count_zero", report.get("workstream_accepted_count"), 0)
    fail_if(report.get("license_missing_decision_count") != len(license_report.get("missing_packet_decisions") or []), failures, "license_missing_count_bound", report.get("license_missing_decision_count"), len(license_report.get("missing_packet_decisions") or []))
    fail_if(report.get("biosecurity_missing_decision_count") != len(bio_report.get("missing_draft_decisions") or []), failures, "biosecurity_missing_count_bound", report.get("biosecurity_missing_decision_count"), len(bio_report.get("missing_draft_decisions") or []))
    fail_if(report.get("ip_fto_missing_delivery_decision_count") != len(ip_report.get("missing_delivery_decisions") or []), failures, "ip_fto_missing_count_bound", report.get("ip_fto_missing_delivery_decision_count"), len(ip_report.get("missing_delivery_decisions") or []))

    allowed_types = {
        "workstream_human_acceptance",
        "external_license_or_customer_delivery_decision",
        "external_license_verification",
        "biosecurity_ordering_decision",
        "sequence_ip_fto_delivery_decision",
    }
    for idx, row in enumerate(audit_rows):
        fail_if(row.get("gap_type") not in allowed_types, failures, "gap_type_allowed", {"index": idx, "observed": row.get("gap_type")}, sorted(allowed_types))
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if row.get("gap_type") == "workstream_human_acceptance":
            fail_if(row.get("accepted") is not False, failures, "workstream_accepted_false", {"index": idx, "observed": row.get("accepted")}, False)
        if row.get("gap_type") == "external_license_verification":
            fail_if(row.get("verification_status") == "verified", failures, "license_verification_not_verified", {"index": idx, "observed": row.get("verification_status")}, "not verified")

    expected_counts = dict(sorted(Counter(row.get("gap_type") for row in audit_rows).items()))
    fail_if(report.get("gap_type_counts") != expected_counts, failures, "gap_type_counts_bound", report.get("gap_type_counts"), expected_counts)
    for field in ("customer_delivery_ready", "biosecurity_ready_for_ordering", "training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "gap_type_counts": expected_counts,
        "failures": failures,
        "customer_delivery_ready": False,
        "biosecurity_ready_for_ordering": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P30 acceptance and governance gaps remain blocking and do not authorize delivery or release.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "gap_type_counts": validation["gap_type_counts"],
        "failures": len(failures),
        "customer_delivery_ready": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
