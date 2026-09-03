#!/usr/bin/env python3
"""Build a read-only audit of quality-bearing evidence for the CM5 codon-262 call."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
CROSS_READ_AUDIT = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_20260807.json"
CROSS_READ_VALIDATION = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.json"
SEQUENCING_MARKER = "/Sequencing data/"
CM5_BASENAME = "CM5 (L15R_S45T_K85P_K231R).seq"
QUALITY_EXTENSIONS = {".ab1", ".abi", ".fastq", ".fq", ".scf"}
CHROMATOGRAM_EXTENSIONS = {".ab1", ".abi", ".scf"}
IUPAC_DNA_SYMBOLS = set("ACGTURYSWKMBDHVN")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    cross_read = json.loads(CROSS_READ_AUDIT.read_text(encoding="utf-8"))
    cross_read_validation = json.loads(CROSS_READ_VALIDATION.read_text(encoding="utf-8"))
    if cross_read_validation.get("audit_valid") is not True:
        raise ValueError("cross-read audit must validate before quality-evidence audit")
    cm5_cross_rows = [row for row in cross_read.get("reads", []) if row.get("basename") == CM5_BASENAME]
    if len(cm5_cross_rows) != 1:
        raise ValueError(f"expected one CM5 cross-read row, found {len(cm5_cross_rows)}")
    cm5_cross = cm5_cross_rows[0]

    with ZipFile(SOURCE) as archive:
        sequencing_infos = sorted(
            (item for item in archive.infolist() if not item.is_dir() and SEQUENCING_MARKER in item.filename),
            key=lambda item: item.filename,
        )
        seq_infos = [item for item in sequencing_infos if Path(item.filename).suffix.lower() == ".seq"]
        quality_infos = [item for item in sequencing_infos if Path(item.filename).suffix.lower() in QUALITY_EXTENSIONS]
        chromatogram_infos = [item for item in sequencing_infos if Path(item.filename).suffix.lower() in CHROMATOGRAM_EXTENSIONS]
        rows = []
        for info in seq_infos:
            payload = archive.read(info)
            try:
                decoded = payload.decode("ascii")
                ascii_decodable = True
            except UnicodeDecodeError:
                decoded = ""
                ascii_decodable = False
            compact = "".join(decoded.split()).upper()
            symbols = sorted(set(compact))
            unexpected_symbols = sorted(set(compact) - IUPAC_DNA_SYMBOLS)
            rows.append({
                "member": info.filename,
                "basename": Path(info.filename).name,
                "size_bytes": info.file_size,
                "crc32": f"{info.CRC:08x}",
                "sha256": sha256_bytes(payload),
                "ascii_decodable": ascii_decodable,
                "sequence_length_nt": len(compact),
                "sequence_symbols": symbols,
                "unexpected_symbols": unexpected_symbols,
                "iupac_sequence_text_only": ascii_decodable and not unexpected_symbols and bool(compact),
                "embedded_quality_scores_present": False,
                "is_cm5_read": Path(info.filename).name == CM5_BASENAME,
            })

    cm5_rows = [row for row in rows if row["is_cm5_read"]]
    if len(cm5_rows) != 1:
        raise ValueError(f"expected one CM5 sequence row, found {len(cm5_rows)}")
    query_span = cm5_cross.get("query_codon_span_zero_based")
    if not isinstance(query_span, list) or len(query_span) != 2:
        raise ValueError("CM5 cross-read query span is missing")
    with ZipFile(SOURCE) as archive:
        cm5_payload = archive.read(str(cm5_cross["member"]))
    cm5_sequence = "".join(cm5_payload.decode("ascii").split()).upper()
    cm5_raw_call = cm5_sequence[int(query_span[0]):int(query_span[1])]

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_codon262_sequence_quality_evidence_audit",
        "stage": 25,
        "source_zip": str(SOURCE.relative_to(AI_ROOT)),
        "source_zip_sha256": sha256_file(SOURCE),
        "cross_read_audit": str(CROSS_READ_AUDIT.relative_to(AI_ROOT)),
        "cross_read_audit_valid": True,
        "sequencing_file_rows": len(sequencing_infos),
        "seq_read_rows": len(rows),
        "snapgene_dna_rows": sum(Path(item.filename).suffix.lower() == ".dna" for item in sequencing_infos),
        "quality_bearing_artifact_rows": len(quality_infos),
        "chromatogram_artifact_rows": len(chromatogram_infos),
        "per_base_quality_artifact_rows": len(quality_infos),
        "sequence_text_only_rows": sum(row["iupac_sequence_text_only"] for row in rows),
        "embedded_quality_score_rows": sum(row["embedded_quality_scores_present"] for row in rows),
        "quality_bearing_extensions_checked": sorted(QUALITY_EXTENSIONS),
        "reads": rows,
        "cm5_member": cm5_cross.get("member"),
        "cm5_member_sha256_matches_cross_read": cm5_rows[0]["sha256"] == cm5_cross.get("sha256"),
        "cm5_codon_262_query_span_zero_based": query_span,
        "cm5_codon_262_raw_text_call": cm5_raw_call,
        "cm5_cross_read_codon_262": cm5_cross.get("codon_262"),
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
        "required_closure_evidence": [
            "CM5 raw chromatogram or equivalent trace containing codon 262",
            "per-base quality scores for the CM5 codon-262 call",
            "independent CM5 clone resequencing or reviewed construct record",
        ],
        "policy": "Plain IUPAC sequence text records a base call but carries no chromatogram or per-base quality evidence. Absence of quality-bearing artifacts cannot confirm a sequencing artifact or resolve CM5 composition, reviewed extraction, SQLite apply, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "seq_read_rows": report["seq_read_rows"],
        "sequence_text_only_rows": report["sequence_text_only_rows"],
        "quality_bearing_artifact_rows": report["quality_bearing_artifact_rows"],
        "cm5_codon_262_raw_text_call": report["cm5_codon_262_raw_text_call"],
        "discrepancy_resolved": report["discrepancy_resolved"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
