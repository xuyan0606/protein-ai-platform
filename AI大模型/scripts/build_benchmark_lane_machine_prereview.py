#!/usr/bin/env python3
"""Build read-only machine pre-review status for the benchmark lane.

This script never creates formal decisions, benchmark intake rows, training
labels, model claims, or release flags.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_PACKETS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl"
STRICT_DECISIONS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl"
STRICT_REPORT = AI_ROOT / "reports/kwb_strict_mutation_holdout_benchmark_report.json"
STRICT_CACHE = AI_ROOT / "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout"
SUBSTRATE_PACKETS = AI_ROOT / "datasets/curation/substrate_identity_review_packets.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl"
SUBSTRATE_CANDIDATES = AI_ROOT / "datasets/curation/substrate_identity_evidence_candidates.jsonl"
SUBSTRATE_REPORT = AI_ROOT / "reports/substrate_identity_evidence_candidate_report.json"
OUT = AI_ROOT / "reports/benchmark_lane_machine_prereview_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def strict_lane() -> dict[str, Any]:
    packets = load_jsonl(STRICT_PACKETS)
    decisions = load_jsonl(STRICT_DECISIONS)
    report = load_json(STRICT_REPORT)
    packet_keys = {str(row.get("review_key")) for row in packets if row.get("review_key")}
    decision_keys = {str(row.get("review_key")) for row in decisions if row.get("review_key")}
    packet_checks = []
    for row in packets:
        checks = {
            "review_key_present": bool(row.get("review_key")),
            "source_receipts_present": bool(row.get("source_receipts")),
            "sequence_pdb_cross_check_exact": bool((row.get("sequence_pdb_cross_check") or {}).get("exact_match")),
            "numbering_not_formally_confirmed": row.get("strict_holdout_eligible_now") is False,
            "training_not_eligible": row.get("training_import_eligible_now") is False,
            "formal_decision_absent": row.get("formal_decision") is None,
        }
        packet_checks.append({
            "review_key": row.get("review_key"),
            "machine_checks": checks,
            "machine_status": "ready_for_human_review" if all(checks.values()) else "blocked_machine_pre_review",
        })
    formal_approved = sum(row.get("decision") == "approve_strict_holdout" for row in decisions)
    return {
        "lane": "kwb_strict_mutation_holdout",
        "packet_rows": len(packets),
        "decision_rows": len(decisions),
        "formal_approved_rows_observed": formal_approved,
        "packet_keys_without_decision": len(packet_keys - decision_keys),
        "benchmark_cache": {
            "dataset_rows": report.get("dataset_rows", 0),
            "primary_holdout_rows": report.get("primary_holdout_rows", 0),
            "leakage_check_status": report.get("leakage_check_status", "missing"),
            "ready_as_benchmark_scorecard": report.get("ready_as_benchmark_scorecard", False),
            "artifacts_present": all((STRICT_CACHE / name).exists() for name in (
                "dataset.jsonl", "split_definition.json", "scorecard.json", "metric_report.json",
            )),
        },
        "machine_status": "ready_for_human_review" if packet_checks and all(
            row["machine_status"] == "ready_for_human_review" for row in packet_checks
        ) else "blocked_machine_pre_review",
        "records": packet_checks,
        "formal_decision_written_by_this_script": False,
        "training_import_written_by_this_script": False,
    }


def substrate_lane() -> dict[str, Any]:
    candidates = load_jsonl(SUBSTRATE_CANDIDATES)
    packets = load_jsonl(SUBSTRATE_PACKETS)
    decisions = load_jsonl(SUBSTRATE_DECISIONS)
    report = load_json(SUBSTRATE_REPORT)
    decision_keys = {str(row.get("review_key")) for row in decisions if row.get("review_key")}
    packet_checks = []
    for row in packets or candidates:
        checks = {
            "candidate_id_present": bool(row.get("candidate_id")),
            "source_hash_present": bool(row.get("source_file_sha256")),
            "source_evidence_present": bool(row.get("evidence_paragraphs")),
            "smiles_not_inferred": row.get("substrate_smiles") is None,
            "formal_decision_absent": row.get("formal_decision") is None,
            "review_status_pending": row.get("review_status") in {"pending_human_review", "unreviewed_candidate"},
        }
        packet_checks.append({
            "candidate_id": row.get("candidate_id"),
            "machine_checks": checks,
            "machine_status": "ready_for_human_review" if all(checks.values()) else "blocked_machine_pre_review",
            "formal_decision_observed": row.get("candidate_id") in decision_keys,
        })
    formal_approved = sum(row.get("decision") == "approve_reviewed_substrate_identity" for row in decisions)
    return {
        "lane": "reviewed_substrate_identity_set",
        "candidate_rows": len(candidates),
        "packet_rows": len(packets),
        "decision_rows": len(decisions),
        "formal_approved_rows_observed": formal_approved,
        "candidate_report_rows": report.get("candidate_rows", 0),
        "machine_status": "ready_for_human_review" if packet_checks and all(
            row["machine_status"] == "ready_for_human_review" for row in packet_checks
        ) else "blocked_machine_pre_review",
        "records": packet_checks,
        "formal_decision_written_by_this_script": False,
        "training_import_written_by_this_script": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark lane machine pre-review report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    strict = strict_lane()
    substrate = substrate_lane()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_human_review" if all(
            lane["machine_status"] == "ready_for_human_review" for lane in (strict, substrate)
        ) else "blocked_machine_pre_review",
        "lanes": {"strict_mutation_holdout": strict, "reviewed_substrate_identity_set": substrate},
        "formal_decision_rows_observed": strict["formal_approved_rows_observed"] + substrate["formal_approved_rows_observed"],
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Machine pre-review only. It checks source and namespace hygiene and never writes formal decisions, training labels, claims, or release state.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "strict_packets": strict["packet_rows"], "substrate_candidates": substrate["candidate_rows"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
