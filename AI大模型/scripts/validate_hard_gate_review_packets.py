#!/usr/bin/env python3
"""Validate hard-gate review packets and formal decisions fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_INPUT = AI_ROOT / "cache/advanced_features/benchmarks/kwb_venus15b_strict_holdout_candidate/dataset.jsonl"
SUBSTRATE_INPUT = AI_ROOT / "datasets/curation/substrate_identity_evidence_candidates.jsonl"
STRICT_PACKETS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl"
SUBSTRATE_PACKETS = AI_ROOT / "datasets/curation/substrate_identity_review_packets.jsonl"
STRICT_DECISIONS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl"
REPORT = AI_ROOT / "reports/hard_gate_review_packet_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(source_file: str) -> Path:
    """Resolve both AI_ROOT-relative and work-area-relative source receipts."""
    direct = AI_ROOT / source_file
    if direct.exists():
        return direct
    return AI_ROOT.parent / source_file


def validate_strict(candidates: list[dict[str, Any]], packets: list[dict[str, Any]], decisions: list[dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    candidate_by_id = {str(row.get("benchmark_record_id")): row for row in candidates}
    packet_by_id = {str(row.get("review_key")): row for row in packets}
    if len(packet_by_id) != len(packets):
        failures.append("strict_packet_duplicate_review_key")
    if set(packet_by_id) != set(candidate_by_id):
        failures.append("strict_packet_candidate_key_mismatch")
    for key, packet in packet_by_id.items():
        candidate = candidate_by_id.get(key)
        if not candidate:
            continue
        if packet.get("formal_decision") is not None:
            failures.append(f"strict_packet_contains_formal_decision:{key}")
        if packet.get("review_status") != "pending_human_review":
            failures.append(f"strict_packet_not_pending:{key}")
        if candidate.get("strict_holdout_eligible_now") is not False or candidate.get("training_import_eligible_now") is not False:
            failures.append(f"strict_candidate_positive_flag:{key}")
        if candidate.get("numbering_cross_check_passed") is not True:
            failures.append(f"strict_sequence_pdb_cross_check_failed:{key}")
        if not packet.get("source_receipts") or not packet.get("measurement_evidence_rows"):
            failures.append(f"strict_packet_missing_evidence:{key}")
    decision_keys = set()
    valid_decisions = 0
    for row in decisions:
        key = str(row.get("review_key") or "")
        if not key or key in decision_keys or key not in candidate_by_id:
            failures.append(f"strict_invalid_or_duplicate_decision:{key}")
            continue
        decision_keys.add(key)
        decision = row.get("decision")
        if decision not in {"approve_strict_holdout", "reject_candidate", "needs_more_info"}:
            failures.append(f"strict_invalid_decision:{key}")
            continue
        if decision == "approve_strict_holdout":
            required = ["source_evidence_confirmed", "numbering_confirmed", "wetlab_result_confirmed", "leakage_check_passed", "acceptance_receipt", "review_basis", "reviewer", "reviewed_at"]
            for field in required:
                value = row.get(field)
                if value is False or value is None or value == "":
                    failures.append(f"strict_approval_missing_{field}:{key}")
            if row.get("approved_label") not in {"go", "watch"}:
                failures.append(f"strict_approval_missing_label:{key}")
        valid_decisions += 1
    return {
        "candidate_rows": len(candidates),
        "packet_rows": len(packets),
        "formal_decision_rows": len(decisions),
        "valid_decision_rows": valid_decisions,
        "approved_decision_rows": sum(1 for row in decisions if row.get("decision") == "approve_strict_holdout"),
        "strict_holdout_rows_written": 0,
    }


def validate_substrate(candidates: list[dict[str, Any]], packets: list[dict[str, Any]], decisions: list[dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    candidate_by_id = {str(row.get("candidate_id")): row for row in candidates}
    packet_by_id = {str(row.get("review_key")): row for row in packets}
    if len(packet_by_id) != len(packets):
        failures.append("substrate_packet_duplicate_review_key")
    if set(packet_by_id) != set(candidate_by_id):
        failures.append("substrate_packet_candidate_key_mismatch")
    expected_sha = {key: sha256(source_path(str(row.get("source_file")))) for key, row in candidate_by_id.items() if source_path(str(row.get("source_file"))).exists()}
    for key, packet in packet_by_id.items():
        candidate = candidate_by_id.get(key)
        if not candidate:
            continue
        if packet.get("formal_decision") is not None:
            failures.append(f"substrate_packet_contains_formal_decision:{key}")
        if packet.get("review_status") != "pending_human_review":
            failures.append(f"substrate_packet_not_pending:{key}")
        source = str(candidate.get("source_file") or "")
        if key in expected_sha and candidate.get("source_file_sha256") != expected_sha[key]:
            failures.append(f"substrate_source_checksum_mismatch:{key}")
        if not packet.get("evidence_paragraphs") or not source:
            failures.append(f"substrate_packet_missing_evidence:{key}")
        if candidate.get("substrate_fit_label_eligible") is not False:
            failures.append(f"substrate_candidate_positive_flag:{key}")
    decision_keys = set()
    valid_decisions = 0
    for row in decisions:
        key = str(row.get("review_key") or "")
        if not key or key in decision_keys or key not in candidate_by_id:
            failures.append(f"substrate_invalid_or_duplicate_decision:{key}")
            continue
        decision_keys.add(key)
        decision = row.get("decision")
        if decision not in {"approve_reviewed_substrate_identity", "reject_substrate_identity", "needs_more_info"}:
            failures.append(f"substrate_invalid_decision:{key}")
            continue
        if decision == "approve_reviewed_substrate_identity":
            required = ["identity_confirmed", "representation_type", "scope_confirmed", "condition_confirmed", "protocol_version_confirmed", "acceptance_receipt", "review_basis", "reviewer", "reviewed_at"]
            for field in required:
                value = row.get(field)
                if value is False or value is None or value == "":
                    failures.append(f"substrate_approval_missing_{field}:{key}")
            if row.get("representation_type") not in {"single_compound", "process_mixture", "defined_substrate_set"}:
                failures.append(f"substrate_invalid_representation_type:{key}")
            if row.get("representation_type") == "process_mixture" and row.get("substrate_smiles"):
                failures.append(f"substrate_mixture_must_not_invent_smiles:{key}")
        valid_decisions += 1
    return {
        "candidate_rows": len(candidates),
        "packet_rows": len(packets),
        "formal_decision_rows": len(decisions),
        "valid_decision_rows": valid_decisions,
        "approved_decision_rows": sum(1 for row in decisions if row.get("decision") == "approve_reviewed_substrate_identity"),
        "substrate_fit_training_rows_written": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hard-gate review packets")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    failures: list[str] = []
    strict = validate_strict(load_jsonl(STRICT_INPUT), load_jsonl(STRICT_PACKETS), load_jsonl(STRICT_DECISIONS), failures)
    substrate = validate_substrate(load_jsonl(SUBSTRATE_INPUT), load_jsonl(SUBSTRATE_PACKETS), load_jsonl(SUBSTRATE_DECISIONS), failures)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "strict": strict,
        "substrate": substrate,
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "failures": failures,
        "policy": "Empty decision files are valid and remain blocked; approval requires explicit human evidence receipt.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "strict_packet_rows": strict["packet_rows"], "substrate_packet_rows": substrate["packet_rows"], "formal_decision_rows": strict["formal_decision_rows"] + substrate["formal_decision_rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
