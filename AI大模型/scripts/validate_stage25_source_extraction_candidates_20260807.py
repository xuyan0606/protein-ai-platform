#!/usr/bin/env python3
"""Validate read-only source extraction candidates without opening evidence gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "datasets/governance/stage25_source_extraction_candidates_20260807.jsonl"
ACS_SOURCE = AI_ROOT / "datasets/source_drops/stage25/39743673/jf4c10256_si_001.doc"
ZENODO_SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
OUTPUT = AI_ROOT / "reports/stage25_source_extraction_candidate_validation_20260807.json"
ACS_SHA256 = "586d17cbe843a1b199d9485f7a90980bb66227a4f6bf33ad3fd5fdd68e03b7c6"
ZENODO_SHA256 = "800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6"
CM5_SEQUENCE_SUFFIX = "Sequencing data/CM5 (L15R_S45T_K85P_K231R).seq"
WT_SNAPGENE_SUFFIX = "Sequencing data/Candida rugosa lipase_WT.dna"
CM5_PDB_SUFFIX = "MD simulation data/CM5-65%DMSO/CM5.pdb"
WT_PDB_SUFFIX = "MD simulation data/WT-65%DMSO/wt.pdb"
CM5_SUBSTITUTIONS = ["L15R", "S45T", "K85P", "K231R"]
CM5_RESIDUES = {"15": "ARG", "45": "THR", "85": "PRO", "231": "ARG"}
WT_RESIDUES = {"15": "LEU", "45": "SER", "85": "LYS", "231": "LYS"}
WT_SNAPGENE_SHA256 = "ca76a27e9a349249ad169286ee9c271822037406b8d2cbde3db4fd14efb081b4"
CODON262_CROSS_READ_ROWS = [
    {"member_suffix":"Sequencing data/CM5 (L15R_S45T_K85P_K231R).seq","covers_codon_262":True,"query_interval_1based":[844,846],"codon":"GTG","amino_acid":"V"},
    {"member_suffix":"Sequencing data/E70Q_T201D.seq","covers_codon_262":True,"query_interval_1based":[858,860],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/K85P_K170Y.seq","covers_codon_262":False,"query_interval_1based":None,"codon":None,"amino_acid":None},
    {"member_suffix":"Sequencing data/K85P_K231R.seq","covers_codon_262":True,"query_interval_1based":[860,862],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/K85P_K431T_F.seq","covers_codon_262":False,"query_interval_1based":None,"codon":None,"amino_acid":None},
    {"member_suffix":"Sequencing data/K85P_K431T_R.seq","covers_codon_262":True,"query_interval_1based":[854,856],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/L15R_S45T.seq","covers_codon_262":True,"query_interval_1based":[859,861],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/L15R_S45T_K85P_K231Q_K280S.seq","covers_codon_262":True,"query_interval_1based":[845,847],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/L15R_S45T_K85P_K231R_K280S.seq","covers_codon_262":True,"query_interval_1based":[845,847],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/L15R_S45T_K85P_K231V.seq","covers_codon_262":True,"query_interval_1based":[845,847],"codon":"TTG","amino_acid":"L"},
    {"member_suffix":"Sequencing data/S45T_N113K_D167K.seq","covers_codon_262":True,"query_interval_1based":[861,863],"codon":"TTG","amino_acid":"L"},
]
NUCLEOTIDE_ALIGNMENT = {
    "tool": "Biopython 1.85 PairwiseAligner local",
    "wt_snapgene_member": WT_SNAPGENE_SUFFIX,
    "wt_snapgene_sha256": WT_SNAPGENE_SHA256,
    "wt_plasmid_length_nt": 2059,
    "wt_crl1_interval_zero_based": [363, 1968],
    "wt_crl1_length_nt": 1605,
    "target_interval_zero_based": [0, 798],
    "query_interval_zero_based": [60, 858],
    "aligned_identity_nt": 787,
    "aligned_mismatch_nt": 11,
    "aligned_gap_nt": 0,
    "declared_amino_acid_differences": CM5_SUBSTITUTIONS,
    "undeclared_amino_acid_difference_candidates": ["L262V"],
    "wt_codon_262": "TTG",
    "cm5_read_codon_262": "GTG",
    "codon262_cross_read_rows": CODON262_CROSS_READ_ROWS,
    "codon262_sequence_member_rows": 11,
    "codon262_coverage_rows": 9,
    "codon262_no_coverage_rows": 2,
    "codon262_wt_codon_rows": 8,
    "codon262_variant_codon_rows": 1,
}
NEGATIVE_FLAGS = (
    "reviewed_extraction_completed", "source_evidence_ready", "ready_for_reviewed_extraction",
    "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed",
    "export_safe_released", "safe_for_model_claim", "release_ready",
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be an object")
            rows.append(value)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def archive_member(archive: ZipFile, suffix: str) -> tuple[str, bytes]:
    matches = [item.filename for item in archive.infolist() if not item.is_dir() and item.filename.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one archive member ending with {suffix!r}, found {len(matches)}")
    return matches[0], archive.read(matches[0])


def pdb_residues(payload: bytes, positions: set[int]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for line in payload.decode("ascii").splitlines():
        if not line.startswith("ATOM") or line[12:16].strip() != "CA":
            continue
        position = int(line[22:26])
        if position in positions:
            observed[str(position)] = line[17:20].strip()
    return observed


def check_closed_flags(row: dict[str, Any], prefix: str, failures: list[dict[str, Any]]) -> None:
    fail_if(row.get("reviewed_source_locator_rows") != 0, failures, f"{prefix}.reviewed_source_locator_rows", row.get("reviewed_source_locator_rows"), 0)
    fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written", row.get("formal_decision_rows_written"), 0)
    for flag in NEGATIVE_FLAGS:
        fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}", row.get(flag), False)


def main() -> int:
    failures: list[dict[str, Any]] = []
    rows = load_rows(RECEIPT) if RECEIPT.exists() else []
    fail_if(not RECEIPT.exists(), failures, "receipt_exists", str(RECEIPT), "present")
    fail_if(len(rows) != 2, failures, "candidate_rows", len(rows), 2)
    fail_if([row.get("pmid") for row in rows] != ["39743673", "42235695"], failures, "pmid_order", [row.get("pmid") for row in rows], ["39743673", "42235695"])
    for index, row in enumerate(rows, 1):
        fail_if(row.get("stage") != 25, failures, f"rows[{index}].stage", row.get("stage"), 25)
        check_closed_flags(row, f"rows[{index}]", failures)

    by_pmid = {str(row.get("pmid")): row for row in rows}
    acs = by_pmid.get("39743673", {})
    acs_present = ACS_SOURCE.is_file()
    acs_sha = sha256_file(ACS_SOURCE) if acs_present else None
    acs_expected = {
        "source_id": "stage25_source_39743673_si",
        "source_local_path": str(ACS_SOURCE.relative_to(AI_ROOT)),
        "source_sha256": ACS_SHA256,
        "preview_content_type": "public.html", "document_page_count": 11,
        "document_text_extraction_succeeded": True, "table_s1_primer_rows": 38,
        "table_s2_disulfide_bridge_rows": 4,
        "dsm4_text_mentions": ["Figure S5 lane 3", "Figure S8 mutant DSM4"],
        "observed_assay_condition_candidates": ["40-50 C for 1 h", "60 C after 55 C for 30 min", "optimal pH and pH stability"],
        "image_ocr_numeric_rows": 0, "dsm4_composition_resolved": False,
        "complete_dsm4_residue_rows": 0, "wt_absolute_baseline_rows": 0,
        "measurement_locator_rows": 0,
    }
    fail_if(not acs_present, failures, "acs.source_present", acs_present, True)
    fail_if(acs_sha != ACS_SHA256, failures, "acs.source_sha256", acs_sha, ACS_SHA256)
    for field, expected in acs_expected.items():
        fail_if(acs.get(field) != expected, failures, f"acs.{field}", acs.get(field), expected)

    cm5 = by_pmid.get("42235695", {})
    cm5_expected = {
        "source_id": "stage25_source_42235695_author_data",
        "source_local_path": str(ZENODO_SOURCE.relative_to(AI_ROOT)),
        "source_sha256": ZENODO_SHA256,
        "cm5_sequence_member_suffix": CM5_SEQUENCE_SUFFIX,
        "cm5_sequence_member_sha256": "6244f5f36d7b1b5d5c2bef40dc3264db8b7a8ab895b973612ef715db86f8463e",
        "cm5_pdb_member_suffix": CM5_PDB_SUFFIX,
        "cm5_pdb_member_sha256": "dde95bc2af984693d2708a9db099e1bab8559f9cd7230dc2bf53ad0c62d5b8cd",
        "wt_pdb_member_suffix": WT_PDB_SUFFIX,
        "wt_pdb_member_sha256": "051b548b4dc547e51b486ea933ec58f7814cca13f5392b340b457c037ee70ce6",
        "cm5_candidate_substitutions": CM5_SUBSTITUTIONS,
        "cm5_pdb_residues": CM5_RESIDUES,
        "wt_pdb_residues": WT_RESIDUES,
        "composition_candidate_corroboration_methods": ["sequencing_member_filename", "CM5_PDB_residue_identity", "WT_PDB_residue_identity"],
        "declared_substitutions_corroborated": True,
        "nucleotide_alignment": NUCLEOTIDE_ALIGNMENT,
        "undeclared_substitution_candidates": ["L262V"],
        "pdb_residue_262": {"cm5": "LEU", "wt": "LEU"},
        "nucleotide_pdb_discrepancy": True,
        "complete_composition_unambiguous": False,
        "cm5_composition_candidate_resolved": False,
        "cm5_composition_formally_reviewed": False,
        "complete_cm5_candidate_residue_rows": 4,
        "mutation_effect_measurement_rows": 0,
        "wt_absolute_baseline_rows": 0,
        "measurement_locator_rows": 0,
    }
    for field, expected in cm5_expected.items():
        fail_if(cm5.get(field) != expected, failures, f"cm5.{field}", cm5.get(field), expected)
    zenodo_present = ZENODO_SOURCE.is_file()
    zenodo_sha = sha256_file(ZENODO_SOURCE) if zenodo_present else None
    fail_if(not zenodo_present, failures, "cm5.source_present", zenodo_present, True)
    fail_if(zenodo_sha != ZENODO_SHA256, failures, "cm5.source_sha256", zenodo_sha, ZENODO_SHA256)
    sequence_verified = False
    pdb_residue_parity = False
    nucleotide_discrepancy_verified = False
    cross_read_matrix_verified = False
    if zenodo_present:
        with ZipFile(ZENODO_SOURCE) as archive:
            try:
                _, sequence = archive_member(archive, CM5_SEQUENCE_SUFFIX)
                _, wt_snapgene = archive_member(archive, WT_SNAPGENE_SUFFIX)
                _, cm5_pdb = archive_member(archive, CM5_PDB_SUFFIX)
                _, wt_pdb = archive_member(archive, WT_PDB_SUFFIX)
            except ValueError as error:
                failures.append({"check": "cm5.archive_members", "observed": str(error), "expected": "one exact member per suffix"})
            else:
                sequence_sha = hashlib.sha256(sequence).hexdigest()
                wt_snapgene_sha = hashlib.sha256(wt_snapgene).hexdigest()
                cm5_pdb_sha = hashlib.sha256(cm5_pdb).hexdigest()
                wt_pdb_sha = hashlib.sha256(wt_pdb).hexdigest()
                observed_cm5_all = pdb_residues(cm5_pdb, {15, 45, 85, 231, 262})
                observed_wt_all = pdb_residues(wt_pdb, {15, 45, 85, 231, 262})
                observed_cm5 = {key: observed_cm5_all.get(key) for key in CM5_RESIDUES}
                observed_wt = {key: observed_wt_all.get(key) for key in WT_RESIDUES}
                cm5_read_codon_262 = sequence.decode("ascii")[843:846]
                fail_if(sequence_sha != cm5_expected["cm5_sequence_member_sha256"], failures, "cm5.sequence_sha256", sequence_sha, cm5_expected["cm5_sequence_member_sha256"])
                fail_if(wt_snapgene_sha != WT_SNAPGENE_SHA256, failures, "cm5.wt_snapgene_sha256", wt_snapgene_sha, WT_SNAPGENE_SHA256)
                fail_if(cm5_pdb_sha != cm5_expected["cm5_pdb_member_sha256"], failures, "cm5.pdb_sha256", cm5_pdb_sha, cm5_expected["cm5_pdb_member_sha256"])
                fail_if(wt_pdb_sha != cm5_expected["wt_pdb_member_sha256"], failures, "cm5.wt_pdb_sha256", wt_pdb_sha, cm5_expected["wt_pdb_member_sha256"])
                fail_if(observed_cm5 != CM5_RESIDUES, failures, "cm5.pdb_residues", observed_cm5, CM5_RESIDUES)
                fail_if(observed_wt != WT_RESIDUES, failures, "cm5.wt_pdb_residues", observed_wt, WT_RESIDUES)
                fail_if(observed_cm5_all.get("262") != "LEU", failures, "cm5.pdb_residue_262", observed_cm5_all.get("262"), "LEU")
                fail_if(observed_wt_all.get("262") != "LEU", failures, "cm5.wt_pdb_residue_262", observed_wt_all.get("262"), "LEU")
                fail_if(cm5_read_codon_262 != "GTG", failures, "cm5.read_codon_262", cm5_read_codon_262, "GTG")
                actual_seq_suffixes = sorted(
                    item.filename.split("/Sequencing data/", 1)[-1]
                    for item in archive.infolist()
                    if not item.is_dir() and "/Sequencing data/" in item.filename and item.filename.endswith(".seq")
                )
                expected_seq_suffixes = sorted(row["member_suffix"].split("Sequencing data/", 1)[-1] for row in CODON262_CROSS_READ_ROWS)
                fail_if(actual_seq_suffixes != expected_seq_suffixes, failures, "cm5.codon262_sequence_member_set", actual_seq_suffixes, expected_seq_suffixes)
                matrix_checks = []
                for row in CODON262_CROSS_READ_ROWS:
                    _, read_payload = archive_member(archive, row["member_suffix"])
                    if row["covers_codon_262"]:
                        start, end = row["query_interval_1based"]
                        observed_codon = read_payload.decode("ascii")[start - 1:end]
                        fail_if(observed_codon != row["codon"], failures, f"cm5.codon262:{row['member_suffix']}", observed_codon, row["codon"])
                        matrix_checks.append(observed_codon == row["codon"])
                    else:
                        matrix_checks.append(True)
                sequence_verified = sequence_sha == cm5_expected["cm5_sequence_member_sha256"]
                pdb_residue_parity = observed_cm5 == CM5_RESIDUES and observed_wt == WT_RESIDUES
                nucleotide_discrepancy_verified = cm5_read_codon_262 == "GTG" and observed_cm5_all.get("262") == "LEU" and observed_wt_all.get("262") == "LEU"
                cross_read_matrix_verified = actual_seq_suffixes == expected_seq_suffixes and all(matrix_checks)

    for term in ("Read-only extraction candidate", "not reviewed extraction", "DSM4 residue composition", "SQLite apply", "release"):
        fail_if(term not in str(acs.get("policy") or ""), failures, f"acs.policy_contains:{term}", acs.get("policy"), f"contains {term}")
    for term in ("Read-only author-data extraction candidate", "complete composition is ambiguous", "not formally reviewed extraction", "SQLite apply", "release"):
        fail_if(term not in str(cm5.get("policy") or ""), failures, f"cm5.policy_contains:{term}", cm5.get("policy"), f"contains {term}")

    report = {
        "schema_version": 2,
        "mode": "stage25_source_extraction_candidate_validation",
        "stage": 25,
        "validation_success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "candidate_rows": len(rows),
        "source_sha256_verified": acs_sha == ACS_SHA256 and zenodo_sha == ZENODO_SHA256,
        "document_text_extraction_succeeded": acs.get("document_text_extraction_succeeded") is True,
        "table_s1_primer_rows": acs.get("table_s1_primer_rows"),
        "table_s2_disulfide_bridge_rows": acs.get("table_s2_disulfide_bridge_rows"),
        "dsm4_text_mentions": acs.get("dsm4_text_mentions"),
        "observed_assay_condition_candidates": acs.get("observed_assay_condition_candidates"),
        "image_ocr_numeric_rows": acs.get("image_ocr_numeric_rows"),
        "dsm4_composition_resolved": False,
        "complete_dsm4_residue_rows": 0,
        "cm5_sequence_member_verified": sequence_verified,
        "cm5_pdb_wt_residue_parity_verified": pdb_residue_parity,
        "cm5_candidate_substitutions": CM5_SUBSTITUTIONS,
        "declared_substitutions_corroborated": sequence_verified and pdb_residue_parity,
        "undeclared_substitution_candidates": ["L262V"],
        "nucleotide_pdb_discrepancy_verified": nucleotide_discrepancy_verified,
        "codon262_cross_read_matrix_verified": cross_read_matrix_verified,
        "codon262_sequence_member_rows": 11,
        "codon262_coverage_rows": 9,
        "codon262_no_coverage_rows": 2,
        "codon262_wt_codon_rows": 8,
        "codon262_variant_codon_rows": 1,
        "complete_composition_unambiguous": False,
        "cm5_composition_candidate_resolved": False,
        "cm5_composition_formally_reviewed": False,
        "complete_cm5_candidate_residue_rows": 4,
        "mutation_effect_measurement_rows": 0,
        "wt_absolute_baseline_rows": 0,
        "measurement_locator_rows": 0,
        "reviewed_source_locator_rows": 0,
        "reviewed_extraction_completed": False,
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Read-only extraction candidate validation only; CM5 composition candidates are not reviewed extraction, measurement evidence, SQLite apply, formal decisions, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "validation_success": report["validation_success"], "failure_count": report["failure_count"], "candidate_rows": report["candidate_rows"], "cm5_composition_candidate_resolved": report["cm5_composition_candidate_resolved"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["validation_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
