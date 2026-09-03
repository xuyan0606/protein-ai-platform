#!/usr/bin/env python3
"""Validate local CM5 L262V adjudication decisions without applying them."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_decisions.local.json"
PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.jsonl"
PACKET_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"
REVIEW_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_reviews.local.json"
RECEIPT_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json"
REVIEW_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_review_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_decision_intake_validation_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"
ALLOWED_DECISIONS = [
    "needs_more_info",
    "confirm_L262V_in_CM5_construct",
    "reject_L262V_as_sequence_artifact",
    "confirm_construct_or_model_version_mismatch",
]
REQUIRED_EVIDENCE_CLASSES = {
    "needs_more_info": set(),
    "confirm_L262V_in_CM5_construct": {
        "raw_trace_or_independent_resequencing",
        "complete_construct_record",
        "sequence_pdb_reconciliation",
    },
    "reject_L262V_as_sequence_artifact": {
        "raw_trace_or_independent_resequencing",
        "sequence_pdb_reconciliation",
    },
    "confirm_construct_or_model_version_mismatch": {
        "version_provenance",
        "complete_composition_decision",
    },
}
SLOT_ALLOWED_EVIDENCE_CLASSES = {
    "cm5_codon262_primary_raw_trace": {"raw_trace_or_independent_resequencing"},
    "cm5_independent_resequencing": {"raw_trace_or_independent_resequencing"},
    "cm5_complete_construct_record": {"complete_construct_record", "complete_composition_decision"},
    "cm5_sequence_pdb_version_reconciliation": {"sequence_pdb_reconciliation", "version_provenance"},
}
NEGATIVE_DECISION_FLAGS = (
    "formal_decision_authorized",
    "discrepancy_resolved",
    "complete_composition_unambiguous",
    "reviewed_extraction_completed",
    "ready_for_sqlite_apply",
    "apply_executed",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number} must contain an object")
        rows.append(value)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (
        ("input", INPUT),
        ("packet", PACKET),
        ("packet_validation", PACKET_VALIDATION),
        ("review_input", REVIEW_INPUT),
        ("receipt_input", RECEIPT_INPUT),
        ("review_validation", REVIEW_VALIDATION),
    ):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")

    intake = load_json(INPUT) if INPUT.is_file() else {}
    packet_rows = load_jsonl(PACKET) if PACKET.is_file() else []
    packet_validation = load_json(PACKET_VALIDATION) if PACKET_VALIDATION.is_file() else {}
    review_validation = load_json(REVIEW_VALIDATION) if REVIEW_VALIDATION.is_file() else {}
    packet = packet_rows[0] if len(packet_rows) == 1 else {}
    decisions = intake.get("decisions") if isinstance(intake.get("decisions"), list) else []

    fail_if(intake.get("schema_version") != 1, failures, "schema_version", intake.get("schema_version"), 1)
    fail_if(intake.get("mode") != "stage25_cm5_l262v_adjudication_decision_intake", failures, "mode", intake.get("mode"), "stage25_cm5_l262v_adjudication_decision_intake")
    fail_if(intake.get("stage") != 25, failures, "stage", intake.get("stage"), 25)
    fail_if(intake.get("packet_id") != PACKET_ID, failures, "packet_id", intake.get("packet_id"), PACKET_ID)
    fail_if(not isinstance(intake.get("decisions"), list), failures, "decisions_list", type(intake.get("decisions")).__name__, "list")
    fail_if(len(decisions) > 1, failures, "decision_rows_max_one", len(decisions), "<=1")
    fail_if(len(packet_rows) != 1, failures, "packet_rows", len(packet_rows), 1)
    fail_if(packet.get("packet_id") != PACKET_ID, failures, "upstream_packet_id", packet.get("packet_id"), PACKET_ID)
    fail_if(packet_validation.get("packet_valid") is not True, failures, "upstream_packet_valid", packet_validation.get("packet_valid"), True)
    fail_if(packet_validation.get("review_fields_empty") is not True, failures, "upstream_review_fields_empty", packet_validation.get("review_fields_empty"), True)
    fail_if(review_validation.get("intake_valid") is not True, failures, "upstream_review_intake_valid", review_validation.get("intake_valid"), True)
    live_review_input_sha = sha256_file(REVIEW_INPUT) if REVIEW_INPUT.is_file() else None
    live_receipt_input_sha = sha256_file(RECEIPT_INPUT) if RECEIPT_INPUT.is_file() else None
    fail_if(review_validation.get("review_input_sha256") != live_review_input_sha, failures, "upstream_review_input_sha256_live", review_validation.get("review_input_sha256"), live_review_input_sha)
    fail_if(review_validation.get("receipt_input_sha256") != live_receipt_input_sha, failures, "upstream_receipt_input_sha256_live", review_validation.get("receipt_input_sha256"), live_receipt_input_sha)
    accepted_reviews = {
        str(row.get("review_id")): row
        for row in review_validation.get("records", [])
        if isinstance(row, dict)
        and row.get("valid") is True
        and row.get("scientific_sufficiency") == "accepted_for_adjudication"
    }
    packet_options = [item.get("decision") for item in packet.get("allowed_adjudication_options", []) if isinstance(item, dict)]
    fail_if(packet_options != ALLOWED_DECISIONS, failures, "allowed_decisions_match_packet", packet_options, ALLOWED_DECISIONS)

    valid_decision_rows = 0
    needs_more_info_rows = 0
    non_needs_more_info_candidate_rows = 0
    evidence_artifact_rows = 0
    review_bound_evidence_rows = 0
    unreviewed_evidence_artifact_rows = 0
    slot_compatible_evidence_rows = 0
    slot_incompatible_evidence_rows = 0
    reviewer_bound_evidence_rows = 0
    missing_review_reviewer_rows = 0
    for index, decision in enumerate(decisions, 1):
        prefix = f"decisions[{index}]"
        before = len(failures)
        fail_if(not isinstance(decision, dict), failures, f"{prefix}.object", decision, "object")
        if not isinstance(decision, dict):
            continue
        expected_keys = {
            "decision_id",
            "packet_id",
            "adjudication_decision",
            "reviewer",
            "reviewed_at",
            "reviewed_source_locator",
            "decision_basis",
            "review_notes",
            "evidence_artifacts",
            "formal_decision_authorized",
            "discrepancy_resolved",
            "complete_composition_unambiguous",
            "reviewed_extraction_completed",
            "ready_for_sqlite_apply",
            "apply_executed",
            "safe_for_model_claim",
            "release_ready",
        }
        fail_if(set(decision) != expected_keys, failures, f"{prefix}.keys_exact", sorted(decision), sorted(expected_keys))
        fail_if(not str(decision.get("decision_id") or "").strip(), failures, f"{prefix}.decision_id", decision.get("decision_id"), "non-empty")
        fail_if(decision.get("packet_id") != PACKET_ID, failures, f"{prefix}.packet_id", decision.get("packet_id"), PACKET_ID)
        outcome = decision.get("adjudication_decision")
        fail_if(outcome not in ALLOWED_DECISIONS, failures, f"{prefix}.adjudication_decision", outcome, ALLOWED_DECISIONS)
        for field in ("reviewer", "reviewed_at", "reviewed_source_locator", "decision_basis"):
            fail_if(not str(decision.get(field) or "").strip(), failures, f"{prefix}.{field}", decision.get(field), "non-empty")
        fail_if(not valid_utc_timestamp(decision.get("reviewed_at")), failures, f"{prefix}.reviewed_at_utc", decision.get("reviewed_at"), "ISO-8601 UTC timestamp ending in Z")
        evidence = decision.get("evidence_artifacts") if isinstance(decision.get("evidence_artifacts"), list) else []
        fail_if(not isinstance(decision.get("evidence_artifacts"), list), failures, f"{prefix}.evidence_artifacts_list", type(decision.get("evidence_artifacts")).__name__, "list")
        evidence_artifact_rows += len(evidence)
        observed_classes: set[str] = set()
        seen_review_ids: set[str] = set()
        for evidence_index, artifact in enumerate(evidence, 1):
            evidence_prefix = f"{prefix}.evidence_artifacts[{evidence_index}]"
            fail_if(not isinstance(artifact, dict), failures, f"{evidence_prefix}.object", artifact, "object")
            if not isinstance(artifact, dict):
                continue
            fail_if(set(artifact) != {"evidence_class", "relative_path", "review_id", "sha256"}, failures, f"{evidence_prefix}.keys_exact", sorted(artifact), ["evidence_class", "relative_path", "review_id", "sha256"])
            evidence_class = str(artifact.get("evidence_class") or "")
            observed_classes.add(evidence_class)
            review_id = str(artifact.get("review_id") or "")
            accepted_review = accepted_reviews.get(review_id)
            fail_if(not review_id or accepted_review is None, failures, f"{evidence_prefix}.accepted_review_id", review_id, "P295 valid accepted_for_adjudication review_id")
            fail_if(review_id in seen_review_ids, failures, f"{evidence_prefix}.review_id_unique", review_id, "unique review_id within decision")
            seen_review_ids.add(review_id)
            relative_path = Path(str(artifact.get("relative_path") or ""))
            safe_relative = bool(str(relative_path)) and not relative_path.is_absolute() and ".." not in relative_path.parts
            fail_if(not safe_relative, failures, f"{evidence_prefix}.safe_relative_path", str(relative_path), "non-empty relative path without ..")
            path = AI_ROOT / relative_path if safe_relative else AI_ROOT / "__invalid__"
            present = path.is_file()
            current_sha = sha256_file(path) if present else None
            fail_if(not present, failures, f"{evidence_prefix}.present", str(path), "present file")
            fail_if(current_sha != artifact.get("sha256"), failures, f"{evidence_prefix}.sha256_live", current_sha, artifact.get("sha256"))
            if accepted_review is not None:
                fail_if(str(relative_path) != accepted_review.get("canonical_path"), failures, f"{evidence_prefix}.relative_path_review_match", str(relative_path), accepted_review.get("canonical_path"))
                fail_if(artifact.get("sha256") != accepted_review.get("artifact_sha256"), failures, f"{evidence_prefix}.sha256_review_match", artifact.get("sha256"), accepted_review.get("artifact_sha256"))
                supported_options = accepted_review.get("supports_adjudication_options")
                fail_if(not isinstance(supported_options, list) or outcome not in supported_options, failures, f"{evidence_prefix}.review_supports_decision", outcome, supported_options)
                slot_id = str(accepted_review.get("slot_id") or "")
                allowed_evidence_classes = SLOT_ALLOWED_EVIDENCE_CLASSES.get(slot_id, set())
                slot_compatible = evidence_class in allowed_evidence_classes
                fail_if(not slot_compatible, failures, f"{evidence_prefix}.evidence_class_slot_compatible", evidence_class, sorted(allowed_evidence_classes))
                slot_compatible_evidence_rows += int(slot_compatible)
                slot_incompatible_evidence_rows += int(not slot_compatible)
                evidence_reviewer = str(accepted_review.get("reviewer") or "").strip()
                fail_if(not evidence_reviewer, failures, f"{evidence_prefix}.reviewer_provenance", accepted_review.get("reviewer"), "non-empty P295 reviewer")
                reviewer_bound_evidence_rows += int(bool(evidence_reviewer))
                missing_review_reviewer_rows += int(not evidence_reviewer)
                review_bound_evidence_rows += 1
            else:
                unreviewed_evidence_artifact_rows += 1
        required_classes = REQUIRED_EVIDENCE_CLASSES.get(str(outcome), set())
        fail_if(not required_classes.issubset(observed_classes), failures, f"{prefix}.required_evidence_classes", sorted(observed_classes), sorted(required_classes))
        for field in NEGATIVE_DECISION_FLAGS:
            fail_if(decision.get(field) is not False, failures, f"{prefix}.{field}_false", decision.get(field), False)
        if len(failures) == before:
            valid_decision_rows += 1
            needs_more_info_rows += outcome == "needs_more_info"
            non_needs_more_info_candidate_rows += outcome != "needs_more_info"

    policy = str(intake.get("policy") or "")
    for term in ("Empty decisions", "formal review", "SQLite", "release"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_decision_intake_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "decision_rows": len(decisions),
        "valid_decision_rows": valid_decision_rows,
        "invalid_decision_rows": len(decisions) - valid_decision_rows,
        "needs_more_info_rows": needs_more_info_rows,
        "non_needs_more_info_candidate_rows": non_needs_more_info_candidate_rows,
        "evidence_artifact_rows": evidence_artifact_rows,
        "accepted_review_rows": len(accepted_reviews),
        "review_bound_evidence_rows": review_bound_evidence_rows,
        "unreviewed_evidence_artifact_rows": unreviewed_evidence_artifact_rows,
        "review_binding_valid": unreviewed_evidence_artifact_rows == 0,
        "slot_compatible_evidence_rows": slot_compatible_evidence_rows,
        "slot_incompatible_evidence_rows": slot_incompatible_evidence_rows,
        "slot_binding_valid": slot_incompatible_evidence_rows == 0,
        "reviewer_bound_evidence_rows": reviewer_bound_evidence_rows,
        "missing_review_reviewer_rows": missing_review_reviewer_rows,
        "reviewer_provenance_valid": missing_review_reviewer_rows == 0,
        "formal_decision_rows_written": 0,
        "discrepancy_resolved_rows": 0,
        "complete_composition_unambiguous_rows": 0,
        "reviewed_extraction_completed_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Decision intake validation only. Valid rows remain candidates for separate formal review and cannot directly resolve the discrepancy, mutate SQLite, open claims, or release artifacts.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "intake_valid": report["intake_valid"],
        "failure_count": report["failure_count"],
        "decision_rows": report["decision_rows"],
        "valid_decision_rows": report["valid_decision_rows"],
        "discrepancy_resolved_rows": report["discrepancy_resolved_rows"],
    }, sort_keys=True))
    return 0 if report["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
