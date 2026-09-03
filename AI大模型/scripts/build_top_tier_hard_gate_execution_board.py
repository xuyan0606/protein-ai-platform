#!/usr/bin/env python3
"""Build a fail-closed execution board for top-tier model hard gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "top_tier_hard_gate_execution_board.json"
MD_OUT = AI_ROOT / "reports" / "top_tier_hard_gate_execution_board.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "top_tier_hard_gate_execution_actions.jsonl"

POLICY = (
    "Fail-closed hard-gate execution board only. It does not write reviewed decisions, "
    "approve wet-lab rows, import labels, approve benchmarks, execute Rosetta/FoldX, "
    "train models, deploy services, sync production, or relax model-quality gates."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def make_gate(
    gate_id: str,
    title: str,
    priority: str,
    owner_lane: str,
    status: str,
    observed: dict[str, Any],
    missing: list[str],
    next_actions: list[str],
    evidence: list[str],
    execution_type: str,
    human_required: bool = True,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "title": title,
        "priority": priority,
        "owner_lane": owner_lane,
        "status": status,
        "execution_type": execution_type,
        "observed": observed,
        "missing": missing,
        "next_actions": next_actions,
        "evidence_artifacts": evidence,
        "human_or_external_authorization_required": human_required,
        "training_unlocked": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "policy": POLICY,
    }


def build_gates() -> list[dict[str, Any]]:
    numbering = load_json(AI_ROOT / "reports" / "numbering_review_operator_queue.json")
    conflicts = load_json(AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json")
    provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    five_head = load_json(AI_ROOT / "reports" / "five_head_training_gap_plan_report.json")
    wetlab = load_json(AI_ROOT / "reports" / "wet_lab_head_authorization_gap_plan_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json")
    substrate = load_json(AI_ROOT / "reports" / "substrate_fit_label_gap_plan_report.json")
    structure = load_json(AI_ROOT / "reports" / "structure_feature_head_gap_plan_report.json")
    ddg = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    ddg_packets = load_json(AI_ROOT / "reports" / "ddg_backend_operator_packet_report.json")
    ddg_discovery = load_json(AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json")

    benchmark_summary = benchmark.get("summary") or {}
    wetlab_source = wetlab.get("source_state") or {}
    label_gap = substrate.get("label_gap") or {}
    structure_summary = structure.get("structure_feature_summary") or {}
    five_head_signals = five_head.get("candidate_signals") or {}
    multitask_heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    blocked_heads = [
        head for head, row in multitask_heads.items()
        if isinstance(row, dict) and row.get("ready") is not True
    ]
    physical_backends = [
        row for row in ddg.get("backends") or []
        if row.get("backend") in {"rosetta", "pyrosetta", "foldx"}
    ]
    semantic_conflict_rows = as_int(conflicts.get("semantic_conflict_rows") or numbering.get("semantic_conflict_rows"))
    open_numbering_rows = as_int(numbering.get("open_numbering_rows"))
    numbering_missing = [
        "Create reviewed numbering decisions backed by real canonical/isoform/literature evidence.",
        "Reach >=100 claim-eligible real supervised rows with synthetic_or_unreceipted_rows=0.",
    ]
    numbering_next_actions = [
        f"Continue reviewing the {open_numbering_rows} open operator-queue rows; reject generated/fixture rows unless real evidence exists.",
        "Rerun numbering validation, apply curation, label provenance audit, and safe pipeline after decisions.",
    ]
    if semantic_conflict_rows:
        numbering_missing.insert(0, f"Resolve {semantic_conflict_rows} semantic conflict rows explicitly.")
        numbering_next_actions.insert(
            0,
            f"Use the numbering review UI to resolve {semantic_conflict_rows} semantic conflict rows.",
        )
    else:
        numbering_next_actions.insert(
            0,
            "Semantic conflict queue is clear; continue reviewed numbering and real-source provenance review.",
        )

    gates = [
        make_gate(
            gate_id="HTG-001-reviewed-numbering-real-labels",
            title="Reviewed numbering and real supervised label provenance",
            priority="P0",
            owner_lane="sequence_data_agent",
            status="blocked",
            execution_type="human_review_and_label_provenance_gate",
            observed={
                "numbering_queue_rows": as_int(numbering.get("queue_rows")),
                "open_numbering_rows": open_numbering_rows,
                "semantic_conflict_rows": semantic_conflict_rows,
                "strict_supervised_rows": as_int(provenance.get("strict_rows")),
                "claim_eligible_rows": as_int(provenance.get("claim_eligible_rows")),
                "synthetic_or_unreceipted_rows": as_int(provenance.get("synthetic_or_unreceipted_rows")),
                "blocked_heads": blocked_heads,
            },
            missing=numbering_missing,
            next_actions=numbering_next_actions,
            evidence=[
                "reports/numbering_review_operator_queue.json",
                "reports/numbering_decision_semantic_conflict_report.json",
                "reports/label_provenance_audit_report.json",
                "reports/multitask_training_readiness_report.json",
            ],
        ),
        make_gate(
            gate_id="HTG-002-wet-lab-training-eligible-feedback",
            title="Wet-lab authorization and training-eligible feedback",
            priority="P0",
            owner_lane="wet_lab_feedback_agent",
            status="blocked",
            execution_type="human_metric_authorization_and_feedback_intake_gate",
            observed={
                "wet_lab_numeric_candidate_rows": as_int(five_head_signals.get("wet_lab_numeric_candidate_rows")),
                "authorization_action_rows": as_int(wetlab.get("action_rows")),
                "authorization_rows": as_int(wetlab_source.get("authorization_rows")),
                "authorized_candidate_rows": as_int(wetlab_source.get("authorized_candidate_rows")),
                "preflight_rows": as_int(wetlab_source.get("preflight_rows")),
                "apply_plan_rows": as_int(wetlab_source.get("apply_plan_rows")),
                "training_rows_added_by_plan": as_int(wetlab.get("training_rows_added_by_plan")),
                "head_action_counts": wetlab.get("head_action_counts") or {},
            },
            missing=[
                "Metric-level human authorization rows for 12 real wet-lab candidates.",
                "Schema-valid feedback preflight and apply-plan rows.",
                "Separate reviewed mapping from wet-lab measurements to model head labels.",
            ],
            next_actions=[
                "Review D105N/E331Q/S265T wet-lab metrics in the wet-lab UI.",
                "Record approve/reject/needs_more_info decisions with reviewer, basis, QC, numbering, units, batch and replicate flags.",
                "Rerun wet-lab authorization validation, preflight, apply-plan, and five-head gap reports.",
            ],
            evidence=[
                "reports/wet_lab_head_authorization_gap_plan_report.json",
                "datasets/feedback/wet_lab_head_authorization_gap_actions.jsonl",
                "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            ],
        ),
        make_gate(
            gate_id="HTG-003-benchmark-scorecard-claim-cache",
            title="Benchmark scorecards, cache, license, leakage, and human acceptance",
            priority="P0",
            owner_lane="benchmark_agent",
            status="blocked",
            execution_type="benchmark_cache_and_acceptance_gate",
            observed={
                "required_benchmarks": as_int(benchmark_summary.get("required_benchmarks")),
                "planned_benchmarks": as_int(benchmark_summary.get("planned_benchmarks")),
                "configured_benchmarks": as_int(benchmark_summary.get("configured_benchmarks")),
                "cache_validated_benchmarks": as_int(benchmark_summary.get("cache_validated_benchmarks")),
                "benchmarks_requiring_download_or_cache": as_int(benchmark_summary.get("benchmarks_requiring_download_or_cache")),
                "benchmarks_requiring_license_authorization": as_int(benchmark_summary.get("benchmarks_requiring_license_authorization")),
                "benchmarks_requiring_human_acceptance": as_int(benchmark_summary.get("benchmarks_requiring_human_acceptance")),
                "heads_with_complete_scorecards": as_int(benchmark_summary.get("heads_with_complete_scorecards")),
            },
            missing=[
                "13 benchmark dataset/cache registrations with checksums.",
                "13 license decisions and leakage/split records.",
                "14 human acceptance receipts before metric claims.",
            ],
            next_actions=[
                "Prepare local cache-intake rows only for benchmark assets that are already downloaded or explicitly authorized.",
                "Attach dataset license, checksum, split/leakage check, scorecard URI, and metric report URI.",
                "Rerun benchmark cache intake, validation, five-head benchmark gap, and claim readiness matrix.",
            ],
            evidence=[
                "reports/five_head_benchmark_gap_plan_report.json",
                "datasets/governance/five_head_benchmark_gap_actions.jsonl",
                "reports/benchmark_score_cache_validation_report.json",
                "datasets/benchmark/benchmark_score_cache_intake.local.jsonl",
            ],
        ),
        make_gate(
            gate_id="HTG-004-physical-ddg-runtime",
            title="Rosetta/PyRosetta/FoldX physical ddG runtime and license gate",
            priority="P0",
            owner_lane="ddg_backend_agent",
            status="blocked",
            execution_type="licensed_runtime_receipt_and_smoke_gate",
            observed={
                "adapter_integrated": bool(ddg.get("adapter_integrated")),
                "physical_backend_rows": len(physical_backends),
                "executable_ddg_backend_ready": bool(ddg.get("executable_ddg_backend_ready")),
                "proxy_ddg_backend_ready": bool(ddg.get("proxy_ddg_backend_ready")),
                "rosetta_candidate_rows": as_int(ddg_discovery.get("rosetta_candidate_rows")),
                "foldx_candidate_rows": as_int(ddg_discovery.get("foldx_candidate_rows")),
                "pyrosetta_module_available": bool(ddg_discovery.get("pyrosetta_module_available")),
                "ready_for_ddg_execution_rows": as_int(ddg_discovery.get("ready_for_ddg_execution_rows")),
                "operator_packet_rows": as_int(ddg_packets.get("packet_rows")),
                "operator_packets_ready_now": as_int(ddg_packets.get("ready_for_execution_now_rows")),
            },
            missing=[
                "Approved license/runtime receipt for at least one physical backend.",
                "Executable or Python module discovery for Rosetta/PyRosetta/FoldX.",
                "Versioned ddG smoke artifact with parameters, input checksum, mutation list, ddG table and runtime log.",
            ],
            next_actions=[
                "Do not install or execute licensed tools without explicit user/legal authorization.",
                "If authorized, record runtime receipt, then run executable probe and backend readiness before any ddG smoke.",
                "Keep ThermoMPNN as proxy/baseline evidence only, not a Rosetta/FoldX physical ddG claim.",
            ],
            evidence=[
                "reports/ddg_backend_readiness_report.json",
                "reports/ddg_backend_operator_packet_report.json",
                "reports/ddg_local_runtime_discovery_report.json",
                "datasets/governance/ddg_backend_runtime_receipts.local.jsonl",
            ],
        ),
        make_gate(
            gate_id="HTG-005-substrate-fit-label-source",
            title="Substrate-fit label schema and source approval",
            priority="P0",
            owner_lane="substrate_fit_agent",
            status="blocked",
            execution_type="label_schema_source_and_legal_gate",
            observed={
                "current_training_rows": as_int(label_gap.get("current_training_rows")),
                "minimum_rows": as_int(label_gap.get("minimum_rows")),
                "missing_to_minimum": as_int(label_gap.get("missing_to_minimum")),
                "ready_candidate_rows": as_int(label_gap.get("ready_candidate_rows")),
                "forbidden_shortcuts": len(substrate.get("forbidden_shortcuts") or []),
                "actions": len(substrate.get("actions") or []),
            },
            missing=[
                "Approved substrate_fit label schema with explicit substrate identity and assay context.",
                "Reviewed substrate-specific wet-lab/plate rows.",
                "Legal/source decisions for substrate-relevant external sources.",
            ],
            next_actions=[
                "Define substrate identity, assay condition, value semantics, QC, lineage and numbering fields.",
                "Keep generic activity, benchmark datasets and affinity predictions out of substrate_fit labels.",
                "Build reviewed substrate_fit intake only after substrate identity and source terms are explicit.",
            ],
            evidence=[
                "reports/substrate_fit_label_gap_plan_report.json",
                "datasets/governance/substrate_fit_label_gap_actions.jsonl",
            ],
        ),
        make_gate(
            gate_id="HTG-006-structure-feature-expansion",
            title="Reviewed structure-feature expansion for five heads",
            priority="P1",
            owner_lane="structure_feature_agent",
            status="blocked",
            execution_type="structure_chain_human_review_and_feature_capacity_gate",
            observed={
                "reviewed_structure_graph_rows": as_int(structure_summary.get("reviewed_structure_graph_rows")),
                "strict_msa_site_feature_rows": as_int(structure_summary.get("strict_msa_site_feature_rows")),
                "effective_strict_structure_feature_rows": as_int(structure_summary.get("effective_strict_structure_feature_rows")),
                "remaining_chain_mapping_rows": as_int(structure_summary.get("remaining_chain_mapping_rows")),
                "next_strict_evidence_candidate_rows": as_int(structure_summary.get("next_strict_evidence_candidate_rows")),
                "ready_heads": as_int(structure.get("ready_heads")),
                "total_heads": as_int(structure.get("total_heads")),
            },
            missing=[
                "Human-reviewed chain mappings for the next strict evidence candidates.",
                "At least 100 effective rows per head after label gates also pass.",
                "Coordinate claims remain closed until chain mapping and label provenance gates pass.",
            ],
            next_actions=[
                "Review the 9 strict DBREF/PDB evidence candidates before expanding coordinate features.",
                "Append explicit set_chain_mapping or reject_structure decisions only after human confirmation.",
                "Rerun reviewed structure graph, strict MSA site features, structure feature gap, and safe pipeline.",
            ],
            evidence=[
                "reports/structure_feature_head_gap_plan_report.json",
                "datasets/governance/structure_feature_head_gap_actions.jsonl",
                "reports/structure_chain_mapping_backlog_readiness_report.json",
            ],
        ),
    ]
    return gates


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Top-Tier Hard-Gate Execution Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board turns the current top-tier model blockers into execution lanes. It is fail-closed.",
        "",
        "## Summary",
        "",
        f"- Gates: {report['gate_count']}",
        f"- Blocked gates: {report['blocked_gates']}",
        f"- Ready gates: {report['ready_gates']}",
        f"- Human/external authorization gates: {report['human_or_external_authorization_gates']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        f"- Release ready: {str(report['release_ready']).lower()}",
        "",
        "## Gates",
        "",
        "| priority | gate | owner | status | key missing |",
        "|---|---|---|---|---|",
    ]
    for gate in report["gates"]:
        lines.append(
            f"| {gate['priority']} | {gate['gate_id']} | {gate['owner_lane']} | {gate['status']} | "
            f"{'; '.join(gate['missing'][:2])} |"
        )
    lines.extend(["", "## Policy", "", report["policy"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build top-tier hard-gate execution board")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    gates = build_gates()
    gates.sort(key=lambda row: (row["priority"], row["gate_id"]))
    for index, gate in enumerate(gates, 1):
        gate["execution_order"] = index

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "gate_count": len(gates),
        "blocked_gates": sum(1 for gate in gates if gate["status"] != "ready"),
        "ready_gates": sum(1 for gate in gates if gate["status"] == "ready"),
        "human_or_external_authorization_gates": sum(
            1 for gate in gates if gate["human_or_external_authorization_required"]
        ),
        "gates": gates,
        "next_parallel_lanes": [
            {
                "owner_lane": gate["owner_lane"],
                "gate_id": gate["gate_id"],
                "execution_type": gate["execution_type"],
                "first_action": gate["next_actions"][0],
                "completion_ready": False,
            }
            for gate in gates
        ],
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }
    write_jsonl(args.jsonl, gates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "gate_count": report["gate_count"],
        "blocked_gates": report["blocked_gates"],
        "ready_gates": report["ready_gates"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
