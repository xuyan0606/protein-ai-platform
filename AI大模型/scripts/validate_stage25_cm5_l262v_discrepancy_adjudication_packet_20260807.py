#!/usr/bin/env python3
"""Validate the CM5 L262V adjudication packet and keep all downstream gates closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.jsonl"
MARKDOWN = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.md"
CANDIDATES = AI_ROOT / "datasets/governance/stage25_source_extraction_candidates_20260807.jsonl"
CLOSURE = AI_ROOT / "datasets/governance/stage25_source_extraction_reviewer_closure_checklist_20260807.jsonl"
CROSS_READ = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_20260807.json"
CROSS_VALIDATION = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_validation_20260807.json"
QUALITY_VALIDATION = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"
EXPECTED_DECISIONS = [
    "needs_more_info",
    "confirm_L262V_in_CM5_construct",
    "reject_L262V_as_sequence_artifact",
    "confirm_construct_or_model_version_mismatch",
]
EMPTY_REVIEW_FIELDS = ("adjudication_decision", "reviewer", "reviewed_at", "reviewed_source_locator", "decision_basis", "review_notes")
NEGATIVE_FLAGS = (
    "other_construct_context_can_resolve_cm5",
    "review_completed",
    "discrepancy_resolved",
    "complete_composition_unambiguous",
    "reviewed_extraction_completed",
    "ready_for_sqlite_apply",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for path, label in ((PACKET, "packet"), (MARKDOWN, "markdown"), (CANDIDATES, "candidates"), (CLOSURE, "closure"), (CROSS_READ, "cross_read"), (CROSS_VALIDATION, "cross_validation"), (QUALITY_VALIDATION, "quality_validation")):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    packet_rows = load_jsonl(PACKET) if PACKET.is_file() else []
    packet = packet_rows[0] if len(packet_rows) == 1 else {}
    candidates = load_jsonl(CANDIDATES) if CANDIDATES.is_file() else []
    closure_rows = load_jsonl(CLOSURE) if CLOSURE.is_file() else []
    cross_read = load_json(CROSS_READ) if CROSS_READ.is_file() else {}
    cross_validation = load_json(CROSS_VALIDATION) if CROSS_VALIDATION.is_file() else {}
    quality_validation = load_json(QUALITY_VALIDATION) if QUALITY_VALIDATION.is_file() else {}
    cm5_candidates = [row for row in candidates if row.get("pmid") == "42235695"]
    l262v_closure = [row for row in closure_rows if row.get("pmid") == "42235695" and row.get("required_review_field") == "resolve_L262V_nucleotide_PDB_discrepancy"]

    fail_if(len(packet_rows) != 1, failures, "packet_rows", len(packet_rows), 1)
    fail_if(len(cm5_candidates) != 1, failures, "cm5_candidate_rows", len(cm5_candidates), 1)
    fail_if(len(l262v_closure) != 1, failures, "l262v_closure_rows", len(l262v_closure), 1)
    candidate = cm5_candidates[0] if len(cm5_candidates) == 1 else {}
    closure = l262v_closure[0] if len(l262v_closure) == 1 else {}
    fail_if(cross_validation.get("audit_valid") is not True, failures, "cross_read_audit_valid", cross_validation.get("audit_valid"), True)
    fail_if(quality_validation.get("audit_valid") is not True, failures, "quality_audit_valid", quality_validation.get("audit_valid"), True)
    fail_if(packet.get("packet_id") != "stage25_cm5_l262v_discrepancy_adjudication_20260807", failures, "packet_id", packet.get("packet_id"), "stage25_cm5_l262v_discrepancy_adjudication_20260807")
    fail_if(packet.get("stage") != 25, failures, "stage", packet.get("stage"), 25)
    fail_if(packet.get("pmid") != "42235695", failures, "pmid", packet.get("pmid"), "42235695")
    fail_if(packet.get("target") != "CM5", failures, "target", packet.get("target"), "CM5")
    fail_if(packet.get("source_extraction_id") != candidate.get("extraction_id"), failures, "source_extraction_id", packet.get("source_extraction_id"), candidate.get("extraction_id"))
    fail_if(packet.get("closure_check_id") != closure.get("check_id"), failures, "closure_check_id", packet.get("closure_check_id"), closure.get("check_id"))
    fail_if(packet.get("declared_substitutions") != ["L15R", "S45T", "K85P", "K231R"], failures, "declared_substitutions", packet.get("declared_substitutions"), ["L15R", "S45T", "K85P", "K231R"])
    fail_if(packet.get("undeclared_substitution_candidates") != ["L262V"], failures, "undeclared_substitution_candidates", packet.get("undeclared_substitution_candidates"), ["L262V"])
    for field, expected in (("wt_codon_262", "TTG"), ("cm5_read_codon_262", "GTG"), ("cm5_pdb_residue_262", "LEU"), ("wt_pdb_residue_262", "LEU")):
        fail_if(packet.get(field) != expected, failures, field, packet.get(field), expected)
    for field, expected in (("direct_cm5_read_rows", 1), ("other_construct_ttg_context_rows", 8), ("other_construct_no_coverage_rows", 2), ("cm5_independent_replicate_rows", 0), ("reviewed_raw_trace_rows", 0), ("quality_bearing_artifact_rows", 0), ("evidence_supplied_rows", 0)):
        fail_if(packet.get(field) != expected, failures, field, packet.get(field), expected)
    fail_if(packet.get("cross_construct_consensus_only") is not True, failures, "cross_construct_consensus_only", packet.get("cross_construct_consensus_only"), True)
    fail_if(packet.get("workflow_status") != "needs_more_info", failures, "workflow_status", packet.get("workflow_status"), "needs_more_info")

    evidence_rows = packet.get("evidence_rows") if isinstance(packet.get("evidence_rows"), list) else []
    source_reads = cross_read.get("reads") if isinstance(cross_read.get("reads"), list) else []
    fail_if(len(evidence_rows) != 11, failures, "evidence_rows", len(evidence_rows), 11)
    fail_if([row.get("basename") for row in evidence_rows] != [row.get("basename") for row in source_reads], failures, "evidence_basenames_match_cross_read", [row.get("basename") for row in evidence_rows], [row.get("basename") for row in source_reads])
    for index, (evidence, source) in enumerate(zip(evidence_rows, source_reads), 1):
        prefix = f"evidence_rows[{index}]"
        for field in ("member", "sha256"):
            fail_if(evidence.get(field) != source.get(field), failures, f"{prefix}.{field}", evidence.get(field), source.get(field))
        fail_if(evidence.get("covers_codon_262") is not source.get("covers_wt_codon_262"), failures, f"{prefix}.covers", evidence.get("covers_codon_262"), source.get("covers_wt_codon_262"))
        fail_if(evidence.get("codon_262") != source.get("codon_262"), failures, f"{prefix}.codon", evidence.get("codon_262"), source.get("codon_262"))
        fail_if(evidence.get("counts_as_cm5_independent_replicate") is not False, failures, f"{prefix}.not_cm5_independent_replicate", evidence.get("counts_as_cm5_independent_replicate"), False)
        fail_if(evidence.get("eligible_to_resolve_cm5_discrepancy_alone") is not False, failures, f"{prefix}.not_resolving_alone", evidence.get("eligible_to_resolve_cm5_discrepancy_alone"), False)
        expected_role = "cm5_direct_read" if source.get("is_cm5_read") is True else "other_construct_wt_context" if source.get("covers_wt_codon_262") is True else "other_construct_no_codon262_coverage"
        fail_if(evidence.get("evidence_role") != expected_role, failures, f"{prefix}.evidence_role", evidence.get("evidence_role"), expected_role)

    decisions = [row.get("decision") for row in packet.get("allowed_adjudication_options", []) if isinstance(row, dict)]
    fail_if(decisions != EXPECTED_DECISIONS, failures, "allowed_adjudication_options", decisions, EXPECTED_DECISIONS)
    fail_if(any(not row.get("minimum_evidence") for row in packet.get("allowed_adjudication_options", [])), failures, "adjudication_options_have_evidence", packet.get("allowed_adjudication_options"), "all minimum_evidence non-empty")
    fail_if(packet.get("required_closure_evidence") != closure.get("closure_evidence_required"), failures, "required_closure_evidence", packet.get("required_closure_evidence"), closure.get("closure_evidence_required"))
    for field in EMPTY_REVIEW_FIELDS:
        fail_if(packet.get(field) != "", failures, f"{field}_empty", packet.get(field), "")
    for field in NEGATIVE_FLAGS:
        fail_if(packet.get(field) is not False, failures, f"{field}_false", packet.get(field), False)
    fail_if(packet.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", packet.get("formal_decision_rows_written"), 0)

    markdown = MARKDOWN.read_text(encoding="utf-8") if MARKDOWN.is_file() else ""
    for term in ("Status: `needs_more_info`", "other constructs", "not independent CM5 replicates", "CM5 independent replicate rows: `0`", "Reviewed raw trace rows: `0`", "Adjudication decision: [blank]", "Reviewer: [blank]", "discrepancy_resolved=false", "ready_for_sqlite_apply=false"):
        fail_if(term not in markdown, failures, f"markdown_contains:{term}", markdown, f"contains {term}")
    policy = str(packet.get("policy") or "")
    for term in ("other constructs", "not independent CM5 replicates", "Empty reviewer fields", "SQLite apply", "release"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_discrepancy_adjudication_packet_validation",
        "stage": 25,
        "packet_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "packet_rows": len(packet_rows),
        "needs_more_info_rows": 1 if packet.get("workflow_status") == "needs_more_info" else 0,
        "adjudication_ready_for_human_review_rows": 1 if not failures and packet.get("workflow_status") == "needs_more_info" else 0,
        "adjudication_completed_rows": 0,
        "evidence_rows": len(evidence_rows),
        "direct_cm5_read_rows": packet.get("direct_cm5_read_rows"),
        "other_construct_ttg_context_rows": packet.get("other_construct_ttg_context_rows"),
        "other_construct_ttg_rows": packet.get("other_construct_ttg_context_rows"),
        "other_construct_no_coverage_rows": packet.get("other_construct_no_coverage_rows"),
        "cm5_independent_replicate_rows": packet.get("cm5_independent_replicate_rows"),
        "independent_cm5_replicate_rows": packet.get("cm5_independent_replicate_rows"),
        "reviewed_raw_trace_rows": packet.get("reviewed_raw_trace_rows"),
        "quality_bearing_artifact_rows": packet.get("quality_bearing_artifact_rows"),
        "allowed_adjudication_option_rows": len(decisions),
        "workflow_status": packet.get("workflow_status"),
        "review_fields_empty": all(packet.get(field) == "" for field in EMPTY_REVIEW_FIELDS),
        "reviewer_filled_rows": 0,
        "source_locator_rows": 0,
        "cross_construct_consensus_only": packet.get("cross_construct_consensus_only") is True,
        "other_construct_reads_accepted_as_cm5_replicates": False,
        "other_construct_context_can_resolve_cm5": False,
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
        "packet_sha256": hashlib.sha256(PACKET.read_bytes()).hexdigest() if PACKET.is_file() else None,
        "markdown_sha256": hashlib.sha256(MARKDOWN.read_bytes()).hexdigest() if MARKDOWN.is_file() else None,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "packet_valid": report["packet_valid"],
        "failure_count": report["failure_count"],
        "evidence_rows": report["evidence_rows"],
        "other_construct_ttg_context_rows": report["other_construct_ttg_context_rows"],
        "cm5_independent_replicate_rows": report["cm5_independent_replicate_rows"],
        "discrepancy_resolved": report["discrepancy_resolved"],
    }, sort_keys=True))
    return 0 if report["packet_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
