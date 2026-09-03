#!/usr/bin/env python3
"""Validate true hard-gate breakthrough candidates remain review drafts only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
NUMBERING_AUDIT_QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_review_queue.jsonl"
NUMBERING_DRAFT = AI_ROOT / "datasets" / "curation" / "numbering_deterministic_reject_decisions.review_draft.jsonl"
STRUCTURE_PACKETS = AI_ROOT / "datasets" / "governance" / "structure_feature_hard_gate_operator_packets.jsonl"
STRUCTURE_DRAFT = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_dbref_decisions.review_draft.jsonl"
WET_LAB_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
WET_LAB_DRAFT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.review_draft.jsonl"
REPORT = AI_ROOT / "reports" / "true_hard_gate_breakthrough_candidate_report.json"
MARKDOWN = AI_ROOT / "reports" / "true_hard_gate_breakthrough_candidates.md"
OUTPUT = AI_ROOT / "reports" / "true_hard_gate_breakthrough_candidate_validation_report.json"


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def check(condition: bool, failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if not condition:
        failures.append({"check": name, "observed": observed, "expected": expected})


def load_json(path: Path, failures: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append({"check": f"{label}_valid_json", "observed": str(exc), "expected": "JSON object"})
        return {}
    if not isinstance(value, dict):
        failures.append({"check": f"{label}_json_object", "observed": type(value).__name__, "expected": "object"})
        return {}
    return value


def load_jsonl(path: Path, failures: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({"check": f"{label}_valid_jsonl", "line": line_number, "observed": str(exc), "expected": "JSON object"})
            continue
        if not isinstance(value, dict):
            failures.append({"check": f"{label}_jsonl_object", "line": line_number, "observed": type(value).__name__, "expected": "object"})
            continue
        rows.append(value)
    return rows


def read_text(path: Path, failures: list[dict[str, Any]], label: str) -> str:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return ""
    return path.read_text(encoding="utf-8")


def numbering_reject_drafts(rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for row in rows:
        if row.get("audit_recommended_decision") != "reject_label":
            continue
        flags = set(row.get("source_lineage_flags") or [])
        if not ({"synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx", "sample_fixture_literal_pmid"} & flags):
            continue
        source_refs = [str(row.get("literature_ref") or ""), f"UniProt:{row.get('uniprot_id')}", "report:numbering_deep_audit_report.json"]
        drafts.append({
            "record_id": row.get("record_id"),
            "decision": "reject_label",
            "canonical_uniprot_id": row.get("uniprot_id"),
            "canonical_position": None,
            "canonical_wild_type": None,
            "canonical_mutant": row.get("reported_mutant"),
            "mapping_basis": "unresolved",
            "confidence": 0,
            "source_refs": [item for item in source_refs if item],
            "curator": "",
            "curated_at": "",
            "notes": (
                "REVIEW_DRAFT: deterministic source audit recommends rejecting this label because the row has "
                f"{sorted(flags)} and cannot support {row.get('uniprot_id')} {row.get('mutation')} as reviewed training evidence. "
                "Human reviewer must confirm before copying to numbering_curation_decisions.jsonl."
            ),
            "review_draft": True,
            "created_at": created_at,
            "draft_policy": "not_reviewed_decision; copy only after human review",
        })
    return drafts


def structure_dbref_drafts(rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for row in rows:
        if row.get("packet_type") != "strict_evidence_chain_mapping_review":
            continue
        chain = row.get("suggested_selected_chain_id")
        uniprot_id = row.get("canonical_uniprot_id")
        structure_id = str(row.get("structure_id") or "").upper()
        if not structure_id or not chain or not uniprot_id:
            continue
        drafts.append({
            "structure_id": structure_id,
            "decision": "set_chain_mapping",
            "canonical_uniprot_id": uniprot_id,
            "selected_chain_id": chain,
            "sequence_to_structure_mapping_status": "manual_alignment_reviewed",
            "residue_numbering_basis": "sifts_uniprot_mapping",
            "missing_residue_ranges": [],
            "source_refs": [f"PDB:{structure_id}", f"UniProt:{uniprot_id}", f"PDB_CHAIN:{chain}", "evidence:dbref_interval"],
            "confidence": 0.9,
            "curator": "",
            "curated_at": "",
            "notes": (
                "REVIEW_DRAFT: DBREF interval evidence suggests this chain maps to the canonical UniProt entry. "
                "Human reviewer must inspect biological chain, numbering basis, missing residues, insertion codes, "
                "construct tags and ligands before copying to structure_chain_mapping_decisions.jsonl."
            ),
            "review_draft": True,
            "created_at": created_at,
            "draft_policy": "not_reviewed_chain_mapping; copy only after human review",
        })
    return drafts


def wet_lab_review_drafts(rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for row in rows:
        summary = row.get("candidate_summary") if isinstance(row.get("candidate_summary"), dict) else {}
        assay_type = summary.get("assay_type")
        suggested_heads = ["activity_risk_head"] if assay_type == "activity" else ["stability_head"]
        draft = dict(row)
        draft.update({
            "authorization_decision": "needs_more_info",
            "approved_training_heads": suggested_heads,
            "qc_decision": "not_reviewed",
            "source_trace_reviewed": False,
            "numbering_reviewed": False,
            "unit_condition_reviewed": False,
            "batch_control_reviewed": False,
            "replicate_policy_reviewed": False,
            "allow_append_to_experiment_feedback_local": False,
            "reviewer": "",
            "reviewed_at": "",
            "authorization_basis": (
                "REVIEW_DRAFT: verify raw wet-lab source row, numeric value semantics, batch/control linkage, "
                "numbering, unit/condition and replicate policy before approving for feedback preflight."
            ),
            "conditions": [],
            "residual_risks": ["human_review_required_before_authorization"],
            "review_draft": True,
            "created_at": created_at,
            "draft_policy": "not_authorization; approve only after human review",
        })
        drafts.append(draft)
    return drafts


def expected_report(created_at: str, numbering: list[dict[str, Any]], structure: list[dict[str, Any]], wet_lab: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "created_at": created_at,
        "local_only": True,
        "status": "review_required",
        "numbering": {"draft_rows": len(numbering), "output": relative(NUMBERING_DRAFT), "real_breakthrough_after_human_confirmation": "numbering rejected rows increase after validate/apply"},
        "structure": {"draft_rows": len(structure), "output": relative(STRUCTURE_DRAFT), "real_breakthrough_after_human_confirmation": "reviewed structure chain mappings and graph rows increase after validate/apply/build"},
        "wet_lab": {"draft_rows": len(wet_lab), "output": relative(WET_LAB_DRAFT), "real_breakthrough_after_human_confirmation": "authorized rows and preflight rows increase after validate/preflight"},
        "formal_decisions_written": 0,
        "curation_applied": False,
        "feedback_intake_written": False,
        "training_rows_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Review drafts only; do not count as reviewed decisions until a human confirms and copies into formal input files.",
    }


def expected_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# True Hard-Gate Breakthrough Candidates",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These are evidence-backed candidates for real gate progress. They are not approvals.",
        "",
        "## Candidate Impact",
        "",
        f"- Numbering deterministic reject drafts: {report['numbering']['draft_rows']}",
        f"- Structure DBREF chain-mapping drafts: {report['structure']['draft_rows']}",
        f"- Wet-lab authorization review drafts: {report['wet_lab']['draft_rows']}",
        "",
        "## What Counts As Real Breakthrough",
        "",
        "1. Numbering: human-reviewed reject decisions are written, validator passes, and apply_numbering_curation removes rejected labels.",
        "2. Structure: human-reviewed chain mapping decisions are written, validator passes, and reviewed structure graph rows increase.",
        "3. Wet lab: human-reviewed authorizations pass validation and preflight rows increase.",
        "",
        "## Fail-Closed Boundary",
        "",
        "This script writes only review drafts and an impact report. It does not write formal decisions, apply curation, import labels, run ddG, train a model, or release claims.",
        "",
    ])


def check_drafts(rows: list[dict[str, Any]], name: str, failures: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        check(row.get("review_draft") is True, failures, f"{name}_{index}_review_draft_true", row.get("review_draft"), True)
        check(bool(row.get("draft_policy")), failures, f"{name}_{index}_draft_policy_present", row.get("draft_policy"), "non-empty")
        check(row.get("curator", "") == "" if "curator" in row else True, failures, f"{name}_{index}_curator_empty_when_present", row.get("curator"), "")
        check(row.get("curated_at", "") == "" if "curated_at" in row else True, failures, f"{name}_{index}_curated_at_empty_when_present", row.get("curated_at"), "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate true hard-gate breakthrough review candidates")
    parser.add_argument("--numbering-audit-queue", type=Path, default=NUMBERING_AUDIT_QUEUE)
    parser.add_argument("--numbering-draft", type=Path, default=NUMBERING_DRAFT)
    parser.add_argument("--structure-packets", type=Path, default=STRUCTURE_PACKETS)
    parser.add_argument("--structure-draft", type=Path, default=STRUCTURE_DRAFT)
    parser.add_argument("--wet-lab-template", type=Path, default=WET_LAB_TEMPLATE)
    parser.add_argument("--wet-lab-draft", type=Path, default=WET_LAB_DRAFT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    failures: list[dict[str, Any]] = []
    report = load_json(args.report, failures, "report")
    markdown = read_text(args.markdown, failures, "markdown")
    numbering_draft = load_jsonl(args.numbering_draft, failures, "numbering_draft")
    structure_draft = load_jsonl(args.structure_draft, failures, "structure_draft")
    wet_lab_draft = load_jsonl(args.wet_lab_draft, failures, "wet_lab_draft")
    created_at = str(report.get("created_at"))
    expected_numbering = numbering_reject_drafts(load_jsonl(args.numbering_audit_queue, failures, "numbering_audit_queue"), created_at)
    expected_structure = structure_dbref_drafts(load_jsonl(args.structure_packets, failures, "structure_packets"), created_at)
    expected_wet_lab = wet_lab_review_drafts(load_jsonl(args.wet_lab_template, failures, "wet_lab_template"), created_at)
    expected = expected_report(created_at, expected_numbering, expected_structure, expected_wet_lab)
    check(numbering_draft == expected_numbering, failures, "numbering_draft_matches_current_sources", numbering_draft, expected_numbering)
    check(structure_draft == expected_structure, failures, "structure_draft_matches_current_sources", structure_draft, expected_structure)
    check(wet_lab_draft == expected_wet_lab, failures, "wet_lab_draft_matches_current_sources", wet_lab_draft, expected_wet_lab)
    check(report == expected, failures, "report_matches_current_drafts", report, expected)
    check(markdown == expected_markdown(expected), failures, "markdown_matches_current_report", markdown, expected_markdown(expected))
    check_drafts(numbering_draft, "numbering", failures)
    check_drafts(structure_draft, "structure", failures)
    check_drafts(wet_lab_draft, "wet_lab", failures)
    for key, value in {"formal_decisions_written": 0, "curation_applied": False, "feedback_intake_written": False, "training_rows_written": 0, "safe_for_model_claim": False, "release_ready": False}.items():
        check(report.get(key) == value, failures, f"report_{key}_fail_closed", report.get(key), value)
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "numbering_draft_rows": len(numbering_draft),
        "structure_draft_rows": len(structure_draft),
        "wet_lab_draft_rows": len(wet_lab_draft),
        "failure_count": len(failures),
        "failures": failures[:500],
        "formal_decisions_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation only. Passing means breakthrough candidates are current review drafts, not formal decisions.",
        "output": relative(args.output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "numbering_draft_rows": validation["numbering_draft_rows"],
        "structure_draft_rows": validation["structure_draft_rows"],
        "wet_lab_draft_rows": validation["wet_lab_draft_rows"],
        "failure_count": validation["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
