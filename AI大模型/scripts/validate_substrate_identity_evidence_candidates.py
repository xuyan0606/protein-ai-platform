#!/usr/bin/env python3
"""Validate source-traced substrate identity candidates fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets/curation/substrate_identity_evidence_candidates.jsonl"
REPORT = AI_ROOT / "reports/substrate_identity_evidence_candidate_validation_report.json"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    rows = load(args.input)
    errors = Counter()
    records = []
    for row in rows:
        row_errors = []
        for field in ("candidate_id", "substrate_identity_normalized", "substrate_name_source_text", "source_file", "source_file_sha256", "review_status"):
            if not row.get(field):
                row_errors.append(f"missing_{field}")
        if row.get("review_status") != "unreviewed_candidate":
            row_errors.append("unexpected_review_status_for_candidate_artifact")
        if row.get("substrate_smiles") is not None:
            row_errors.append("candidate_must_not_invent_smiles")
        if row.get("formal_decision") is not None:
            row_errors.append("candidate_must_not_contain_formal_decision")
        errors.update(row_errors)
        records.append({"candidate_id": row.get("candidate_id"), "valid": not row_errors, "errors": row_errors})
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "rows": len(rows),
        "valid_rows": sum(1 for item in records if item["valid"]),
        "invalid_rows": sum(1 for item in records if not item["valid"]),
        "reviewed_rows": 0,
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "error_counts": dict(errors),
        "records": records,
        "policy": "Validation confirms candidate evidence hygiene only; it cannot promote a row to reviewed substrate identity or training data.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": report["rows"], "valid_rows": report["valid_rows"], "invalid_rows": report["invalid_rows"], "reviewed_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
