#!/usr/bin/env python3
"""Validate the field-level source extraction reviewer closure checklist."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets/governance/stage25_source_extraction_reviewer_closure_checklist_20260807.jsonl"
PACKET = AI_ROOT / "datasets/governance/stage25_source_extraction_candidate_reviewer_packet_20260807.jsonl"
PACKET_VALIDATION = AI_ROOT / "reports/stage25_source_extraction_candidate_reviewer_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_source_extraction_reviewer_closure_checklist_validation_20260807.json"
NEGATIVE_FLAGS = (
    "completed",
    "approved",
    "reviewed_source_locator_present",
    "ready_for_reviewed_extraction",
    "ready_for_sqlite_apply",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("checklist", CHECKLIST), ("packet", PACKET), ("packet_validation", PACKET_VALIDATION)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    checklist = load_jsonl(CHECKLIST) if CHECKLIST.is_file() else []
    packets = load_jsonl(PACKET) if PACKET.is_file() else []
    packet_validation = load_json(PACKET_VALIDATION) if PACKET_VALIDATION.is_file() else {}

    expected_fields = [
        (str(packet.get("packet_id")), str(packet.get("pmid")), str(packet.get("target")), str(field))
        for packet in packets
        for field in (packet.get("required_review_fields") or [])
    ]
    observed_fields = [
        (str(row.get("packet_id")), str(row.get("pmid")), str(row.get("target")), str(row.get("required_review_field")))
        for row in checklist
    ]
    fail_if(packet_validation.get("reviewer_packet_valid") is not True, failures, "reviewer_packet_valid", packet_validation.get("reviewer_packet_valid"), True)
    fail_if(packet_validation.get("required_review_field_rows") != 12, failures, "packet_required_review_field_rows", packet_validation.get("required_review_field_rows"), 12)
    fail_if(packet_validation.get("cm5_composition_ambiguous_rows") != 1, failures, "cm5_composition_ambiguous_rows", packet_validation.get("cm5_composition_ambiguous_rows"), 1)
    fail_if(packet_validation.get("nucleotide_pdb_discrepancy_rows") != 1, failures, "cm5_nucleotide_pdb_discrepancy_rows", packet_validation.get("nucleotide_pdb_discrepancy_rows"), 1)
    fail_if(len(checklist) != 12, failures, "checklist_rows", len(checklist), 12)
    fail_if(observed_fields != expected_fields, failures, "required_fields_exact_order", observed_fields, expected_fields)
    fail_if(len(set(observed_fields)) != 12, failures, "unique_required_fields", len(set(observed_fields)), 12)

    for index, row in enumerate(checklist, 1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("completion_status") != "missing", failures, f"{prefix}.completion_status", row.get("completion_status"), "missing")
        fail_if(row.get("review_decision") != "needs_more_info", failures, f"{prefix}.review_decision", row.get("review_decision"), "needs_more_info")
        fail_if(row.get("source_locator") != "", failures, f"{prefix}.source_locator_empty", row.get("source_locator"), "")
        for field in ("reviewer", "reviewed_at", "review_notes"):
            fail_if(row.get(field) != "", failures, f"{prefix}.{field}_empty", row.get(field), "")
        fail_if(not isinstance(row.get("current_candidate_evidence"), list) or not row.get("current_candidate_evidence"), failures, f"{prefix}.current_candidate_evidence", row.get("current_candidate_evidence"), "non-empty list")
        fail_if(not isinstance(row.get("closure_evidence_required"), list) or not row.get("closure_evidence_required"), failures, f"{prefix}.closure_evidence_required", row.get("closure_evidence_required"), "non-empty list")
        fail_if(not str(row.get("evidence_class") or ""), failures, f"{prefix}.evidence_class", row.get("evidence_class"), "non-empty")
        for flag in NEGATIVE_FLAGS:
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)

    target_counts = Counter(str(row.get("target")) for row in checklist)
    report = {
        "schema_version": 1,
        "mode": "stage25_source_extraction_reviewer_closure_checklist_validation",
        "stage": 25,
        "checklist_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "checklist_rows": len(checklist),
        "unique_check_rows": len(set(observed_fields)),
        "dsm4_rows": target_counts.get("DSM4", 0),
        "cm5_rows": target_counts.get("CM5", 0),
        "cm5_l262v_discrepancy_rows": sum(row.get("required_review_field") == "resolve_L262V_nucleotide_PDB_discrepancy" for row in checklist),
        "missing_rows": sum(row.get("completion_status") == "missing" for row in checklist),
        "needs_more_info_rows": sum(row.get("review_decision") == "needs_more_info" for row in checklist),
        "evidence_supplied_rows": 0,
        "reviewed_rows": 0,
        "completed_rows": 0,
        "reviewer_filled_rows": 0,
        "source_locator_rows": 0,
        "approved_rows": 0,
        "ready_for_reviewed_extraction_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "checklist_sha256": sha256(CHECKLIST) if CHECKLIST.is_file() else None,
        "packet_sha256": sha256(PACKET) if PACKET.is_file() else None,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Field-level reviewer closure checklist only. Missing needs_more_info rows do not create reviewed evidence, formal decisions, SQLite approval, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "checklist_valid": report["checklist_valid"], "failure_count": report["failure_count"], "checklist_rows": report["checklist_rows"], "completed_rows": report["completed_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["checklist_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
