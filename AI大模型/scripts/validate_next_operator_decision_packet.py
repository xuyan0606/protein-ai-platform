#!/usr/bin/env python3
"""Validate the local next-operator decision packet.

This validator is intentionally read-only. It checks that the packet points to
real local review packets, decision templates, decision files, and validators,
while preserving fail-closed wording.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "reports" / "next_operator_decision_packet_20260805.md"
REPORT_OUT = AI_ROOT / "reports" / "next_operator_decision_packet_validation_report.json"

REQUIRED_PATHS = [
    "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl",
    "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl",
    "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.template.jsonl",
    "datasets/curation/substrate_identity_review_packets.jsonl",
    "datasets/curation/substrate_identity_review_decisions.jsonl",
    "datasets/curation/substrate_identity_review_decisions.template.jsonl",
    "datasets/curation/numbering_curation_decisions.jsonl",
    "datasets/feedback/experiment_feedback_plate.local.jsonl",
    "datasets/governance/external_license_review_decisions.jsonl",
    "datasets/governance/biosecurity_screening_decisions.jsonl",
    "datasets/governance/sequence_ip_fto_decisions.jsonl",
    "datasets/governance/workstream_acceptance_decisions.jsonl",
    "datasets/governance/operator_review_action_decisions.jsonl",
    "reports/hard_gate_decision_benchmark_bridge_report.json",
    "reports/hard_gate_decision_benchmark_bridge_validation_report.json",
    "reports/benchmark_readiness_packets.md",
    "reports/benchmark_hard_gate_operator_packets.md",
]

REQUIRED_VALIDATORS = [
    "scripts/validate_hard_gate_review_packets.py",
    "scripts/build_hard_gate_decision_benchmark_bridge.py",
    "scripts/validate_hard_gate_decision_benchmark_bridge.py",
    "scripts/validate_benchmark_readiness_packet.py",
    "scripts/validate_numbering_curation_decisions.py",
    "scripts/validate_external_license_review_decisions.py",
    "scripts/validate_biosecurity_screening_decisions.py",
    "scripts/validate_sequence_ip_fto_decisions.py",
    "scripts/validate_workstream_acceptance_decisions.py",
    "scripts/validate_operator_review_action_decisions.py",
    "scripts/validate_claim_readiness_matrix_fail_closed_policy.py",
    "scripts/validate_local_release_manifest_fail_closed_consistency.py",
    "scripts/validate_no_review_draft_training_leakage.py",
    "scripts/validate_benchmark_score_cache.py",
]

REQUIRED_TERMS = [
    "local-only operator packet",
    "does not approve",
    "does not approve, reject, unlock",
    "Do not copy template rows",
    "Do not use draft packets",
    "Do not invent SMILES",
    "Do not promote PyRosetta/Rosetta smoke results",
    "Do not mark `safe_for_model_claim`, `customer_ready`, or `release_ready` true",
    "Only complete formal decisions with receipts may flow through the bridge",
]

STRICT_REVIEW_KEYS = [
    "kwb_venus15b_strict_candidate::D105N",
    "kwb_venus15b_strict_candidate::E331Q",
    "kwb_venus15b_strict_candidate::S265T",
]

STRICT_ALLOWED_DECISIONS = [
    "approve_strict_holdout",
    "reject_candidate",
    "needs_more_info",
]

SUBSTRATE_ALLOWED_DECISIONS = [
    "approve_reviewed_substrate_identity",
    "reject_substrate_identity",
    "needs_more_info",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def file_exists(rel_path: str) -> bool:
    return (AI_ROOT / rel_path).exists()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local next operator decision packet")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    packet_text = args.packet.read_text(encoding="utf-8") if args.packet.exists() else ""
    strict_packets = load_jsonl(AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_packets.jsonl")
    substrate_packets = load_jsonl(AI_ROOT / "datasets" / "curation" / "substrate_identity_review_packets.jsonl")

    strict_keys = sorted(str(row.get("review_key")) for row in strict_packets if row.get("review_key"))
    substrate_identities = sorted({
        str(row.get("substrate_identity_normalized"))
        for row in substrate_packets
        if row.get("substrate_identity_normalized")
    })
    missing_paths = [path for path in REQUIRED_PATHS if not file_exists(path)]
    missing_validators = [path for path in REQUIRED_VALIDATORS if not file_exists(path)]
    missing_terms = [term for term in REQUIRED_TERMS if term not in packet_text]
    missing_strict_keys = [key for key in STRICT_REVIEW_KEYS if key not in packet_text]
    missing_strict_decisions = [value for value in STRICT_ALLOWED_DECISIONS if value not in packet_text]
    missing_substrate_decisions = [value for value in SUBSTRATE_ALLOWED_DECISIONS if value not in packet_text]

    checks = [
        check("packet exists", args.packet.exists(), rel(args.packet), "existing markdown packet"),
        check("required local paths exist", not missing_paths, missing_paths, []),
        check("required validators exist", not missing_validators, missing_validators, []),
        check("strict packet rows remain 3", len(strict_packets) == 3, len(strict_packets), 3),
        check("strict review keys are listed", not missing_strict_keys, missing_strict_keys, []),
        check("strict allowed decisions are listed", not missing_strict_decisions, missing_strict_decisions, []),
        check("substrate packet rows remain 9", len(substrate_packets) == 9, len(substrate_packets), 9),
        check("substrate identities are listed", set(substrate_identities) == {"corn_whole_flour", "starch_slurry"}, substrate_identities, ["corn_whole_flour", "starch_slurry"]),
        check("substrate allowed decisions are listed", not missing_substrate_decisions, missing_substrate_decisions, []),
        check("fail-closed policy terms are present", not missing_terms, missing_terms, []),
        check("packet does not contain readiness unlock", "release_ready=true" not in packet_text and "safe_for_model_claim=true" not in packet_text, "no true readiness flags", "no true readiness flags"),
    ]
    failures = [item for item in checks if not item["passed"]]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet": rel(args.packet),
        "success": not failures,
        "checks": checks,
        "failures": failures,
        "strict_review_packet_rows": len(strict_packets),
        "strict_review_keys": strict_keys,
        "substrate_review_packet_rows": len(substrate_packets),
        "substrate_identities": substrate_identities,
        "safe_for_model_claim": False,
        "customer_ready": False,
        "release_ready": False,
        "policy": "Validation only. This report does not create decisions, approve benchmarks, unlock claims, approve customer delivery, or authorize release.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "success": report["success"],
        "failures": len(failures),
        "strict_review_packet_rows": len(strict_packets),
        "substrate_review_packet_rows": len(substrate_packets),
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
