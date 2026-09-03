#!/usr/bin/env python3
"""Build a fail-closed promotion audit for locally verified workstreams."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "ready_to_verify_promotion_board.json"
ROWS_OUTPUT = AI_ROOT / "datasets" / "governance" / "ready_to_verify_promotion_status.jsonl"

EXPECTED_IDS = {
    "top_tier:cross_rosetta_foldx_ddg_backend",
    "top_tier:p0_kwb_wet_lab_feedback",
    "top_tier:p0_reviewed_structure_graph",
    "non_human:nhc_ddg_physics_backend",
    "non_human:nhc_structure_gnn_features",
    "non_human:nhc_data_lake_cache_governance",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def receipt_valid(scope: str, workstream_id: str) -> bool:
    prefix = "top_tier_model" if scope == "top_tier" else "non_human"
    validation = load_json(AI_ROOT / "reports" / f"{prefix}_ready_to_verify_receipt_validation_report.json")
    receipt_path = AI_ROOT / "datasets" / "governance" / f"{prefix}_ready_to_verify_receipts.jsonl"
    rows = load_jsonl(receipt_path)
    row = next((item for item in rows if item.get("workstream_id") == workstream_id), {})
    return bool(
        validation.get("success") is True
        and row.get("verification_status") == "verification_passed"
        and row.get("commands_ok") is True
        and row.get("evidence_ok") is True
        and row.get("completion_ready") is False
        and row.get("safe_for_model_claim") is False
        and row.get("release_ready") is False
    )


def graph_rows() -> list[dict[str, Any]]:
    return load_jsonl(AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl")


def graph_rows_traceable(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        digest = str(row.get("graph_sha256") or "")
        graph_path = AI_ROOT / str(row.get("graph_path") or "")
        if len(digest) != 64 or not graph_path.is_file() or sha256(graph_path) != digest:
            return False
    return True


def make_row(
    scope: str,
    workstream_id: str,
    title: str,
    checks: dict[str, bool],
    context: dict[str, Any],
) -> dict[str, Any]:
    local_checks_met = bool(checks) and all(value is True for value in checks.values())
    return {
        "audit_id": f"{scope}:{workstream_id}",
        "scope": scope,
        "workstream_id": workstream_id,
        "title": title,
        "receipt_valid": checks.get("receipt_valid") is True,
        "completion_checks": checks,
        "context": context,
        "local_artifact_completion_checks_met": local_checks_met,
        "promotion_status": "verified_local_artifact_only" if local_checks_met else "verified_blocked",
        "remaining_blockers": sorted(key for key, value in checks.items() if value is not True),
        "automatic_promotion_allowed": False,
        "workstream_completion_ready": False,
        "execution_ready": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "selected_variant_rows": 0,
        "policy": "Local completion checks may identify a verified artifact only. Automatic promotion, execution, training, model, customer-delivery, and release gates remain closed.",
    }


def build_rows() -> list[dict[str, Any]]:
    graph_validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
    graphs = graph_rows()
    graph_traceable = graph_rows_traceable(graphs)
    numbering_review_cleared = bool(graphs) and all(
        row.get("requires_mutation_numbering_review") is False for row in graphs
    )

    plate_intake = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    feedback_intake = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    wet_lab_preflight = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json")

    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    ddg_plan = load_json(AI_ROOT / "reports" / "ddg_backend_execution_plan_report.json")
    ddg_readiness = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    ddg_operator = load_json(AI_ROOT / "reports" / "ddg_backend_operator_packet_validation_report.json")
    ddg_contract = load_json(AI_ROOT / "reports" / "ddg_model_consumption_contract_validation_report.json")
    convention_ok = bool((ddg_contract.get("state_summary") or {}).get("negative_ddg_is_stabilizing"))

    data_lake = load_json(AI_ROOT / "reports" / "data_lake_manifest.json")
    provenance = load_json(AI_ROOT / "reports" / "provenance_graph_report.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    artifacts = [item for item in data_lake.get("artifacts") or [] if isinstance(item, dict)]
    manifest_complete = bool(artifacts) and all(item.get("exists") is not False for item in artifacts)

    rows = [
        make_row(
            "top_tier",
            "cross_rosetta_foldx_ddg_backend",
            "Rosetta/PyRosetta/FoldX ddG backend gate",
            {
                "receipt_valid": receipt_valid("top_tier", "cross_rosetta_foldx_ddg_backend"),
                "commercial_license_verified_for_customer_delivery": int(
                    license_validation.get("verified_customer_delivery_rows") or 0
                ) > 0,
                "ddg_execution_plan_has_ready_rows": int(ddg_plan.get("ready_rows") or 0) > 0,
                "negative_ddg_stabilization_convention_preserved": convention_ok,
            },
            {
                "plan_rows": int(ddg_plan.get("plan_rows") or 0),
                "ready_plan_rows": int(ddg_plan.get("ready_rows") or 0),
                "verified_customer_delivery_rows": int(
                    license_validation.get("verified_customer_delivery_rows") or 0
                ),
            },
        ),
        make_row(
            "top_tier",
            "p0_kwb_wet_lab_feedback",
            "KWB plate/well wet-lab feedback calibration",
            {
                "receipt_valid": receipt_valid("top_tier", "p0_kwb_wet_lab_feedback"),
                "plate_feedback_rows_present": int(plate_intake.get("input_rows") or 0) > 0,
                "plate_feedback_rows_valid": int(plate_intake.get("valid_rows") or 0) > 0
                and int(plate_intake.get("invalid_rows") or 0) == 0,
                "authorized_preflight_has_ready_rows": int(
                    wet_lab_preflight.get("ready_for_feedback_intake_rows") or 0
                ) > 0,
                "feedback_linked_numbering_verified": bool(plate_intake.get("records"))
                and all(
                    row.get("valid") is True and row.get("training_eligible") is True
                    for row in plate_intake.get("records") or []
                    if isinstance(row, dict)
                ),
            },
            {
                "general_feedback_valid_rows": int(feedback_intake.get("valid_rows") or 0),
                "plate_feedback_rows": int(plate_intake.get("input_rows") or 0),
                "authorized_preflight_rows": int(wet_lab_preflight.get("preflight_rows") or 0),
                "ready_preflight_rows": int(wet_lab_preflight.get("ready_for_feedback_intake_rows") or 0),
            },
        ),
        make_row(
            "top_tier",
            "p0_reviewed_structure_graph",
            "Reviewed structure graph feature builder",
            {
                "receipt_valid": receipt_valid("top_tier", "p0_reviewed_structure_graph"),
                "reviewed_structure_graph_ready": graph_validation.get("ready_for_coordinate_feature_use") is True,
                "valid_graph_rows_present": int(graph_validation.get("valid_rows") or 0) > 0
                and int(graph_validation.get("invalid_rows") or 0) == 0,
                "graph_checksums_traceable": graph_traceable,
                "mutation_numbering_review_cleared": numbering_review_cleared,
            },
            {
                "valid_graph_rows": int(graph_validation.get("valid_rows") or 0),
                "invalid_graph_rows": int(graph_validation.get("invalid_rows") or 0),
                "graph_rows_requiring_mutation_numbering_review": sum(
                    row.get("requires_mutation_numbering_review") is True for row in graphs
                ),
            },
        ),
        make_row(
            "non_human",
            "nhc_ddg_physics_backend",
            "Rosetta/PyRosetta/FoldX physics ddG backend",
            {
                "receipt_valid": receipt_valid("non_human", "nhc_ddg_physics_backend"),
                "executable_ddg_backend_ready": ddg_readiness.get("executable_ddg_backend_ready") is True,
                "operator_packet_ready_now": int(ddg_operator.get("ready_for_execution_now_rows") or 0) > 0,
                "ddg_execution_plan_has_ready_rows": int(ddg_plan.get("ready_rows") or 0) > 0,
                "negative_ddg_stabilization_convention_preserved": convention_ok,
            },
            {
                "operator_ready_now_rows": int(ddg_operator.get("ready_for_execution_now_rows") or 0),
                "plan_rows": int(ddg_plan.get("plan_rows") or 0),
                "ready_plan_rows": int(ddg_plan.get("ready_rows") or 0),
            },
        ),
        make_row(
            "non_human",
            "nhc_structure_gnn_features",
            "Structure graph and GNN feature production",
            {
                "receipt_valid": receipt_valid("non_human", "nhc_structure_gnn_features"),
                "reviewed_structure_graph_ready": graph_validation.get("ready_for_coordinate_feature_use") is True,
                "valid_graph_rows_present": int(graph_validation.get("valid_rows") or 0) > 0
                and int(graph_validation.get("invalid_rows") or 0) == 0,
                "coordinate_graph_checksums_traceable": graph_traceable,
            },
            {
                "valid_graph_rows": int(graph_validation.get("valid_rows") or 0),
                "invalid_graph_rows": int(graph_validation.get("invalid_rows") or 0),
            },
        ),
        make_row(
            "non_human",
            "nhc_data_lake_cache_governance",
            "Data lake, cache manifest and provenance governance",
            {
                "receipt_valid": receipt_valid("non_human", "nhc_data_lake_cache_governance"),
                "data_lake_manifest_has_no_missing_artifacts": manifest_complete,
                "provenance_graph_ready": provenance.get("ready_for_release_traceability") is True,
                "governance_readiness_report_exists": bool(governance),
            },
            {
                "manifest_artifact_rows": len(artifacts),
                "provenance_entity_count": int(provenance.get("entity_count") or 0),
                "governance_ready": governance.get("ready") is True,
                "governance_blockers": len(governance.get("blockers") or []),
            },
        ),
    ]
    if {row["audit_id"] for row in rows} != EXPECTED_IDS:
        raise RuntimeError("promotion audit IDs do not match the expected six-lane contract")
    return sorted(rows, key=lambda row: row["audit_id"])


def build_report() -> dict[str, Any]:
    rows = build_rows()
    local_complete = sum(row["local_artifact_completion_checks_met"] is True for row in rows)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "receipt_valid_rows": sum(row["receipt_valid"] is True for row in rows),
        "local_artifact_completion_rows": local_complete,
        "verified_blocked_rows": len(rows) - local_complete,
        "automatic_promotion_rows": 0,
        "workstream_completion_ready_rows": 0,
        "execution_ready_rows": 0,
        "safe_for_training_import_rows": 0,
        "safe_for_model_claim_rows": 0,
        "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0,
        "selected_variant_rows": 0,
        "rows": rows,
        "policy": "This audit separates local artifact verification from automatic workstream completion and all downstream scientific or release gates.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ready-to-verify promotion board")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--rows-output", type=Path, default=ROWS_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(args.rows_output, report["rows"])
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "receipt_valid_rows": report["receipt_valid_rows"],
        "local_artifact_completion_rows": report["local_artifact_completion_rows"],
        "verified_blocked_rows": report["verified_blocked_rows"],
        "automatic_promotion_rows": report["automatic_promotion_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
