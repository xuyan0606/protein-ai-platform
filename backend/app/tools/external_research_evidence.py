"""Expose local external-research evidence to the platform LLM.

The tool is deliberately read-only. It reports governance state and evidence
references; it never imports training rows, approves claims, or creates a
customer/release artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.tools.registry import ToolRegistry


PLATFORM_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = PLATFORM_ROOT / "AI大模型"
RESEARCH_EVIDENCE_SCOPES = ("training", "model_claim", "customer_delivery", "release", "human_target", "all")


def _load_json(relative_path: str) -> dict[str, Any]:
    path = RESEARCH_ROOT / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": relative_path, "exists": True, "read_error": str(exc)}
    return {"path": relative_path, "exists": True, "payload": payload}


def _load_jsonl(relative_path: str) -> dict[str, Any]:
    path = RESEARCH_ROOT / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False, "rows": []}
    rows: list[dict[str, Any]] = []
    read_errors: list[str] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                read_errors.append(f"line {line_number}: {exc}")
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                read_errors.append(f"line {line_number}: expected object")
    except OSError as exc:
        return {"path": relative_path, "exists": True, "rows": [], "read_error": str(exc)}
    return {
        "path": relative_path,
        "exists": True,
        "rows": rows,
        "read_errors": read_errors,
    }


def external_research_evidence(scope: str = "all") -> dict[str, Any]:
    """Return read-only status for research integration scopes."""
    normalized = str(scope or "all").strip().lower()
    if normalized not in RESEARCH_EVIDENCE_SCOPES:
        raise ValueError(f"INVALID_SCOPE: expected one of {sorted(RESEARCH_EVIDENCE_SCOPES)}")

    matrix_path = "reports/external_research_integration_matrix_2026-08-04.md"
    claim = _load_json("reports/claim_readiness_matrix.json")
    training = _load_json("reports/five_head_training_execution_contract_report.json")
    kinetics_candidate = _load_json("reports/cleanroom_kinetics_training_candidate_report.json")
    kinetics_candidate_validation = _load_json(
        "reports/cleanroom_kinetics_training_candidate_validation_report.json"
    )
    customer = _load_json("reports/customer_delivery_readiness_report.json")
    release = _load_json("reports/local_release_manifest.json")
    human_target_gap = _load_json("reports/human_target_contract_gap_report.json")
    human_target_source_runtime = _load_json("reports/human_target_source_runtime_manifest.json")
    human_target_source_runtime_validation = _load_json(
        "reports/human_target_source_runtime_manifest_validation_report.json"
    )
    human_target_blocked_source_index = _load_json("reports/human_target_blocked_source_manifest_index.json")
    human_target_blocked_source_index_validation = _load_json(
        "reports/human_target_blocked_source_manifest_index_validation_report.json"
    )
    human_target_unlock_checklist = _load_jsonl(
        "datasets/governance/human_target_source_unlock_checklist.jsonl"
    )
    human_target_unlock_checklist_validation = _load_json(
        "reports/human_target_source_unlock_checklist_validation_report.json"
    )
    human_target_unlock_checklist_report = _load_json(
        "reports/human_target_source_unlock_checklist_report.json"
    )

    human_target_payload = (
        human_target_source_runtime.get("payload", {})
        if isinstance(human_target_source_runtime.get("payload"), dict)
        else {}
    )
    human_target_summary = human_target_payload.get("summary", {}) if isinstance(human_target_payload, dict) else {}
    human_target_gap_payload = (
        human_target_gap.get("payload", {}) if isinstance(human_target_gap.get("payload"), dict) else {}
    )
    human_target_split_payload = (
        human_target_blocked_source_index.get("payload", {})
        if isinstance(human_target_blocked_source_index.get("payload"), dict)
        else {}
    )
    split_index = human_target_split_payload.get("source_manifest_index", [])
    split_path_by_source = {
        item.get("source_id"): item.get("path")
        for item in split_index
        if isinstance(item, dict) and item.get("source_id")
    }
    human_target_sources = []
    for source in human_target_payload.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = source.get("source_id")
        human_target_sources.append({**source, "split_manifest_path": split_path_by_source.get(source_id)})

    unlock_rows = []
    for row in human_target_unlock_checklist.get("rows", []):
        unlock_rows.append(
            {
                "checklist_id": row.get("checklist_id"),
                "source_id": row.get("source_id"),
                "source_manifest_path": row.get("source_manifest_path"),
                "current_status": row.get("current_status", "blocked"),
                "completed_steps": row.get("completed_steps", []),
                "missing_steps": row.get("missing_steps", []),
                "required_steps": row.get("required_steps", []),
                "ready_to_unlock": bool(row.get("ready_to_unlock", False)),
                "claim_eligible": bool(row.get("claim_eligible", False)),
                "customer_ready": bool(row.get("customer_ready", False)),
                "release_ready": bool(row.get("release_ready", False)),
            }
        )
    unlock_report_payload = (
        human_target_unlock_checklist_report.get("payload", {})
        if isinstance(human_target_unlock_checklist_report.get("payload"), dict)
        else {}
    )
    unlock_validation_payload = (
        human_target_unlock_checklist_validation.get("payload", {})
        if isinstance(human_target_unlock_checklist_validation.get("payload"), dict)
        else {}
    )
    unlock_checklist_summary = {
        "checklist_rows": int(unlock_report_payload.get("checklist_rows", len(unlock_rows)) or 0),
        "ready_to_unlock_rows": int(unlock_report_payload.get("ready_to_unlock_rows", 0) or 0),
        "blocked_rows": int(unlock_report_payload.get("blocked_rows", 0) or 0),
        "validation_success": bool(unlock_validation_payload.get("success", False)),
        "path": human_target_unlock_checklist["path"],
        "validation_path": human_target_unlock_checklist_validation["path"],
        "report_path": human_target_unlock_checklist_report["path"],
        "rows": unlock_rows,
    }

    payload = {
        "scope": normalized,
        "local_only": True,
        "read_only": True,
        "matrix": {"path": matrix_path, "exists": (RESEARCH_ROOT / matrix_path).exists()},
        "training": {
            "training_import_eligible_rows": (
                training.get("payload", {}).get("training_import", {}).get("training_import_eligible_rows", 0)
                if isinstance(training.get("payload"), dict)
                else 0
            ),
            "training_execution_allowed": (
                training.get("payload", {}).get("training_execution_allowed", False)
                if isinstance(training.get("payload"), dict)
                else False
            ),
            "status": "blocked",
            "cleanroom_kinetics_candidate": {
                "training_import_written_rows": (
                    kinetics_candidate.get("payload", {}).get("training_import_written_rows", 0)
                    if isinstance(kinetics_candidate.get("payload"), dict)
                    else 0
                ),
                "training_eligible": (
                    kinetics_candidate.get("payload", {}).get("training_eligible", False)
                    if isinstance(kinetics_candidate.get("payload"), dict)
                    else False
                ),
                "validation_success": (
                    kinetics_candidate_validation.get("payload", {}).get("success", False)
                    if isinstance(kinetics_candidate_validation.get("payload"), dict)
                    else False
                ),
            },
        },
        "model_claim": {
            "safe_for_model_claim": (
                claim.get("payload", {}).get("safe_for_model_claim", False)
                if isinstance(claim.get("payload"), dict)
                else False
            ),
            "claims_allowed": (
                claim.get("payload", {}).get("claims_allowed", 0)
                if isinstance(claim.get("payload"), dict)
                else 0
            ),
            "status": "blocked",
        },
        "customer_delivery": {
            "ready": (
                customer.get("payload", {}).get("ready", False)
                if isinstance(customer.get("payload"), dict)
                else False
            ),
            "status": "internal_review_only",
        },
        "release": {
            "release_ready": (
                release.get("payload", {}).get("release_ready", False)
                if isinstance(release.get("payload"), dict)
                else False
            ),
            "local_only": (
                release.get("payload", {}).get("local_only", True)
                if isinstance(release.get("payload"), dict)
                else True
            ),
            "status": "blocked",
        },
        "human_target": {
            "status": "blocked",
            "schema_contract_status": "schema_only_contracts_present_no_runtime",
            "source_runtime_validation_success": (
                human_target_source_runtime_validation.get("payload", {}).get("success", False)
                if isinstance(human_target_source_runtime_validation.get("payload"), dict)
                else False
            ),
            "split_manifest_validation_success": (
                human_target_blocked_source_index_validation.get("payload", {}).get("success", False)
                if isinstance(human_target_blocked_source_index_validation.get("payload"), dict)
                else False
            ),
            "total_sources": human_target_summary.get("total_sources", 0),
            "ready_sources": human_target_summary.get("ready_sources", 0),
            "blocked_sources": human_target_summary.get("blocked_sources", 0),
            "split_manifests": split_index,
            "unlock_checklist": unlock_checklist_summary,
            "product_lines": human_target_gap_payload.get("product_lines", {}),
            "sources": human_target_sources,
            "safe_for_model_claim": False,
            "customer_ready": False,
            "release_ready": False,
        },
        "evidence_paths": [
            matrix_path,
            "reports/claim_readiness_matrix.json",
            "reports/five_head_training_execution_contract_report.json",
            "reports/cleanroom_kinetics_training_candidate_report.json",
            "reports/cleanroom_kinetics_training_candidate_validation_report.json",
            "reports/customer_delivery_readiness_report.json",
            "reports/local_release_manifest.json",
            "reports/human_target_contract_gap_report.json",
            "reports/human_target_contract_gap_validation_report.json",
            "reports/human_target_source_runtime_manifest.json",
            "reports/human_target_source_runtime_manifest_validation_report.json",
            "reports/human_target_blocked_source_manifest_index.json",
            "reports/human_target_blocked_source_manifest_index_validation_report.json",
            "datasets/governance/human_target_source_unlock_checklist.jsonl",
            "reports/human_target_source_unlock_checklist_report.json",
            "reports/human_target_source_unlock_checklist_validation_report.json",
        ],
        "forbidden_side_effects": [
            "write_training_rows",
            "approve_model_claims",
            "approve_customer_delivery",
            "set_release_ready",
            "deploy_or_sync",
        ],
    }
    if normalized != "all":
        return {
            "scope": normalized,
            "local_only": True,
            "read_only": True,
            "normalized_result": payload[normalized],
        }
    return payload


ToolRegistry.register(
    name="external_research_evidence",
    description=(
        "Read-only local status for external research integration into training, "
        "human target, model claims, customer delivery, and release. Returns evidence paths and "
        "fail-closed gates; never writes data or approves capabilities."
    ),
    parameters={
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": list(RESEARCH_EVIDENCE_SCOPES),
                "description": "Evidence scope to inspect.",
            }
        },
        "required": [],
    },
    handler=external_research_evidence,
    category="governance",
    timeout_seconds=10,
    annotations={
        "read_only": True,
        "local_only": True,
        "claim_eligible": False,
        "training_eligible": False,
        "customer_ready": False,
        "release_ready": False,
    },
)
