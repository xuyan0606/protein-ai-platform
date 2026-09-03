#!/usr/bin/env python3
"""Build a fail-closed structure-feature readiness gap plan for five heads.

This builder is read-only with respect to source evidence. It summarizes
reviewed structure graph coverage, strict MSA site-feature coverage, and the
next strict evidence chain-mapping candidates. It never writes chain-mapping
decisions, imports labels, trains a model, or opens coordinate claims.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]

GRAPH_REPORT = AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json"
CHAIN_READINESS_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness_report.json"
STRICT_MSA_REPORT = AI_ROOT / "reports" / "strict_msa_site_feature_report.json"
FIVE_HEAD_GAP_REPORT = AI_ROOT / "reports" / "five_head_training_gap_plan_report.json"

REPORT_OUT = AI_ROOT / "reports" / "structure_feature_head_gap_plan_report.json"
MD_OUT = AI_ROOT / "reports" / "structure_feature_head_gap_plan.md"
ACTIONS_OUT = AI_ROOT / "datasets" / "governance" / "structure_feature_head_gap_actions.jsonl"

HEAD_ORDER = [
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
]
MIN_ROWS_FALLBACK = 100
POLICY = (
    "Fail-closed structure feature gap plan only. This report does not write "
    "chain mapping decisions, approve coordinate claims, import labels, train "
    "models, or relax model-quality gates."
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def bool_false_from_sources(*reports: dict[str, Any]) -> bool:
    return any(report.get("safe_for_model_claim") is False for report in reports if report)


def head_gap_map(five_head_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = five_head_report.get("head_gap_actions") or []
    return {str(row.get("head")): row for row in rows if row.get("head")}


def source_blockers(
    graph_report: dict[str, Any],
    chain_report: dict[str, Any],
    msa_report: dict[str, Any],
    five_head_report: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if int_value(graph_report.get("failure_rows")):
        blockers.append("reviewed_structure_graph_has_failures")
    if int_value(graph_report.get("graph_rows")) == 0:
        blockers.append("no_reviewed_structure_graph_rows")
    if int_value(msa_report.get("missing_rows")):
        blockers.append("strict_msa_site_feature_rows_missing")
    if not msa_report.get("cache_validation_ready"):
        blockers.append("strict_msa_cache_validation_not_ready")
    for blocker in chain_report.get("blockers") or []:
        if blocker not in blockers:
            blockers.append(str(blocker))
    if five_head_report.get("status") == "blocked":
        blockers.append("five_head_training_gap_plan_blocked")
    if bool_false_from_sources(graph_report, chain_report, msa_report, five_head_report):
        blockers.append("source_reports_safe_for_model_claim_false")
    blockers.append("coordinate_claims_remain_closed_until_reviewed_chain_mappings_and_label_gates_pass")
    return blockers


def build_head_rows(
    graph_report: dict[str, Any],
    chain_report: dict[str, Any],
    msa_report: dict[str, Any],
    five_head_report: dict[str, Any],
) -> list[dict[str, Any]]:
    gap_by_head = head_gap_map(five_head_report)
    min_rows = int_value(five_head_report.get("minimum_rows_per_head"), MIN_ROWS_FALLBACK)
    graph_rows = int_value(graph_report.get("graph_rows"))
    msa_rows = int_value(msa_report.get("feature_rows"))
    usable_coordinate_rows = int_value(chain_report.get("usable_for_coordinate_features"))
    strict_candidate_rows = int_value(chain_report.get("strict_evidence_remaining_rows"))
    chain_backlog_rows = int_value(chain_report.get("remaining_unreviewed_rows"))
    feature_rows = min(graph_rows, msa_rows) if graph_rows and msa_rows else 0
    potential_after_next_batch = feature_rows + strict_candidate_rows

    rows: list[dict[str, Any]] = []
    for index, head in enumerate(HEAD_ORDER, start=1):
        gap = gap_by_head.get(head, {})
        current_label_rows = int_value(gap.get("current_training_rows"))
        minimum_rows = int_value(gap.get("minimum_rows"), min_rows)
        effective_rows = min(current_label_rows, feature_rows)
        next_batch_effective_rows = min(current_label_rows, potential_after_next_batch)
        head_blockers = [
            "minimum_effective_structure_feature_training_rows_not_met",
            "safe_for_model_claim_false",
            "coordinate_claims_closed",
        ]
        if current_label_rows < minimum_rows:
            head_blockers.append("head_label_rows_below_minimum")
        if strict_candidate_rows:
            head_blockers.append("strict_evidence_chain_candidates_require_human_decisions")
        if chain_backlog_rows:
            head_blockers.append("remaining_chain_mapping_backlog_requires_review")
        if gap.get("blocking_gate"):
            head_blockers.append(str(gap["blocking_gate"]))

        rows.append({
            "action_id": f"SFH-H{index:03d}",
            "action_scope": "structure_feature_head_gap",
            "head": head,
            "priority": gap.get("priority") or ("P1" if head == "substrate_fit" else "P0"),
            "status": "blocked",
            "current_label_rows": current_label_rows,
            "minimum_rows": minimum_rows,
            "label_gap_to_minimum": max(minimum_rows - current_label_rows, 0),
            "reviewed_structure_graph_rows": graph_rows,
            "strict_msa_site_feature_rows": msa_rows,
            "usable_coordinate_feature_rows": usable_coordinate_rows,
            "effective_training_rows_with_structure_features": effective_rows,
            "effective_gap_to_minimum": max(minimum_rows - effective_rows, 0),
            "next_strict_chain_candidate_rows": strict_candidate_rows,
            "potential_effective_rows_after_next_strict_batch": next_batch_effective_rows,
            "potential_gap_after_next_strict_batch": max(minimum_rows - next_batch_effective_rows, 0),
            "chain_mapping_backlog_rows": chain_backlog_rows,
            "label_candidate_rows_observed": int_value(gap.get("candidate_rows_observed")),
            "ready_label_candidate_rows": int_value(gap.get("ready_candidate_rows")),
            "blocking_gate": gap.get("blocking_gate")
            or "structure features and reviewed labels do not meet five-head minimums",
            "next_action": (
                "Use reviewed structure graph features only in offline fail-closed experiments; "
                "review strict evidence chain candidates before expanding coordinate features."
            ),
            "training_unlocked": False,
            "coordinate_claim_allowed": False,
            "safe_for_model_claim": False,
            "human_review_required": True,
            "source_reports": [
                rel(GRAPH_REPORT),
                rel(CHAIN_READINESS_REPORT),
                rel(STRICT_MSA_REPORT),
            ],
            "blockers": head_blockers,
            "policy": POLICY,
        })
    return rows


def strict_candidate_rows(chain_report: dict[str, Any], created_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    strict_queue = [
        row for row in chain_report.get("next_review_queue") or []
        if row.get("evidence_tier") == "strict_evidence_ready_for_human_decision"
    ]
    for index, row in enumerate(strict_queue[:9], start=1):
        structure_id = str(row.get("structure_id") or "").upper()
        rows.append({
            "action_id": f"SFH-C{index:03d}-{structure_id}",
            "action_scope": "strict_evidence_chain_candidate",
            "created_at": created_at,
            "status": "ready_for_human_review_blocked",
            "priority": "P0",
            "structure_id": structure_id,
            "canonical_uniprot_id": row.get("canonical_uniprot_id"),
            "protein_name": row.get("protein_name"),
            "review_rank": row.get("review_rank"),
            "review_bucket": row.get("review_bucket"),
            "packet_id": row.get("packet_id"),
            "suggested_selected_chain_id": row.get("suggested_selected_chain_id"),
            "strict_evidence_sources": row.get("strict_evidence_sources") or [],
            "chain_count": row.get("chain_count"),
            "parsed_chain_ids": row.get("parsed_chain_ids") or [],
            "db_chain_ids": row.get("db_chain_ids") or [],
            "resolution": row.get("resolution"),
            "decision_input": row.get("decision_input"),
            "required_human_checks": row.get("required_human_checks") or [],
            "operator_action": (
                "Review evidence packet and append an explicit set_chain_mapping or "
                "reject_structure decision only after human confirmation."
            ),
            "forbidden_actions": [
                "auto_write_structure_chain_mapping_decision",
                "auto_apply_coordinate_claim",
                "training_label_import",
                "model_quality_claim_unlock",
            ],
            "coordinate_claim_allowed": False,
            "safe_for_model_claim": False,
            "human_review_required": True,
            "policy": "Strict evidence review candidate only; not a reviewed chain mapping decision.",
        })
    return rows


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Structure Feature Head Gap Plan",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This is a fail-closed, read-only readiness plan. It does not write chain mapping decisions or open coordinate claims.",
        "",
        "## Summary",
        "",
        f"- Status: {report['status']}",
        f"- Heads ready for structure-feature training: {report['ready_heads']}/{report['total_heads']}",
        f"- Reviewed structure graph rows: {report['structure_feature_summary']['reviewed_structure_graph_rows']}",
        f"- Strict MSA site feature rows: {report['structure_feature_summary']['strict_msa_site_feature_rows']}",
        f"- Effective strict structure-feature rows: {report['structure_feature_summary']['effective_strict_structure_feature_rows']}",
        f"- Remaining chain-mapping backlog: {report['structure_feature_summary']['remaining_chain_mapping_rows']}",
        f"- Next strict evidence candidates: {report['structure_feature_summary']['next_strict_evidence_candidate_rows']}",
        f"- Coordinate claims allowed: {str(report['coordinate_claim_allowed']).lower()}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Head Readiness",
        "",
        "| head | labels | effective structure-feature rows | effective gap | next strict batch potential | blocker |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in report["head_readiness"]:
        lines.append(
            "| {head} | {current_label_rows} | {effective_training_rows_with_structure_features} | "
            "{effective_gap_to_minimum} | {potential_effective_rows_after_next_strict_batch} | {blocking_gate} |".format(
                **row
            )
        )

    lines.extend([
        "",
        "## Next 9 Strict Evidence Chain Candidates",
        "",
        "| # | structure | UniProt | packet | suggested chain | bucket | resolution |",
        "|---:|---|---|---|---|---|---:|",
    ])
    for index, row in enumerate(report["strict_evidence_chain_candidates"], start=1):
        resolution = row.get("resolution")
        resolution_text = "" if resolution is None else str(resolution)
        lines.append(
            f"| {index} | {row['structure_id']} | {row.get('canonical_uniprot_id') or ''} | "
            f"{row.get('packet_id') or ''} | {row.get('suggested_selected_chain_id') or ''} | "
            f"{row.get('review_bucket') or ''} | {resolution_text} |"
        )

    lines.extend([
        "",
        "## Blockers",
        "",
    ])
    for blocker in report["blockers"]:
        lines.append(f"- {blocker}")
    lines.extend([
        "",
        "## Policy",
        "",
        report["policy"],
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    graph_report = load_json(args.graph_report)
    chain_report = load_json(args.chain_readiness_report)
    msa_report = load_json(args.strict_msa_report)
    five_head_report = load_json(args.five_head_gap_report)
    created_at = datetime.now(timezone.utc).isoformat()

    head_rows = build_head_rows(graph_report, chain_report, msa_report, five_head_report)
    candidate_rows = strict_candidate_rows(chain_report, created_at)
    all_actions = head_rows + candidate_rows
    graph_rows = int_value(graph_report.get("graph_rows"))
    msa_rows = int_value(msa_report.get("feature_rows"))
    effective_feature_rows = min(graph_rows, msa_rows) if graph_rows and msa_rows else 0
    strict_candidate_count = len(candidate_rows)
    min_rows = int_value(five_head_report.get("minimum_rows_per_head"), MIN_ROWS_FALLBACK)

    return {
        "created_at": created_at,
        "local_only": True,
        "status": "blocked",
        "total_heads": len(head_rows),
        "ready_heads": 0,
        "minimum_rows_per_head": min_rows,
        "source_reports": {
            "reviewed_structure_graph_feature_report": rel(args.graph_report),
            "structure_chain_mapping_backlog_readiness_report": rel(args.chain_readiness_report),
            "strict_msa_site_feature_report": rel(args.strict_msa_report),
            "five_head_training_gap_plan_report": rel(args.five_head_gap_report),
        },
        "structure_feature_summary": {
            "reviewed_structure_graph_rows": graph_rows,
            "reviewed_structure_graph_failure_rows": int_value(graph_report.get("failure_rows")),
            "reviewed_structure_graph_node_count_total": int_value(graph_report.get("node_count_total")),
            "reviewed_structure_graph_edge_count_total": int_value(graph_report.get("edge_count_total")),
            "mapping_status_counts": graph_report.get("mapping_status_counts") or {},
            "strict_msa_site_feature_rows": msa_rows,
            "strict_msa_site_missing_rows": int_value(msa_report.get("missing_rows")),
            "strict_msa_cache_validation_ready": bool(msa_report.get("cache_validation_ready")),
            "strict_msa_cache_validation_valid_rows": int_value(msa_report.get("cache_validation_valid_rows")),
            "strict_msa_label_distribution": msa_report.get("label_distribution") or {},
            "effective_strict_structure_feature_rows": effective_feature_rows,
            "usable_coordinate_feature_rows": int_value(chain_report.get("usable_for_coordinate_features")),
            "reviewed_chain_mapping_rows": int_value(chain_report.get("reviewed_chain_mapping_rows"))
            or int_value(chain_report.get("decision_rows")),
            "remaining_chain_mapping_rows": int_value(chain_report.get("remaining_unreviewed_rows")),
            "strict_evidence_total_rows": int_value(chain_report.get("strict_evidence_total_rows")),
            "strict_evidence_already_decided_rows": int_value(chain_report.get("strict_evidence_already_decided_rows")),
            "next_strict_evidence_candidate_rows": strict_candidate_count,
            "potential_feature_rows_after_next_strict_batch": effective_feature_rows + strict_candidate_count,
            "potential_feature_gap_after_next_strict_batch": max(
                min_rows - (effective_feature_rows + strict_candidate_count),
                0,
            ),
            "missing_packet_rows": int_value(chain_report.get("missing_packet_rows")),
        },
        "gap_summary": {
            "heads_below_effective_minimum": len(head_rows),
            "total_effective_training_row_gap_to_minimum": sum(
                int_value(row.get("effective_gap_to_minimum")) for row in head_rows
            ),
            "total_label_row_gap_to_minimum": sum(
                int_value(row.get("label_gap_to_minimum")) for row in head_rows
            ),
            "structure_feature_capacity_gap_to_minimum": max(min_rows - effective_feature_rows, 0),
            "next_strict_batch_size": strict_candidate_count,
            "full_chain_mapping_backlog_rows": int_value(chain_report.get("remaining_unreviewed_rows")),
        },
        "head_readiness": head_rows,
        "strict_evidence_chain_candidates": candidate_rows,
        "action_jsonl": rel(args.actions),
        "action_rows": len(all_actions),
        "head_action_rows": len(head_rows),
        "strict_candidate_action_rows": len(candidate_rows),
        "blockers": source_blockers(graph_report, chain_report, msa_report, five_head_report),
        "next_actions": [
            "Review the 9 strict evidence chain candidates in order and write explicit decisions only after human confirmation.",
            "After any reviewed decisions, run validate_structure_chain_mapping_decisions.py and apply_structure_chain_mapping_decisions.py.",
            "Rebuild reviewed structure graph features, strict MSA site features, five-head gap plan, and this structure-feature gap report.",
            "Keep coordinate claims, training imports, model-quality claims, and release gates closed until all upstream gates pass.",
        ],
        "coordinate_claim_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure feature head gap plan")
    parser.add_argument("--graph-report", type=Path, default=GRAPH_REPORT)
    parser.add_argument("--chain-readiness-report", type=Path, default=CHAIN_READINESS_REPORT)
    parser.add_argument("--strict-msa-report", type=Path, default=STRICT_MSA_REPORT)
    parser.add_argument("--five-head-gap-report", type=Path, default=FIVE_HEAD_GAP_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--actions", type=Path, default=ACTIONS_OUT)
    args = parser.parse_args()

    report = build_report(args)
    write_jsonl(args.actions, report["head_readiness"] + report["strict_evidence_chain_candidates"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "ready_heads": report["ready_heads"],
        "total_heads": report["total_heads"],
        "effective_strict_structure_feature_rows": report["structure_feature_summary"]["effective_strict_structure_feature_rows"],
        "next_strict_evidence_candidate_rows": report["structure_feature_summary"]["next_strict_evidence_candidate_rows"],
        "action_rows": report["action_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
