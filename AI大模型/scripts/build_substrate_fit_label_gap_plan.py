#!/usr/bin/env python3
"""Build a fail-closed substrate_fit label gap audit plan.

This script is intentionally audit-only. It reads existing readiness reports and
candidate-source scaffolds, then writes a substrate_fit-specific gap report and
operator actions. It does not read curated training label tables, import labels,
run the safe pipeline, or relax any model-claim gate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "substrate_fit_label_gap_plan_report.json"
MD_OUT = AI_ROOT / "reports" / "substrate_fit_label_gap_plan.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "substrate_fit_label_gap_actions.jsonl"
MIN_ROWS_DEFAULT = 100

SUBSTRATE_TERMS = (
    "substrate",
    "ligand",
    "affinity",
    "pose",
    "底物",
    "配体",
    "亲和",
    "选择性",
)

SUBSTRATE_RELEVANT_FEATURES = {
    "structure_affinity_complex",
    "kinetics_function",
    "wet_lab_feedback_calibration",
}

SUBSTRATE_RELEVANT_LICENSE_ITEMS = {
    "data_source:BRENDA",
    "data_source:PDBbind",
    "data_source:RCSB PDB",
    "data_source:SABIO-RK",
    "foreign_tool:alphafold3",
    "foreign_tool:boltz2",
    "foreign_tool:chai1",
    "foreign_tool:clean",
    "foreign_tool:ligandmpnn",
}

USABLE_QC_FLAGS = {"pass", "warning", "fail"}
USABLE_OUTCOMES = {"go", "watch", "no_go", "failed", "inconclusive"}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text_has_substrate_signal(value: Any) -> bool:
    text = str(value or "").lower()
    return any(term.lower() in text for term in SUBSTRATE_TERMS)


def row_has_substrate_text(row: dict[str, Any]) -> bool:
    for key in ("assay_type", "metric_name", "metric_code", "source_file", "benchmark_name", "notes"):
        if text_has_substrate_signal(row.get(key)):
            return True
    return False


def feedback_substrate_value(row: dict[str, Any]) -> Any:
    condition = row.get("assay_condition") or {}
    if isinstance(condition, dict):
        return condition.get("substrate")
    return None


def feedback_has_substrate_context(row: dict[str, Any]) -> bool:
    return bool(feedback_substrate_value(row)) or row_has_substrate_text(row)


def feedback_is_ready_substrate_fit_label(row: dict[str, Any]) -> bool:
    return (
        row.get("assay_type") == "substrate_fit"
        and row.get("source") != "local_fixture"
        and row.get("numbering_verified") is True
        and feedback_has_substrate_context(row)
        and row.get("outcome") in USABLE_OUTCOMES
    )


def plate_is_ready_substrate_fit_label(row: dict[str, Any]) -> bool:
    return (
        row.get("assay_type") == "substrate_fit"
        and row.get("review_status") == "reviewed"
        and row.get("qc_flag") in USABLE_QC_FLAGS
        and bool(row.get("substrate_smiles"))
        and row.get("raw_signal") is not None
    )


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "missing") for row in rows)
    return [{"value": value, "rows": rows_count} for value, rows_count in counts.most_common(limit)]


def status_from_ready(ready_rows: int) -> str:
    return "candidate_ready" if ready_rows else "blocked"


def build_candidate_sources(
    feedback_rows: list[dict[str, Any]],
    plate_rows: list[dict[str, Any]],
    wet_candidates: list[dict[str, Any]],
    wet_worklist: list[dict[str, Any]],
    wet_authorizations: list[dict[str, Any]],
    benchmark_manifest: dict[str, Any],
    benchmark_validation: dict[str, Any],
    feature_manifest: dict[str, Any],
    license_validation: dict[str, Any],
) -> list[dict[str, Any]]:
    feedback_context_rows = [row for row in feedback_rows if feedback_has_substrate_context(row)]
    feedback_substrate_fit_rows = [row for row in feedback_rows if row.get("assay_type") == "substrate_fit"]
    feedback_ready_rows = [row for row in feedback_substrate_fit_rows if feedback_is_ready_substrate_fit_label(row)]

    plate_substrate_fit_rows = [row for row in plate_rows if row.get("assay_type") == "substrate_fit"]
    plate_ready_rows = [row for row in plate_substrate_fit_rows if plate_is_ready_substrate_fit_label(row)]

    wet_substrate_text_rows = [row for row in wet_candidates if row_has_substrate_text(row)]
    wet_substrate_fit_rows = [row for row in wet_candidates if row.get("assay_type") == "substrate_fit"]
    wet_ready_rows = [
        row
        for row in wet_substrate_fit_rows
        if row.get("ready_for_feedback_intake") is True and row.get("claim_eligible_now") is True
    ]
    wet_authorized_substrate_fit_rows = [
        row
        for row in wet_authorizations
        if row.get("assay_type") == "substrate_fit"
        and row.get("authorized_for_feedback_intake") is True
    ]

    benchmark_rows = [
        row for row in benchmark_manifest.get("rows", [])
        if row.get("head") == "substrate_fit"
    ]
    benchmark_present_rows = [row for row in benchmark_rows if row.get("status") == "present"]
    benchmark_scorecard = (benchmark_validation.get("head_scorecards") or {}).get("substrate_fit") or {}
    benchmark_valid_rows = as_int(benchmark_scorecard.get("valid_rows"))

    feature_rows = [
        row for row in feature_manifest.get("feature_families", [])
        if row.get("family_id") in SUBSTRATE_RELEVANT_FEATURES
    ]
    feature_ready_to_implement_rows = [
        row for row in feature_rows
        if row.get("status") == "ready_to_implement"
    ]

    missing_license_items = sorted(
        set(license_validation.get("missing_packet_decisions") or [])
        & SUBSTRATE_RELEVANT_LICENSE_ITEMS
    )

    return [
        {
            "source_id": "local_feedback_substrate_context",
            "artifact": "datasets/feedback/experiment_feedback.local.jsonl",
            "observed_rows": len(feedback_rows),
            "substrate_context_rows": len(feedback_context_rows),
            "candidate_rows": len(feedback_substrate_fit_rows),
            "ready_candidate_rows": len(feedback_ready_rows),
            "status": status_from_ready(len(feedback_ready_rows)),
            "blocker": "context-only feedback is not a substrate_fit assay label unless assay_type, substrate identity, outcome, provenance, and numbering are reviewed.",
        },
        {
            "source_id": "plate_level_substrate_fit_intake",
            "artifact": "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "observed_rows": len(plate_rows),
            "substrate_context_rows": sum(1 for row in plate_rows if row.get("substrate_smiles")),
            "candidate_rows": len(plate_substrate_fit_rows),
            "ready_candidate_rows": len(plate_ready_rows),
            "status": status_from_ready(len(plate_ready_rows)),
            "blocker": "plate rows require assay_type=substrate_fit, substrate_smiles, reviewed status, usable QC, and raw signal.",
        },
        {
            "source_id": "wet_lab_metric_candidates",
            "artifact": "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
            "observed_rows": len(wet_candidates),
            "substrate_text_rows": len(wet_substrate_text_rows),
            "candidate_rows": len(wet_substrate_fit_rows),
            "ready_candidate_rows": len(wet_ready_rows),
            "numeric_training_candidate_rows": sum(1 for row in wet_candidates if row.get("numeric_training_candidate") is True),
            "status": status_from_ready(len(wet_ready_rows)),
            "blocker": "current wet-lab metric candidates are activity/stability focused; generic activity cannot be relabeled as substrate_fit.",
        },
        {
            "source_id": "wet_lab_authorization_worklist",
            "artifact": "datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl",
            "observed_rows": len(wet_worklist),
            "candidate_rows": sum(1 for row in wet_worklist if row.get("assay_type") == "substrate_fit"),
            "ready_candidate_rows": len(wet_authorized_substrate_fit_rows),
            "authorized_rows": sum(1 for row in wet_authorizations if row.get("authorized_for_feedback_intake") is True),
            "status": status_from_ready(len(wet_authorized_substrate_fit_rows)),
            "blocker": "authorization is metric-level and currently contains no approved substrate_fit metric rows.",
        },
        {
            "source_id": "substrate_fit_benchmark_scorecards",
            "artifact": "reports/benchmark_score_cache_manifest.json",
            "expected_benchmark_entries": len(benchmark_rows),
            "present_benchmark_entries": len(benchmark_present_rows),
            "valid_scorecard_rows": benchmark_valid_rows,
            "candidate_rows": 0,
            "ready_candidate_rows": 0,
            "status": "blocked",
            "blocker": "benchmarks validate model claims; they are not KWB training labels and substrate_fit scorecards are not present.",
        },
        {
            "source_id": "substrate_relevant_feature_adapters",
            "artifact": "reports/advanced_feature_cache_manifest.json",
            "relevant_feature_families": len(feature_rows),
            "ready_to_implement_feature_families": len(feature_ready_to_implement_rows),
            "blocked_feature_families": sum(1 for row in feature_rows if row.get("status") == "blocked"),
            "candidate_rows": 0,
            "ready_candidate_rows": 0,
            "status": "blocked",
            "blocker": "feature/proxy adapters can provide evidence after gates, but cannot be promoted into supervised substrate_fit labels.",
        },
        {
            "source_id": "external_license_and_use_gates",
            "artifact": "reports/external_license_review_decision_validation_report.json",
            "packet_rows": as_int(license_validation.get("packet_rows")),
            "observed_rows": as_int(license_validation.get("packet_rows")),
            "decision_rows": as_int(license_validation.get("decision_rows")),
            "approved_for_training_rows": as_int(license_validation.get("approved_for_training_rows")),
            "missing_substrate_relevant_decisions": missing_license_items,
            "missing_substrate_relevant_decision_count": len(missing_license_items),
            "candidate_rows": 0,
            "ready_candidate_rows": 0,
            "status": "blocked",
            "blocker": "external substrate/function/ligand sources remain blocked without explicit human/legal decisions.",
        },
    ]


def build_label_requirements(candidate_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_id = {row["source_id"]: row for row in candidate_sources}
    local_context = source_by_id["local_feedback_substrate_context"]
    plate_context = source_by_id["plate_level_substrate_fit_intake"]
    wet_candidates = source_by_id["wet_lab_metric_candidates"]
    wet_auth = source_by_id["wet_lab_authorization_worklist"]

    return [
        {
            "requirement_id": "substrate_fit_assay_type",
            "required_evidence": "assay_type is explicitly substrate_fit",
            "observed_support_rows": (
                local_context["candidate_rows"]
                + plate_context["candidate_rows"]
                + wet_candidates["candidate_rows"]
                + wet_auth["candidate_rows"]
            ),
            "ready_rows": (
                local_context["ready_candidate_rows"]
                + plate_context["ready_candidate_rows"]
                + wet_candidates["ready_candidate_rows"]
                + wet_auth["ready_candidate_rows"]
            ),
            "status": "missing",
        },
        {
            "requirement_id": "substrate_identity",
            "required_evidence": "substrate name or substrate_smiles is explicit and source-traced",
            "observed_support_rows": local_context["substrate_context_rows"] + plate_context["substrate_context_rows"],
            "ready_rows": local_context["ready_candidate_rows"] + plate_context["ready_candidate_rows"],
            "status": "context_only",
        },
        {
            "requirement_id": "variant_or_mutation_identity",
            "required_evidence": "variant_id or mutation set is linked to the substrate assay row",
            "observed_support_rows": local_context["observed_rows"] + plate_context["observed_rows"],
            "ready_rows": local_context["ready_candidate_rows"] + plate_context["ready_candidate_rows"],
            "status": "blocked_until_assay_label_exists",
        },
        {
            "requirement_id": "numbering_and_lineage_review",
            "required_evidence": "numbering and source lineage are reviewed for the exact substrate assay",
            "observed_support_rows": local_context["candidate_rows"] + wet_auth["authorized_rows"],
            "ready_rows": local_context["ready_candidate_rows"] + wet_auth["ready_candidate_rows"],
            "status": "missing",
        },
        {
            "requirement_id": "condition_context",
            "required_evidence": "pH, temperature, batch/control, replicate/QC, and protocol are preserved",
            "observed_support_rows": plate_context["observed_rows"],
            "ready_rows": plate_context["ready_candidate_rows"],
            "status": "missing",
        },
        {
            "requirement_id": "label_value",
            "required_evidence": "reviewed go/watch/no_go/failed/inconclusive or numeric substrate-fit response",
            "observed_support_rows": (
                local_context["candidate_rows"]
                + plate_context["candidate_rows"]
                + wet_candidates["candidate_rows"]
            ),
            "ready_rows": (
                local_context["ready_candidate_rows"]
                + plate_context["ready_candidate_rows"]
                + wet_candidates["ready_candidate_rows"]
            ),
            "status": "missing",
        },
        {
            "requirement_id": "legal_and_use_scope",
            "required_evidence": "human/legal decisions approve any external substrate source or tool output use",
            "observed_support_rows": source_by_id["external_license_and_use_gates"]["decision_rows"],
            "ready_rows": source_by_id["external_license_and_use_gates"]["approved_for_training_rows"],
            "status": "missing",
        },
        {
            "requirement_id": "leakage_safe_evaluation",
            "required_evidence": "substrate_fit benchmark scorecards exist only for evaluation, not labels",
            "observed_support_rows": source_by_id["substrate_fit_benchmark_scorecards"]["present_benchmark_entries"],
            "ready_rows": source_by_id["substrate_fit_benchmark_scorecards"]["valid_scorecard_rows"],
            "status": "missing",
        },
    ]


def build_forbidden_shortcuts(candidate_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_id = {row["source_id"]: row for row in candidate_sources}
    return [
        {
            "shortcut_id": "generic_activity_to_substrate_fit",
            "observed_rows": source_by_id["local_feedback_substrate_context"]["substrate_context_rows"],
            "allowed": False,
            "reason": "activity with a substrate context is not a substrate-fit label without an explicit substrate_fit assay definition.",
        },
        {
            "shortcut_id": "activity_or_stability_metric_relabel",
            "observed_rows": source_by_id["wet_lab_metric_candidates"]["numeric_training_candidate_rows"],
            "allowed": False,
            "reason": "numeric activity/stability candidates cannot be reinterpreted as substrate selectivity or fit.",
        },
        {
            "shortcut_id": "benchmark_dataset_as_training_label",
            "observed_rows": source_by_id["substrate_fit_benchmark_scorecards"]["expected_benchmark_entries"],
            "allowed": False,
            "reason": "PDBbind/CASF/D3R/PoseBusters-style assets are evaluation gates, not KWB supervised labels.",
        },
        {
            "shortcut_id": "affinity_or_pose_prediction_as_ground_truth",
            "observed_rows": source_by_id["substrate_relevant_feature_adapters"]["relevant_feature_families"],
            "allowed": False,
            "reason": "Boltz/Chai/AlphaFold-style complex or affinity predictions may become features only after gates.",
        },
        {
            "shortcut_id": "function_or_ec_proxy_as_substrate_fit",
            "observed_rows": source_by_id["substrate_relevant_feature_adapters"]["relevant_feature_families"],
            "allowed": False,
            "reason": "CatPred/CLEAN/EC-style function proxies do not supply substrate-fit labels.",
        },
        {
            "shortcut_id": "license_inference",
            "observed_rows": source_by_id["external_license_and_use_gates"]["missing_substrate_relevant_decision_count"],
            "allowed": False,
            "reason": "missing external source/tool decisions must remain blocked and cannot be inferred from availability.",
        },
        {
            "shortcut_id": "model_claim_unlock",
            "observed_rows": 0,
            "allowed": False,
            "reason": "current labels, candidates, benchmark scorecards, and legal gates do not permit a substrate_fit model claim.",
        },
    ]


def build_actions(
    current_rows: int,
    minimum_rows: int,
    ready_candidate_rows: int,
    candidate_sources: list[dict[str, Any]],
    forbidden_shortcuts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_by_id = {row["source_id"]: row for row in candidate_sources}
    missing_to_minimum = max(minimum_rows - current_rows, 0)

    base_policy = "Action scaffold only; not a reviewed decision, training label, safe-pipeline integration, or model claim."
    return [
        {
            "action_id": "substrate-fit-label-schema-p0",
            "priority": "P0",
            "action": "Define substrate_fit label schema with explicit substrate identity, assay condition, value semantics, lineage, numbering, QC, and review status.",
            "current_training_rows": current_rows,
            "minimum_rows": minimum_rows,
            "ready_candidate_rows": ready_candidate_rows,
            "missing_to_minimum": missing_to_minimum,
            "blocked_by": "no approved substrate_fit label schema/source",
            "owner_lane": "label_governance",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
        {
            "action_id": "audit-existing-feedback-context-p0",
            "priority": "P0",
            "action": "Review existing feedback rows with substrate context and decide whether any require a new substrate_fit assay record rather than relabeling activity.",
            "source": source_by_id["local_feedback_substrate_context"]["artifact"],
            "observed_rows": source_by_id["local_feedback_substrate_context"]["observed_rows"],
            "substrate_context_rows": source_by_id["local_feedback_substrate_context"]["substrate_context_rows"],
            "ready_candidate_rows": source_by_id["local_feedback_substrate_context"]["ready_candidate_rows"],
            "blocked_by": "context-only rows are not substrate_fit labels",
            "owner_lane": "wet_lab_review",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
        {
            "action_id": "build-substrate-fit-plate-intake-p0",
            "priority": "P0",
            "action": "Create reviewed plate-level substrate_fit intake rows only when substrate_smiles, raw signal, QC, replicate, and protocol are present.",
            "source": source_by_id["plate_level_substrate_fit_intake"]["artifact"],
            "observed_rows": source_by_id["plate_level_substrate_fit_intake"]["observed_rows"],
            "candidate_rows": source_by_id["plate_level_substrate_fit_intake"]["candidate_rows"],
            "ready_candidate_rows": source_by_id["plate_level_substrate_fit_intake"]["ready_candidate_rows"],
            "blocked_by": "no reviewed plate-level substrate_fit rows",
            "owner_lane": "wet_lab_review",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
        {
            "action_id": "separate-proxies-from-labels-p0",
            "priority": "P0",
            "action": "Keep activity/stability wet-lab metrics, benchmark assets, and affinity/function predictions out of substrate_fit labels.",
            "wet_lab_numeric_candidate_rows": source_by_id["wet_lab_metric_candidates"]["numeric_training_candidate_rows"],
            "substrate_fit_benchmark_entries": source_by_id["substrate_fit_benchmark_scorecards"]["expected_benchmark_entries"],
            "forbidden_shortcut_count": len(forbidden_shortcuts),
            "blocked_by": "proxy rows are not supervised substrate_fit ground truth",
            "owner_lane": "model_governance",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
        {
            "action_id": "external-substrate-source-legal-p1",
            "priority": "P1",
            "action": "Resolve human/legal decisions for substrate-relevant external sources before using them as evaluation data or feature evidence.",
            "source": source_by_id["external_license_and_use_gates"]["artifact"],
            "packet_rows": source_by_id["external_license_and_use_gates"]["packet_rows"],
            "decision_rows": source_by_id["external_license_and_use_gates"]["decision_rows"],
            "approved_for_training_rows": source_by_id["external_license_and_use_gates"]["approved_for_training_rows"],
            "missing_substrate_relevant_decision_count": source_by_id["external_license_and_use_gates"]["missing_substrate_relevant_decision_count"],
            "blocked_by": "missing substrate-relevant legal/source decisions",
            "owner_lane": "legal_review",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
        {
            "action_id": "substrate-fit-claim-remains-locked-p0",
            "priority": "P0",
            "action": "Keep substrate_fit training and model-claim gates locked until minimum reviewed labels and scorecards are present.",
            "current_training_rows": current_rows,
            "ready_candidate_rows": ready_candidate_rows,
            "missing_to_minimum": missing_to_minimum,
            "valid_substrate_fit_scorecard_rows": source_by_id["substrate_fit_benchmark_scorecards"]["valid_scorecard_rows"],
            "blocked_by": "label gap and evaluation scorecard gap both remain open",
            "owner_lane": "model_governance",
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "policy": base_policy,
        },
    ]


def write_markdown(report: dict[str, Any], path: Path) -> None:
    def clean(value: Any) -> str:
        return str(value).replace("|", "/")

    lines = [
        "# Substrate Fit Label Gap Plan",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This is a fail-closed audit scaffold. It does not import labels, run training, connect to the safe pipeline, or unlock model claims.",
        "",
        "## Summary",
        "",
        f"- Status: {report['status']}",
        f"- Current substrate_fit training rows: {report['label_gap']['current_training_rows']}",
        f"- Minimum required rows: {report['label_gap']['minimum_rows']}",
        f"- Ready candidate rows: {report['label_gap']['ready_candidate_rows']}",
        f"- Missing rows to minimum: {report['label_gap']['missing_to_minimum']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Candidate Sources",
        "",
        "| source | observed | candidates | ready | status | blocker |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in report["candidate_sources"]:
        observed = row.get("observed_rows", row.get("expected_benchmark_entries", row.get("relevant_feature_families", 0)))
        lines.append(
            f"| {clean(row['source_id'])} | {observed} | {row.get('candidate_rows', 0)} | {row.get('ready_candidate_rows', 0)} | {clean(row['status'])} | {clean(row['blocker'])} |"
        )

    lines.extend([
        "",
        "## Forbidden Shortcuts",
        "",
        "| shortcut | observed | allowed | reason |",
        "|---|---:|---|---|",
    ])
    for row in report["forbidden_shortcuts"]:
        lines.append(
            f"| {clean(row['shortcut_id'])} | {row['observed_rows']} | {str(row['allowed']).lower()} | {clean(row['reason'])} |"
        )

    lines.extend([
        "",
        "## Actions",
        "",
        "| action | priority | blocker | training unlocked | model claim |",
        "|---|---|---|---|---|",
    ])
    for row in report["actions"]:
        lines.append(
            f"| {clean(row['action_id'])} | {row['priority']} | {clean(row['blocked_by'])} | {str(row['training_unlocked']).lower()} | {str(row['safe_for_model_claim']).lower()} |"
        )

    lines.extend([
        "",
        "## Policy",
        "",
        report["policy"],
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build substrate_fit label gap audit plan")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    benchmark_manifest = load_json(AI_ROOT / "reports" / "benchmark_score_cache_manifest.json")
    benchmark_validation = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")
    feature_manifest = load_json(AI_ROOT / "reports" / "advanced_feature_cache_manifest.json")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    feedback_rows = load_jsonl(AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl")
    plate_rows = load_jsonl(AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.local.jsonl")
    wet_candidates = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl")
    wet_worklist = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl")
    wet_authorizations = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl")

    substrate_head = ((multitask.get("heads") or {}).get("substrate_fit") or {})
    current_rows = as_int(substrate_head.get("rows"))
    minimum_rows = as_int(substrate_head.get("minimum_rows"), MIN_ROWS_DEFAULT) or MIN_ROWS_DEFAULT

    candidate_sources = build_candidate_sources(
        feedback_rows=feedback_rows,
        plate_rows=plate_rows,
        wet_candidates=wet_candidates,
        wet_worklist=wet_worklist,
        wet_authorizations=wet_authorizations,
        benchmark_manifest=benchmark_manifest,
        benchmark_validation=benchmark_validation,
        feature_manifest=feature_manifest,
        license_validation=license_validation,
    )
    ready_candidate_rows = sum(as_int(row.get("ready_candidate_rows")) for row in candidate_sources[:4])
    forbidden_shortcuts = build_forbidden_shortcuts(candidate_sources)
    actions = build_actions(
        current_rows=current_rows,
        minimum_rows=minimum_rows,
        ready_candidate_rows=ready_candidate_rows,
        candidate_sources=candidate_sources,
        forbidden_shortcuts=forbidden_shortcuts,
    )
    label_requirements = build_label_requirements(candidate_sources)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "head": "substrate_fit",
        "audit_only": True,
        "does_not_read_training_label_tables": True,
        "training_label_inputs_read": [],
        "safe_pipeline_integrated": False,
        "model_claim_released": False,
        "label_gap": {
            "label_fields": substrate_head.get("label_fields") or ["substrate_fit_label"],
            "current_training_rows": current_rows,
            "minimum_rows": minimum_rows,
            "ready_candidate_rows": ready_candidate_rows,
            "missing_to_minimum": max(minimum_rows - current_rows, 0),
            "training_ready": False,
        },
        "required_label_requirements": label_requirements,
        "candidate_sources": candidate_sources,
        "candidate_signal_summary": {
            "local_feedback_rows": len(feedback_rows),
            "local_feedback_substrate_context_rows": candidate_sources[0]["substrate_context_rows"],
            "plate_feedback_rows": len(plate_rows),
            "wet_lab_candidate_rows": len(wet_candidates),
            "wet_lab_numeric_candidate_rows": candidate_sources[2]["numeric_training_candidate_rows"],
            "wet_lab_authorization_worklist_rows": len(wet_worklist),
            "wet_lab_metric_class_counts": top_counts(wet_worklist, "metric_class"),
            "substrate_fit_benchmark_expected_entries": candidate_sources[4]["expected_benchmark_entries"],
            "substrate_fit_benchmark_present_entries": candidate_sources[4]["present_benchmark_entries"],
            "substrate_fit_benchmark_valid_scorecard_rows": candidate_sources[4]["valid_scorecard_rows"],
            "substrate_relevant_feature_families": candidate_sources[5]["relevant_feature_families"],
            "substrate_relevant_license_missing_decisions": candidate_sources[6]["missing_substrate_relevant_decision_count"],
        },
        "forbidden_shortcuts": forbidden_shortcuts,
        "actions": actions,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Substrate_fit labels require explicit substrate identity, reviewed assay context, provenance, QC, and legal/use gates. This scaffold quantifies gaps only and never converts candidates, proxies, benchmarks, or context-only activity rows into labels.",
        "audit_inputs": [
            "reports/multitask_training_readiness_report.json",
            "reports/benchmark_score_cache_manifest.json",
            "reports/benchmark_score_cache_validation_report.json",
            "reports/advanced_feature_cache_manifest.json",
            "reports/external_license_review_decision_validation_report.json",
            "datasets/feedback/experiment_feedback.local.jsonl",
            "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
            "datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl",
            "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        ],
        "audit_outputs": [
            str(args.output.relative_to(AI_ROOT) if args.output.is_absolute() and args.output.is_relative_to(AI_ROOT) else args.output),
            str(args.markdown.relative_to(AI_ROOT) if args.markdown.is_absolute() and args.markdown.is_relative_to(AI_ROOT) else args.markdown),
            str(args.jsonl.relative_to(AI_ROOT) if args.jsonl.is_absolute() and args.jsonl.is_relative_to(AI_ROOT) else args.jsonl),
        ],
    }

    write_json(args.output, report)
    write_jsonl(args.jsonl, actions)
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "head": report["head"],
        "current_training_rows": current_rows,
        "minimum_rows": minimum_rows,
        "ready_candidate_rows": ready_candidate_rows,
        "missing_to_minimum": report["label_gap"]["missing_to_minimum"],
        "forbidden_shortcuts": len(forbidden_shortcuts),
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
