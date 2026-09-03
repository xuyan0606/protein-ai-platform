#!/usr/bin/env python3
"""Build a source-bound P30 acceptance and governance gap audit."""

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
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p30_acceptance_governance_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p30_acceptance_governance_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def common(gap_id: str, gap_type: str, source_report: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": gap_id,
        "gap_type": gap_type,
        "source_report": source_report,
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Audit-only governance gap row; does not create acceptance, license, biosecurity, IP/FTO, delivery, release, or production authorization.",
    }


def main() -> int:
    workstream = load_json(WORKSTREAM)
    license_report = load_json(LICENSE)
    bio_report = load_json(BIOSECURITY)
    ip_report = load_json(IP_FTO)
    rows: list[dict[str, Any]] = []

    for gate in workstream.get("gates") or []:
        stream = str(gate.get("stream"))
        row = common(
            f"p30-workstream-acceptance::{stream}",
            "workstream_human_acceptance",
            "reports/workstream_acceptance_gates.json",
            {
                "stream": stream,
                "technical_ready": gate.get("technical_ready"),
                "human_accepted": gate.get("human_accepted"),
                "accepted": gate.get("accepted"),
                "acceptance_requires": gate.get("acceptance_requires"),
            },
            "human acceptance decision is missing or not accepted",
        )
        row.update({
            "stream": stream,
            "human_accepted": gate.get("human_accepted") is True,
            "accepted": gate.get("accepted") is True,
        })
        rows.append(row)

    missing_license = license_report.get("missing_packet_decisions") or []
    for item_id in missing_license:
        rows.append(common(
            f"p30-license-decision::{item_id}",
            "external_license_or_customer_delivery_decision",
            "reports/external_license_review_decision_validation_report.json",
            {"review_item_id": item_id, "decision_present": False},
            "license/customer-delivery decision is missing",
        ) | {"review_item_id": item_id, "decision_present": False})

    for record in license_report.get("records") or []:
        if record.get("verification_required") is True and record.get("verification_status") != "verified":
            rows.append(common(
                f"p30-license-verification::{record.get('review_item_id')}",
                "external_license_verification",
                "reports/external_license_review_decision_validation_report.json",
                {
                    "review_item_id": record.get("review_item_id"),
                    "authorization_status": record.get("authorization_status"),
                    "verification_required": record.get("verification_required"),
                    "verification_status": record.get("verification_status"),
                    "approved_for_customer_delivery": record.get("approved_for_customer_delivery"),
                },
                "self-attested or unverified license scope cannot open customer delivery",
            ) | {
                "review_item_id": record.get("review_item_id"),
                "decision_present": True,
                "verification_status": record.get("verification_status"),
            })

    for item_id in bio_report.get("missing_draft_decisions") or []:
        rows.append(common(
            f"p30-biosecurity::{item_id}",
            "biosecurity_ordering_decision",
            "reports/biosecurity_screening_decision_validation_report.json",
            {"screening_id": item_id, "decision_present": False},
            "biosecurity/ordering decision is missing",
        ) | {"screening_id": item_id, "decision_present": False})

    for item_id in ip_report.get("missing_delivery_decisions") or []:
        rows.append(common(
            f"p30-ip-fto::{item_id}",
            "sequence_ip_fto_delivery_decision",
            "reports/sequence_ip_fto_decision_validation_report.json",
            {"delivery_decision_id": item_id, "decision_present": False},
            "sequence IP/FTO delivery decision is missing",
        ) | {"delivery_decision_id": item_id, "decision_present": False})

    gap_type_counts = dict(sorted(Counter(row["gap_type"] for row in rows).items()))
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "gap_type_counts": gap_type_counts,
        "workstream_count": len(workstream.get("gates") or []),
        "workstream_accepted_count": sum(1 for gate in workstream.get("gates") or [] if gate.get("accepted") is True),
        "license_missing_decision_count": len(missing_license),
        "license_unverified_decision_count": sum(
            1 for record in license_report.get("records") or []
            if record.get("verification_required") is True and record.get("verification_status") != "verified"
        ),
        "biosecurity_missing_decision_count": len(bio_report.get("missing_draft_decisions") or []),
        "ip_fto_missing_delivery_decision_count": len(ip_report.get("missing_delivery_decisions") or []),
        "customer_delivery_ready": False,
        "biosecurity_ready_for_ordering": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p30_acceptance_governance_gap_audit.jsonl",
        "policy": "P30 acceptance/governance audit only. Self-attested license decisions, missing biosecurity decisions, missing IP/FTO decisions, and unaccepted workstreams do not authorize delivery or release.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "gap_type_counts": report["gap_type_counts"],
        "workstream_accepted_count": report["workstream_accepted_count"],
        "customer_delivery_ready": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
