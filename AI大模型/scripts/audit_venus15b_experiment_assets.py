#!/usr/bin/env python3
"""Audit Venus-15B experiment assets without promoting unsupported labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


AI_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = AI_ROOT / "Venus-15B淀粉酶项目"
REPORT_OUT = AI_ROOT / "reports" / "venus15b_experiment_asset_audit_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "feedback" / "venus15b_experiment_evidence_audit.jsonl"

SEQUENCE_FILE = "淀粉酶15B序列.txt"
BACKGROUND_FILE = "淀粉酶背景.txt"
STRUCTURE_FILE = "15B-AAP-noCa.pdb"
CANDIDATE_MUTATIONS = ["S265D", "D405N", "E331Q", "M204H"]

TABULAR_SUFFIXES = {".csv", ".tsv", ".xls", ".xlsx"}
DOC_SUFFIXES = {".txt", ".docx", ".md"}
PDF_SUFFIXES = {".pdf"}
MUTATION_RE = re.compile(r"\b[A-Z][0-9]{1,5}[A-Z]\b")
NUMERIC_ASSAY_RE = re.compile(
    r"(?:活性|酶活|activity|比值|ratio|OD|A540|DNS|U/mL|U/g|IU|吸光度).{0,24}"
    r"[-+]?(?:\d+\.\d+|\d+)(?:\s*%|\s*倍|\s*U/mL|\s*U/g|\s*IU)?",
    re.IGNORECASE,
)
PLATE_TERMS = ["plate", "well", "孔板", "孔位", "酶标仪", "raw_signal", "normalized_activity", "OD", "A540"]
QC_TERMS = ["replicate", "重复", "QC", "质控", "标准差", "SD", "CV", "instrument", "仪器"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile, OSError):
        return ""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return ""
    texts = []
    for elem in root.iter():
        if elem.tag.endswith("}t") and elem.text:
            texts.append(elem.text)
    return "\n".join(texts)


def readable_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        return docx_text(path)
    return ""


def verify_mutation(sequence: str, mutation: str) -> dict[str, Any]:
    wt = mutation[0]
    mutant = mutation[-1]
    position = int(mutation[1:-1])
    observed = sequence[position - 1] if 1 <= position <= len(sequence) else None
    return {
        "mutation": mutation,
        "wild_type": wt,
        "mutant": mutant,
        "canonical_position": position,
        "observed_sequence_residue": observed,
        "numbering_verified": observed == wt,
    }


def file_record(project_dir: Path, path: Path) -> dict[str, Any]:
    rel = str(path.relative_to(project_dir))
    suffix = path.suffix.lower()
    text = readable_text(path) if suffix in DOC_SUFFIXES else ""
    mutation_hits = sorted(set(MUTATION_RE.findall(text)))
    candidate_hits = [mutation for mutation in CANDIDATE_MUTATIONS if mutation in text]
    numeric_hints = NUMERIC_ASSAY_RE.findall(text)
    lower_text = text.lower()
    return {
        "relative_path": rel,
        "suffix": suffix or None,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "text_scanned": bool(text),
        "character_count": len(text),
        "candidate_mutation_hits": candidate_hits,
        "mutation_token_hits": mutation_hits[:50],
        "numeric_assay_hint_count": len(numeric_hints),
        "numeric_assay_hints": numeric_hints[:20],
        "plate_term_hits": [term for term in PLATE_TERMS if term.lower() in lower_text],
        "qc_term_hits": [term for term in QC_TERMS if term.lower() in lower_text],
        "is_tabular_assay_candidate": suffix in TABULAR_SUFFIXES,
        "is_pdf": suffix in PDF_SUFFIXES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Venus-15B local experiment assets")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    sequence_path = args.project_dir / SEQUENCE_FILE
    background_path = args.project_dir / BACKGROUND_FILE
    structure_path = args.project_dir / STRUCTURE_FILE
    sequence = sequence_path.read_text(encoding="utf-8").strip()
    background = background_path.read_text(encoding="utf-8", errors="replace")

    files = [path for path in sorted(args.project_dir.rglob("*")) if path.is_file()]
    file_rows = [file_record(args.project_dir, path) for path in files]
    mutation_rows = []
    for mutation in CANDIDATE_MUTATIONS:
        verified = verify_mutation(sequence, mutation)
        evidence_phrase_present = (
            mutation == "E331Q"
            and all(token in background for token in ["E331Q", "pH4.5", "pH6.0", "活性比值"])
        )
        mutation_rows.append({
            **verified,
            "project_id": "venus-15b",
            "source_granularity": "qualitative_historical_observation" if evidence_phrase_present else "design_candidate_only",
            "feedback_intake_allowed": bool(verified["numbering_verified"] and evidence_phrase_present),
            "numeric_training_eligible": False,
            "plate_training_eligible": False,
            "evidence_files": [str(background_path.relative_to(args.project_dir))] if evidence_phrase_present else [],
            "blockers": [] if evidence_phrase_present else ["no_current_source_text_reports_measured_outcome"],
            "policy": "Mutation evidence audit only; unsupported candidates are not feedback labels.",
        })

    tabular_files = [row for row in file_rows if row["is_tabular_assay_candidate"]]
    plate_hint_files = [row for row in file_rows if row["plate_term_hits"]]
    numeric_hint_files = [row for row in file_rows if row["numeric_assay_hint_count"] > 0]
    report = {
        "project_dir": str(args.project_dir),
        "local_only": True,
        "source_files_scanned": len(file_rows),
        "sequence_length": len(sequence),
        "sequence_sha256": sha256(sequence_path),
        "background_sha256": sha256(background_path),
        "structure_sha256": sha256(structure_path),
        "candidate_mutation_rows": len(mutation_rows),
        "numbering_verified_mutation_rows": sum(1 for row in mutation_rows if row["numbering_verified"]),
        "qualitative_feedback_rows": sum(1 for row in mutation_rows if row["feedback_intake_allowed"]),
        "numeric_training_eligible_rows": sum(1 for row in mutation_rows if row["numeric_training_eligible"]),
        "plate_training_eligible_rows": sum(1 for row in mutation_rows if row["plate_training_eligible"]),
        "tabular_assay_file_count": len(tabular_files),
        "plate_hint_file_count": len(plate_hint_files),
        "numeric_assay_hint_file_count": len(numeric_hint_files),
        "tabular_assay_files": tabular_files,
        "plate_hint_files": plate_hint_files[:20],
        "numeric_assay_hint_files": numeric_hint_files[:20],
        "mutation_evidence_rows": mutation_rows,
        "missing_for_numeric_training": [
            "numeric pH4.5/pH6.0 activity ratio or normalized activity",
            "WT comparator value",
            "replicate count or replicate-level values",
            "unit and assay protocol version",
            "reviewed QC status",
        ],
        "missing_for_plate_training": [
            "plate_id",
            "well_id",
            "variant_id",
            "replicate",
            "raw_signal",
            "normalized_activity",
            "qc_flag",
            "instrument",
            "operator",
            "recorded_at",
        ],
        "safe_for_model_claim": False,
        "policy": "The user-designated source is treated as real experiment evidence, but only observed fields are eligible for downstream training gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(args.jsonl, mutation_rows)
    print(json.dumps({
        "source_files_scanned": report["source_files_scanned"],
        "qualitative_feedback_rows": report["qualitative_feedback_rows"],
        "numeric_training_eligible_rows": report["numeric_training_eligible_rows"],
        "plate_training_eligible_rows": report["plate_training_eligible_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
