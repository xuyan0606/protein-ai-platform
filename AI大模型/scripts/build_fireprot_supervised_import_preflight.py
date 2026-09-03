#!/usr/bin/env python3
"""Build FireProt supervised-import preflight rows from formal authorization."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "fireprot_supervised_import_authorization_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "curation" / "fireprot_supervised_import_preflight.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_supervised_import_preflight_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt supervised import preflight")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--authorization-report", type=Path, default=AUTH_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    auth_report = load_json(args.authorization_report)
    candidate_by_id = {str(row.get("reviewed_import_candidate_id")): row for row in candidates}
    authorized_ids = set(auth_report.get("authorized_reviewed_import_candidate_ids") or [])

    rows: list[dict[str, Any]] = []
    for candidate_id in sorted(authorized_ids):
        candidate = candidate_by_id.get(candidate_id)
        if not candidate:
            continue
        rows.append({
            "preflight_row_id": f"fireprot-preflight-{candidate_id}",
            "reviewed_import_candidate_id": candidate_id,
            "mutation_key": candidate.get("mutation_key"),
            "uniprot_id": candidate.get("uniprot_id"),
            "mutation": candidate.get("mutation"),
            "label_ddg_kcal_mol": candidate.get("approved_label_ddg_kcal_mol"),
            "source_file_sha256s": candidate.get("source_file_sha256s"),
            "reviewed_import_receipt": candidate.get("reviewed_import_receipt"),
            "ready_for_training_import": False,
            "claim_eligible_now": False,
            "remaining_blockers": [
                "separate_apply_to_supervised_schema_not_executed",
                "model_quality_release_gate_not_approved",
            ],
            "policy": "Preflight row only; not appended to KWB supervised training data.",
        })

    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "authorization_report": str(args.authorization_report),
        "output": str(args.output),
        "reviewed_import_candidate_rows": len(candidates),
        "authorized_candidate_rows": len(authorized_ids),
        "preflight_rows": len(rows),
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "policy": "Preflight does not modify KWB supervised tables and cannot support model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorized_candidate_rows": report["authorized_candidate_rows"],
        "preflight_rows": report["preflight_rows"],
        "ready_for_training_import_rows": report["ready_for_training_import_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
