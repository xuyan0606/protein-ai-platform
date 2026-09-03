#!/usr/bin/env python3
"""Build a fail-closed five-head training gap plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "five_head_training_gap_plan_report.json"
MD_OUT = AI_ROOT / "reports" / "five_head_training_gap_plan.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "five_head_training_gap_actions.jsonl"
MIN_ROWS = 100


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "missing") for row in rows)
    return [{"value": value, "rows": count} for value, count in counts.most_common(limit)]


def gap_row(
    head: str,
    current_rows: int,
    candidate_rows: int,
    ready_candidate_rows: int,
    primary_source: str,
    review_queue: str,
    blocking_gate: str,
    next_action: str,
    priority: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "head": head,
        "priority": priority,
        "current_training_rows": current_rows,
        "minimum_rows": MIN_ROWS,
        "missing_to_minimum": max(MIN_ROWS - current_rows, 0),
        "candidate_rows_observed": candidate_rows,
        "ready_candidate_rows": ready_candidate_rows,
        "primary_source": primary_source,
        "review_queue": review_queue,
        "blocking_gate": blocking_gate,
        "next_action": next_action,
        "notes": notes,
        "training_unlocked": False,
        "safe_for_model_claim": False,
        "policy": "Gap plan only; not a training row, approval, reviewed decision, or model-quality claim.",
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Five-Head Training Gap Plan",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This is a fail-closed engineering plan. It does not import labels or train a model.",
        "",
        "## Summary",
        "",
        f"- Status: {report['status']}",
        f"- Ready heads: {report['ready_heads']}/{report['total_heads']}",
        f"- Minimum rows per head: {report['minimum_rows_per_head']}",
        "- Minimum explicit replicates per head: 3",
        "- Minimum independent groups per head: 10",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Head Gaps",
        "",
        "| head | label rows | missing | candidates | samples/reps/groups | thresholds | status | blocker |",
        "|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in report["head_gap_actions"]:
        lines.append(
            "| {head} | {current_training_rows} | {missing_to_minimum} | {candidate_rows_observed} | "
            "{observed_sample_count}/{observed_replicate_count}/{observed_group_count} | "
            "{minimum_rows}/{minimum_replicates}/{minimum_groups} | {head_status} | {blocking_gate} |".format(**row)
        )
    signals = report["candidate_signals"]
    lines.extend([
        "",
        "## Candidate Signals",
        "",
        f"- Wet-lab numeric candidates: {signals['wet_lab_numeric_candidate_rows']}",
        f"- Wet-lab authorization worklist rows: {signals['wet_lab_authorization_worklist_rows']}",
        f"- FireProt mapped stability candidates: {signals['fireprot_mapping_candidate_rows']}",
        f"- FireProt reviewed import candidates: {signals['fireprot_reviewed_import_candidate_rows']}",
        "",
        "## Policy",
        "",
        report["policy"],
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head training gap plan")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    claim = load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json")
    threshold = load_json(AI_ROOT / "reports" / "five_head_training_threshold_report.json")
    numbering = load_json(AI_ROOT / "reports" / "numbering_review_operator_queue.json")
    wet_candidates = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl")
    wet_worklist = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl")
    wet_auth = load_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl")
    plate_backlog = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json")
    fireprot_mapping = load_jsonl(AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl")
    fireprot_reviewed = load_jsonl(AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")

    heads = multitask.get("heads") or {}
    wet_numeric = [row for row in wet_candidates if row.get("numeric_training_candidate") is True]
    wet_ready = [row for row in wet_candidates if row.get("ready_for_feedback_intake") is True]
    wet_activity = [row for row in wet_numeric if row.get("assay_type") == "activity"]
    wet_stability = [row for row in wet_numeric if row.get("assay_type") == "stability"]
    auth_approved = [
        row for row in wet_auth
        if row.get("authorization_decision") == "approved_for_feedback_intake"
    ]
    plate_ready = plate_backlog.get("ready_for_feedback_intake_rows") or plate_backlog.get("training_eligible_rows") or 0
    plate_blocked = plate_backlog.get("blocked_rows") or plate_backlog.get("blocked_draft_rows") or plate_backlog.get("backlog_rows") or 0

    actions = [
        gap_row(
            "mutation_rank",
            int((heads.get("mutation_rank") or {}).get("rows") or 0),
            int(numbering.get("queue_rows") or 0),
            int(numbering.get("reviewed_no_conflict_rows") or 0),
            "reviewed numbering + claim-eligible real supervised labels",
            "reports/numbering_review_operator_queue.json",
            "MQ-U001 reviewed numbering and real label provenance",
            "Resolve semantic conflicts, then approve only real-source reviewed numbering decisions.",
            "P0",
            "Ranking labels must come from claim-eligible real supervised rows, not synthetic ProThermDB fixtures.",
        ),
        gap_row(
            "stability",
            int((heads.get("stability") or {}).get("rows") or 0),
            len(fireprot_mapping) + len(wet_stability),
            len(fireprot_reviewed) + len([row for row in wet_ready if row.get("assay_type") == "stability"]),
            "FireProt reviewed import candidates + KWB wet-lab stability metrics",
            "datasets/curation/fireprot_dedup_review_decisions.jsonl; datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "FireProt license/dedup/import receipt + wet-lab authorization",
            "Approve license scope, dedup policy, reviewed import receipt, and metric-level wet-lab authorizations.",
            "P0",
            "ThermoMPNN proxy ddG is usable as a feature/baseline, not as a substitute for reviewed stability labels.",
        ),
        gap_row(
            "activity_risk",
            int((heads.get("activity_risk") or {}).get("rows") or 0),
            len(wet_activity),
            len([row for row in wet_ready if row.get("assay_type") == "activity"]),
            "KWB wet-lab activity metrics",
            "datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl",
            "metric-level human authorization and feedback preflight",
            "Authorize or reject each activity metric row, then rerun wet-lab preflight and apply-plan validators.",
            "P0",
            "Activity labels should preserve condition context such as pH, control, batch, unit, and QC class.",
        ),
        gap_row(
            "substrate_fit",
            int((heads.get("substrate_fit") or {}).get("rows") or 0),
            0,
            0,
            "substrate-specific assay labels or substrate annotations",
            "not yet built",
            "no substrate-fit label source approved",
            "Create a substrate label schema and extract substrate/assay-specific wet-lab rows only after source review.",
            "P1",
            "Do not infer substrate fit from generic activity without substrate identity and assay conditions.",
        ),
        gap_row(
            "assay_success",
            int((heads.get("assay_success") or {}).get("rows") or 0),
            int(plate_blocked),
            int(plate_ready),
            "plate/well-level assay execution feedback",
            "datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl",
            "plate intake QC and human extraction",
            "Convert reviewed plate/well rows into schema-valid feedback with success/failure/QC labels.",
            "P0",
            "Assay success must include failed and low-quality experiments, not only successful designs.",
        ),
    ]

    # The threshold report is the source of truth for current label rows. Keep
    # legacy candidate discovery visible, but never let candidates replace the
    # per-head label/replicate/group census.
    threshold_heads = threshold.get("heads") if isinstance(threshold.get("heads"), dict) else {}
    threshold_sources = threshold.get("source_counts") if isinstance(threshold.get("source_counts"), dict) else {}
    for action in actions:
        threshold_head = threshold_heads.get(action["head"])
        if not isinstance(threshold_head, dict):
            continue
        thresholds = threshold_head.get("thresholds") if isinstance(threshold_head.get("thresholds"), dict) else {}
        metrics = threshold_head.get("label_metrics") if isinstance(threshold_head.get("label_metrics"), dict) else {}
        action.update({
            "current_training_rows": int(threshold_head.get("label_rows") or 0),
            "minimum_rows": int(thresholds.get("minimum_samples") or MIN_ROWS),
            "missing_to_minimum": max(
                int(thresholds.get("minimum_samples") or MIN_ROWS)
                - int(threshold_head.get("label_rows") or 0),
                0,
            ),
            "candidate_rows_observed": int(threshold_head.get("candidate_rows") or 0),
            "ready_candidate_rows": 0,
            "minimum_replicates": int(thresholds.get("minimum_replicates") or 0),
            "minimum_groups": int(thresholds.get("minimum_groups") or 0),
            "observed_sample_count": int(metrics.get("sample_count") or 0),
            "observed_replicate_count": int(metrics.get("replicate_count") or 0),
            "observed_group_count": int(metrics.get("group_count") or 0),
            "head_status": threshold_head.get("status"),
            "thresholds_met": threshold_head.get("thresholds_met") is True,
            "training_unlocked": False,
            "safe_for_model_claim": False,
        })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "total_heads": len(actions),
        "ready_heads": len(threshold.get("threshold_ready_heads") or []),
        "minimum_rows_per_head": MIN_ROWS,
        "threshold_report": "reports/five_head_training_threshold_report.json",
        "threshold_source_counts": threshold_sources,
        "threshold_ready_heads": threshold.get("threshold_ready_heads"),
        "candidate_heads": threshold.get("candidate_heads"),
        "blocked_heads": threshold.get("blocked_heads"),
        "claim_matrix_blocked_claims": claim.get("claims_blocked"),
        "head_gap_actions": actions,
        "candidate_signals": {
            "wet_lab_candidate_rows": len(wet_candidates),
            "wet_lab_numeric_candidate_rows": int(
                threshold_sources["numeric_feedback_rows"]
                if "numeric_feedback_rows" in threshold_sources
                else len(wet_numeric)
            ),
            "wet_lab_numeric_activity_rows": int(
                (threshold_heads.get("activity_risk") or {}).get("candidate_rows")
                if "activity_risk" in threshold_heads
                else len(wet_activity)
            ),
            "wet_lab_numeric_stability_rows": int(
                (threshold_heads.get("stability") or {}).get("candidate_rows")
                if "stability" in threshold_heads
                else len(wet_stability)
            ),
            "wet_lab_ready_for_feedback_intake_rows": len(wet_ready),
            "wet_lab_authorization_worklist_rows": len(wet_worklist),
            "wet_lab_authorized_rows": len(auth_approved),
            "wet_lab_metric_class_counts": top_counts(wet_worklist, "metric_class"),
            "wet_lab_variant_counts": top_counts(wet_worklist, "variant"),
            "fireprot_mapping_candidate_rows": len(fireprot_mapping),
            "fireprot_reviewed_import_candidate_rows": int(
                threshold_sources["fireprot_reviewed_import_rows"]
                if "fireprot_reviewed_import_rows" in threshold_sources
                else len(fireprot_reviewed)
            ),
            "fireprot_label_method_counts": top_counts(fireprot_mapping, "label_method"),
            "license_ready_for_training": bool(license_validation.get("ready_for_training")),
            "plate_feedback_blocked_rows": plate_blocked,
            "plate_feedback_ready_for_intake_rows": int(
                threshold_sources["plate_training_eligible_rows"]
                if "plate_training_eligible_rows" in threshold_sources
                else plate_ready
            ),
            "feature_rows_excluded_from_labels": int(
                ((threshold.get("feature_label_boundary") or {}).get("feature_rows_observed") or 0)
            ),
        },
        "next_execution_order": [
            "P0 resolve numbering semantic conflicts and keep generated/fixture rows rejected unless real receipts exist",
            "P0 authorize/reject 12 KWB wet-lab metric rows for activity/stability heads",
            "P0 finish FireProt license/dedup/reviewed import receipt before stability import",
            "P0 build plate/well success/failure intake rows for assay_success",
            "P1 define substrate_fit label schema only after substrate identity is explicit",
            "rerun python3 scripts/run_safe_training_pipeline.py before any training run",
        ],
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "This plan quantifies head-specific gaps only. It never approves data, imports labels, trains models, or relaxes model-claim gates.",
    }
    write_jsonl(args.jsonl, actions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "ready_heads": report["ready_heads"],
        "total_heads": report["total_heads"],
        "wet_lab_numeric_candidate_rows": report["candidate_signals"]["wet_lab_numeric_candidate_rows"],
        "fireprot_mapping_candidate_rows": report["candidate_signals"]["fireprot_mapping_candidate_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
