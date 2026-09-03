#!/usr/bin/env python3
"""Build fail-closed unlock checklist for split human target source manifests."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index.json"
OUT = AI_ROOT / "datasets" / "governance" / "human_target_source_unlock_checklist.jsonl"
REPORT = AI_ROOT / "reports" / "human_target_source_unlock_checklist_report.json"


COMMON_STEPS = [
    "source_manifest_with_version",
    "license_scope_reviewed",
    "checksum_or_runtime_receipt_present",
    "schema_mapping_validator_passed",
    "claim_boundary_reviewed",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_checklist(
    index_path: Path = INDEX,
    output_path: Path = OUT,
    report_created_at: str | None = None,
    row_created_at: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = load_json(index_path)
    rows: list[dict[str, Any]] = []
    for item in index.get("source_manifest_index") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        checklist_id = f"human-target-source-unlock-{source_id}"
        steps = list(COMMON_STEPS)
        if source_id == "anarci_imgt_runtime":
            steps.append("numbering_runtime_smoke_artifact_present")
        if source_id in {"hpa_expression", "gtex_expression"}:
            steps.append("rna_protein_expression_unit_boundary_reviewed")
        rows.append(
            {
                "checklist_id": checklist_id,
                "source_id": source_id,
                "source_manifest_path": item.get("path"),
                "current_status": "blocked",
                "required_steps": steps,
                "completed_steps": [],
                "missing_steps": steps,
                "ready_to_unlock": False,
                "claim_eligible": False,
                "customer_ready": False,
                "release_ready": False,
                "policy": "Checklist only. Completing it requires reviewed source/runtime evidence; this generated row does not unlock the source.",
                "created_at": (row_created_at or {}).get(source_id) or datetime.now(timezone.utc).isoformat(),
            }
        )
    report = {
        "created_at": report_created_at or datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checklist_rows": len(rows),
        "ready_to_unlock_rows": 0,
        "blocked_rows": len(rows),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(output_path),
        "policy": "Unlock checklist report only; no source is unlocked by this report.",
    }
    return rows, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human target source unlock checklist")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows, report = build_checklist(index_path=args.index, output_path=args.output)
    write_jsonl(args.output, rows)
    write_json(args.report, report)
    print(json.dumps({"success": True, "checklist_rows": len(rows), "ready_to_unlock_rows": 0, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
