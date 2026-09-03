#!/usr/bin/env python3
"""Validate completion status for next-unlock start packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "next_unlock_start_packets.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_completion_status.jsonl"
STRICT_ROW_THRESHOLD = 100
DOMAIN_UNRESOLVED_START = 157


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def as_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def rel(path: str | None) -> str | None:
    if not path:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def status_from_checks(checks: list[dict[str, Any]]) -> str:
    return "completion_ready" if checks and all(item["passed"] for item in checks) else "started_blocked"


def completion_checks(packet: dict[str, Any], reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    action_id = packet.get("action_id")
    target_rows = as_int(packet.get("target_rows"))
    numbering = reports["numbering"]
    repaired = reports["repaired"]
    safe_entry = reports["safe_entry"]
    structure_validation = reports["structure_validation"]
    structure_apply = reports["structure_apply"]
    domain_packets = reports["domain_packets"]
    domain_validation = reports["domain_validation"]
    domain_apply = reports["domain_apply"]
    msa_runtime = reports["msa_runtime"]
    msa_cache = reports["msa_cache"]
    feedback = reports["feedback"]
    plate_feedback = reports["plate_feedback"]
    license_validation = reports["license"]
    biosecurity = reports["biosecurity"]
    ip_fto = reports["ip_fto"]
    workstream = reports["workstream"]
    operator = reports["operator"]
    claims = reports["claims"]

    if action_id == "P43-A001":
        strict_rows = as_int(repaired.get("supervised_rows") or safe_entry.get("rows"))
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("numbering valid rows meet action target", as_int(numbering.get("valid_rows")) >= target_rows, numbering.get("valid_rows"), target_rows),
            check("strict supervised rows meet model-claim threshold", strict_rows >= STRICT_ROW_THRESHOLD, strict_rows, STRICT_ROW_THRESHOLD),
            check("safe entrypoint has no failures", as_int(safe_entry.get("failures")) == 0, safe_entry.get("failures"), 0),
        ]
    if action_id == "P43-A002":
        reviewed = as_int(structure_validation.get("reviewed_chain_mapping_rows") or structure_apply.get("reviewed_chain_mapping_rows"))
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("reviewed chain mapping rows meet action target", reviewed >= target_rows, reviewed, target_rows),
            check("structure chain mapping invalid rows are zero", as_int(structure_validation.get("invalid_rows")) == 0, structure_validation.get("invalid_rows"), 0),
            check("usable coordinate feature mappings meet action target", as_int(structure_apply.get("usable_for_coordinate_features")) >= target_rows, structure_apply.get("usable_for_coordinate_features"), target_rows),
        ]
    if action_id == "P43-A003":
        expected_remaining = max(DOMAIN_UNRESOLVED_START - target_rows, 0)
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("domain unresolved rows reduced by action target", as_int(domain_packets.get("unresolved_rows")) <= expected_remaining, domain_packets.get("unresolved_rows"), f"<= {expected_remaining}"),
            check("domain decision invalid rows are zero", as_int(domain_validation.get("invalid_rows")) == 0, domain_validation.get("invalid_rows"), 0),
            check("domain usable rows remain present", as_int(domain_apply.get("usable_for_position_features")) > 0, domain_apply.get("usable_for_position_features"), "> 0"),
        ]
    if action_id == "P43-A004":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("MSA runtime or trusted cache is ready", msa_runtime.get("runtime_ready") is True or msa_cache.get("ready") is True, {
                "runtime_ready": msa_runtime.get("runtime_ready"),
                "cache_ready": msa_cache.get("ready"),
            }, "runtime_ready or cache_ready"),
            check("MSA cache manifest has no manifest errors", not msa_cache.get("manifest_errors"), msa_cache.get("manifest_errors"), []),
        ]
    if action_id == "P43-A005":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("feedback training eligible rows present", as_int(feedback.get("training_eligible_rows")) > 0, feedback.get("training_eligible_rows"), "> 0"),
            check("feedback invalid rows are zero", as_int(feedback.get("invalid_rows")) == 0, feedback.get("invalid_rows"), 0),
        ]
    if action_id == "P43-A006":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("plate feedback training eligible rows present", as_int(plate_feedback.get("training_eligible_rows")) > 0, plate_feedback.get("training_eligible_rows"), "> 0"),
            check("plate feedback invalid rows are zero", as_int(plate_feedback.get("invalid_rows")) == 0, plate_feedback.get("invalid_rows"), 0),
        ]
    if action_id == "P43-A007":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("license decisions cover all packets", license_validation.get("all_packet_items_decided") is True, license_validation.get("all_packet_items_decided"), True),
            check("license decisions ready for customer delivery", license_validation.get("ready_for_customer_delivery") is True, license_validation.get("ready_for_customer_delivery"), True),
        ]
    if action_id == "P43-A008":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("biosecurity drafts all decided", biosecurity.get("all_drafts_decided") is True, biosecurity.get("all_drafts_decided"), True),
            check("biosecurity ready for ordering", biosecurity.get("ready_for_ordering") is True, biosecurity.get("ready_for_ordering"), True),
        ]
    if action_id == "P43-A009":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("IP/FTO delivery candidates all decided", ip_fto.get("all_packet_candidates_decided_for_delivery") is True, ip_fto.get("all_packet_candidates_decided_for_delivery"), True),
            check("IP/FTO ready for customer delivery", ip_fto.get("ready_for_customer_delivery") is True, ip_fto.get("ready_for_customer_delivery"), True),
        ]
    if action_id == "P43-A010":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("all workstreams human accepted", workstream.get("all_streams_accepted") is True, workstream.get("all_streams_accepted"), True),
        ]
    if action_id == "P43-A011":
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("all operator actions completed", operator.get("all_actions_completed") is True, operator.get("all_actions_completed"), True),
        ]
    if action_id == "P43-A012":
        claim_policy = reports["claim_policy"]
        claim_policy_anchor = reports["claim_policy_anchor"]
        claim_policy_anchor_regression = reports["claim_policy_anchor_regression"]
        claim_promotion = reports["claim_promotion"]
        claim_policy_current = reports["claim_policy_current"]
        claim_policy_current_regression = reports["claim_policy_current_regression"]
        observed_claim_ids = set(claims.get("allowed_claim_ids") or []) | set(claims.get("blocked_claim_ids") or [])
        canonical_claim_ids = set(claim_policy.get("canonical_claim_ids") or [])
        return [
            check("start packet is started", packet.get("started") is True, packet.get("started"), True),
            check("claim matrix policy validation passes", claim_policy.get("success") is True, claim_policy.get("success"), True),
            check("independent claim policy anchor passes", claim_policy_anchor.get("success") is True, claim_policy_anchor.get("success"), True),
            check("independent claim policy anchor regression passes", claim_policy_anchor_regression.get("success") is True and claim_policy_anchor_regression.get("passed_case_count") == 8, {"success": claim_policy_anchor_regression.get("success"), "passed_case_count": claim_policy_anchor_regression.get("passed_case_count")}, {"success": True, "passed_case_count": 8}),
            check("claim matrix policy receipt is current", claim_policy_current.get("success") is True, claim_policy_current.get("success"), True),
            check("claim matrix policy current regression passes", claim_policy_current_regression.get("success") is True and claim_policy_current_regression.get("passed_case_count") == 11, {"success": claim_policy_current_regression.get("success"), "passed_case_count": claim_policy_current_regression.get("passed_case_count")}, {"success": True, "passed_case_count": 11}),
            check("claim promotion decision gate passes", claim_promotion.get("ready_for_claim_promotion") is True, claim_promotion.get("ready_for_claim_promotion"), True),
            check("claim matrix matches current upstream sources", claim_policy.get("source_parity_success") is True, claim_policy.get("source_parity_success"), True),
            check("claim matrix has exact canonical claims", observed_claim_ids == canonical_claim_ids, sorted(observed_claim_ids), sorted(canonical_claim_ids)),
            check("all canonical claims are dynamically ready", claim_policy.get("all_claims_ready") is True, claim_policy.get("not_ready_claim_ids"), []),
            check("promotion policy allows all canonical claims", claim_policy.get("promotion_policy_allows_all_claims") is True, claim_policy.get("promotion_policy_allows_all_claims"), True),
            check("claim matrix has zero blocked claims", as_int(claims.get("claims_blocked")) == 0, claims.get("claims_blocked"), 0),
        ]
    return [
        check("known action id", False, action_id, "P43-A001..P43-A012"),
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock execution completion")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    reports = {
        "numbering": load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json"),
        "repaired": load_json(AI_ROOT / "reports" / "repaired_supervised_table_report.json"),
        "safe_entry": load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json"),
        "structure_validation": load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json"),
        "structure_apply": load_json(AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json"),
        "domain_packets": load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json"),
        "domain_validation": load_json(AI_ROOT / "reports" / "domain_interval_decision_validation_report.json"),
        "domain_apply": load_json(AI_ROOT / "reports" / "domain_interval_apply_report.json"),
        "msa_runtime": load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json"),
        "msa_cache": load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"),
        "feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json"),
        "plate_feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"),
        "license": load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"),
        "biosecurity": load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"),
        "ip_fto": load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"),
        "workstream": load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json"),
        "operator": load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json"),
        "claims": load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json"),
        "claim_policy": load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"),
        "claim_policy_anchor": load_json(AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json"),
        "claim_policy_anchor_regression": load_json(AI_ROOT / "reports" / "claim_readiness_policy_anchor_regression_report.json"),
        "claim_promotion": load_json(AI_ROOT / "reports" / "claim_promotion_decision_validation_report.json"),
        "claim_policy_current": load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json"),
        "claim_policy_current_regression": load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json"),
    }
    packets = load_jsonl(args.packets)
    rows = []
    for packet in packets:
        checks = completion_checks(packet, reports)
        status = status_from_checks(checks)
        failed = [item["name"] for item in checks if not item["passed"]]
        rows.append({
            "packet_id": packet.get("packet_id"),
            "action_id": packet.get("action_id"),
            "stage_id": packet.get("stage_id"),
            "stage_order": packet.get("stage_order"),
            "workstream": packet.get("workstream"),
            "priority": packet.get("priority"),
            "assigned_role": packet.get("assigned_role"),
            "started": bool(packet.get("started")),
            "completion_ready": status == "completion_ready",
            "status": status,
            "failed_checks": failed,
            "checks": checks,
            "validator_report": packet.get("validator_report"),
            "decision_input": packet.get("decision_input"),
            "policy": "Completion is detected only from explicit validator/report fields; start packets and drafts do not count as reviewed decisions.",
        })
    write_jsonl(args.jsonl, rows)

    ready_rows = [row for row in rows if row["completion_ready"]]
    blocked_rows = [row for row in rows if not row["completion_ready"]]
    stage_ids = sorted({str(row.get("stage_id")) for row in rows if row.get("stage_id")})
    stage_summary = []
    for stage_id in stage_ids:
        stage_rows = [row for row in rows if row.get("stage_id") == stage_id]
        ready = [row for row in stage_rows if row["completion_ready"]]
        stage_summary.append({
            "stage_id": stage_id,
            "stage_order": min(as_int(row.get("stage_order")) for row in stage_rows),
            "action_rows": len(stage_rows),
            "completion_ready_actions": len(ready),
            "blocked_actions": len(stage_rows) - len(ready),
            "completion_ready": len(ready) == len(stage_rows) and bool(stage_rows),
        })
    stage_summary.sort(key=lambda row: row["stage_order"])

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packets": rel(str(args.packets)),
        "jsonl": rel(str(args.jsonl)),
        "total_actions": len(rows),
        "started_actions": sum(1 for row in rows if row["started"]),
        "completion_ready_actions": len(ready_rows),
        "blocked_actions": len(blocked_rows),
        "stage_count": len(stage_summary),
        "completion_ready_stage_count": sum(1 for row in stage_summary if row["completion_ready"]),
        "stage_summary": stage_summary,
        "top_blocked_actions": [
            {
                "action_id": row["action_id"],
                "workstream": row["workstream"],
                "failed_checks": row["failed_checks"],
            }
            for row in blocked_rows[:12]
        ],
        "policy": "This validation is fail-closed. It does not write reviewed decisions, grant approvals, unlock claims, download tools, deploy services, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "total_actions": report["total_actions"],
        "completion_ready_actions": report["completion_ready_actions"],
        "blocked_actions": report["blocked_actions"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
