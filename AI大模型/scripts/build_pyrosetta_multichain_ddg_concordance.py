#!/usr/bin/env python3
"""Summarize chain-context spread for multi-chain PyRosetta ddG features."""

from __future__ import annotations

import argparse
import json
from collections import Counter
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_features.jsonl"
OUT = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_concordance.jsonl"
REPORT = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build multi-chain PyRosetta ddG concordance report")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--concordance-span-reu", type=float, default=1.0)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("chain_execution_mode") == "multi_chain_context":
            grouped[str(row.get("candidate_id"))].append(row)

    output = []
    for candidate_id, members in sorted(grouped.items()):
        values = [float(member["ddg_reu"]) for member in members]
        span = max(values) - min(values)
        quality_reasons: list[str] = []
        if any(member.get("quality_gate_passed") is not True for member in members):
            quality_reasons.append("member_score_quality_blocked")
        if span > args.concordance_span_reu:
            quality_reasons.append("ddg_span_gt_concordance_threshold")
        output.append(
            {
                "candidate_id": candidate_id,
                "record_id": members[0].get("record_id"),
                "uniprot_id": members[0].get("uniprot_id"),
                "structure_id": members[0].get("structure_id"),
                "mutation": members[0].get("mutation"),
                "chain_ids": sorted(str(member.get("chain_id")) for member in members),
                "chain_feature_rows": len(members),
                "ddg_reu_min": min(values),
                "ddg_reu_max": max(values),
                "ddg_reu_median": statistics.median(values),
                "ddg_reu_span": span,
                "concordance_threshold_reu": args.concordance_span_reu,
                "chain_context_status": (
                    "chain_concordant_input_feature"
                    if span <= args.concordance_span_reu
                    else "chain_context_sensitive_manual_review"
                ),
                "quality_gate_passed": not quality_reasons,
                "quality_gate_status": "passed" if not quality_reasons else "blocked",
                "quality_gate_reasons": quality_reasons,
                "manual_review_required": True,
                "training_label": False,
                "safe_for_training_import": False,
                "safe_for_model_claim": False,
                "release_ready": False,
                "policy": (
                    "Chain-level DDG spread is a structural-context diagnostic only. "
                    "It does not select a chain, create a label, or open a claim gate."
                ),
            }
        )

    write_jsonl(args.output, output)
    report = {
        "input_feature_rows": len(rows),
        "multi_chain_feature_rows": sum(len(items) for items in grouped.values()),
        "multi_chain_candidate_rows": len(output),
        "chain_concordant_rows": sum(
            1 for row in output if row["chain_context_status"] == "chain_concordant_input_feature"
        ),
        "chain_context_sensitive_rows": sum(
            1 for row in output if row["chain_context_status"] == "chain_context_sensitive_manual_review"
        ),
        "quality_passed_rows": sum(1 for row in output if row["quality_gate_passed"] is True),
        "quality_blocked_rows": sum(1 for row in output if row["quality_gate_passed"] is False),
        "quality_block_reason_counts": dict(
            Counter(reason for row in output for reason in row["quality_gate_reasons"])
        ),
        "concordance_span_reu": args.concordance_span_reu,
        "output": str(args.output.relative_to(AI_ROOT)),
        "safe_for_model_claim": False,
        "policy": "Concordance report is an input-feature diagnostic, not a chain-selection or model-quality decision.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "multi_chain_candidate_rows": report["multi_chain_candidate_rows"],
            "chain_concordant_rows": report["chain_concordant_rows"],
            "chain_context_sensitive_rows": report["chain_context_sensitive_rows"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
