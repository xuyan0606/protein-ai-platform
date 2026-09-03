#!/usr/bin/env python3
"""Normalize FireProt curated candidate ddG direction for KWB review.

KWB convention: negative ddG is stabilizing, positive ddG is destabilizing.
This script keeps FireProt/ThermoMPNN source ddG sign as the normalized value,
records a dTm sign sanity check, and still blocks training import until license,
schema mapping, leakage policy and reviewed import approval are complete.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_stability_import_candidates.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_stability_direction_normalized_candidates.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "fireprot_curated_stability_direction_normalization_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def threshold_class(ddg: float) -> str:
    if ddg < -1.0:
        return "stabilizing_hypothesis"
    if -1.0 <= ddg <= 1.0:
        return "near_neutral_manual_review"
    if 1.0 < ddg <= 2.0:
        return "destabilizing_watch"
    return "destabilizing_no_go"


def dtm_sanity(ddg: float, dtm: float | None) -> str:
    if dtm is None:
        return "no_dtm_reference"
    if ddg == 0 or dtm == 0:
        return "zero_reference"
    if (ddg < 0 and dtm > 0) or (ddg > 0 and dtm < 0):
        return "direction_consistent_with_negative_ddg_stabilizing"
    return "direction_conflict_with_dtm"


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize FireProt candidate ddG direction")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    normalized = []
    sanity_counts: Counter[str] = Counter()
    threshold_counts: Counter[str] = Counter()
    for row in rows:
        ddg = float(row["ddg_source_value"])
        sanity = dtm_sanity(ddg, row.get("dTm_c"))
        klass = threshold_class(ddg)
        sanity_counts[sanity] += 1
        threshold_counts[klass] += 1
        blockers = [
            item for item in row.get("blocked_from_training_reasons", [])
            if item != "ddg_direction_not_kwb_normalized"
        ]
        blockers.extend([
            "license_scope_not_selected",
            "reviewed_import_receipt_missing",
            "not_written_to_kwb_supervised_schema",
            "leakage_review_not_approved_for_training",
        ])
        output = dict(row)
        output.update({
            "kwb_ddg_kcal_mol": ddg,
            "kwb_negative_ddg_is_stabilizing": True,
            "kwb_ddg_direction_normalized": True,
            "kwb_ddg_direction_rule": "source_ddg_kept; dTm sanity supports negative ddG as stabilizing for most rows",
            "kwb_threshold_class": klass,
            "dtm_direction_sanity": sanity,
            "manual_review_required": sanity != "direction_consistent_with_negative_ddg_stabilizing",
            "claim_eligible_now": False,
            "blocked_from_training_reasons": sorted(set(blockers)),
        })
        normalized.append(output)

    write_jsonl(args.output, normalized)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "output": str(args.output),
        "candidate_rows": len(rows),
        "direction_normalized_rows": len(normalized),
        "claim_eligible_rows_now": 0,
        "kwb_negative_ddg_is_stabilizing": True,
        "dtm_sanity_counts": dict(sanity_counts),
        "threshold_class_counts": dict(threshold_counts),
        "ready_for_schema_mapping": bool(normalized),
        "ready_for_training_import": False,
        "remaining_blockers": [
            "license_scope_not_selected",
            "reviewed_import_receipt_missing",
            "not_written_to_kwb_supervised_schema",
            "leakage_review_not_approved_for_training",
        ],
        "safe_for_model_claim": False,
        "policy": "Direction-normalized candidates remain blocked from training until reviewed import approval.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "direction_normalized_rows": report["direction_normalized_rows"],
        "claim_eligible_rows_now": report["claim_eligible_rows_now"],
        "dtm_sanity_counts": report["dtm_sanity_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
