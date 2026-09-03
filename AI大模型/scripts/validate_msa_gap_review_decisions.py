#!/usr/bin/env python3
"""Generate and validate explicit human decisions for MSA gap intake."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets/curation/msa_gap_human_review_queue.jsonl"
DECISIONS = AI_ROOT / "datasets/curation/msa_gap_human_review_decisions.local.jsonl"
REPORT = AI_ROOT / "reports/msa_gap_review_decision_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_decision(decision: dict[str, Any], queue_row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if decision.get("review_id") != queue_row.get("review_id"):
        errors.append("review_id_mismatch")
    if decision.get("uniprot_id") != queue_row.get("uniprot_id"):
        errors.append("uniprot_id_mismatch")
    if decision.get("decision") not in {"approved", "rejected"}:
        errors.append("decision_missing_or_invalid")
    if not decision.get("reviewer"):
        errors.append("reviewer_missing")
    reviewed_at = decision.get("reviewed_at")
    if not reviewed_at:
        errors.append("reviewed_at_missing")
    else:
        try:
            datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            errors.append("reviewed_at_invalid_format")
    return errors

def build_validation_report(queue: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("review_id")): row for row in queue}
    records, seen, global_errors = [], set(), []
    for decision in decisions:
        review_id = str(decision.get("review_id"))
        errors = validate_decision(decision, by_id.get(review_id, {}))
        if review_id in seen:
            errors.append("duplicate_review_id")
            if "duplicate_review_id" not in global_errors: global_errors.append("duplicate_review_id")
        seen.add(review_id)
        if review_id not in by_id: errors.append("queue_row_missing")
        records.append({"review_id": decision.get("review_id"), "decision": decision.get("decision"), "valid": not errors, "errors": errors})
    if set(by_id) - seen: global_errors.append("missing_decision_for_queue_row")
    return {"queue_rows": len(queue), "decision_rows": len(decisions), "valid_decision_rows": sum(r["valid"] for r in records), "approved_rows": sum(1 for d,r in zip(decisions, records) if d.get("decision") == "approved" and r["valid"]), "pending_rows": sum(1 for d in decisions if d.get("decision") == "pending"), "records": records, "global_errors": global_errors, "formal_intake_authorized": False, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False}

def build_approved_preview(queue: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("review_id")): row for row in queue}
    rows = []
    for decision in decisions:
        queue_row = by_id.get(str(decision.get("review_id")))
        if queue_row and decision.get("decision") == "approved" and not validate_decision(decision, queue_row):
            rows.append({"review_id": queue_row.get("review_id"), "uniprot_id": queue_row.get("uniprot_id"), "reviewer": decision.get("reviewer"), "reviewed_at": decision.get("reviewed_at"), "conservation_feature_path": queue_row.get("conservation_feature_path"), "conservation_sha256": queue_row.get("conservation_sha256")})
    return {"rows": rows, "formal_intake_authorized": False, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Read-only preview; explicit merge step and independent gates remain required."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MSA gap review decisions")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--write-template", action="store_true")
    args = parser.parse_args()
    queue = load_jsonl(args.queue)
    if args.write_template and not args.decisions.exists():
        args.decisions.parent.mkdir(parents=True, exist_ok=True)
        args.decisions.write_text("".join(json.dumps({
            "review_id": row.get("review_id"), "uniprot_id": row.get("uniprot_id"),
            "decision": "pending", "reviewer": "", "reviewed_at": "", "notes": "",
        }, ensure_ascii=False, sort_keys=True) + "\n" for row in queue), encoding="utf-8")
    decisions = load_jsonl(args.decisions)
    summary = build_validation_report(queue, decisions)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "local_only": True,
        **summary,
        "policy": "Explicit human decision required; this validator never authorizes formal intake or training.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not summary["global_errors"] and all(row["valid"] for row in summary["records"]) and len(decisions) == len(queue) else 1


if __name__ == "__main__":
    raise SystemExit(main())
