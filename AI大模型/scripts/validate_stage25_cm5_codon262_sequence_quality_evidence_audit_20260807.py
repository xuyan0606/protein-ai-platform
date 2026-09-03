#!/usr/bin/env python3
"""Validate the Stage 25 CM5 codon-262 quality-evidence audit fail closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
AUDIT = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.json"
CROSS_READ = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json"
SOURCE_SHA256 = "800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6"
SEQUENCING_MARKER = "/Sequencing data/"
CM5_BASENAME = "CM5 (L15R_S45T_K85P_K231R).seq"
EXPECTED_SEQ_BASENAMES = [
    "CM5 (L15R_S45T_K85P_K231R).seq",
    "E70Q_T201D.seq",
    "K85P_K170Y.seq",
    "K85P_K231R.seq",
    "K85P_K431T_F.seq",
    "K85P_K431T_R.seq",
    "L15R_S45T.seq",
    "L15R_S45T_K85P_K231Q_K280S.seq",
    "L15R_S45T_K85P_K231R_K280S.seq",
    "L15R_S45T_K85P_K231V.seq",
    "S45T_N113K_D167K.seq",
]
QUALITY_EXTENSIONS = {".ab1", ".abi", ".fastq", ".fq", ".scf"}
NEGATIVE_FLAGS = (
    "cm5_quality_evidence_available",
    "sequencing_artifact_hypothesis_confirmed",
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
    fail_if(not CROSS_READ.is_file(), failures, "cross_read_validation_exists", str(CROSS_READ), "present file")
    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else {}
    cross_read = json.loads(CROSS_READ.read_text(encoding="utf-8")) if CROSS_READ.is_file() else {}
    rows = audit.get("reads") if isinstance(audit.get("reads"), list) else []

    source_sha = sha256_file(SOURCE) if SOURCE.is_file() else None
    fail_if(source_sha != SOURCE_SHA256, failures, "source_zip_sha256_live", source_sha, SOURCE_SHA256)
    fail_if(audit.get("source_zip_sha256") != SOURCE_SHA256, failures, "audit_source_zip_sha256", audit.get("source_zip_sha256"), SOURCE_SHA256)
    fail_if(audit.get("mode") != "stage25_cm5_codon262_sequence_quality_evidence_audit", failures, "mode", audit.get("mode"), "stage25_cm5_codon262_sequence_quality_evidence_audit")
    fail_if(audit.get("stage") != 25, failures, "stage", audit.get("stage"), 25)
    fail_if(cross_read.get("audit_valid") is not True, failures, "cross_read_audit_valid", cross_read.get("audit_valid"), True)
    fail_if(audit.get("cross_read_audit_valid") is not True, failures, "audit_cross_read_valid", audit.get("cross_read_audit_valid"), True)

    live_rows: dict[str, dict[str, Any]] = {}
    sequencing_file_rows = 0
    snapgene_dna_rows = 0
    quality_artifact_rows = 0
    if SOURCE.is_file():
        with ZipFile(SOURCE) as archive:
            for item in archive.infolist():
                if item.is_dir() or SEQUENCING_MARKER not in item.filename:
                    continue
                sequencing_file_rows += 1
                suffix = Path(item.filename).suffix.lower()
                snapgene_dna_rows += suffix == ".dna"
                quality_artifact_rows += suffix in QUALITY_EXTENSIONS
                if suffix != ".seq":
                    continue
                payload = archive.read(item)
                decoded = payload.decode("ascii")
                compact = "".join(decoded.split()).upper()
                live_rows[Path(item.filename).name] = {
                    "member": item.filename,
                    "size_bytes": item.file_size,
                    "crc32": f"{item.CRC:08x}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "sequence_length_nt": len(compact),
                    "sequence_symbols": sorted(set(compact)),
                    "cm5_raw_call": compact[843:846] if Path(item.filename).name == CM5_BASENAME else None,
                }

    for field, expected in (
        ("sequencing_file_rows", 12),
        ("seq_read_rows", 11),
        ("snapgene_dna_rows", 1),
        ("quality_bearing_artifact_rows", 0),
        ("chromatogram_artifact_rows", 0),
        ("per_base_quality_artifact_rows", 0),
        ("sequence_text_only_rows", 11),
        ("embedded_quality_score_rows", 0),
    ):
        fail_if(audit.get(field) != expected, failures, field, audit.get(field), expected)
    fail_if(sequencing_file_rows != 12, failures, "live_sequencing_file_rows", sequencing_file_rows, 12)
    fail_if(snapgene_dna_rows != 1, failures, "live_snapgene_dna_rows", snapgene_dna_rows, 1)
    fail_if(quality_artifact_rows != 0, failures, "live_quality_artifact_rows", quality_artifact_rows, 0)
    fail_if(len(rows) != 11, failures, "reads_len", len(rows), 11)
    basenames = [str(row.get("basename")) for row in rows if isinstance(row, dict)]
    fail_if(basenames != EXPECTED_SEQ_BASENAMES, failures, "read_basenames_exact", basenames, EXPECTED_SEQ_BASENAMES)
    fail_if(sorted(live_rows) != EXPECTED_SEQ_BASENAMES, failures, "live_read_basenames_exact", sorted(live_rows), EXPECTED_SEQ_BASENAMES)
    for index, row in enumerate(rows, 1):
        prefix = f"reads[{index}]"
        basename = str(row.get("basename"))
        live = live_rows.get(basename, {})
        for field in ("member", "size_bytes", "crc32", "sha256", "sequence_length_nt", "sequence_symbols"):
            fail_if(row.get(field) != live.get(field), failures, f"{prefix}.{field}_live", row.get(field), live.get(field))
        fail_if(row.get("ascii_decodable") is not True, failures, f"{prefix}.ascii_decodable", row.get("ascii_decodable"), True)
        fail_if(row.get("unexpected_symbols") != [], failures, f"{prefix}.unexpected_symbols", row.get("unexpected_symbols"), [])
        fail_if(row.get("iupac_sequence_text_only") is not True, failures, f"{prefix}.iupac_sequence_text_only", row.get("iupac_sequence_text_only"), True)
        fail_if(row.get("embedded_quality_scores_present") is not False, failures, f"{prefix}.embedded_quality_scores_present", row.get("embedded_quality_scores_present"), False)
        fail_if(row.get("is_cm5_read") is not (basename == CM5_BASENAME), failures, f"{prefix}.is_cm5_read", row.get("is_cm5_read"), basename == CM5_BASENAME)

    fail_if(audit.get("cm5_member_sha256_matches_cross_read") is not True, failures, "cm5_member_sha_matches_cross_read", audit.get("cm5_member_sha256_matches_cross_read"), True)
    fail_if(audit.get("cm5_codon_262_query_span_zero_based") != [843, 846], failures, "cm5_query_span", audit.get("cm5_codon_262_query_span_zero_based"), [843, 846])
    fail_if(audit.get("cm5_codon_262_raw_text_call") != "GTG", failures, "cm5_raw_text_call", audit.get("cm5_codon_262_raw_text_call"), "GTG")
    fail_if(audit.get("cm5_cross_read_codon_262") != "GTG", failures, "cm5_cross_read_call", audit.get("cm5_cross_read_codon_262"), "GTG")
    fail_if(live_rows.get(CM5_BASENAME, {}).get("cm5_raw_call") != "GTG", failures, "live_cm5_raw_call", live_rows.get(CM5_BASENAME, {}).get("cm5_raw_call"), "GTG")
    fail_if(len(audit.get("required_closure_evidence") or []) != 3, failures, "required_closure_evidence_rows", len(audit.get("required_closure_evidence") or []), 3)
    for flag in NEGATIVE_FLAGS:
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    fail_if(audit.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", audit.get("formal_decision_rows_written"), 0)
    policy = str(audit.get("policy") or "")
    for term in ("no chromatogram", "cannot confirm a sequencing artifact", "resolve CM5 composition", "SQLite apply", "release"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_codon262_sequence_quality_evidence_audit_validation",
        "stage": 25,
        "audit_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "sequencing_file_rows": audit.get("sequencing_file_rows"),
        "seq_read_rows": len(rows),
        "snapgene_dna_rows": audit.get("snapgene_dna_rows"),
        "sequence_text_only_rows": audit.get("sequence_text_only_rows"),
        "quality_bearing_artifact_rows": audit.get("quality_bearing_artifact_rows"),
        "chromatogram_artifact_rows": audit.get("chromatogram_artifact_rows"),
        "per_base_quality_artifact_rows": audit.get("per_base_quality_artifact_rows"),
        "cm5_codon_262_raw_text_call": audit.get("cm5_codon_262_raw_text_call"),
        "cm5_quality_evidence_available": False,
        "sequencing_artifact_hypothesis_confirmed": False,
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
    print(json.dumps({
        "output": str(OUTPUT),
        "audit_valid": report["audit_valid"],
        "failure_count": report["failure_count"],
        "seq_read_rows": report["seq_read_rows"],
        "quality_bearing_artifact_rows": report["quality_bearing_artifact_rows"],
        "discrepancy_resolved": report["discrepancy_resolved"],
    }, sort_keys=True))
    return 0 if report["audit_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
