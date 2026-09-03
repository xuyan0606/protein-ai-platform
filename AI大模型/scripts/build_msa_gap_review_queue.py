#!/usr/bin/env python3
"""Create an auditable, fail-closed queue for MSA gap cache review."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
INTAKE = AI_ROOT / "datasets/curation/msa_gap_trusted_cache_intake.local.jsonl"
CONSERVATION_ROOT = AI_ROOT / "datasets/curation/msa_conservation_gap"
OUT = AI_ROOT / "datasets/curation/msa_gap_human_review_queue.jsonl"
REPORT = AI_ROOT / "reports/msa_gap_human_review_queue_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_review_row(intake: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    length = int(intake.get("sequence_length") or 0)
    covered = int((payload.get("summary") or {}).get("positions_with_homolog_coverage") or 0)
    return {
        "review_id": f"msa-gap-review::{intake.get('uniprot_id')}",
        "uniprot_id": intake.get("uniprot_id"),
        "sequence_length": length,
        "hit_count": int(payload.get("hit_count") or 0),
        "raw_hit_count": int(payload.get("raw_hit_count") or 0),
        "covered_positions": covered,
        "coverage_fraction": round(covered / length, 6) if length else 0.0,
        "mean_homolog_depth": (payload.get("summary") or {}).get("mean_homolog_depth"),
        "msa_path": intake.get("msa_path"),
        "msa_sha256": intake.get("msa_sha256"),
        "conservation_feature_path": intake.get("conservation_feature_path"),
        "conservation_sha256": intake.get("conservation_sha256"),
        "source_database": intake.get("source_database"),
        "database_version": intake.get("database_version"),
        "review_status": "pending_human_review",
        "review_required": True,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Review queue only; no formal trusted-cache intake, training import, model claim, or release approval.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA gap human review queue")
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--conservation-root", type=Path, default=CONSERVATION_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.intake.read_text(encoding="utf-8").splitlines() if line.strip()] if args.intake.exists() else []
    queue = []
    errors = []
    for intake in rows:
        path = Path(str(intake.get("conservation_feature_path") or ""))
        if not path.is_absolute():
            path = AI_ROOT / path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            queue.append(build_review_row(intake, payload))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"uniprot_id": intake.get("uniprot_id"), "error": type(exc).__name__})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue), encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input_rows": len(rows),
        "queue_rows": len(queue),
        "error_rows": len(errors),
        "errors": errors,
        "all_pending_human_review": all(row["review_status"] == "pending_human_review" for row in queue),
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output.relative_to(AI_ROOT)),
        "policy": "Queue is an auditable handoff artifact; human approval is required before formal manifest changes.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
