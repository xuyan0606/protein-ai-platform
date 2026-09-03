#!/usr/bin/env python3
"""Read-only extractor for local experiment feedback SQLite tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
DEFAULT_OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_features.jsonl"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def parse_json_field(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def extract(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return [{"source": "experiment_feedback_records", "status": "missing", "path": str(path)}]
    with connect_ro(path) as conn:
        if not table_exists(conn, "experiment_feedback_records"):
            return [{"source": "experiment_feedback_records", "status": "missing_table", "path": str(path)}]
        rows = conn.execute(
            """
            SELECT id, project_id, linked_task_id, enzyme_name, variant_name, parent_variant,
                   mutations, assay_payload, metrics_payload, quality_payload,
                   interpretation_payload, created_at
            FROM experiment_feedback_records
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        outputs = []
        for row in rows:
            interpretation = parse_json_field(row["interpretation_payload"]) or {}
            metrics = parse_json_field(row["metrics_payload"]) or {}
            outputs.append({
                "source": "experiment_feedback_records",
                "record_id": row["id"],
                "project_id": row["project_id"],
                "linked_task_id": row["linked_task_id"],
                "enzyme_name": row["enzyme_name"],
                "variant_name": row["variant_name"],
                "parent_variant": row["parent_variant"],
                "mutations": parse_json_field(row["mutations"]) or [],
                "decision": interpretation.get("decision") if isinstance(interpretation, dict) else None,
                "positive_flags": interpretation.get("positive_flags", []) if isinstance(interpretation, dict) else [],
                "warning_flags": interpretation.get("warning_flags", []) if isinstance(interpretation, dict) else [],
                "blocker_flags": interpretation.get("blocker_flags", []) if isinstance(interpretation, dict) else [],
                "activity_retention_pct": metrics.get("activity_retention_pct") if isinstance(metrics, dict) else None,
                "tm_delta_c": metrics.get("tm_delta_c") if isinstance(metrics, dict) else None,
                "created_at": row["created_at"],
            })
        return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract read-only experiment feedback features")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    rows = extract(args.db, max(1, args.limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

