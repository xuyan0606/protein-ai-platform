#!/usr/bin/env python3
"""Build the fail-closed evidence intake contract for CM5 L262V adjudication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ADJUDICATION_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"
MARKDOWN_OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_20260807.md"
BASE = "datasets/source_drops/stage25/42235695/cm5_l262v_adjudication"
SLOTS = [
    {
        "slot_id": "cm5_codon262_primary_raw_trace",
        "evidence_class": "raw_chromatogram",
        "canonical_path": f"{BASE}/cm5_codon262_primary_trace.ab1",
        "allowed_extensions": [".ab1", ".abi", ".scf"],
        "supports_options": ["confirm_L262V_in_CM5_construct", "reject_L262V_as_sequence_artifact"],
        "review_requirement": "reviewed trace peaks and per-base quality at CM5 codon 262",
    },
    {
        "slot_id": "cm5_independent_resequencing",
        "evidence_class": "independent_cm5_resequencing_with_quality",
        "canonical_path": f"{BASE}/cm5_independent_resequencing.fastq",
        "allowed_extensions": [".fastq", ".fq"],
        "supports_options": ["confirm_L262V_in_CM5_construct", "reject_L262V_as_sequence_artifact"],
        "review_requirement": "reviewed independent CM5 clone identity, codon-262 call, and quality scores",
    },
    {
        "slot_id": "cm5_complete_construct_record",
        "evidence_class": "complete_construct_record",
        "canonical_path": f"{BASE}/cm5_complete_construct_record.pdf",
        "allowed_extensions": [".pdf"],
        "supports_options": ["confirm_L262V_in_CM5_construct", "reject_L262V_as_sequence_artifact", "confirm_construct_or_model_version_mismatch"],
        "review_requirement": "reviewed complete CM5 composition and construct provenance",
    },
    {
        "slot_id": "cm5_sequence_pdb_version_reconciliation",
        "evidence_class": "sequence_pdb_version_reconciliation",
        "canonical_path": f"{BASE}/cm5_sequence_pdb_version_reconciliation.md",
        "allowed_extensions": [".md"],
        "supports_options": ["confirm_L262V_in_CM5_construct", "reject_L262V_as_sequence_artifact", "confirm_construct_or_model_version_mismatch"],
        "review_requirement": "reviewed linkage among sequence read, physical construct, and PDB model versions",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_rows() -> list[dict[str, Any]]:
    adjudication = json.loads(ADJUDICATION_VALIDATION.read_text(encoding="utf-8"))
    if adjudication.get("packet_valid") is not True or adjudication.get("discrepancy_resolved") is not False:
        raise ValueError("P281 adjudication packet must be valid and unresolved")
    rows = []
    for slot in SLOTS:
        path = AI_ROOT / slot["canonical_path"]
        exists = path.is_file()
        rows.append({
            **slot,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else None,
            "sha256": sha256_file(path) if exists else None,
            "intake_status": "present_unreviewed" if exists else "missing",
            "format_review_completed": False,
            "integrity_review_completed": False,
            "reviewed_source_locator": "",
            "reviewer": "",
            "reviewed_at": "",
            "reviewed_evidence": False,
            "file_presence_is_reviewed_evidence": False,
            "ready_for_adjudication": False,
            "ready_for_reviewed_extraction": False,
            "ready_for_sqlite_apply": False,
            "external_sqlite_mutated": False,
            "formal_decision_rows_written": 0,
            "apply_executed": False,
            "export_safe_released": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })
    return rows


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CM5 L262V Adjudication Evidence Intake",
        "",
        "File presence is inventory evidence only. It is not format review, scientific review, adjudication, reviewed extraction, or SQLite approval.",
        "",
        "| Slot | Evidence class | Canonical path | Status | Reviewed | Adjudication-ready |",
        "|---|---|---|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['slot_id']}` | `{row['evidence_class']}` | `{row['canonical_path']}` | `{row['intake_status']}` | `{str(row['reviewed_evidence']).lower()}` | `{str(row['ready_for_adjudication']).lower()}` |"
        )
    lines.extend([
        "",
        f"Present rows: `{sum(row['exists'] for row in rows)}`",
        f"Missing rows: `{sum(not row['exists'] for row in rows)}`",
        "Reviewed evidence rows: `0`",
        "Adjudication-ready rows: `0`",
        "",
        "`file_presence_is_reviewed_evidence=false`; `discrepancy_resolved=false`; `ready_for_sqlite_apply=false`; `apply_executed=false`; `safe_for_model_claim=false`; `release_ready=false`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    rows = build_rows()
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(build_markdown(rows), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "markdown_output": str(MARKDOWN_OUTPUT),
        "slot_rows": len(rows),
        "present_rows": sum(row["exists"] for row in rows),
        "missing_rows": sum(not row["exists"] for row in rows),
        "reviewed_evidence_rows": 0,
        "ready_for_adjudication_rows": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
