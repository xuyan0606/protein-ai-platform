#!/usr/bin/env python3
"""Build a read-only P2/P3/P4 roadmap and readiness packet.

This script is intentionally static and non-executing.  It records which
contracts are already present in the repository and where P2/P3/P4 work is
blocked by missing external evidence or future product decisions.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "p2-p3-p4-roadmap.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "p2-p3-p4-roadmap.md"


def _read(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _source(relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    return {
        "path": relative_path,
        "exists": path.exists(),
    }


def _has(relative_path: str, *tokens: str) -> bool:
    text = _read(relative_path)
    return bool(text) and all(token in text for token in tokens)


def _item(
    *,
    phase: str,
    name: str,
    status: str,
    summary: str,
    source_paths: list[str],
    evidence_tokens: list[str],
    next_local_actions: list[str] | None = None,
    external_blockers: list[str] | None = None,
    must_not_claim: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "name": name,
        "status": status,
        "summary": summary,
        "sources": [_source(path) for path in source_paths],
        "evidence_tokens": evidence_tokens,
        "next_local_actions": next_local_actions or [],
        "external_blockers": external_blockers or [],
        "must_not_claim": must_not_claim or [],
    }


def build_roadmap() -> dict[str, Any]:
    items = [
        _item(
            phase="P2",
            name="residue_feature_table_contract",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/site_structure_function_features.py",
                "site_structure_function_features_v1",
                "residue_distance_graph_v1",
            )
            else "partial",
            summary="Residue structure-function rows and residue distance graph are present as traceable contracts.",
            source_paths=[
                "backend/app/tools/site_structure_function_features.py",
                "backend/tests/test_mutation_objective_scores.py",
            ],
            evidence_tokens=[
                "site_structure_function_features_v1",
                "residue_distance_graph_v1",
                "p2_structure_feature_gap_summary_v1",
            ],
            next_local_actions=[
                "Expose a structure-feature gap summary in downstream SOP/status exports so pocket/channel/interface, conservation, ddG, and MD-derived fields remain explicit until computed.",
                "Expose the calculator/source boundary in downstream SOP/status exports and continue widening residue feature fields only when a structured calculator or curated source exists.",
            ],
            external_blockers=[
                "curated conservation database or MSA pipeline",
                "validated pocket/channel/tunnel calculation",
                "real ddG or MD RMSF artifacts",
            ],
            must_not_claim=["complete residue feature table", "DSSP/MD/conservation coverage when unavailable"],
        ),
        _item(
            phase="P2",
            name="objective_score_contract",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/mutation_priority_score.py",
                "mutation_objective_score_v1",
                "p2_objective_score_readiness_summary_v1",
                "p2_objective_assay_gap_summary_v1",
                "project_feedback_readiness",
                "aggregation",
                "none",
            )
            else "partial",
            summary="Activity, stability, specificity, pH, expression, and risk scores are component-local; no total score is emitted.",
            source_paths=[
                "backend/app/tools/mutation_priority_score.py",
                "backend/tests/test_mutation_objective_scores.py",
            ],
            evidence_tokens=[
                "mutation_objective_score_v1",
                "p2_objective_score_readiness_summary_v1",
                "p2_objective_assay_gap_summary_v1",
                "no_composite_score",
                "unknown_policy",
            ],
            next_local_actions=[
                "Expose unknown-component blocking state in downstream SOP/status exports and keep unknown objective components blocking instead of neutral.",
                "Expose objective assay gaps beside project feedback readiness in downstream SOP/status exports.",
            ],
            external_blockers=[
                "matched WT baseline for claim upgrade",
                "objective-specific assay data",
            ],
            must_not_claim=["single objective total score", "measured improvement without assay"],
        ),
        _item(
            phase="P2",
            name="candidate_table_generation_contract",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/mutation_priority_score.py",
                "candidate_table_generation_v1",
                "p2_engineering_scorecard_contract_v1",
                "p2_candidate_readiness_summary_v1",
                "experiment_design_schedulability_policy_v1",
            )
            else "partial",
            summary="Candidate rows are grouped as high-confidence, exploratory, or blocked using residue features and objective score contracts.",
            source_paths=[
                "backend/app/tools/mutation_priority_score.py",
                "frontend/src/components/analysis/MutationScoreCard.tsx",
                "frontend/src/lib/report.ts",
            ],
            evidence_tokens=[
                "candidate_table_generation_v1",
                "p2_engineering_scorecard_contract_v1",
                "p2_candidate_readiness_summary_v1",
                "experiment_design_schedulability_policy_v1",
            ],
            next_local_actions=[
                "Expose experiment design schedulability policy in downstream SOP views.",
                "Keep candidate table promotion tied to candidate_status and assay readiness.",
            ],
            external_blockers=["wet-lab validation for candidate promotion"],
            must_not_claim=["blocked candidates are schedulable", "candidate table is wet-lab validated"],
        ),
        _item(
            phase="P3",
            name="dbtl_trace_contract",
            status="ready_local_contract"
            if _has(
                "backend/app/services/dbtl_trace.py",
                "dbtl_trace_v1",
                "dbtl_project_model_v1",
                "dbtl_project_memory_readiness_v1",
                "dbtl_trace_summary_v1",
                "dbtl_readiness_bridge_v1",
            )
            else "partial",
            summary="Project DBTL trace aggregates existing checkpoints, feedback, calibration, formal decision, and next-round preview as read-only memory.",
            source_paths=[
                "backend/app/services/dbtl_trace.py",
                "backend/tests/test_project_dbtl_trace.py",
                "frontend/src/pages/ProjectDetailPage.tsx",
                "frontend/src/pages/ProjectListPage.tsx",
            ],
            evidence_tokens=[
                "dbtl_trace_v1",
                "dbtl_project_model_v1",
                "dbtl_project_memory_readiness_v1",
                "dbtl_trace_summary_v1",
                "dbtl_readiness_bridge_v1",
            ],
            next_local_actions=[
                "Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved.",
                "Expose project memory readiness in downstream SOP/status views.",
            ],
            external_blockers=["product decision for formal DBTL write model"],
            must_not_claim=["formal Project/Round/Variant tables exist", "trace has trained a model"],
        ),
        _item(
            phase="P3",
            name="feedback_import_and_next_round_contract",
            status="ready_local_contract"
            if _has(
                "backend/app/services/experiment_feedback.py",
                "experiment_feedback_import_v1",
            )
            and _has(
                "backend/app/services/dbtl_trace.py",
                "dbtl_feedback_readiness_summary_v1",
            )
            and _has(
                "backend/app/tools/feedback_iteration_planner.py",
                "next_round_library_design_v1",
                "constrained_feedback_reweighting_not_trained_epistasis_model",
            )
            else "partial",
            summary="Experiment feedback import gates training/claim eligibility, and next-round library planning is constrained by validated singleton evidence.",
            source_paths=[
                "backend/app/services/experiment_feedback.py",
                "backend/app/tools/feedback_iteration_planner.py",
                "backend/tests/test_experiment_feedback_import_contract.py",
                "frontend/src/pages/DataBrowser.tsx",
                "frontend/src/pages/ProjectDetailPage.tsx",
            ],
            evidence_tokens=[
                "experiment_feedback_import_v1",
                "dbtl_feedback_readiness_summary_v1",
                "next_round_library_design_v1",
                "next_round_combination_evidence_contract_v1",
            ],
            next_local_actions=[
                "Expose feedback readiness in downstream SOP/status exports.",
                "Expose pair/higher-order gate state in downstream SOP/status exports and keep pair/higher-order designs blocked until singleton and structure evidence pass.",
            ],
            external_blockers=[
                "QC-passed replicated wet-lab feedback",
                "assay condition completeness",
                "formal Go/Watch/No-Go decisions",
            ],
            must_not_claim=["trained epistasis model", "higher-order combination readiness without pair data"],
        ),
        _item(
            phase="P4",
            name="industrial_closed_loop_readiness",
            status="ready_local_contract"
            if _has(
                "backend/app/services/dbtl_trace.py",
                "p4_closed_loop_readiness_v1",
                "p4_active_learning_batch_contract_v1",
                "p4_model_calibration_registry_contract_v1",
                "p4_manufacturing_constraint_schema_v1",
                "model_retrained",
                "live_gate_approval",
                "p4_operator_review_contract_v1",
            )
            else "defined_not_started",
            summary=(
                "P4 is defined as production-grade closed-loop operation: active learning batches, "
                "model calibration registry, manufacturing constraints, and approved live-gate execution."
            ),
            source_paths=[
                "backend/app/services/dbtl_trace.py",
                "frontend/src/lib/report.ts",
                "docs/manuals/remaining-backlog-go-no-go-summary.json",
            ],
            evidence_tokens=[
                "p4_closed_loop_readiness_v1",
                "p4_active_learning_batch_contract_v1",
                "p4_model_calibration_registry_contract_v1",
                "p4_manufacturing_constraint_schema_v1",
                "live_gate_approval",
                "model_retrained",
                "p4_operator_review_contract_v1",
            ],
            next_local_actions=[
                "Expose P4 contract status and operator review state in downstream SOP/status exports.",
                "Expose live-gate approval block state in downstream SOP/status exports and keep live gate approval blocked until an explicit operator review is recorded.",
            ],
            external_blockers=[
                "approved production learning policy",
                "sufficient training-eligible feedback",
                "maintenance window and live gate approval",
                "manufacturing/process constraint owner input",
            ],
            must_not_claim=["P4 production loop is running", "model is retrained", "manufacturing constraints are validated"],
        ),
    ]

    phase_summary: dict[str, dict[str, Any]] = {}
    for item in items:
        row = phase_summary.setdefault(
            item["phase"],
            {
                "item_count": 0,
                "ready_local_contract": 0,
                "partial": 0,
                "defined_not_started": 0,
                "external_blocker_count": 0,
                "items": [],
            },
        )
        row["item_count"] += 1
        row["items"].append(item["name"])
        if item["status"] in row:
            row[item["status"]] += 1
        row["external_blocker_count"] += len(item["external_blockers"])

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_p2_p3_p4_roadmap",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "decision": "continue_local_contract_hardening_fail_closed_for_live_dependencies",
        "phase_summary": {phase: phase_summary[phase] for phase in sorted(phase_summary)},
        "items": items,
        "next_action": (
            "Continue P2/P3 local contract hardening and define P4 contracts; do not execute live gates "
            "or claim wet-lab/model-training completion without external evidence."
        ),
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# P2/P3/P4 Roadmap",
        "",
        f"- decision: `{payload['decision']}`",
        f"- network_io: `{payload['network_io']}`",
        f"- destructive_actions: `{payload['destructive_actions']}`",
        f"- live_gate_execution_allowed: `{payload['live_gate_execution_allowed']}`",
        "",
        "## Phase Summary",
        "",
        "| Phase | Items | Ready Local | Partial | Defined Not Started | External Blockers |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for phase, row in payload["phase_summary"].items():
        lines.append(
            f"| `{phase}` | `{row['item_count']}` | `{row['ready_local_contract']}` | "
            f"`{row['partial']}` | `{row['defined_not_started']}` | `{row['external_blocker_count']}` |"
        )
    lines.append("")
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['phase']} / {item['name']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Summary: {item['summary']}",
                f"- Evidence tokens: `{', '.join(item['evidence_tokens'])}`",
                "- Sources:",
            ]
        )
        for source in item["sources"]:
            lines.append(f"  - `{source['path']}` exists=`{source['exists']}`")
        if item["next_local_actions"]:
            lines.append("- Next local actions:")
            for action in item["next_local_actions"]:
                lines.append(f"  - {action}")
        if item["external_blockers"]:
            lines.append("- External blockers:")
            for blocker in item["external_blockers"]:
                lines.append(f"  - {blocker}")
        if item["must_not_claim"]:
            lines.append("- Must not claim:")
            for claim in item["must_not_claim"]:
                lines.append(f"  - {claim}")
        lines.append("")
    lines.append(f"Next action: {payload['next_action']}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    payload = build_roadmap()
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, output_md)

    response = {
        "decision": payload["decision"],
        "phase_summary": payload["phase_summary"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": payload["network_io"],
        "destructive_actions": payload["destructive_actions"],
        "secrets_printed": payload["secrets_printed"],
        "live_gate_execution_allowed": payload["live_gate_execution_allowed"],
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True) if args.json else f"roadmap\t{response['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
