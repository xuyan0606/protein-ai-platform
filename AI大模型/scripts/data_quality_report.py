#!/usr/bin/env python3
"""Generate a conservative local data-quality report for KWB model R&D."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = AI_ROOT / "reports" / "local_data_discovery.json"
REPORT = AI_ROOT / "reports" / "data_quality_report.json"


def score_lipase_db(lipase: dict) -> tuple[int, list[str]]:
    score = 0
    warnings = []
    expected = {
        "papers",
        "variants",
        "variant_mutations",
        "evidence_claims",
        "substrates",
        "metrics",
        "unresolved_gaps",
    }
    tables = lipase.get("tables") or {}
    if lipase.get("status") == "ready":
        score += 20
    else:
        warnings.append("lipase_db_not_ready")
    if lipase.get("integrity_check") == "ok":
        score += 20
    else:
        warnings.append("lipase_integrity_not_ok")
    present = expected & set(tables)
    score += int(40 * len(present) / len(expected))
    missing = sorted(expected - set(tables))
    if missing:
        warnings.append("missing_lipase_tables:" + ",".join(missing))
    if sum(int(tables.get(table) or 0) for table in present) > 0:
        score += 20
    else:
        warnings.append("lipase_tables_empty")
    return min(score, 100), warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local data quality report")
    parser.add_argument("--discovery", type=Path, default=DISCOVERY)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    discovery = json.loads(args.discovery.read_text(encoding="utf-8"))
    lipase_score, lipase_warnings = score_lipase_db(discovery.get("lipase_db") or {})
    deploy_counts = discovery.get("deploy_data", {}).get("counts", {})
    deploy_score = 0
    deploy_warnings = []
    for group, counts in deploy_counts.items():
        total = sum(int(value or 0) for value in counts.values())
        if total > 0:
            deploy_score += 10
        else:
            deploy_warnings.append(f"deploy_group_empty:{group}")
    deploy_score = min(deploy_score, 100)

    overall = round(0.6 * lipase_score + 0.4 * deploy_score, 2)
    report = {
        "overall_score": overall,
        "ready_for_training": overall >= 70 and lipase_score >= 70,
        "lipase_score": lipase_score,
        "deploy_data_score": deploy_score,
        "warnings": lipase_warnings + deploy_warnings,
        "recommended_next_steps": [
            "extract read-only lipase variant and mutation rows",
            "extract experiment_feedback_records from local app DB if present",
            "keep benchmark cases out of training split",
            "use family-level split before claiming model performance",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "overall_score": overall, "ready_for_training": report["ready_for_training"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

