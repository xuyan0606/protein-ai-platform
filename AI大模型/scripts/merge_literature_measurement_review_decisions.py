#!/usr/bin/env python3
"""Atomically merge parallel literature review submissions."""
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path
from typing import Any
import fcntl
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "datasets/curation/literature_measurement_review_decisions.local.jsonl"
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def merge_rows(target: Path, incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = load_jsonl(target)
        by_id = {str(row.get("review_task_id")): row for row in rows}
        for row in incoming:
            task_id = str(row.get("review_task_id", ""))
            if not task_id: raise ValueError("review_task_id_missing")
            if task_id in by_id and by_id[task_id] != row:
                existing = by_id[task_id]
                if existing.get("decision") == "pending" and row.get("decision") in {"approved_for_intake", "rejected"}:
                    by_id[task_id] = row
                    continue
                raise ValueError(f"decision_conflict:{task_id}")
            by_id[task_id] = row
        merged = list(by_id.values())
        fd, temp_name = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in merged))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return merged

def merge_validated_rows(target: Path, incoming: list[dict[str, Any]], queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validator_path = Path(__file__).with_name("validate_literature_measurement_review_decisions.py")
    spec = importlib.util.spec_from_file_location("lit_decision_validator", validator_path)
    validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    by_id = {str(row.get("review_task_id")): row for row in queue}
    errors = []
    for row in incoming:
        if row.get("decision") == "evidence_verified":
            row["decision"] = "approved_for_intake"
        elif row.get("decision") == "reject_evidence":
            row["decision"] = "rejected"
        if not row.get("review_basis") and row.get("notes"):
            row["review_basis"] = row["notes"]
        task_id = str(row.get("review_task_id", ""))
        if isinstance(row.get("measurement_ids"), list):
            row["measurement_ids"] = "|".join(str(value) for value in row["measurement_ids"])
        if task_id not in by_id:
            errors.append(f"{task_id}:unknown_task")
        else:
            row_errors = validator.validate_decision(row, by_id[task_id])
            if row_errors: errors.append(f"{task_id}:{','.join(row_errors)}")
    if errors:
        raise ValueError("invalid_decision:" + ";".join(errors))
    return merge_rows(target, incoming)

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path); parser.add_argument("--target", type=Path, default=TARGET); parser.add_argument("--queue", type=Path, default=QUEUE)
    args = parser.parse_args(); queue = json.loads(args.queue.read_text(encoding="utf-8"))["rows"]; merged = merge_validated_rows(args.target, load_jsonl(args.input), queue); print(json.dumps({"merged_rows": len(merged), "target": str(args.target)}, ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
