#!/usr/bin/env python3
"""Extract source-traced substrate identity candidates from local protocols.

This creates an evidence packet for human review. It does not infer SMILES,
mark rows reviewed, or create substrate_fit labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader
except ImportError:  # Keep the candidate builder runnable without optional PDF support.
    PdfReader = None


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT.parent / "Venus-15B淀粉酶项目" / "incoming/reference_docs/auto_selected"
OUT = AI_ROOT / "datasets/curation/substrate_identity_evidence_candidates.jsonl"
REPORT = AI_ROOT / "reports/substrate_identity_evidence_candidate_report.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    # Word tables often repeat each cell twice in the XML extraction. Collapse
    # only adjacent duplicate runs; preserve all actual source wording.
    text = re.sub(r"(.{2,80})\1", r"\1", text)
    return text


def docx_paragraphs(path: Path) -> list[tuple[int, str]]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    result = []
    for index, para in enumerate(root.findall(".//w:p", ns), start=1):
        text = clean_text("".join(node.text or "" for node in para.findall(".//w:t", ns)))
        if text:
            result.append((index, text))
    return result


def pdf_paragraphs(path: Path) -> list[tuple[int, str]]:
    if PdfReader is None:
        return []
    result = []
    reader = PdfReader(str(path))
    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        if text:
            result.append((page_number, text))
    return result


def extract_numbers(text: str) -> dict[str, list[str]]:
    return {
        "ph": sorted(set(re.findall(r"pH\s*[=为]?\s*[0-9]+(?:\.[0-9]+)?(?:\s*[-至]\s*[0-9]+(?:\.[0-9]+)?)?", text, flags=re.I))),
        "temperature": sorted(set(re.findall(r"(?:温度|喷射温度|后熟器维持温度)[^，。；;]{0,18}[0-9]+(?:\.[0-9]+)?(?:\s*[-至±]\s*[0-9]+(?:\.[0-9]+)?)?\s*[℃C]", text))),
        "time": sorted(set(re.findall(r"(?:时间|维持时间|糖化时间)[^，。；;]{0,18}[0-9]+(?:\s*[-至]\s*[0-9]+)?\s*(?:分钟|min|h|小时)", text, flags=re.I))),
    }


def substrate_candidates(path: Path, paragraphs: list[tuple[int, str]]) -> list[dict[str, Any]]:
    full = " ".join(text for _, text in paragraphs)
    candidates: list[tuple[str, str, str]] = []
    if "玉米全粉" in full:
        candidates.append(("corn_whole_flour", "玉米全粉", "source_text_explicit"))
    if "淀粉乳" in full:
        candidates.append(("starch_slurry", "淀粉乳", "source_text_explicit"))
    if "玉米粉" in full and not any(item[0] == "corn_whole_flour" for item in candidates):
        candidates.append(("corn_flour", "玉米粉", "source_text_explicit"))

    records = []
    for identity, name, basis in candidates:
        refs = [(index, text) for index, text in paragraphs if name in text]
        records.append({
            "candidate_id": f"substrate-identity-candidate::{path.stem}::{identity}",
            "substrate_identity_normalized": identity,
            "substrate_name_source_text": name,
            "substrate_smiles": None,
            "smiles_status": "not_inferred",
            "smiles_blocker": "source describes a process substrate or mixture; do not invent a single-molecule SMILES",
            "source_file": str(path.relative_to(AI_ROOT.parent)),
            "source_file_sha256": sha256(path),
            "source_format": path.suffix.lower().lstrip("."),
            "evidence_paragraphs": [{"paragraph_index": index, "text": text} for index, text in refs[:20]],
            "protocol_numeric_evidence": extract_numbers(full),
            "assay_context": {
                "enzyme_context": "alpha_amylase_or_amylase_process_protocol",
                "substrate_identity_basis": basis,
                "process_stage": "liquefaction_or_saccharification",
            },
            "review_status": "unreviewed_candidate",
            "reviewer": None,
            "reviewed_at": None,
            "formal_decision": None,
            "candidate_for_reviewed_substrate_identity_set": False,
            "substrate_fit_label_eligible": False,
            "policy": "Source-traced candidate only. Human review must confirm identity, scope, protocol version, and whether the process mixture can be represented for substrate_fit.",
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Build substrate identity evidence candidates")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    file_reports = []
    for path in sorted(args.source_dir.iterdir() if args.source_dir.exists() else []):
        if path.suffix.lower() == ".docx":
            paragraphs = docx_paragraphs(path)
            candidates = substrate_candidates(path, paragraphs)
            rows.extend(candidates)
            file_reports.append({"file": str(path), "format": "docx", "sha256": sha256(path), "paragraphs": len(paragraphs), "candidate_rows": len(candidates), "extraction_status": "text_extracted"})
        elif path.suffix.lower() == ".pdf":
            paragraphs = pdf_paragraphs(path)
            candidates = substrate_candidates(path, paragraphs)
            rows.extend(candidates)
            file_reports.append({"file": str(path), "format": "pdf", "sha256": sha256(path), "pages": len(PdfReader(str(path)).pages) if PdfReader else None, "paragraphs": len(paragraphs), "candidate_rows": len(candidates), "extraction_status": "text_extracted" if paragraphs else "text_extraction_unavailable_in_runtime", "requires_review": True})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(args.source_dir),
        "source_files_scanned": len(file_reports),
        "docx_files_extracted": sum(1 for row in file_reports if row["format"] == "docx" and row["extraction_status"] == "text_extracted"),
        "pdf_files_extracted": sum(1 for row in file_reports if row["format"] == "pdf" and row["extraction_status"] == "text_extracted"),
        "pdf_files_needing_extraction": sum(1 for row in file_reports if row["format"] == "pdf" and row["extraction_status"] != "text_extracted"),
        "candidate_rows": len(rows),
        "candidate_identities": sorted({row["substrate_identity_normalized"] for row in rows}),
        "reviewed_rows": 0,
        "substrate_fit_training_rows_written": 0,
        "formal_decision_rows": 0,
        "output": str(args.output.relative_to(AI_ROOT)),
        "file_reports": file_reports,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Protocol evidence is extracted into a candidate packet only. No SMILES, reviewed decision, training label, or quality claim is inferred.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_rows": len(rows), "candidate_identities": report["candidate_identities"], "reviewed_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
