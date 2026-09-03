#!/usr/bin/env python3
"""Build a fail-closed reviewer adjudication packet for the CM5 L262V discrepancy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets/governance/stage25_source_extraction_candidates_20260807.jsonl"
CLOSURE = AI_ROOT / "datasets/governance/stage25_source_extraction_reviewer_closure_checklist_20260807.jsonl"
CROSS_READ = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_20260807.json"
CROSS_READ_VALIDATION = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_validation_20260807.json"
QUALITY_VALIDATION = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json"
OUTPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.jsonl"
MARKDOWN_OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.md"
PMID = "42235695"
TARGET = "CM5"
CLOSURE_FIELD = "resolve_L262V_nucleotide_PDB_discrepancy"
HUMAN_REVIEW_FIELDS = ("adjudication_decision", "reviewer", "reviewed_at", "reviewed_source_locator", "decision_basis", "review_notes")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path} contains a non-object row")
        rows.append(row)
    return rows


def one(rows: list[dict[str, Any]], predicate: Any, label: str) -> dict[str, Any]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"expected one {label}, found {len(matches)}")
    return matches[0]


def build_packet() -> dict[str, Any]:
    candidate = one(load_jsonl(CANDIDATES), lambda row: row.get("pmid") == PMID, "CM5 extraction candidate")
    closure = one(
        load_jsonl(CLOSURE),
        lambda row: row.get("pmid") == PMID and row.get("required_review_field") == CLOSURE_FIELD,
        "L262V closure row",
    )
    cross_read = load_json(CROSS_READ)
    cross_validation = load_json(CROSS_READ_VALIDATION)
    quality_validation = load_json(QUALITY_VALIDATION)
    if cross_validation.get("audit_valid") is not True or quality_validation.get("audit_valid") is not True:
        raise ValueError("P279 and P280 validations must pass before building adjudication packet")

    evidence_rows = []
    for row in cross_read.get("reads", []):
        if row.get("is_cm5_read") is True:
            evidence_role = "cm5_direct_read"
        elif row.get("covers_wt_codon_262") is True:
            evidence_role = "other_construct_wt_context"
        else:
            evidence_role = "other_construct_no_codon262_coverage"
        evidence_rows.append({
            "basename": row.get("basename"),
            "member": row.get("member"),
            "sha256": row.get("sha256"),
            "evidence_role": evidence_role,
            "covers_codon_262": row.get("covers_wt_codon_262"),
            "codon_262": row.get("codon_262"),
            "amino_acid_262": row.get("amino_acid_262"),
            "is_cm5_primary_read": row.get("is_cm5_read") is True,
            "counts_as_cm5_independent_replicate": False,
            "eligible_to_resolve_cm5_discrepancy_alone": False,
        })

    options = [
        {
            "decision": "needs_more_info",
            "minimum_evidence": [
                "Keep the discrepancy open while any decisive CM5-specific evidence is missing",
            ],
        },
        {
            "decision": "confirm_L262V_in_CM5_construct",
            "minimum_evidence": [
                "Reviewed CM5 raw trace with per-base quality supporting GTG at codon 262 or independent CM5 clone resequencing supporting GTG",
                "Reviewed complete CM5 construct record including L262V",
                "Reviewed reconciliation of the CM5 nucleotide call with the LEU262 PDB model",
            ],
        },
        {
            "decision": "reject_L262V_as_sequence_artifact",
            "minimum_evidence": [
                "Reviewed CM5 raw trace demonstrating an unreliable or incorrect GTG call or independent CM5 clone resequencing supporting TTG",
                "Reviewed explanation linking the corrected sequence to the CM5 construct and LEU262 PDB model",
            ],
        },
        {
            "decision": "confirm_construct_or_model_version_mismatch",
            "minimum_evidence": [
                "Reviewed provenance linking the sequence read, physical CM5 construct, and PDB model to distinct versions",
                "Reviewed complete composition decision for each version",
            ],
        },
    ]

    direct_cm5 = [row for row in evidence_rows if row["evidence_role"] == "cm5_direct_read"]
    other_ttg = [row for row in evidence_rows if row["evidence_role"] == "other_construct_wt_context"]
    no_coverage = [row for row in evidence_rows if row["evidence_role"] == "other_construct_no_codon262_coverage"]
    return {
        "packet_id": "stage25_cm5_l262v_discrepancy_adjudication_20260807",
        "stage": 25,
        "pmid": PMID,
        "target": TARGET,
        "discrepancy": "L262V_nucleotide_PDB_discrepancy",
        "source_extraction_id": candidate.get("extraction_id"),
        "closure_check_id": closure.get("check_id"),
        "upstream_cross_read_audit_valid": True,
        "upstream_quality_evidence_audit_valid": True,
        "declared_substitutions": candidate.get("cm5_candidate_substitutions"),
        "undeclared_substitution_candidates": candidate.get("undeclared_substitution_candidates"),
        "wt_codon_262": (candidate.get("nucleotide_alignment") or {}).get("wt_codon_262"),
        "cm5_read_codon_262": (candidate.get("nucleotide_alignment") or {}).get("cm5_read_codon_262"),
        "cm5_pdb_residue_262": (candidate.get("pdb_residue_262") or {}).get("cm5"),
        "wt_pdb_residue_262": (candidate.get("pdb_residue_262") or {}).get("wt"),
        "direct_cm5_read_rows": len(direct_cm5),
        "other_construct_ttg_context_rows": len(other_ttg),
        "other_construct_no_coverage_rows": len(no_coverage),
        "cm5_independent_replicate_rows": 0,
        "reviewed_raw_trace_rows": 0,
        "quality_bearing_artifact_rows": quality_validation.get("quality_bearing_artifact_rows"),
        "cross_construct_consensus_only": True,
        "other_construct_context_can_resolve_cm5": False,
        "evidence_rows": evidence_rows,
        "allowed_adjudication_options": options,
        "required_closure_evidence": closure.get("closure_evidence_required"),
        "workflow_status": "needs_more_info",
        "adjudication_decision": "",
        "reviewer": "",
        "reviewed_at": "",
        "reviewed_source_locator": "",
        "decision_basis": "",
        "review_notes": "",
        "evidence_supplied_rows": 0,
        "review_completed": False,
        "discrepancy_resolved": False,
        "complete_composition_unambiguous": False,
        "reviewed_extraction_completed": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed human adjudication packet only. The eight TTG calls are from other constructs and are WT-context evidence, not independent CM5 replicates. Empty reviewer fields and needs_more_info do not resolve L262V, complete CM5 composition, reviewed extraction, SQLite apply, model claims, customer delivery, or release.",
    }


def build_markdown(packet: dict[str, Any]) -> str:
    evidence_lines = [
        f"| `{row['basename']}` | `{row['evidence_role']}` | `{row['codon_262']}` | `{str(row['counts_as_cm5_independent_replicate']).lower()}` |"
        for row in packet["evidence_rows"]
    ]
    option_lines = [
        f"- `{option['decision']}`: " + "; ".join(option["minimum_evidence"])
        for option in packet["allowed_adjudication_options"]
    ]
    return "\n".join([
        "# CM5 L262V Discrepancy Adjudication Packet",
        "",
        "Status: `needs_more_info`",
        "",
        f"Declared substitutions: `{','.join(packet['declared_substitutions'])}`",
        f"Observed conflict: WT codon 262 `{packet['wt_codon_262']}` / CM5 read `{packet['cm5_read_codon_262']}` / CM5 PDB `{packet['cm5_pdb_residue_262']}` / WT PDB `{packet['wt_pdb_residue_262']}`.",
        "",
        "The eight TTG calls are from other constructs. They provide WT-context evidence but are not independent CM5 replicates and cannot resolve CM5 composition.",
        "",
        "| Read | Evidence role | Codon 262 | Counts as CM5 independent replicate |",
        "|---|---|---:|---:|",
        *evidence_lines,
        "",
        f"CM5 independent replicate rows: `{packet['cm5_independent_replicate_rows']}`",
        f"Reviewed raw trace rows: `{packet['reviewed_raw_trace_rows']}`",
        f"Quality-bearing artifact rows: `{packet['quality_bearing_artifact_rows']}`",
        "",
        "## Allowed Adjudication Options",
        "",
        *option_lines,
        "",
        "## Reviewer Fields",
        "",
        "- Adjudication decision: [blank]",
        "- Reviewer: [blank]",
        "- Reviewed at: [blank]",
        "- Reviewed source locator: [blank]",
        "- Decision basis: [blank]",
        "- Review notes: [blank]",
        "",
        "`discrepancy_resolved=false`; `complete_composition_unambiguous=false`; `reviewed_extraction_completed=false`; `ready_for_sqlite_apply=false`; `apply_executed=false`; `safe_for_model_claim=false`; `release_ready=false`.",
        "",
    ])


def main() -> int:
    if OUTPUT.is_file():
        existing_rows = load_jsonl(OUTPUT)
        existing = existing_rows[0] if len(existing_rows) == 1 else {}
        human_review_present = any(str(existing.get(field) or "").strip() for field in HUMAN_REVIEW_FIELDS)
        if human_review_present or existing.get("review_completed") is True:
            raise SystemExit("refusing to overwrite adjudication packet with human review content")
    packet = build_packet()
    OUTPUT.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(build_markdown(packet), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "markdown_output": str(MARKDOWN_OUTPUT),
        "evidence_rows": len(packet["evidence_rows"]),
        "other_construct_ttg_context_rows": packet["other_construct_ttg_context_rows"],
        "cm5_independent_replicate_rows": packet["cm5_independent_replicate_rows"],
        "workflow_status": packet["workflow_status"],
        "discrepancy_resolved": packet["discrepancy_resolved"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
