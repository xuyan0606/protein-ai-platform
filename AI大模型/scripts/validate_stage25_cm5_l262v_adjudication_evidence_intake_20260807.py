#!/usr/bin/env python3
"""Validate the CM5 L262V evidence intake contract and filesystem parity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INTAKE = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"
MARKDOWN = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_20260807.md"
ADJUDICATION = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"
EXPECTED = [
    ("cm5_codon262_primary_raw_trace", "raw_chromatogram", "datasets/source_drops/stage25/42235695/cm5_l262v_adjudication/cm5_codon262_primary_trace.ab1"),
    ("cm5_independent_resequencing", "independent_cm5_resequencing_with_quality", "datasets/source_drops/stage25/42235695/cm5_l262v_adjudication/cm5_independent_resequencing.fastq"),
    ("cm5_complete_construct_record", "complete_construct_record", "datasets/source_drops/stage25/42235695/cm5_l262v_adjudication/cm5_complete_construct_record.pdf"),
    ("cm5_sequence_pdb_version_reconciliation", "sequence_pdb_version_reconciliation", "datasets/source_drops/stage25/42235695/cm5_l262v_adjudication/cm5_sequence_pdb_version_reconciliation.md"),
]
NEGATIVE_FLAGS = (
    "format_review_completed",
    "integrity_review_completed",
    "reviewed_evidence",
    "file_presence_is_reviewed_evidence",
    "ready_for_adjudication",
    "ready_for_reviewed_extraction",
    "ready_for_sqlite_apply",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
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
    for path, label in ((INTAKE, "intake"), (MARKDOWN, "markdown"), (ADJUDICATION, "adjudication")):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    rows = load_jsonl(INTAKE) if INTAKE.is_file() else []
    adjudication = load_json(ADJUDICATION) if ADJUDICATION.is_file() else {}
    fail_if(adjudication.get("packet_valid") is not True, failures, "upstream_packet_valid", adjudication.get("packet_valid"), True)
    fail_if(adjudication.get("discrepancy_resolved") is not False, failures, "upstream_discrepancy_unresolved", adjudication.get("discrepancy_resolved"), False)
    fail_if(len(rows) != 4, failures, "slot_rows", len(rows), 4)
    observed_contract = [(row.get("slot_id"), row.get("evidence_class"), row.get("canonical_path")) for row in rows]
    fail_if(observed_contract != EXPECTED, failures, "exact_slot_contract", observed_contract, EXPECTED)
    paths = [str(row.get("canonical_path")) for row in rows]
    fail_if(len(set(paths)) != 4, failures, "unique_canonical_paths", len(set(paths)), 4)

    present_rows = 0
    filesystem_parity_rows = 0
    for index, row in enumerate(rows, 1):
        prefix = f"slots[{index}]"
        path = AI_ROOT / str(row.get("canonical_path"))
        exists = path.is_file()
        size = path.stat().st_size if exists else None
        sha = sha256_file(path) if exists else None
        present_rows += exists
        parity = row.get("exists") is exists and row.get("size_bytes") == size and row.get("sha256") == sha
        filesystem_parity_rows += parity
        fail_if(not parity, failures, f"{prefix}.filesystem_parity", {"exists": row.get("exists"), "size_bytes": row.get("size_bytes"), "sha256": row.get("sha256")}, {"exists": exists, "size_bytes": size, "sha256": sha})
        fail_if(row.get("intake_status") != ("present_unreviewed" if exists else "missing"), failures, f"{prefix}.intake_status", row.get("intake_status"), "present_unreviewed" if exists else "missing")
        fail_if(Path(str(row.get("canonical_path"))).suffix.lower() not in row.get("allowed_extensions", []), failures, f"{prefix}.canonical_extension_allowed", Path(str(row.get("canonical_path"))).suffix.lower(), row.get("allowed_extensions"))
        fail_if(not row.get("review_requirement"), failures, f"{prefix}.review_requirement", row.get("review_requirement"), "non-empty")
        fail_if(not row.get("supports_options"), failures, f"{prefix}.supports_options", row.get("supports_options"), "non-empty")
        fail_if(row.get("reviewed_source_locator") != "", failures, f"{prefix}.reviewed_source_locator_empty", row.get("reviewed_source_locator"), "")
        fail_if(row.get("reviewer") != "", failures, f"{prefix}.reviewer_empty", row.get("reviewer"), "")
        fail_if(row.get("reviewed_at") != "", failures, f"{prefix}.reviewed_at_empty", row.get("reviewed_at"), "")
        for field in NEGATIVE_FLAGS:
            fail_if(row.get(field) is not False, failures, f"{prefix}.{field}_false", row.get(field), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)

    markdown = MARKDOWN.read_text(encoding="utf-8") if MARKDOWN.is_file() else ""
    for _, _, path in EXPECTED:
        fail_if(path not in markdown, failures, f"markdown_contains:{path}", markdown, f"contains {path}")
    for term in ("File presence is inventory evidence only", "Reviewed evidence rows: `0`", "Adjudication-ready rows: `0`", "file_presence_is_reviewed_evidence=false", "discrepancy_resolved=false"):
        fail_if(term not in markdown, failures, f"markdown_contains:{term}", markdown, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_evidence_intake_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "slot_rows": len(rows),
        "unique_path_rows": len(set(paths)),
        "present_rows": present_rows,
        "missing_rows": len(rows) - present_rows,
        "filesystem_parity_rows": filesystem_parity_rows,
        "reviewed_evidence_rows": 0,
        "ready_for_adjudication_rows": 0,
        "ready_for_reviewed_extraction_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "file_presence_is_reviewed_evidence": False,
        "discrepancy_resolved": False,
        "complete_composition_unambiguous": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "intake_valid": report["intake_valid"],
        "failure_count": report["failure_count"],
        "slot_rows": report["slot_rows"],
        "present_rows": report["present_rows"],
        "missing_rows": report["missing_rows"],
        "ready_for_adjudication_rows": report["ready_for_adjudication_rows"],
    }, sort_keys=True))
    return 0 if report["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
