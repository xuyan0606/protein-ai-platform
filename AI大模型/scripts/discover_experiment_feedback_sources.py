#!/usr/bin/env python3
"""Discover local candidate sources for KWB experiment feedback intake."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_ROOT.parent
OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_candidates.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_source_discovery_report.json"

EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".jsonl", ".md", ".txt", ".docx"}
KEYWORDS = [
    "实验", "酶", "活性", "底物", "突变", "稳定", "热稳定", "ph", "温度", "转化率",
    "activity", "assay", "substrate", "mutation", "mutant", "stability", "yield",
    "conversion", "expression", "screening", "tm", "ddg",
]
SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", "cache/structures"}
SKIP_REL_PREFIXES = (
    "AI大模型/",
)


def is_skipped(path: Path) -> bool:
    text = str(path)
    if any(part in text for part in SKIP_PARTS):
        return True
    try:
        rel = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return False
    return rel.startswith(SKIP_REL_PREFIXES)


def read_text_sample(path: Path, max_bytes: int) -> str:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", xml)[:max_bytes]
        except Exception:
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
    except Exception:
        return ""


def score_text(path: Path, text: str) -> tuple[int, list[str]]:
    lower = f"{path.name} {text}".lower()
    hits = sorted({keyword for keyword in KEYWORDS if keyword.lower() in lower})
    score = len(hits) * 10
    if path.suffix.lower() in {".csv", ".tsv", ".xlsx", ".xls"}:
        score += 20
    if "experiment_feedback" in str(path):
        score += 20
    if "template" in path.name.lower():
        score -= 30
    return score, hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover experiment feedback source candidates")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--sample-bytes", type=int, default=12000)
    args = parser.parse_args()

    candidates: list[dict[str, Any]] = []
    for path in args.root.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue
        if path.suffix.lower() not in EXTENSIONS:
            continue
        text = read_text_sample(path, args.sample_bytes)
        score, hits = score_text(path, text)
        if score <= 0:
            continue
        candidates.append({
            "path": str(path),
            "relative_path": str(path.relative_to(PROJECT_ROOT)),
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "keyword_hits": hits,
            "candidate_score": score,
            "status": "candidate_needs_manual_review",
            "policy": "source discovery only; not validated feedback and not training data",
        })
    candidates.sort(key=lambda row: (-row["candidate_score"], row["relative_path"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates), encoding="utf-8")
    report = {
        "root": str(args.root),
        "candidate_rows": len(candidates),
        "top_candidates": candidates[:20],
        "output": str(args.output),
        "policy": "candidate source files must be manually reviewed and converted to experiment_feedback.local.jsonl before training",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
