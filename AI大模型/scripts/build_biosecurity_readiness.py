#!/usr/bin/env python3
"""Build local biosecurity/order-output readiness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "biosecurity_readiness_report.json"
DECISION_VALIDATION = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"

STATE_MACHINE = [
    "not_requested",
    "screening_required",
    "screening_pending",
    "screening_denied",
    "screening_granted",
    "manual_exemption_required",
    "approved_for_ordering",
]


ORDER_APPROVAL_KEYS = {
    "approved_for_ordering",
    "approved_for_synthesis",
    "order_ready",
    "ready_for_ordering",
}
ORDER_PAYLOAD_KEYS = {
    "order_items",
    "order_payload",
    "provider_order_id",
    "synthesis_payload",
    "synthesis_request",
}
NUCLEOTIDE_PAYLOAD_KEYS = {
    "codon_optimized_sequence",
    "construct_sequence",
    "dna_sequence",
    "nucleotide_sequence",
    "rna_sequence",
}
EXPLICIT_ORDER_NAME_TOKENS = {
    "construct_order",
    "dna_order",
    "gene_order",
    "oligo_order",
    "order_payload",
    "rna_order",
    "sequence_order",
    "synthesis_order",
}


def load_payload(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def walk_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_objects(nested)


def nonempty(value: Any) -> bool:
    return value not in (None, False, "", [], {})


def order_artifact_reasons(path: Path) -> list[str]:
    explicit_name = any(token in path.name.casefold() for token in EXPLICIT_ORDER_NAME_TOKENS)
    try:
        payload = load_payload(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["explicit_order_artifact_unparseable"] if explicit_name else []

    reasons: set[str] = set()
    for row in walk_objects(payload):
        approval_keys = sorted(key for key in ORDER_APPROVAL_KEYS if row.get(key) is True)
        payload_keys = sorted(key for key in ORDER_PAYLOAD_KEYS if key in row and nonempty(row.get(key)))
        nucleotide_keys = sorted(key for key in NUCLEOTIDE_PAYLOAD_KEYS if key in row and nonempty(row.get(key)))
        if approval_keys:
            reasons.add(f"ordering_approval_true:{','.join(approval_keys)}")
        if payload_keys:
            reasons.add(f"order_payload_present:{','.join(payload_keys)}")
        if nucleotide_keys and (explicit_name or approval_keys or payload_keys):
            reasons.add(f"ordering_nucleotide_payload_present:{','.join(nucleotide_keys)}")
    return sorted(reasons)


def suspicious_order_artifacts(roots: list[Path] | None = None) -> list[dict[str, Any]]:
    scan_roots = roots or [AI_ROOT / "datasets", AI_ROOT / "reports", AI_ROOT / "prototype"]
    rows: list[dict[str, Any]] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for path in sorted([*root.rglob("*.json"), *root.rglob("*.jsonl")]):
            reasons = order_artifact_reasons(path)
            if not reasons:
                continue
            try:
                relative_path = str(path.relative_to(AI_ROOT))
            except ValueError:
                relative_path = str(path)
            rows.append({"path": relative_path, "reasons": reasons})
    return rows


def suspicious_order_files() -> list[str]:
    return [row["path"] for row in suspicious_order_artifacts()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build biosecurity readiness report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    order_artifacts = suspicious_order_artifacts()
    order_like_files = [row["path"] for row in order_artifacts]
    decision_validation = load_json(DECISION_VALIDATION)
    approved_rows = decision_validation.get("approved_for_ordering_rows", 0)
    ready_for_ordering = bool(decision_validation.get("ready_for_ordering")) and not order_like_files
    blockers = []
    if order_like_files:
        blockers.append("order-ready output-like files exist and require review/removal")
    if not decision_validation.get("ready_for_ordering"):
        blockers.append("biosecurity screening decision validation is not ready")
    report = {
        "local_only": True,
        "state_machine": STATE_MACHINE,
        "state_machine_ready": True,
        "default_state": "not_requested",
        "approved_for_ordering_requires": [
            "screening provider/reference",
            "sequence screening pass",
            "customer/use approval",
            "intended use statement",
            "human reviewer decision",
        ],
        "order_ready_outputs_detected": len(order_like_files),
        "order_ready_output_files": order_like_files,
        "order_ready_output_artifacts": order_artifacts,
        "decision_validation_ready": decision_validation.get("ready_for_ordering"),
        "decision_rows": decision_validation.get("decision_rows", 0),
        "valid_decision_rows": decision_validation.get("valid_rows", 0),
        "invalid_decision_rows": decision_validation.get("invalid_rows", 0),
        "approved_for_ordering_rows": approved_rows,
        "ready_for_ordering": ready_for_ordering,
        "blockers": blockers,
        "policy": "KWB may emit design_candidate internally, but must not emit order-ready DNA/RNA/construct payloads in this stage.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready_for_ordering": ready_for_ordering, "order_ready_outputs_detected": len(order_like_files), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
