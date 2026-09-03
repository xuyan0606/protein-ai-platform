#!/usr/bin/env python3
"""Bridge approved hard-gate decisions into benchmark score-cache artifacts.

This script is intentionally fail-closed.  With zero approved formal decisions
it writes only a blocked receipt report and does not update benchmark intake.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_PACKETS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl"
STRICT_DECISIONS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_PACKETS = AI_ROOT / "datasets/curation/substrate_identity_review_packets.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl"
INTAKE = AI_ROOT / "datasets/benchmark/benchmark_score_cache_intake.local.jsonl"
STRICT_OUT = AI_ROOT / "cache/advanced_features/benchmarks/kwb_venus15b_reviewed_strict_holdout"
SUBSTRATE_OUT = AI_ROOT / "cache/advanced_features/benchmarks/reviewed_substrate_identity_set"
REPORT = AI_ROOT / "reports/hard_gate_decision_benchmark_bridge_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def update_intake(row: dict[str, Any]) -> None:
    rows = load_jsonl(INTAKE)
    key = (row["head"], row["benchmark_name"])
    output = []
    replaced = False
    for existing in rows:
        if (existing.get("head"), existing.get("benchmark_name")) == key:
            output.append(row)
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(row)
    write_jsonl(INTAKE, output)


def complete(value: Any) -> bool:
    return value not in (None, "", False, [])


def approved_strict_decisions(packets: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packet_by_key = {str(row.get("review_key")): row for row in packets}
    approved = []
    for decision in decisions:
        key = str(decision.get("review_key") or "")
        if decision.get("decision") != "approve_strict_holdout" or key not in packet_by_key:
            continue
        required = [
            "source_evidence_confirmed",
            "numbering_confirmed",
            "wetlab_result_confirmed",
            "leakage_check_passed",
            "acceptance_receipt",
            "review_basis",
            "reviewer",
            "reviewed_at",
        ]
        if all(complete(decision.get(field)) for field in required) and decision.get("approved_label") in {"go", "watch"}:
            approved.append({"packet": packet_by_key[key], "decision": decision})
    return approved


def approved_substrate_decisions(packets: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packet_by_key = {str(row.get("review_key")): row for row in packets}
    approved = []
    for decision in decisions:
        key = str(decision.get("review_key") or "")
        if decision.get("decision") != "approve_reviewed_substrate_identity" or key not in packet_by_key:
            continue
        required = [
            "identity_confirmed",
            "scope_confirmed",
            "condition_confirmed",
            "protocol_version_confirmed",
            "representation_type",
            "acceptance_receipt",
            "review_basis",
            "reviewer",
            "reviewed_at",
        ]
        if not all(complete(decision.get(field)) for field in required):
            continue
        if decision.get("representation_type") not in {"single_compound", "process_mixture", "defined_substrate_set"}:
            continue
        if decision.get("representation_type") == "process_mixture" and decision.get("substrate_smiles"):
            continue
        approved.append({"packet": packet_by_key[key], "decision": decision})
    return approved


def build_strict(approved: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    if not approved:
        return {"status": "blocked_no_approved_decisions", "dataset_rows": 0, "intake_written": False}
    dataset = []
    for index, item in enumerate(approved, start=1):
        packet = item["packet"]
        decision = item["decision"]
        dataset.append({
            "benchmark_record_id": f"kwb_venus15b_reviewed_strict::{packet.get('variant')}",
            "project_id": packet.get("project_id"),
            "variant": packet.get("variant"),
            "mutation": packet.get("mutation"),
            "wild_type": packet.get("wild_type"),
            "canonical_position": packet.get("canonical_position"),
            "mutant": packet.get("mutant"),
            "actual_label": decision.get("approved_label"),
            "split": "test" if index % 5 == 0 else "validation",
            "review_key": decision.get("review_key"),
            "reviewer": decision.get("reviewer"),
            "reviewed_at": decision.get("reviewed_at"),
            "acceptance_receipt": decision.get("acceptance_receipt"),
            "source_receipts": packet.get("source_receipts"),
            "measurement_evidence_rows": packet.get("measurement_evidence_rows"),
            "training_import_written_by_bridge": False,
        })
    label_counts = Counter(row["actual_label"] for row in dataset)
    dataset_path = STRICT_OUT / "dataset.jsonl"
    split_path = STRICT_OUT / "split_definition.json"
    scorecard_path = STRICT_OUT / "scorecard.json"
    metric_path = STRICT_OUT / "metric_report.json"
    write_jsonl(dataset_path, dataset)
    write_json(split_path, {
        "benchmark_name": "KWB strict mutation holdout",
        "head": "mutation_rank",
        "created_at": created_at,
        "dataset_rows": len(dataset),
        "split_rule": "approved Venus-15B strict decisions; validation/test partition deterministic by row index",
        "split_counts": dict(Counter(row["split"] for row in dataset)),
        "leakage_check_status": "passed",
        "leakage_checks": {
            "formal_decision_required": True,
            "all_rows_have_acceptance_receipt": all(bool(row.get("acceptance_receipt")) for row in dataset),
            "training_import_written_by_bridge": False,
        },
    })
    write_json(scorecard_path, {
        "benchmark_name": "KWB strict mutation holdout",
        "head": "mutation_rank",
        "created_at": created_at,
        "rows_scored": len(dataset),
        "label_counts": dict(label_counts),
        "score_type": "reviewed_reference_set_readiness",
        "model_runtime_executed": False,
        "policy": "This scorecard proves reviewed reference-set availability only. It does not train or claim model quality.",
    })
    write_json(metric_path, {
        "benchmark_name": "KWB strict mutation holdout",
        "head": "mutation_rank",
        "created_at": created_at,
        "dataset_rows": len(dataset),
        "primary_metric": "reviewed_reference_rows",
        "primary_metric_value": len(dataset),
        "label_counts": dict(label_counts),
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_quality_claim": False,
    })
    intake_row = {
        "head": "mutation_rank",
        "benchmark_name": "KWB strict mutation holdout",
        "dataset_version": "kwb-venus15b-reviewed-strict-holdout-v1",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(dataset_path),
        "dataset_sha256": sha256(dataset_path),
        "split_definition_uri": rel(split_path),
        "split_sha256": sha256(split_path),
        "scorecard_uri": rel(scorecard_path),
        "scorecard_sha256": sha256(scorecard_path),
        "metric_report_uri": rel(metric_path),
        "metric_sha256": sha256(metric_path),
        "leakage_check_status": "passed",
        "reviewer": "hard_gate_decision_benchmark_bridge",
        "reviewed_at": created_at,
        "notes": "Generated only from approved formal Venus-15B strict-holdout decisions with receipts.",
    }
    update_intake(intake_row)
    return {"status": "intake_written", "dataset_rows": len(dataset), "intake_written": True, "dataset": rel(dataset_path)}


def build_substrate(approved: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    if not approved:
        return {"status": "blocked_no_approved_decisions", "dataset_rows": 0, "intake_written": False}
    dataset = []
    for item in approved:
        packet = item["packet"]
        decision = item["decision"]
        dataset.append({
            "benchmark_record_id": f"reviewed_substrate_identity::{packet.get('candidate_id')}",
            "candidate_id": packet.get("candidate_id"),
            "substrate_identity_normalized": packet.get("substrate_identity_normalized"),
            "substrate_name_source_text": packet.get("substrate_name_source_text"),
            "representation_type": decision.get("representation_type"),
            "substrate_smiles": decision.get("substrate_smiles"),
            "source_file": packet.get("source_file"),
            "source_file_sha256": packet.get("source_file_sha256"),
            "protocol_numeric_evidence": packet.get("protocol_numeric_evidence"),
            "assay_context": packet.get("assay_context"),
            "review_key": decision.get("review_key"),
            "reviewer": decision.get("reviewer"),
            "reviewed_at": decision.get("reviewed_at"),
            "acceptance_receipt": decision.get("acceptance_receipt"),
            "training_import_written_by_bridge": False,
        })
    rep_counts = Counter(row["representation_type"] for row in dataset)
    dataset_path = SUBSTRATE_OUT / "dataset.jsonl"
    split_path = SUBSTRATE_OUT / "split_definition.json"
    scorecard_path = SUBSTRATE_OUT / "scorecard.json"
    metric_path = SUBSTRATE_OUT / "metric_report.json"
    write_jsonl(dataset_path, dataset)
    write_json(split_path, {
        "benchmark_name": "reviewed substrate identity set",
        "head": "substrate_fit",
        "created_at": created_at,
        "dataset_rows": len(dataset),
        "split_rule": "reviewed substrate identity reference set; all rows test/reference",
        "split_counts": {"test": len(dataset)},
        "leakage_check_status": "passed",
        "leakage_checks": {
            "formal_decision_required": True,
            "all_rows_have_acceptance_receipt": all(bool(row.get("acceptance_receipt")) for row in dataset),
            "mixtures_have_no_inferred_smiles": all(row.get("representation_type") != "process_mixture" or not row.get("substrate_smiles") for row in dataset),
        },
    })
    write_json(scorecard_path, {
        "benchmark_name": "reviewed substrate identity set",
        "head": "substrate_fit",
        "created_at": created_at,
        "rows_scored": len(dataset),
        "representation_type_counts": dict(rep_counts),
        "score_type": "reviewed_reference_set_readiness",
        "model_runtime_executed": False,
        "policy": "Reviewed substrate identity reference set only. It does not convert generic activity into substrate_fit labels.",
    })
    write_json(metric_path, {
        "benchmark_name": "reviewed substrate identity set",
        "head": "substrate_fit",
        "created_at": created_at,
        "dataset_rows": len(dataset),
        "primary_metric": "reviewed_substrate_identity_rows",
        "primary_metric_value": len(dataset),
        "representation_type_counts": dict(rep_counts),
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_quality_claim": False,
    })
    intake_row = {
        "head": "substrate_fit",
        "benchmark_name": "reviewed substrate identity set",
        "dataset_version": "kwb-reviewed-substrate-identity-set-v1",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(dataset_path),
        "dataset_sha256": sha256(dataset_path),
        "split_definition_uri": rel(split_path),
        "split_sha256": sha256(split_path),
        "scorecard_uri": rel(scorecard_path),
        "scorecard_sha256": sha256(scorecard_path),
        "metric_report_uri": rel(metric_path),
        "metric_sha256": sha256(metric_path),
        "leakage_check_status": "passed",
        "reviewer": "hard_gate_decision_benchmark_bridge",
        "reviewed_at": created_at,
        "notes": "Generated only from approved formal substrate identity decisions with receipts.",
    }
    update_intake(intake_row)
    return {"status": "intake_written", "dataset_rows": len(dataset), "intake_written": True, "dataset": rel(dataset_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark bridge from approved hard-gate decisions")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    created_at = datetime.now(timezone.utc).isoformat()
    strict_approved = approved_strict_decisions(load_jsonl(STRICT_PACKETS), load_jsonl(STRICT_DECISIONS))
    substrate_approved = approved_substrate_decisions(load_jsonl(SUBSTRATE_PACKETS), load_jsonl(SUBSTRATE_DECISIONS))
    strict = build_strict(strict_approved, created_at)
    substrate = build_substrate(substrate_approved, created_at)
    report = {
        "created_at": created_at,
        "strict_formal_approved_rows": len(strict_approved),
        "substrate_formal_approved_rows": len(substrate_approved),
        "strict": strict,
        "substrate": substrate,
        "intake_rows_written": int(strict["intake_written"]) + int(substrate["intake_written"]),
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only complete formal decisions with receipts may update benchmark intake. Zero approvals must remain blocked.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "strict_formal_approved_rows": len(strict_approved),
        "substrate_formal_approved_rows": len(substrate_approved),
        "intake_rows_written": report["intake_rows_written"],
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
