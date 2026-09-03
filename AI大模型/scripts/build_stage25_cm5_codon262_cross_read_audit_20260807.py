#!/usr/bin/env python3
"""Build a read-only codon-262 audit across all CM5 author-data sequencing reads."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import Bio
from Bio import SeqIO
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"
OUTPUT = AI_ROOT / "reports/stage25_cm5_codon262_cross_read_audit_20260807.json"
WT_SUFFIX = "Sequencing data/Candida rugosa lipase_WT.dna"
CM5_BASENAME = "CM5 (L15R_S45T_K85P_K231R).seq"
WT_CODON_START = (262 - 1) * 3


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one_member(archive: ZipFile, suffix: str) -> tuple[str, bytes]:
    matches = [item.filename for item in archive.infolist() if not item.is_dir() and item.filename.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one member ending with {suffix!r}, found {len(matches)}")
    return matches[0], archive.read(matches[0])


def best_alignment(aligner: PairwiseAligner, target: str, raw_query: str) -> tuple[str, str, object]:
    candidates = [
        ("forward", raw_query),
        ("reverse_complement", str(Seq(raw_query).reverse_complement())),
    ]
    orientation, query = max(candidates, key=lambda item: aligner.score(target, item[1]))
    return orientation, query, aligner.align(target, query)[0]


def map_target_interval(alignment: object, start: int, end: int) -> list[int] | None:
    for target_segment, query_segment in zip(*alignment.aligned):
        if int(target_segment[0]) <= start and end <= int(target_segment[1]):
            query_start = int(query_segment[0]) + start - int(target_segment[0])
            return [query_start, query_start + end - start]
    return None


def main() -> int:
    with ZipFile(SOURCE) as archive:
        wt_member, wt_payload = one_member(archive, WT_SUFFIX)
        wt_record = SeqIO.read(BytesIO(wt_payload), "snapgene")
        crl1_features = [
            feature for feature in wt_record.features
            if str((feature.qualifiers.get("label") or [""])[0]) == "CRL1"
        ]
        if len(crl1_features) != 1:
            raise ValueError(f"expected one CRL1 feature, found {len(crl1_features)}")
        crl1 = crl1_features[0]
        crl1_start = int(crl1.location.start)
        crl1_end = int(crl1.location.end)
        wt_crl1 = str(wt_record.seq[crl1_start:crl1_end]).upper()

        aligner = PairwiseAligner()
        aligner.mode = "local"
        aligner.match_score = 2
        aligner.mismatch_score = -1
        aligner.open_gap_score = -5
        aligner.extend_gap_score = -1

        read_infos = sorted(
            (item for item in archive.infolist() if not item.is_dir() and "Sequencing data/" in item.filename and item.filename.endswith(".seq")),
            key=lambda item: Path(item.filename).name,
        )
        rows = []
        for info in read_infos:
            payload = archive.read(info)
            raw_query = payload.decode("ascii").strip().upper()
            orientation, query, alignment = best_alignment(aligner, wt_crl1, raw_query)
            query_codon_span = map_target_interval(alignment, WT_CODON_START, WT_CODON_START + 3)
            codon = query[query_codon_span[0]:query_codon_span[1]] if query_codon_span else None
            amino_acid = str(Seq(codon).translate()) if codon and len(codon) == 3 else None
            target_span = [int(alignment.aligned[0][0][0]), int(alignment.aligned[0][-1][1])]
            rows.append({
                "member": info.filename,
                "basename": Path(info.filename).name,
                "size_bytes": info.file_size,
                "crc32": f"{info.CRC:08x}",
                "sha256": sha256_bytes(payload),
                "orientation": orientation,
                "alignment_score": float(alignment.score),
                "target_span_zero_based": target_span,
                "query_codon_span_zero_based": query_codon_span,
                "covers_wt_codon_262": query_codon_span is not None,
                "codon_262": codon,
                "amino_acid_262": amino_acid,
                "is_cm5_read": Path(info.filename).name == CM5_BASENAME,
            })

    covered = [row for row in rows if row["covers_wt_codon_262"]]
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_codon262_cross_read_audit",
        "stage": 25,
        "source_zip": str(SOURCE.relative_to(AI_ROOT)),
        "source_zip_sha256": sha256_file(SOURCE),
        "biopython_version": Bio.__version__,
        "alignment_method": {
            "mode": "local",
            "orientation_selection": "higher forward/reverse-complement score",
            "match_score": 2.0,
            "mismatch_score": -1.0,
            "open_gap_score": -5.0,
            "extend_gap_score": -1.0,
        },
        "wt_snapgene_member": wt_member,
        "wt_snapgene_sha256": sha256_bytes(wt_payload),
        "wt_plasmid_length_nt": len(wt_record.seq),
        "wt_crl1_interval_zero_based": [crl1_start, crl1_end],
        "wt_crl1_length_nt": len(wt_crl1),
        "wt_codon_262_span_zero_based": [WT_CODON_START, WT_CODON_START + 3],
        "wt_codon_262": wt_crl1[WT_CODON_START:WT_CODON_START + 3],
        "read_rows": len(rows),
        "covered_rows": len(covered),
        "not_covered_rows": len(rows) - len(covered),
        "ttg_rows": sum(row["codon_262"] == "TTG" for row in rows),
        "gtg_rows": sum(row["codon_262"] == "GTG" for row in rows),
        "other_codon_rows": sum(row["covers_wt_codon_262"] and row["codon_262"] not in {"TTG", "GTG"} for row in rows),
        "cm5_gtg_rows": sum(row["is_cm5_read"] and row["codon_262"] == "GTG" for row in rows),
        "non_cm5_ttg_rows": sum(not row["is_cm5_read"] and row["codon_262"] == "TTG" for row in rows),
        "all_best_orientations_forward": all(row["orientation"] == "forward" for row in rows),
        "cross_read_consensus_supports_wt_leu262": sum(row["codon_262"] == "TTG" for row in rows) == 8,
        "cm5_single_read_outlier": sum(row["codon_262"] == "GTG" for row in rows) == 1,
        "reads": rows,
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
        "policy": "Read-only cross-read audit only. Eight TTG reads and one CM5 GTG read support an outlier hypothesis but do not resolve sequencing quality, construct composition, reviewed extraction, SQLite apply, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "read_rows": report["read_rows"], "covered_rows": report["covered_rows"], "ttg_rows": report["ttg_rows"], "gtg_rows": report["gtg_rows"], "discrepancy_resolved": report["discrepancy_resolved"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
