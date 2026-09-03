#!/usr/bin/env python3
"""Build non-applied decision templates for curation batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = AI_ROOT / "datasets" / "curation" / "batches"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "decision_templates"
REPORT_OUT = AI_ROOT / "reports" / "curation_decision_template_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def template_for(row: dict[str, Any]) -> dict[str, Any]:
    source_refs = [row["literature_ref"]] if row.get("literature_ref") else []
    return {
        "record_id": row.get("record_id"),
        "decision": "keep_unresolved_weak",
        "canonical_uniprot_id": row.get("uniprot_id"),
        "canonical_position": None,
        "canonical_wild_type": None,
        "canonical_mutant": row.get("mutation", "")[-1:] or None,
        "mapping_basis": "unresolved",
        "source_refs": source_refs,
        "confidence": 0.0,
        "notes": "Template only. Review literature/source sequence before changing decision to map_to_canonical.",
        "curator": "local-curator",
        "curated_at": "2026-07-24T00:00:00+08:00",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build curation decision templates")
    parser.add_argument("--batch-dir", type=Path, default=BATCH_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    batch_files = sorted(args.batch_dir.glob("*.jsonl"))
    reports = []
    for batch_file in batch_files:
        rows = load_jsonl(batch_file)
        template_rows = [template_for(row) for row in rows]
        out_path = args.out_dir / f"{batch_file.stem}.decisions.template.jsonl"
        write_jsonl(out_path, template_rows)
        reports.append({
            "batch_id": batch_file.stem,
            "rows": len(template_rows),
            "template": str(out_path),
        })
    report = {
        "batches": len(reports),
        "rows": sum(item["rows"] for item in reports),
        "templates": reports,
        "policy": "template files are not read by apply_numbering_curation.py; copy reviewed rows into numbering_curation_decisions.jsonl",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batches": report["batches"], "rows": report["rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
