#!/usr/bin/env python3
"""Summarize public structure download failures for curation follow-up."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "reports" / "structure_public_download_report.json"
ACQUISITION = AI_ROOT / "datasets" / "curation" / "structure_acquisition_manifest.jsonl"
OUT = AI_ROOT / "reports" / "structure_download_failure_summary.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize structure download failures")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--acquisition", type=Path, default=ACQUISITION)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8")) if args.input.exists() else {}
    acquisition_rows = load_jsonl(args.acquisition)
    acquisition_by_id = {str(row.get("structure_id")): row for row in acquisition_rows}
    failures = report.get("failures") or []
    reason_counts = Counter(str(row.get("reason") or "unknown") for row in failures)
    failed_ids = [str(row.get("structure_id")) for row in failures]
    records = []
    for row in failures:
        structure_id = str(row.get("structure_id"))
        acquisition = acquisition_by_id.get(structure_id, {})
        records.append({
            "structure_id": structure_id,
            "reason": row.get("reason"),
            "expected_path": acquisition.get("expected_path"),
            "retrieval_url": acquisition.get("retrieval_url"),
            "next_action": "verify PDB ID against RCSB/PDBe; map obsolete or superseded IDs before retry",
        })

    summary = {
        "local_only": True,
        "attempted": report.get("attempted", 0),
        "downloaded": report.get("downloaded", 0),
        "present_after": report.get("present_after", 0),
        "missing_after": report.get("missing_after", 0),
        "failed": len(failures),
        "failure_reason_counts": dict(reason_counts),
        "failed_ids": failed_ids,
        "records": records,
        "policy": "do not fabricate or silently replace missing structures; verify obsolete IDs before substitution",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "failed": summary["failed"],
        "present_after": summary["present_after"],
        "missing_after": summary["missing_after"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
