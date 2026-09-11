#!/usr/bin/env python3
"""Build a read-only preview of valid approved literature review tasks."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_literature_measurement_review_decisions import load_jsonl, load_queue, validate_decision, QUEUE, DECISIONS

def build_preview(queue: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("review_task_id")): row for row in queue}; rows = []
    for decision in decisions:
        task_id = str(decision.get("review_task_id")); source = by_id.get(task_id)
        if source and decision.get("decision") == "approved_for_intake" and not validate_decision(decision, source):
            rows.append({"review_task_id": task_id, "measurement_ids": source.get("measurement_ids"), "pmcid": source.get("pmcid"), "doi": source.get("doi"), "source_file_sha256": source.get("source_file_sha256"), "license": source.get("license"), "training_import_status": "needs_review", "reviewer": decision.get("reviewer"), "reviewed_at": decision.get("reviewed_at"), "review_basis": decision.get("review_basis"), "authorization_receipt": decision.get("authorization_receipt"), "evidence_only": True})
    return {"rows": rows, "approved_preview_rows": len(rows), "formal_intake_authorized": False, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Read-only preview; separate authorization and formal intake gates remain required."}

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--queue", type=Path, default=QUEUE); p.add_argument("--decisions", type=Path, default=DECISIONS); p.add_argument("--output", type=Path, default=ROOT / "reports/literature_measurement_approved_preview.json"); a = p.parse_args()
    result = build_preview(load_queue(a.queue), load_jsonl(a.decisions)); a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
