#!/usr/bin/env python3
"""Build the P677 completion checklist for P0 real-input handoff rows."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P676_PACKAGE = AI_ROOT / "datasets" / "governance" / "p676_p0_real_input_handoff_work_package.jsonl"
P676_VALIDATION = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
OUT_CSV = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.csv"
OUT_REPORT = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist_report.json"
OUT_MD = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist.md"

FALSE_FLAGS = {
    "real_input_received": False,
    "formal_validator_passed": False,
    "completion_ready": False,
    "p0_unblocked": False,
    "training_import_allowed": False,
    "safe_for_training_import": False,
    "safe_for_model_claim": False,
    "customer_delivery_ready": False,
    "release_ready": False,
    "production_execution_allowed": False,
}

CHECKLISTS: dict[str, dict[str, Any]] = {
    "p676::plate_feedback_4g_human_qc_review": {
        "lane": "plate_feedback",
        "priority": 1,
        "first_operator_action": "fill P676 4G worksheet formal plate metadata and human QC/review fields, then transcribe approved rows into formal plate intake",
        "source_work_file": "datasets/feedback/p676_4g_plate_feedback_human_review_worksheet.csv",
        "formal_target_file": "datasets/feedback/experiment_feedback_plate.local.jsonl",
        "template_or_reference_file": "datasets/feedback/experiment_feedback_plate.template.jsonl",
        "primary_validator_command": "python3 scripts/validate_experiment_feedback_plate_intake.py",
        "completion_condition": "formal plate intake has reviewed, QC-classified rows and training_eligible_rows only if policy permits",
        "required_fields": [
            "formal_plate_id",
            "instrument_id",
            "protocol_version",
            "recorded_at",
            "human_qc_decision",
            "human_review_status",
            "reviewer",
            "reviewed_at",
            "review_notes",
        ],
    },
    "p676::strict_mutation_holdout_benchmark": {
        "lane": "strict_holdout",
        "priority": 2,
        "first_operator_action": "provide real strict holdout records or reviewed import receipts, then rebuild strict holdout benchmark artifacts",
        "source_work_file": "reports/kwb_strict_mutation_holdout_benchmark_report.json",
        "formal_target_file": "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl",
        "template_or_reference_file": "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
        "primary_validator_command": "python3 scripts/build_kwb_strict_mutation_holdout_benchmark.py && python3 scripts/apply_benchmark_score_cache_intake.py && python3 scripts/validate_benchmark_score_cache.py",
        "completion_condition": "KWB strict mutation holdout benchmark has nonzero rows and benchmark score cache validates it",
        "required_fields": [
            "real_record_id",
            "source_checksum",
            "label",
            "split_assignment",
            "leakage_review_status",
            "human_acceptance_receipt",
        ],
    },
    "p676::substrate_identity_review": {
        "lane": "substrate_identity",
        "priority": 3,
        "first_operator_action": "write reviewed substrate identity decisions from source evidence, not from candidate rows alone",
        "source_work_file": "datasets/curation/substrate_identity_evidence_candidates.jsonl",
        "formal_target_file": "datasets/curation/substrate_identity_review_decisions.jsonl",
        "template_or_reference_file": "datasets/curation/substrate_identity_review_decisions.template.jsonl",
        "primary_validator_command": "python3 scripts/validate_substrate_identity_evidence_candidates.py",
        "completion_condition": "reviewed substrate identity decisions exist and downstream benchmark/label gate accepts them",
        "required_fields": [
            "candidate_id",
            "review_decision",
            "substrate_identity_normalized",
            "source_evidence_locator",
            "reviewer",
            "reviewed_at",
            "decision_rationale",
        ],
    },
    "p676::numbering_curation_review": {
        "lane": "numbering_curation",
        "priority": 4,
        "first_operator_action": "write accepted canonical mappings only with reviewed source receipt and WT match evidence",
        "source_work_file": "datasets/curation/numbering_curation_queue.jsonl",
        "formal_target_file": "datasets/curation/numbering_curation_decisions.jsonl",
        "template_or_reference_file": "datasets/curation/numbering_curation_decisions.template.jsonl",
        "primary_validator_command": "python3 scripts/validate_numbering_curation_decisions.py && python3 scripts/apply_numbering_curation.py",
        "completion_condition": "active map_to_canonical decisions validate and increase strict usable supervised rows without deep-audit conflict",
        "required_fields": [
            "record_id",
            "decision",
            "canonical_uniprot_id",
            "canonical_position",
            "canonical_wild_type",
            "canonical_mutant",
            "source_refs",
            "curator",
            "curated_at",
        ],
    },
    "p676::license_ip_biosecurity_governance": {
        "lane": "governance",
        "priority": 5,
        "first_operator_action": "record verified license/IP/FTO/biosecurity decisions in their formal decision files",
        "source_work_file": "reports/governance_review_bundle_report.json",
        "formal_target_file": "datasets/governance/external_license_review_decisions.jsonl;datasets/governance/sequence_ip_fto_decisions.jsonl;datasets/governance/biosecurity_screening_decisions.jsonl",
        "template_or_reference_file": "datasets/governance/external_license_review_decisions.template.jsonl;datasets/governance/sequence_ip_fto_decisions.template.jsonl;datasets/governance/biosecurity_screening_decisions.template.jsonl",
        "primary_validator_command": "python3 scripts/validate_external_license_review_decisions.py && python3 scripts/validate_sequence_ip_fto_decisions.py && python3 scripts/validate_biosecurity_screening_decisions.py",
        "completion_condition": "verified license, IP/FTO, and biosecurity decision validators pass for the intended delivery or production scope",
        "required_fields": [
            "source_id",
            "decision_scope",
            "verification_status",
            "approved_use",
            "reviewer",
            "reviewed_at",
            "evidence_locator",
        ],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "checklist_id",
        "priority",
        "lane",
        "handoff_id",
        "first_operator_action",
        "source_work_file",
        "formal_target_file",
        "template_or_reference_file",
        "primary_validator_command",
        "completion_condition",
        "required_fields",
        "completion_ready",
        "release_ready",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {key: row.get(key) for key in fieldnames}
            out["required_fields"] = ";".join(row.get("required_fields") or [])
            writer.writerow(out)


def existing_line_count(rel_path: str) -> int | None:
    if ";" in rel_path:
        return None
    path = AI_ROOT / rel_path
    if not path.exists() or not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p676_rows = load_jsonl(P676_PACKAGE)
    p676_validation = load_json(P676_VALIDATION)
    rows: list[dict[str, Any]] = []
    for source in p676_rows:
        handoff_id = str(source.get("handoff_id") or "")
        spec = CHECKLISTS.get(handoff_id)
        if not spec:
            continue
        target = str(spec["formal_target_file"])
        rows.append({
            "checklist_id": f"p677::{spec['lane']}",
            "created_at": created_at,
            "handoff_id": handoff_id,
            "source_status": source.get("status"),
            "source_blocker": source.get("blocker"),
            "source_state": source.get("source_state") or {},
            "source_required_real_inputs": source.get("required_real_inputs") or [],
            "target_existing_nonempty_lines": existing_line_count(target),
            "policy": "Completion checklist only. Operators must write real reviewed inputs to the formal target files before validators can promote any downstream state.",
            **spec,
            **FALSE_FLAGS,
        })
    rows.sort(key=lambda row: int(row["priority"]))
    write_jsonl(OUT_JSONL, rows)
    write_csv(OUT_CSV, rows)

    report = {
        "created_at": created_at,
        "local_only": True,
        "source_handoff_rows": len(p676_rows),
        "source_handoff_validation_success": p676_validation.get("success"),
        "checklist_rows": len(rows),
        "open_checklist_rows": len(rows),
        "completion_ready_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "p0_unblocked_rows": 0,
        "checklist_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "checklist_csv": str(OUT_CSV.relative_to(AI_ROOT)),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "P677 makes the P0 pending list executable and auditable; it does not complete any pending item without real formal inputs.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P677 P0 real-input completion checklist",
        "",
        f"- checklist_rows: `{len(rows)}`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "- safe_for_model_claim: `false`",
        "",
        "| Priority | Lane | Formal target | Validator |",
        "|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['priority']} | {row['lane']} | `{row['formal_target_file']}` | `{row['primary_validator_command']}` |"
        )
    lines.extend([
        "",
        "This checklist is a handoff/control artifact. It does not write reviewed decisions, formal intake, training labels, model claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "checklist_rows": len(rows),
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
