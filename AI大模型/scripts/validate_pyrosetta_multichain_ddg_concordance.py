#!/usr/bin/env python3
"""Validate multi-chain ddG concordance remains diagnostic and fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURES = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_features.jsonl"
INDEX = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_concordance.jsonl"
REPORT = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate multi-chain PyRosetta ddG concordance")
    parser.add_argument("--features", type=Path, default=FEATURES)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_jsonl(args.features):
        if row.get("chain_execution_mode") == "multi_chain_context":
            source_groups[str(row.get("candidate_id"))].append(row)
    rows = load_jsonl(args.index)
    by_candidate = {str(row.get("candidate_id")): row for row in rows}
    errors: Counter[str] = Counter()
    records = []
    for candidate_id, members in sorted(source_groups.items()):
        row = by_candidate.get(candidate_id)
        item_errors = []
        if row is None:
            item_errors.append("concordance_row_missing")
        else:
            values = [float(member["ddg_reu"]) for member in members]
            expected_span = max(values) - min(values)
            if int(row.get("chain_feature_rows") or 0) != len(members):
                item_errors.append("chain_feature_row_count_mismatch")
            if abs(float(row.get("ddg_reu_span") or 0) - expected_span) > 1e-9:
                item_errors.append("ddg_span_mismatch")
            if row.get("manual_review_required") is not True:
                item_errors.append("manual_review_missing")
            if row.get("quality_gate_status") not in {"passed", "blocked"}:
                item_errors.append("quality_gate_status_invalid")
            if not isinstance(row.get("quality_gate_reasons"), list):
                item_errors.append("quality_gate_reasons_missing")
            expected_quality_blocked = bool(
                any(member.get("quality_gate_passed") is not True for member in members)
                or expected_span > float(row.get("concordance_threshold_reu") or 1.0)
            )
            if row.get("quality_gate_passed") is not (not expected_quality_blocked):
                item_errors.append("quality_gate_state_mismatch")
            for field in ("training_label", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
                if row.get(field) is not False:
                    item_errors.append(f"{field}_must_be_false")
        errors.update(item_errors)
        records.append({"candidate_id": candidate_id, "valid": not item_errors, "errors": item_errors})
    report = {
        "source_multi_chain_candidate_rows": len(source_groups),
        "concordance_rows": len(rows),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "quality_passed_rows": sum(1 for row in rows if row.get("quality_gate_passed") is True),
        "quality_blocked_rows": sum(1 for row in rows if row.get("quality_gate_passed") is False),
        "quality_gate_status": "blocked" if any(
            row.get("quality_gate_passed") is False for row in rows
        ) else "passed",
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "error_counts": dict(errors),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation confirms diagnostic integrity only; it never upgrades ambiguous chains to reviewed decisions.",
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "source_multi_chain_candidate_rows": report["source_multi_chain_candidate_rows"],
            "valid_rows": report["valid_rows"],
            "invalid_rows": report["invalid_rows"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
