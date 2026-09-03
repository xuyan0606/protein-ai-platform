#!/usr/bin/env python3
"""Read-only extractor for local tool task audit SQLite tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
DEFAULT_OUT = AI_ROOT / "datasets" / "features" / "tool_audit_features.jsonl"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def extract(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return [{"source": "tool_task_audits", "status": "missing", "path": str(path)}]
    with connect_ro(path) as conn:
        if not table_exists(conn, "tool_task_audits"):
            return [{"source": "tool_task_audits", "status": "missing_table", "path": str(path)}]
        cols = table_columns(conn, "tool_task_audits")
        select_fields = [
            "id",
            "tool_name" if "tool_name" in cols else "NULL AS tool_name",
            "status" if "status" in cols else "NULL AS status",
            "queue" if "queue" in cols else "NULL AS queue",
            "failure_classification" if "failure_classification" in cols else "NULL AS failure_classification",
            "duration_ms" if "duration_ms" in cols else "NULL AS duration_ms",
            "created_at" if "created_at" in cols else "NULL AS created_at",
        ]
        rows = conn.execute(
            f'SELECT {", ".join(select_fields)} FROM tool_task_audits ORDER BY id LIMIT ?',
            (limit,),
        ).fetchall()
        return [
            {
                "source": "tool_task_audits",
                "record_id": row["id"],
                "tool_name": row["tool_name"],
                "status": row["status"],
                "queue": row["queue"],
                "failure_classification": row["failure_classification"],
                "duration_ms": row["duration_ms"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract read-only tool audit features")
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
