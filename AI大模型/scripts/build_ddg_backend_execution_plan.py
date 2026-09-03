#!/usr/bin/env python3
"""Build a fail-closed ddG execution plan for reviewed structures and strict mutations."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
STRUCTURE_MAPPINGS = AI_ROOT / "datasets" / "curation" / "structure_chain_mappings_curated.jsonl"
STRICT_TABLE = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
OUT_JSONL = AI_ROOT / "datasets" / "curation" / "ddg_backend_execution_plan.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "ddg_backend_execution_plan_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def compatible_mutations(structure: dict[str, Any], strict_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accession = structure.get("canonical_uniprot_id") or structure.get("uniprot_id")
    return [
        {
            "record_id": row.get("record_id"),
            "mutation": row.get("mutation"),
            "mutation_position": row.get("mutation_position"),
            "wild_type": row.get("wild_type"),
            "mutant": row.get("mutant"),
            "label_decision": row.get("label_decision"),
        }
        for row in strict_rows
        if row.get("uniprot_id") == accession and row.get("usable_as_supervised_label")
    ]


def selected_backend(readiness: dict[str, Any], requested_backend: str | None = None) -> dict[str, Any]:
    if requested_backend:
        for row in readiness.get("backends", []):
            if row.get("backend") == requested_backend:
                return row
        return {
            "backend": requested_backend,
            "ready_for_execution": False,
            "blockers": [f"requested ddG backend not registered: {requested_backend}"],
        }
    for row in readiness.get("backends", []):
        if row.get("ready_for_execution"):
            return row
    for row in readiness.get("backends", []):
        if row.get("backend") in {"rosetta", "pyrosetta", "foldx"}:
            return row
    return {"backend": "none", "ready_for_execution": False, "blockers": ["no ddG backend registered"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG backend execution plan")
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--structure-mappings", type=Path, default=STRUCTURE_MAPPINGS)
    parser.add_argument("--strict-table", type=Path, default=STRICT_TABLE)
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    parser.add_argument(
        "--backend",
        choices=["rosetta", "pyrosetta", "foldx"],
        help="Build a plan for a specific physical ddG backend. Default keeps the existing automatic selection.",
    )
    args = parser.parse_args()

    readiness = load_json(args.readiness)
    mappings = [row for row in load_jsonl(args.structure_mappings) if row.get("usable_for_coordinate_features")]
    strict_rows = load_jsonl(args.strict_table)
    backend = selected_backend(readiness, args.backend)
    created_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for structure in mappings:
        mutations = compatible_mutations(structure, strict_rows)
        blockers = list(backend.get("blockers") or [])
        if not mutations:
            blockers.append("no strict verified mutation rows currently mapped to this reviewed structure accession")
        status = "ready_to_execute" if backend.get("ready_for_execution") and mutations else "blocked"
        rows.append({
            "plan_id": f"ddg::{structure.get('structure_id')}::{backend.get('backend')}",
            "created_at": created_at,
            "backend": backend.get("backend"),
            "status": status,
            "structure_id": structure.get("structure_id"),
            "structure_path": structure.get("actual_cache_path"),
            "structure_sha256": structure.get("sha256"),
            "uniprot_id": structure.get("canonical_uniprot_id") or structure.get("uniprot_id"),
            "chain_id": structure.get("selected_chain_id"),
            "sequence_to_structure_mapping_status": structure.get("sequence_to_structure_mapping_status"),
            "mutations": mutations,
            "negative_ddg_is_stabilizing": bool(readiness.get("negative_ddg_is_stabilizing", True)),
            "manual_review_required": True,
            "blockers": blockers,
            "expected_artifacts": readiness.get("artifact_requirements", []),
            "policy": "Execution plan only. Do not claim ddG execution until a ready backend produces ddG artifacts with checksums.",
        })
    write_jsonl(args.output_jsonl, rows)
    ready_rows = sum(1 for row in rows if row["status"] == "ready_to_execute")
    report = {
        "created_at": created_at,
        "local_only": True,
        "plan_rows": len(rows),
        "ready_rows": ready_rows,
        "blocked_rows": len(rows) - ready_rows,
        "selected_backend": backend.get("backend"),
        "requested_backend": args.backend,
        "backend_selection_mode": "requested" if args.backend else "automatic",
        "one_ddg_backend_ready": bool(readiness.get("one_ddg_backend_ready")),
        "executable_ddg_backend_ready": bool(readiness.get("executable_ddg_backend_ready")),
        "output_jsonl": str(args.output_jsonl),
        "safe_for_model_claim": False,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "plan_rows": report["plan_rows"],
        "ready_rows": report["ready_rows"],
        "blocked_rows": report["blocked_rows"],
        "selected_backend": report["selected_backend"],
        "one_ddg_backend_ready": report["one_ddg_backend_ready"],
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
