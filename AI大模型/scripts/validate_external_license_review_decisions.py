#!/usr/bin/env python3
"""Validate human/legal license review decisions fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "external_license_review_packets.jsonl"
INPUT = AI_ROOT / "datasets" / "governance" / "external_license_review_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "external_license_review_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"

VALID_TYPES = {"external_data_source", "foreign_tool"}
VALID_DECISIONS = {"approved", "approved_with_conditions", "rejected", "needs_more_info"}
VALID_AUTHORIZATION_SOURCES = {"user_attestation", "contract_or_license", "official_license_text", "internal_policy"}
VALID_AUTHORIZATION_STATUSES = {"self_attested", "pending_verification", "verified", "denied"}
VALID_CAPABILITY_STATUSES = {"allowed", "pending", "denied"}
CAPABILITY_FIELDS = [
    "commercial_evaluation",
    "training_import",
    "customer_delivery",
    "service_hosting",
    "publication",
]

TEMPLATE_ROW = {
    "review_item_id": "data_source:UniProt",
    "item_type": "external_data_source",
    "review_decision": "needs_more_info",
    "reviewer": "human-legal-reviewer",
    "reviewed_at": "2026-07-27T00:00:00+08:00",
    "license_reference": "path-or-url-to-reviewed-license-text",
    "approval_scope": "platform policy permits commercial workflows; component authorization is pending verification",
    "authorization_source": "user_attestation",
    "authorization_status": "pending_verification",
    "verification_required": True,
    "capability_authorizations": {
        "commercial_evaluation": "pending",
        "training_import": "pending",
        "customer_delivery": "pending",
        "service_hosting": "pending",
        "publication": "pending",
    },
    "license_type": None,
    "license_holder": None,
    "contract_reference": None,
    "valid_from": None,
    "valid_until": None,
    "verification_status": "pending_verification",
    "approved_for_training": False,
    "approved_for_local_evaluation": False,
    "approved_for_customer_delivery": False,
    "attribution_text": None,
    "version_or_retrieval_date": None,
    "conditions": [],
    "prohibited_uses": ["representing unverified authorization as verified clearance"],
    "notes": "template only; copy to the local decisions file after human/legal review or user attestation",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def missing(value: Any) -> bool:
    return value is None or value == ""


def validate(row: dict[str, Any], packet_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "review_item_id",
        "item_type",
        "review_decision",
        "reviewer",
        "reviewed_at",
        "license_reference",
        "authorization_source",
        "authorization_status",
        "verification_required",
        "capability_authorizations",
        "approved_for_training",
        "approved_for_local_evaluation",
        "approved_for_customer_delivery",
        "conditions",
        "prohibited_uses",
    ]:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")
    review_item_id = row.get("review_item_id")
    packet = packet_by_id.get(str(review_item_id))
    if not packet:
        errors.append("unknown_review_item_id")
    elif row.get("item_type") != packet.get("item_type"):
        errors.append("item_type_mismatch")
    if row.get("item_type") not in VALID_TYPES:
        errors.append("invalid_item_type")
    if row.get("review_decision") not in VALID_DECISIONS:
        errors.append("invalid_review_decision")
    if row.get("authorization_source") not in VALID_AUTHORIZATION_SOURCES:
        errors.append("invalid_authorization_source")
    if row.get("authorization_status") not in VALID_AUTHORIZATION_STATUSES:
        errors.append("invalid_authorization_status")
    if not isinstance(row.get("verification_required"), bool):
        errors.append("invalid_verification_required")
    if row.get("verification_status") not in VALID_AUTHORIZATION_STATUSES and row.get("verification_status") is not None:
        errors.append("invalid_verification_status")
    capabilities = row.get("capability_authorizations")
    if not isinstance(capabilities, dict):
        errors.append("invalid_capability_authorizations")
        capabilities = {}
    for capability in CAPABILITY_FIELDS:
        if capability not in capabilities:
            errors.append(f"missing_capability_{capability}")
        elif capabilities.get(capability) not in VALID_CAPABILITY_STATUSES:
            errors.append(f"invalid_capability_{capability}")
    for field in ["approved_for_training", "approved_for_local_evaluation", "approved_for_customer_delivery"]:
        if not isinstance(row.get(field), bool):
            errors.append(f"invalid_{field}")
    if not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if not isinstance(row.get("prohibited_uses"), list):
        errors.append("invalid_prohibited_uses")
    approvals = [
        bool(row.get("approved_for_training")),
        bool(row.get("approved_for_local_evaluation")),
        bool(row.get("approved_for_customer_delivery")),
    ]
    if any(approvals) and row.get("review_decision") not in {"approved", "approved_with_conditions"}:
        errors.append("approval_flag_without_approved_decision")
    if row.get("authorization_status") == "verified" and row.get("verification_required") is True:
        errors.append("verified_authorization_cannot_require_verification")
    if row.get("authorization_status") == "self_attested" and row.get("verification_required") is not True:
        errors.append("self_attested_authorization_must_require_verification")
    if row.get("authorization_status") == "verified":
        if row.get("authorization_source") != "contract_or_license":
            errors.append("verified_authorization_requires_contract_or_license_source")
        if not row.get("contract_reference"):
            errors.append("verified_authorization_missing_contract_reference")
    allowed_caps = [cap for cap in CAPABILITY_FIELDS if capabilities.get(cap) == "allowed"]
    if allowed_caps and row.get("review_decision") not in {"approved", "approved_with_conditions"}:
        errors.append("allowed_capability_without_approved_decision")
    if row.get("authorization_status") in {"denied", "pending_verification"} and allowed_caps:
        errors.append("allowed_capability_with_denied_or_pending_authorization")
    if row.get("approved_for_training") and row.get("item_type") != "external_data_source":
        errors.append("training_approval_not_applicable_to_tool")
    if row.get("approved_for_local_evaluation") and row.get("item_type") != "foreign_tool":
        errors.append("local_evaluation_approval_not_applicable_to_data_source")
    if row.get("item_type") == "external_data_source" and row.get("approved_for_customer_delivery") and not row.get("attribution_text"):
        errors.append("missing_attribution_text_for_delivery")
    if row.get("item_type") == "external_data_source" and any(approvals) and not row.get("version_or_retrieval_date"):
        errors.append("missing_version_or_retrieval_date_for_data_source")
    if row.get("review_decision") == "approved_with_conditions" and not row.get("conditions"):
        errors.append("approved_with_conditions_missing_conditions")
    if packet and packet.get("commercial_status") == "restricted" and any(approvals) and row.get("authorization_status") != "verified":
        errors.append("restricted_item_requires_verified_authorization_for_legacy_approval")
    return errors


def capability_status(row: dict[str, Any], capability: str) -> str | None:
    capabilities = row.get("capability_authorizations")
    if not isinstance(capabilities, dict):
        return None
    value = capabilities.get(capability)
    return str(value) if value in VALID_CAPABILITY_STATUSES else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external license review decisions")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    packets = load_jsonl(args.packets)
    decisions = load_jsonl(args.input)
    packet_by_id = {str(row.get("review_item_id")): row for row in packets}
    records = []
    errors = Counter()
    seen = set()
    duplicates = set()
    for row in decisions:
        review_item_id = str(row.get("review_item_id"))
        if review_item_id in seen:
            duplicates.add(review_item_id)
        seen.add(review_item_id)
        row_errors = validate(row, packet_by_id)
        errors.update(row_errors)
        records.append({
            "review_item_id": row.get("review_item_id"),
            "item_type": row.get("item_type"),
            "review_decision": row.get("review_decision"),
            "valid": not row_errors,
            "authorization_source": row.get("authorization_source"),
            "authorization_status": row.get("authorization_status"),
            "verification_required": row.get("verification_required"),
            "verification_status": row.get("verification_status"),
            "capability_authorizations": row.get("capability_authorizations") if isinstance(row.get("capability_authorizations"), dict) else {},
            "approved_for_training": bool(row.get("approved_for_training")) and not row_errors,
            "approved_for_local_evaluation": bool(row.get("approved_for_local_evaluation")) and not row_errors,
            "approved_for_customer_delivery": bool(row.get("approved_for_customer_delivery")) and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_review_item_id": len(duplicates)})
        for record in records:
            if record["review_item_id"] in duplicates:
                record["valid"] = False
                record["approved_for_training"] = False
                record["approved_for_local_evaluation"] = False
                record["approved_for_customer_delivery"] = False
                record["errors"].append("duplicate_review_item_id")

    valid_rows = sum(1 for item in records if item["valid"])
    approved_training = sum(1 for item in records if item["approved_for_training"])
    approved_local_eval = sum(1 for item in records if item["approved_for_local_evaluation"])
    approved_delivery = sum(1 for item in records if item["approved_for_customer_delivery"])
    self_attested_rows = sum(1 for item in records if item["valid"] and item.get("authorization_status") == "self_attested")
    pending_verification_rows = sum(1 for item in records if item["valid"] and item.get("authorization_status") == "pending_verification")
    verified_rows = sum(1 for item in records if item["valid"] and item.get("authorization_status") == "verified")
    verification_required_rows = sum(1 for item in records if item["valid"] and item.get("verification_required") is True)
    capability_counts: dict[str, dict[str, int]] = {
        capability: {status: 0 for status in sorted(VALID_CAPABILITY_STATUSES)}
        for capability in CAPABILITY_FIELDS
    }
    verified_capability_allowed_counts = {capability: 0 for capability in CAPABILITY_FIELDS}
    self_attested_capability_allowed_counts = {capability: 0 for capability in CAPABILITY_FIELDS}
    for record in records:
        if not record["valid"]:
            continue
        for capability in CAPABILITY_FIELDS:
            status = capability_status(record, capability)
            if status:
                capability_counts[capability][status] += 1
                if status == "allowed" and record.get("authorization_status") == "verified":
                    verified_capability_allowed_counts[capability] += 1
                if status == "allowed" and record.get("authorization_status") == "self_attested":
                    self_attested_capability_allowed_counts[capability] += 1
    verified_customer_delivery = verified_capability_allowed_counts["customer_delivery"]
    data_packet_rows = sum(1 for row in packets if row.get("item_type") == "external_data_source")
    tool_packet_rows = sum(1 for row in packets if row.get("item_type") == "foreign_tool")
    decided_packet_ids = {str(item["review_item_id"]) for item in records if item["valid"]}
    missing_packet_decisions = sorted(set(packet_by_id) - decided_packet_ids)
    report = {
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "packet_rows": len(packets),
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "invalid_rows": len(records) - valid_rows,
        "approved_for_training_rows": approved_training,
        "approved_for_local_evaluation_rows": approved_local_eval,
        "approved_for_customer_delivery_rows": approved_delivery,
        "authorization_status_counts": {
            "self_attested": self_attested_rows,
            "pending_verification": pending_verification_rows,
            "verified": verified_rows,
        },
        "verification_required_rows": verification_required_rows,
        "capability_authorization_counts": capability_counts,
        "verified_capability_allowed_counts": verified_capability_allowed_counts,
        "self_attested_capability_allowed_counts": self_attested_capability_allowed_counts,
        "self_attested_commercial_evaluation_rows": self_attested_capability_allowed_counts["commercial_evaluation"],
        "verified_commercial_evaluation_rows": verified_capability_allowed_counts["commercial_evaluation"],
        "verified_training_import_rows": verified_capability_allowed_counts["training_import"],
        "verified_customer_delivery_rows": verified_customer_delivery,
        "data_packet_rows": data_packet_rows,
        "tool_packet_rows": tool_packet_rows,
        "all_packet_items_decided": len(missing_packet_decisions) == 0 and bool(packets),
        "missing_packet_decisions": missing_packet_decisions[:100],
        "ready_for_training": approved_training == data_packet_rows and data_packet_rows > 0 and not errors,
        "ready_for_local_evaluation": approved_local_eval > 0 and not errors,
        "verified_ready_for_local_evaluation": verified_capability_allowed_counts["commercial_evaluation"] > 0 and not errors,
        "ready_for_customer_delivery": verified_customer_delivery == len(packets) and bool(packets) and not errors,
        "customer_delivery_ready_requires_verified_scope": True,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "平台不设置一刀切的非商业限制。具体能力根据组件许可证、企业授权和项目授权状态判定；self_attested 可作为工作流输入继续技术配置，但不能包装成 verified 法律结论或 customer_delivery/release ready。",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "self_attested_rows": self_attested_rows,
        "verified_rows": verified_rows,
        "approved_for_customer_delivery_rows": approved_delivery,
        "verified_customer_delivery_rows": verified_customer_delivery,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
