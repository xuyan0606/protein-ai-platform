#!/usr/bin/env python3
"""Build non-applied domain interval decision templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = AI_ROOT / "datasets" / "curation" / "domain_batches"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "domain_decision_templates"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_decision_template_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build domain interval decision templates")
    parser.add_argument("--batch-dir", type=Path, default=BATCH_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    reports = []
    for batch_file in sorted(args.batch_dir.glob("*.jsonl")):
        rows = load_jsonl(batch_file)
        template_rows = [
            {
                "domain_record_id": row.get("domain_record_id"),
                "decision": "keep_unresolved",
                "start_pos": None,
                "end_pos": None,
                "basis": "unresolved",
                "confidence": 0.0,
                "notes": f"Template only for {row.get('uniprot_id')} {row.get('pfam_id')}. Confirm interval before set_interval.",
                "curator": "local-curator",
                "curated_at": "2026-07-24T00:00:00+08:00",
            }
            for row in rows
        ]
        out_path = args.out_dir / f"{batch_file.stem}.decisions.template.jsonl"
        write_jsonl(out_path, template_rows)
        reports.append({"batch_id": batch_file.stem, "rows": len(template_rows), "template": str(out_path)})
    report = {
        "batches": len(reports),
        "rows": sum(row["rows"] for row in reports),
        "templates": reports,
        "policy": "template files are not read by apply_domain_interval_curation.py",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batches": report["batches"], "rows": report["rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
