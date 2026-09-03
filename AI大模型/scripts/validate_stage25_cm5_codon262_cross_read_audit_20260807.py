#!/usr/bin/env python3
"""Validate the Stage 25 CM5 codon-262 cross-read audit fail closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
AUDIT = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_validation_20260807.json"
SOURCE_SHA256 = "800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6"
WT_SHA256 = "ca76a27e9a349249ad169286ee9c271822037406b8d2cbde3db4fd14efb081b4"
EXPECTED_CODONS = {
    "CM5 (L15R_S45T_K85P_K231R).seq": "GTG",
    "E70Q_T201D.seq": "TTG",
    "K85P_K170Y.seq": None,
    "K85P_K231R.seq": "TTG",
    "K85P_K431T_F.seq": None,
    "K85P_K431T_R.seq": "TTG",
    "L15R_S45T.seq": "TTG",
    "L15R_S45T_K85P_K231Q_K280S.seq": "TTG",
    "L15R_S45T_K85P_K231R_K280S.seq": "TTG",
    "L15R_S45T_K85P_K231V.seq": "TTG",
    "S45T_N113K_D167K.seq": "TTG",
}
NEGATIVE_FLAGS = (
    "discrepancy_resolved",
    "complete_composition_unambiguous",
    "reviewed_extraction_completed",
    "reviewer_decision_written",
    "ready_for_sqlite_apply",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def sha256_file(path: Path) -> str:
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
    fail_if(not SOURCE.is_file(), failures, "source_exists", str(SOURCE), "present file")
    fail_if(not AUDIT.is_file(), failures, "audit_exists", str(AUDIT), "present file")
    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else {}
    rows = audit.get("reads") if isinstance(audit.get("reads"), list) else []
    source_sha = sha256_file(SOURCE) if SOURCE.is_file() else None
    fail_if(source_sha != SOURCE_SHA256, failures, "source_zip_sha256_live", source_sha, SOURCE_SHA256)
    fail_if(audit.get("source_zip_sha256") != SOURCE_SHA256, failures, "audit_source_zip_sha256", audit.get("source_zip_sha256"), SOURCE_SHA256)
    fail_if(audit.get("mode") != "stage25_cm5_codon262_cross_read_audit", failures, "mode", audit.get("mode"), "stage25_cm5_codon262_cross_read_audit")
    fail_if(audit.get("stage") != 25, failures, "stage", audit.get("stage"), 25)
    fail_if(audit.get("wt_snapgene_sha256") != WT_SHA256, failures, "wt_snapgene_sha256", audit.get("wt_snapgene_sha256"), WT_SHA256)
    fail_if(audit.get("wt_plasmid_length_nt") != 2059, failures, "wt_plasmid_length_nt", audit.get("wt_plasmid_length_nt"), 2059)
    fail_if(audit.get("wt_crl1_interval_zero_based") != [363, 1968], failures, "wt_crl1_interval", audit.get("wt_crl1_interval_zero_based"), [363, 1968])
    fail_if(audit.get("wt_crl1_length_nt") != 1605, failures, "wt_crl1_length_nt", audit.get("wt_crl1_length_nt"), 1605)
    fail_if(audit.get("wt_codon_262_span_zero_based") != [783, 786], failures, "wt_codon_262_span", audit.get("wt_codon_262_span_zero_based"), [783, 786])
    fail_if(audit.get("wt_codon_262") != "TTG", failures, "wt_codon_262", audit.get("wt_codon_262"), "TTG")
    for field, expected in (("read_rows", 11), ("covered_rows", 9), ("not_covered_rows", 2), ("ttg_rows", 8), ("gtg_rows", 1), ("other_codon_rows", 0), ("cm5_gtg_rows", 1), ("non_cm5_ttg_rows", 8)):
        fail_if(audit.get(field) != expected, failures, field, audit.get(field), expected)
    for field in ("all_best_orientations_forward", "cross_read_consensus_supports_wt_leu262", "cm5_single_read_outlier"):
        fail_if(audit.get(field) is not True, failures, field, audit.get(field), True)
    fail_if(len(rows) != 11, failures, "reads_len", len(rows), 11)
    basenames = [str(row.get("basename")) for row in rows if isinstance(row, dict)]
    fail_if(basenames != sorted(EXPECTED_CODONS), failures, "read_basenames_exact", basenames, sorted(EXPECTED_CODONS))
    fail_if(len(set(basenames)) != 11, failures, "unique_read_basenames", len(set(basenames)), 11)

    live_members: dict[str, dict[str, Any]] = {}
    if SOURCE.is_file():
        with ZipFile(SOURCE) as archive:
            for item in archive.infolist():
                if item.is_dir() or "Sequencing data/" not in item.filename or not item.filename.endswith(".seq"):
                    continue
                payload = archive.read(item)
                live_members[Path(item.filename).name] = {
                    "member": item.filename,
                    "size_bytes": item.file_size,
                    "crc32": f"{item.CRC:08x}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
    fail_if(sorted(live_members) != sorted(EXPECTED_CODONS), failures, "live_members_exact", sorted(live_members), sorted(EXPECTED_CODONS))
    for index, row in enumerate(rows, 1):
        prefix = f"reads[{index}]"
        basename = str(row.get("basename"))
        expected_codon = EXPECTED_CODONS.get(basename)
        live = live_members.get(basename, {})
        for field in ("member", "size_bytes", "crc32", "sha256"):
            fail_if(row.get(field) != live.get(field), failures, f"{prefix}.{field}_live", row.get(field), live.get(field))
        fail_if(row.get("orientation") != "forward", failures, f"{prefix}.orientation", row.get("orientation"), "forward")
        fail_if(row.get("codon_262") != expected_codon, failures, f"{prefix}.codon_262", row.get("codon_262"), expected_codon)
        fail_if(row.get("covers_wt_codon_262") is not (expected_codon is not None), failures, f"{prefix}.covers_wt_codon_262", row.get("covers_wt_codon_262"), expected_codon is not None)
        expected_aa = "L" if expected_codon == "TTG" else "V" if expected_codon == "GTG" else None
        fail_if(row.get("amino_acid_262") != expected_aa, failures, f"{prefix}.amino_acid_262", row.get("amino_acid_262"), expected_aa)
        fail_if(row.get("is_cm5_read") is not (basename == "CM5 (L15R_S45T_K85P_K231R).seq"), failures, f"{prefix}.is_cm5_read", row.get("is_cm5_read"), basename == "CM5 (L15R_S45T_K85P_K231R).seq")
    for flag in NEGATIVE_FLAGS:
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    fail_if(audit.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", audit.get("formal_decision_rows_written"), 0)
    policy = str(audit.get("policy") or "")
    for term in ("Eight TTG reads", "one CM5 GTG read", "do not resolve", "SQLite apply", "release"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_codon262_cross_read_audit_validation",
        "stage": 25,
        "audit_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "read_rows": len(rows),
        "covered_rows": audit.get("covered_rows"),
        "not_covered_rows": audit.get("not_covered_rows"),
        "ttg_rows": audit.get("ttg_rows"),
        "gtg_rows": audit.get("gtg_rows"),
        "cm5_gtg_rows": audit.get("cm5_gtg_rows"),
        "non_cm5_ttg_rows": audit.get("non_cm5_ttg_rows"),
        "cross_read_consensus_supports_wt_leu262": audit.get("cross_read_consensus_supports_wt_leu262") is True,
        "cm5_single_read_outlier": audit.get("cm5_single_read_outlier") is True,
        "discrepancy_resolved": False,
        "complete_composition_unambiguous": False,
        "reviewed_extraction_completed": False,
        "reviewer_decision_written": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "audit_valid": report["audit_valid"], "failure_count": report["failure_count"], "read_rows": report["read_rows"], "ttg_rows": report["ttg_rows"], "gtg_rows": report["gtg_rows"], "discrepancy_resolved": report["discrepancy_resolved"]}, sort_keys=True))
    return 0 if report["audit_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
