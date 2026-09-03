#!/usr/bin/env python3
"""Validate source-extraction candidate reviewer rows fail closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "datasets/governance/stage25_source_extraction_candidate_reviewer_packet_20260807.jsonl"
ACQUISITION = AI_ROOT / "reports/stage25_source_acquisition_receipts_validation_20260807.json"
EXTRACTION = AI_ROOT / "reports/stage25_source_extraction_candidate_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_source_extraction_candidate_reviewer_packet_validation_20260807.json"
ACS_PATH = AI_ROOT / "datasets/source_drops/stage25/39743673/jf4c10256_si_001.doc"
CM5_PATH = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
ACS_SHA256 = "586d17cbe843a1b199d9485f7a90980bb66227a4f6bf33ad3fd5fdd68e03b7c6"
CM5_SHA256 = "800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6"
SUBSTITUTIONS = ["L15R", "S45T", "K85P", "K231R"]
ALLOWED_DECISIONS = ["needs_more_info", "approved", "rejected"]
NEGATIVE_FLAGS = (
    "approved_for_reviewed_extraction",
    "reviewed_extraction_completed",
    "source_evidence_ready",
    "ready_for_sqlite_apply",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number} must contain an object")
        rows.append(value)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    rows = load_jsonl(PACKET) if PACKET.exists() else []
    acquisition = load_json(ACQUISITION) if ACQUISITION.exists() else {}
    extraction = load_json(EXTRACTION) if EXTRACTION.exists() else {}
    fail_if(not PACKET.exists(), failures, "packet_exists", "missing", str(PACKET))
    fail_if(not ACQUISITION.exists(), failures, "acquisition_validation_exists", "missing", str(ACQUISITION))
    fail_if(not EXTRACTION.exists(), failures, "extraction_validation_exists", "missing", str(EXTRACTION))
    fail_if(len(rows) != 2, failures, "packet_rows", len(rows), 2)
    fail_if([row.get("pmid") for row in rows] != ["39743673", "42235695"], failures, "pmid_order", [row.get("pmid") for row in rows], ["39743673", "42235695"])
    by_pmid = {str(row.get("pmid")): row for row in rows}
    dsm4 = by_pmid.get("39743673", {})
    cm5 = by_pmid.get("42235695", {})

    common_expected = {
        "stage": 25,
        "allowed_review_decisions": ALLOWED_DECISIONS,
        "review_decision": "needs_more_info",
        "candidate_ready_for_human_review": True,
        "reviewer": "",
        "reviewed_at": "",
        "approval_basis": "",
        "review_notes": "",
        "approved_for_reviewed_extraction": False,
        "reviewed_source_locator_rows": 0,
        "reviewed_extraction_completed": False,
        "source_evidence_ready": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for index, row in enumerate(rows, 1):
        prefix = f"rows[{index}]"
        for field, expected in common_expected.items():
            fail_if(row.get(field) != expected, failures, f"{prefix}.{field}", row.get(field), expected)
        fail_if(set(row.get("allowed_review_decisions") or []) != set(ALLOWED_DECISIONS), failures, f"{prefix}.allowed_decisions_exact", row.get("allowed_review_decisions"), ALLOWED_DECISIONS)
        fail_if(not isinstance(row.get("required_review_fields"), list) or not row.get("required_review_fields"), failures, f"{prefix}.required_review_fields", row.get("required_review_fields"), "non-empty list")
        for flag in NEGATIVE_FLAGS:
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)

    dsm4_expected = {
        "packet_id": "stage25_source_candidate_review_39743673_dsm4_20260807",
        "target": "DSM4",
        "candidate_substitutions": [],
        "composition_candidate_resolved": False,
        "source_local_path": str(ACS_PATH.relative_to(AI_ROOT)),
        "source_sha256": ACS_SHA256,
        "required_review_fields": ["complete_dsm4_residue_composition", "wt_absolute_baseline", "measurement_values_and_units", "assay_conditions", "reviewed_table_or_figure_locator"],
    }
    cm5_expected = {
        "packet_id": "stage25_source_candidate_review_42235695_cm5_20260807",
        "target": "CM5",
        "candidate_substitutions": SUBSTITUTIONS,
        "composition_candidate_resolved": False,
        "declared_substitutions_corroborated": True,
        "undeclared_substitution_candidates": ["L262V"],
        "nucleotide_pdb_discrepancy": True,
        "complete_composition_unambiguous": False,
        "source_local_path": str(CM5_PATH.relative_to(AI_ROOT)),
        "source_sha256": CM5_SHA256,
        "required_review_fields": ["article_fulltext", "reviewed_source_table_or_locator", "mutation_effect_measurements", "absolute_wt_baseline", "units_and_assay_conditions", "mutation_process_separation_rationale", "resolve_L262V_nucleotide_PDB_discrepancy"],
    }
    for field, expected in dsm4_expected.items():
        fail_if(dsm4.get(field) != expected, failures, f"dsm4.{field}", dsm4.get(field), expected)
    for field, expected in cm5_expected.items():
        fail_if(cm5.get(field) != expected, failures, f"cm5.{field}", cm5.get(field), expected)
    nucleotide_probe = (cm5.get("evidence_summary") or {}).get("nucleotide_alignment_probe") or {}
    for field, expected in (
        ("codon262_sequence_member_rows", 11),
        ("codon262_coverage_rows", 9),
        ("codon262_no_coverage_rows", 2),
        ("codon262_wt_codon_rows", 8),
        ("codon262_variant_codon_rows", 1),
    ):
        fail_if(nucleotide_probe.get(field) != expected, failures, f"cm5.nucleotide_probe.{field}", nucleotide_probe.get(field), expected)

    for label, path, expected_sha in (("dsm4", ACS_PATH, ACS_SHA256), ("cm5", CM5_PATH, CM5_SHA256)):
        present = path.is_file()
        current_sha = sha256(path) if present else None
        fail_if(not present, failures, f"{label}.source_present", present, True)
        fail_if(current_sha != expected_sha, failures, f"{label}.source_sha256_live", current_sha, expected_sha)

    fail_if(acquisition.get("receipt_valid") is not True, failures, "acquisition_receipt_valid", acquisition.get("receipt_valid"), True)
    fail_if(acquisition.get("acquisition_integrity_verified") is not True, failures, "acquisition_integrity_verified", acquisition.get("acquisition_integrity_verified"), True)
    fail_if(extraction.get("validation_success") is not True, failures, "extraction_validation_success", extraction.get("validation_success"), True)
    fail_if(extraction.get("dsm4_composition_resolved") is not False, failures, "dsm4_composition_unresolved", extraction.get("dsm4_composition_resolved"), False)
    fail_if(extraction.get("complete_dsm4_residue_rows") != 0, failures, "complete_dsm4_residue_rows_zero", extraction.get("complete_dsm4_residue_rows"), 0)
    fail_if(extraction.get("declared_substitutions_corroborated") is not True, failures, "cm5_declared_substitutions_corroborated", extraction.get("declared_substitutions_corroborated"), True)
    fail_if(extraction.get("undeclared_substitution_candidates") != ["L262V"], failures, "cm5_undeclared_substitution_candidates", extraction.get("undeclared_substitution_candidates"), ["L262V"])
    fail_if(extraction.get("nucleotide_pdb_discrepancy_verified") is not True, failures, "cm5_nucleotide_pdb_discrepancy_verified", extraction.get("nucleotide_pdb_discrepancy_verified"), True)
    fail_if(extraction.get("complete_composition_unambiguous") is not False, failures, "cm5_complete_composition_unambiguous_false", extraction.get("complete_composition_unambiguous"), False)
    fail_if(extraction.get("cm5_composition_candidate_resolved") is not False, failures, "cm5_composition_candidate_resolved_false", extraction.get("cm5_composition_candidate_resolved"), False)
    fail_if(extraction.get("cm5_composition_formally_reviewed") is not False, failures, "cm5_composition_formally_reviewed_false", extraction.get("cm5_composition_formally_reviewed"), False)
    fail_if(extraction.get("cm5_candidate_substitutions") != SUBSTITUTIONS, failures, "cm5_candidate_substitutions", extraction.get("cm5_candidate_substitutions"), SUBSTITUTIONS)
    fail_if(extraction.get("mutation_effect_measurement_rows") != 0, failures, "mutation_effect_measurement_rows_zero", extraction.get("mutation_effect_measurement_rows"), 0)

    report = {
        "schema_version": 1,
        "mode": "stage25_source_extraction_candidate_reviewer_packet_validation",
        "stage": 25,
        "packet_valid": not failures,
        "reviewer_packet_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "packet_rows": len(rows),
        "reviewer_rows": len(rows),
        "unique_pmid_rows": len({row.get("pmid") for row in rows}),
        "needs_more_info_rows": sum(row.get("review_decision") == "needs_more_info" for row in rows),
        "candidate_ready_for_human_review_rows": sum(row.get("candidate_ready_for_human_review") is True for row in rows),
        "reviewer_completed_rows": sum(bool(row.get("reviewer") and row.get("reviewed_at") and row.get("approval_basis")) for row in rows),
        "composition_candidate_resolved_rows": sum(row.get("composition_candidate_resolved") is True for row in rows),
        "dsm4_unresolved_rows": sum(row.get("pmid") == "39743673" and row.get("composition_candidate_resolved") is False for row in rows),
        "cm5_composition_ambiguous_rows": sum(row.get("pmid") == "42235695" and row.get("composition_candidate_resolved") is False for row in rows),
        "declared_substitutions_corroborated_rows": sum(row.get("declared_substitutions_corroborated") is True for row in rows),
        "nucleotide_pdb_discrepancy_rows": sum(row.get("nucleotide_pdb_discrepancy") is True for row in rows),
        "codon262_sequence_member_rows": nucleotide_probe.get("codon262_sequence_member_rows"),
        "codon262_coverage_rows": nucleotide_probe.get("codon262_coverage_rows"),
        "codon262_no_coverage_rows": nucleotide_probe.get("codon262_no_coverage_rows"),
        "codon262_wt_codon_rows": nucleotide_probe.get("codon262_wt_codon_rows"),
        "codon262_variant_codon_rows": nucleotide_probe.get("codon262_variant_codon_rows"),
        "approved_for_reviewed_extraction_rows": sum(row.get("approved_for_reviewed_extraction") is True for row in rows),
        "approved_rows": 0,
        "formal_review_rows": 0,
        "reviewed_extraction_rows": 0,
        "reviewer_filled_rows": 0,
        "source_locator_rows": 0,
        "required_review_field_rows": sum(len(row.get("required_review_fields") or []) for row in rows),
        "reviewed_source_locator_rows": 0,
        "reviewed_extraction_completed_rows": 0,
        "source_evidence_ready_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Reviewer packet validation only. needs_more_info rows cannot satisfy reviewed extraction, formal decisions, SQLite apply, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "packet_valid": report["packet_valid"], "failure_count": report["failure_count"], "packet_rows": report["packet_rows"], "needs_more_info_rows": report["needs_more_info_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["packet_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
