#!/usr/bin/env python3
"""Build a read-only P0-P4 gap audit.

This script does not run live gates, download data, train models, mutate
databases, or print secrets. It scans local contract tokens and summarizes
which gaps remain local-buildable versus blocked by external evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p2_p3_p4_roadmap import build_roadmap
from check_remaining_backlog_readiness import DEFAULT_DEPLOY_ROOT, _load_values, _summary, collect


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-gap-audit.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-gap-audit.md"
P2_P3_P4_EXPECTED_TOKENS = [
    "p2_candidate_readiness_summary_v1",
    "p2_objective_score_readiness_summary_v1",
    "dbtl_project_memory_readiness_v1",
    "dbtl_feedback_readiness_summary_v1",
    "p4_active_learning_batch_contract_v1",
    "p4_model_calibration_registry_contract_v1",
    "p4_manufacturing_constraint_schema_v1",
]
STATUS_EXPORT_TOKENS = [
    "p0_p4_status_export_v1",
    "p0_p4_status_export_contract_v1",
    "p0_p4_contract_status_export_v1",
    "contract_status_items",
    "evidence_tokens",
    "approval_required",
]
STATUS_EXPORT_COVERED_LOCAL_GAPS = {
    "specified_mutation_review": {
        "surface the review contract in P0/P1/P2/P3/P4 gap audit exports",
    },
    "site_structure_function_mvp": {
        "add downstream SOP/status rollup for pocket/channel/interface unknown fields",
    },
    "multi_objective_candidate_table": {
        "expose schedulability and objective gaps in SOP/status exports",
    },
    "followup_review_routes": {
        "add explicit P0 follow-up status line to audit/report exports",
    },
    "numbering_registry": {
        "publish numbering registry readiness in P0-P4 audit outputs",
    },
    "catalytic_mechanism_profile": {
        "add explicit second-shell/source-coordinate coverage rollup to audit exports",
    },
    "reaction_profile": {
        "connect reaction profile readiness into the P0-P4 audit and report status exports",
    },
    "wt_baseline_registry": {
        "show WT baseline readiness next to objective assay gaps in downstream exports",
    },
    "residue_feature_table_contract": {
        "Expose a structure-feature gap summary in downstream SOP/status exports so pocket/channel/interface, conservation, ddG, and MD-derived fields remain explicit until computed.",
        "Expose the calculator/source boundary in downstream SOP/status exports and continue widening residue feature fields only when a structured calculator or curated source exists.",
    },
    "objective_score_contract": {
        "Expose unknown-component blocking state in downstream SOP/status exports and keep unknown objective components blocking instead of neutral.",
        "Expose objective assay gaps beside project feedback readiness in downstream SOP/status exports.",
    },
    "candidate_table_generation_contract": {
        "Expose experiment design schedulability policy in downstream SOP views.",
        "Keep candidate table promotion tied to candidate_status and assay readiness.",
    },
    "dbtl_trace_contract": {
        "Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved.",
        "Expose project memory readiness in downstream SOP/status views.",
    },
    "feedback_import_and_next_round_contract": {
        "Expose feedback readiness in downstream SOP/status exports.",
        "Expose pair/higher-order gate state in downstream SOP/status exports and keep pair/higher-order designs blocked until singleton and structure evidence pass.",
    },
    "industrial_closed_loop_readiness": {
        "Expose P4 contract status and operator review state in downstream SOP/status exports.",
        "Expose live-gate approval block state in downstream SOP/status exports and keep live gate approval blocked until an explicit operator review is recorded.",
    },
}


def _status_export_ready() -> bool:
    return _has("scripts/build_p0_p4_status_export.py", *STATUS_EXPORT_TOKENS)


def _local_gap_coverage(name: str, gaps: list[str], *, status_export_ready: bool) -> dict[str, Any]:
    covered: list[dict[str, str]] = []
    open_gaps: list[str] = []
    covered_gaps = STATUS_EXPORT_COVERED_LOCAL_GAPS.get(name, set())
    for gap in gaps:
        if status_export_ready and gap in covered_gaps:
            covered.append(
                {
                    "gap": gap,
                    "status": "covered_by_contract_status_export",
                    "evidence": "p0_p4_contract_status_export_v1",
                }
            )
        else:
            open_gaps.append(gap)
    return {
        "covered": covered,
        "open": open_gaps,
        "covered_count": len(covered),
        "open_count": len(open_gaps),
    }


def _read(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _source(relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    return {"path": relative_path, "exists": path.exists()}


def _audit_values() -> dict[str, str]:
    values = _load_values(PROJECT_ROOT / "docker" / ".env.aliyun.app.example")
    for key in (
        "PUBLIC_BASE_URL",
        "FRONTEND_URL",
        "OIDC_ISSUER",
        "MD_BLACKBOX_TASK_ID",
        "MD_BLACKBOX_EMAIL",
        "LIVE_AI_EMAIL",
        "MD_BLACKBOX_PASSWORD",
        "LIVE_AI_PASSWORD",
        "ALLOW_MD_BLACKBOX_SUBMIT",
        "REMOTE_TEST_RUNNER_IMAGE",
        "TEST_RUNNER_IMAGE",
        "CI_TEST_RUNNER_URL",
        "CI_PIPELINE_URL",
        "SCREENSHOT_EMAIL",
        "SCREENSHOT_PASSWORD",
        "MAINTENANCE_WINDOW_ID",
        "ALLOW_PRODUCTION_DRILL",
        "REMOTE_BACKUP_TARGET",
        "OFFSITE_BACKUP_TARGET",
        "EXTERNAL_STORAGE_RESTORE_TARGET",
        "MINIO_ENDPOINT",
        "MINIO_BUCKET",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_REGION",
        "ALIYUN_OSS_ENDPOINT",
        "ALIYUN_OSS_REGION",
        "ALIYUN_OSS_BUCKET",
        "ALIYUN_OSS_ACCESS_KEY_ID",
        "ALIYUN_OSS_ACCESS_KEY_SECRET",
    ):
        values.pop(key, None)
    return values


def _has(relative_path: str, *tokens: str) -> bool:
    text = _read(relative_path)
    return bool(text) and all(token in text for token in tokens)


def _phase_item(
    *,
    phase: str,
    name: str,
    status: str,
    summary: str,
    source_paths: list[str],
    evidence_tokens: list[str],
    local_gaps: list[str] | None = None,
    external_blockers: list[str] | None = None,
    next_actions: list[str] | None = None,
    must_not_claim: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "name": name,
        "status": status,
        "summary": summary,
        "sources": [_source(path) for path in source_paths],
        "evidence_tokens": evidence_tokens,
        "local_gaps": local_gaps or [],
        "external_blockers": external_blockers or [],
        "next_actions": next_actions or [],
        "must_not_claim": must_not_claim or [],
    }


def _p0_items() -> list[dict[str, Any]]:
    return [
        _phase_item(
            phase="P0",
            name="specified_mutation_review",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/mutation_priority_score.py",
                "specified_mutation_reviews",
                "specified_mutation_review_computational_hypothesis",
            )
            and _has("backend/app/core/agent_graph.py", "specified_mutation_reviews")
            else "partial",
            summary="User-requested point mutations are parsed and reviewed separately from generic candidate generation.",
            source_paths=[
                "backend/app/tools/mutation_priority_score.py",
                "backend/app/core/agent_graph.py",
                "backend/tests/test_requested_mutation_review.py",
                "backend/tests/test_tools_api.py",
            ],
            evidence_tokens=["specified_mutation_reviews", "specified_mutation_review_computational_hypothesis"],
            local_gaps=["surface the review contract in P0/P1/P2/P3/P4 gap audit exports"],
            external_blockers=["complete numbering, pocket, conservation, WT baseline, and experiment feedback evidence for claim upgrade"],
            next_actions=["Keep specified mutation output in Watch/No-Go when numbering or protection evidence is incomplete."],
            must_not_claim=["specified mutation is experimentally validated by review", "numbering mismatch can be ignored"],
        ),
        _phase_item(
            phase="P0",
            name="site_structure_function_mvp",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/site_structure_function_features.py",
                "site_structure_function_features_v1",
                "residue_distance_graph_v1",
            )
            else "partial",
            summary="Residue-level CA geometry, relSASA, HETATM distance, secondary-structure annotation, and distance graph are available with conservative unknowns.",
            source_paths=[
                "backend/app/tools/site_structure_function_features.py",
                "backend/tests/test_mutation_objective_scores.py",
                "frontend/src/components/analysis/SiteStructureFunctionFeaturesCard.tsx",
            ],
            evidence_tokens=["site_structure_function_features_v1", "residue_distance_graph_v1"],
            local_gaps=["add downstream SOP/status rollup for pocket/channel/interface unknown fields"],
            external_blockers=["validated pocket/channel/interface calculator", "curated conservation or MSA pipeline", "real ddG/packing/MD RMSF artifacts"],
            next_actions=["Keep uncomputed fields as unknown and visible in candidate evidence summaries."],
            must_not_claim=["complete residue feature table", "DSSP/pocket/conservation/ddG/MD coverage when unavailable"],
        ),
        _phase_item(
            phase="P0",
            name="multi_objective_candidate_table",
            status="ready_local_contract"
            if _has(
                "backend/app/tools/mutation_priority_score.py",
                "candidate_table_generation_v1",
                "experiment_design_schedulability_policy_v1",
            )
            else "partial",
            summary="Candidate table separates activity, stability, risk, evidence, status, and experiment action with schedulability policy.",
            source_paths=[
                "backend/app/tools/mutation_priority_score.py",
                "frontend/src/components/analysis/MutationScoreCard.tsx",
                "frontend/src/lib/report.ts",
            ],
            evidence_tokens=["candidate_table_generation_v1", "experiment_design_schedulability_policy_v1"],
            local_gaps=["expose schedulability and objective gaps in SOP/status exports"],
            external_blockers=["wet-lab validation for promotion", "matched WT baseline and assay controls for improvement claims"],
            next_actions=["Continue excluding blocked/No-Go/protected rows from experiment design tables."],
            must_not_claim=["blocked candidates are schedulable", "candidate table is wet-lab validated"],
        ),
        _phase_item(
            phase="P0",
            name="followup_review_routes",
            status="ready_local_contract"
            if _has(
                "backend/app/core/agent_graph.py",
                "_is_p0_followup_review",
                "_message_requests_prediction_experiment_mismatch_followup",
                "_message_requests_venus_gap_followup",
            )
            else "partial",
            summary="Follow-up questions for Venus comparison, candidate explanation, experiment mismatch, and specified mutations reuse the prior object instead of replanning new candidates.",
            source_paths=["backend/app/core/agent_graph.py", "backend/tests/test_agent_binder.py"],
            evidence_tokens=["_is_p0_followup_review", "specified_mutation_reviews"],
            local_gaps=["add explicit P0 follow-up status line to audit/report exports"],
            external_blockers=["prior trace context and structured experiment feedback for conflict explanation"],
            next_actions=["Keep follow-up routes fail-closed when prior object or numbering context is absent."],
            must_not_claim=["follow-up generated new validated candidates", "experiment mismatch is resolved without assay context"],
        ),
    ]


def _p1_items() -> list[dict[str, Any]]:
    return [
        _phase_item(
            phase="P1",
            name="numbering_registry",
            status="ready_local_contract"
            if _has("backend/app/tools/residue_mapping_sifts.py", "numbering_registry_rows", "numbering_registry_status")
            and _has("backend/app/tools/residue_numbering_gate.py", "unified_numbering_registry_v1")
            else "partial",
            summary="SIFTS/curated rows and inferred mappings are normalized into unified numbering registry rows consumed by numbering gate.",
            source_paths=[
                "backend/app/tools/residue_mapping_sifts.py",
                "backend/app/tools/residue_numbering_gate.py",
                "backend/tests/test_structure_tools.py",
                "backend/tests/test_tools_api.py",
            ],
            evidence_tokens=["numbering_registry_rows", "unified_numbering_registry_v1"],
            local_gaps=["publish numbering registry readiness in P0-P4 audit outputs"],
            external_blockers=["complete SIFTS coverage or user-confirmed numbering for each target"],
            next_actions=["Keep inferred mappings downgraded until confirmed."],
            must_not_claim=["inferred mapping is verified SIFTS", "unmapped residues support strong site claims"],
        ),
        _phase_item(
            phase="P1",
            name="catalytic_mechanism_profile",
            status="ready_local_contract"
            if _has(
                "backend/app/services/annotation_query_service.py",
                "catalytic_mechanism_profile_v1",
                "pending_numbering",
                "first_shell_positions",
            )
            else "partial",
            summary="Catalytic role, first-shell state, pending numbering, and mechanism report contract are available from local annotation services.",
            source_paths=[
                "backend/app/services/annotation_query_service.py",
                "backend/app/services/annotation_facade.py",
                "backend/tests/test_annotation_facade.py",
                "backend/tests/test_data_api.py",
            ],
            evidence_tokens=["catalytic_mechanism_profile_v1", "pending_numbering", "first_shell_positions"],
            local_gaps=["add explicit second-shell/source-coordinate coverage rollup to audit exports"],
            external_blockers=["complete M-CSA-style curated mechanism coverage and user-coordinate verification"],
            next_actions=["Keep first shell under manual review and block protected catalytic residues."],
            must_not_claim=["complete M-CSA mechanism map", "second shell fully computed"],
        ),
        _phase_item(
            phase="P1",
            name="reaction_profile",
            status="ready_local_contract"
            if _has("backend/app/services/reaction_profile.py", "reaction_profile_v1", "requires_reaction_profile")
            else "partial",
            summary="Reaction Profile is available for exact local EC/Rhea-style matches and blocks substrate-scope claims when incomplete.",
            source_paths=[
                "backend/app/services/reaction_profile.py",
                "backend/tests/test_reaction_profile.py",
                "backend/tests/test_data_api.py",
            ],
            evidence_tokens=["reaction_profile_v1", "requires_reaction_profile"],
            local_gaps=["connect reaction profile readiness into the P0-P4 audit and report status exports"],
            external_blockers=["Rhea/ChEBI production coverage and curated substrate/product/cofactor directionality"],
            next_actions=["Keep substrate specificity and activity claims blocked when reaction evidence is partial."],
            must_not_claim=["substrate spectrum optimized without reaction evidence", "Rhea/ChEBI production sync complete"],
        ),
        _phase_item(
            phase="P1",
            name="wt_baseline_registry",
            status="ready_local_contract"
            if _has("backend/app/services/wt_baseline_registry.py", "wt_baseline_registry_v1", "wt_baseline_report_contract_v1")
            else "partial",
            summary="WT baseline registry resolves only exact-condition QC-passed WT feedback and blocks improvement claims without matched baseline.",
            source_paths=[
                "backend/app/services/wt_baseline_registry.py",
                "backend/app/tools/wt_baseline_registry.py",
                "backend/tests/test_wt_baseline_registry.py",
                "backend/tests/test_tools_api.py",
            ],
            evidence_tokens=["wt_baseline_registry_v1", "wt_baseline_report_contract_v1"],
            local_gaps=["show WT baseline readiness next to objective assay gaps in downstream exports"],
            external_blockers=["same-batch WT baseline, assay conditions, replicate/QC metadata, BRENDA/SABIO-RK-style curation"],
            next_actions=["Keep baseline-dependent claims blocked unless registry status is ready."],
            must_not_claim=["improvement without exact-condition WT baseline", "approximate baseline is equivalent"],
        ),
    ]


def _phase_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in items:
        row = summary.setdefault(
            item["phase"],
            {
                "item_count": 0,
                "ready_local_contract": 0,
                "partial": 0,
                "blocked": 0,
                "external_blocker_count": 0,
                "local_gap_count": 0,
                "open_local_gap_count": 0,
                "covered_local_gap_count": 0,
                "items": [],
            },
        )
        row["item_count"] += 1
        row["items"].append(item["name"])
        if item["status"] in row:
            row[item["status"]] += 1
        row["external_blocker_count"] += len(item.get("external_blockers") or [])
        row["local_gap_count"] += len(item.get("local_gaps") or [])
        gap_status = item.get("local_gap_status") if isinstance(item.get("local_gap_status"), dict) else {}
        row["open_local_gap_count"] += int(gap_status.get("open_count") or 0)
        row["covered_local_gap_count"] += int(gap_status.get("covered_count") or 0)
    return summary


def build_gap_audit() -> dict[str, Any]:
    p2_p3_p4 = build_roadmap()
    status_export_ready = _status_export_ready()
    p0_p1_items = _p0_items() + _p1_items()
    downstream_items = []
    for item in p2_p3_p4["items"]:
        downstream_items.append(
            {
                **item,
                "local_gaps": item.get("next_local_actions", []),
                "next_actions": item.get("next_local_actions", []),
            }
        )
    items = p0_p1_items + downstream_items
    for item in items:
        gaps = [str(gap) for gap in item.get("local_gaps") or []]
        item["local_gap_status"] = _local_gap_coverage(
            str(item.get("name") or ""),
            gaps,
            status_export_ready=status_export_ready,
        )

    backlog_items = collect(DEFAULT_DEPLOY_ROOT, _audit_values(), runtime_env={})
    backlog_summary = _summary(backlog_items)
    external_backlog = [
        item.as_dict()
        for item in backlog_items
        if item.status in {"external_required", "blocked", "planned"}
    ]

    next_local_actions = [
        "Keep downstream contract-status export explicit for P0 follow-up, P1 evidence readiness, and P2/P3/P4 readiness contracts.",
        "Keep P2/P3/P4 local contracts source-bound and fail-closed while widening visibility.",
        "Do not execute live gates until remaining-backlog external inputs are complete and operator-approved.",
    ]

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_p0_p4_gap_audit",
        "decision": "continue_local_gap_closure_fail_closed_for_external_dependencies",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "phase_summary": _phase_summary(items),
        "items": items,
        "status_export_ready": status_export_ready,
        "remaining_backlog_summary": backlog_summary,
        "remaining_external_backlog": external_backlog,
        "imported_roadmap_expected_tokens": P2_P3_P4_EXPECTED_TOKENS,
        "next_local_actions": next_local_actions,
        "must_not_claim": [
            "P0-P4 production system is fully complete",
            "live gates have run",
            "model has been trained or retrained",
            "wet-lab validation or manufacturing constraints are proven by this audit",
        ],
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# P0-P4 Gap Audit",
        "",
        f"- decision: `{payload['decision']}`",
        f"- network_io: `{payload['network_io']}`",
        f"- destructive_actions: `{payload['destructive_actions']}`",
        f"- live_gate_execution_allowed: `{payload['live_gate_execution_allowed']}`",
        "",
        "## Phase Summary",
        "",
        "| Phase | Items | Ready Local | Partial | Blocked | Open Local Gaps | Covered Local Gaps | External Blockers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for phase, row in sorted(payload["phase_summary"].items()):
        lines.append(
            f"| `{phase}` | `{row['item_count']}` | `{row['ready_local_contract']}` | "
            f"`{row['partial']}` | `{row['blocked']}` | `{row['open_local_gap_count']}` | "
            f"`{row['covered_local_gap_count']}` | `{row['external_blocker_count']}` |"
        )

    lines.extend(["", "## Items", ""])
    for item in payload["items"]:
        lines.extend(
            [
                f"### {item['phase']} / {item['name']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Summary: {item['summary']}",
                f"- Evidence tokens: `{', '.join(item['evidence_tokens'])}`",
                "- Sources:",
            ]
        )
        for source in item["sources"]:
            lines.append(f"  - `{source['path']}` exists=`{source['exists']}`")
        if item.get("local_gaps"):
            lines.append("- Local gaps:")
            lines.extend([f"  - {gap}" for gap in item["local_gaps"]])
        gap_status = item.get("local_gap_status") if isinstance(item.get("local_gap_status"), dict) else {}
        if gap_status.get("covered"):
            lines.append("- Covered local gaps:")
            for covered in gap_status["covered"]:
                lines.append(f"  - {covered['gap']} -> `{covered['status']}` via `{covered['evidence']}`")
        if gap_status.get("open"):
            lines.append("- Open local gaps:")
            lines.extend([f"  - {gap}" for gap in gap_status["open"]])
        if item.get("external_blockers"):
            lines.append("- External blockers:")
            lines.extend([f"  - {blocker}" for blocker in item["external_blockers"]])
        if item.get("must_not_claim"):
            lines.append("- Must not claim:")
            lines.extend([f"  - {claim}" for claim in item["must_not_claim"]])
        lines.append("")

    lines.extend(
        [
            "## Remaining External Backlog",
            "",
            f"- status: `{payload['remaining_backlog_summary']['status']}`",
            f"- counts: `{json.dumps(payload['remaining_backlog_summary']['counts'], sort_keys=True)}`",
            "",
        ]
    )
    for item in payload["remaining_external_backlog"]:
        lines.extend(
            [
                f"### {item['name']}",
                f"- Status: `{item['status']}`",
                f"- Bucket: `{item['bucket']}`",
                f"- Detail: {item['detail']}",
            ]
        )
        if item.get("missing_requirements"):
            lines.append("- Missing requirements:")
            lines.extend([f"  - {value}" for value in item["missing_requirements"]])
        lines.append("")

    lines.append("## Next Local Actions")
    lines.extend([f"- {action}" for action in payload["next_local_actions"]])
    lines.append("")
    lines.append("## Must Not Claim")
    lines.extend([f"- {claim}" for claim in payload["must_not_claim"]])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    payload = build_gap_audit()
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, output_md)

    response = {
        "decision": payload["decision"],
        "phase_summary": payload["phase_summary"],
        "remaining_backlog_summary": payload["remaining_backlog_summary"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": payload["network_io"],
        "destructive_actions": payload["destructive_actions"],
        "secrets_printed": payload["secrets_printed"],
        "live_gate_execution_allowed": payload["live_gate_execution_allowed"],
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True) if args.json else f"gap-audit\t{response['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
