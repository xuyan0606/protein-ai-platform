#!/usr/bin/env python3
"""Read-only extractor for local KWB Lipase DB feature rows."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "deploy_data" / "lipase" / "lipase.db"
DEFAULT_OUT = AI_ROOT / "datasets" / "features" / "lipase_features.jsonl"
MUTATION_RE = re.compile(r"(?<![A-Z])([A-Z])(\d+)([A-Z])(?![A-Z])")


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def extract_codes(*values: Any) -> list[str]:
    codes: set[str] = set()
    for value in values:
        text = str(value or "").upper()
        for match in MUTATION_RE.finditer(text):
            codes.add("".join(match.groups()))
    return sorted(codes)


def safe_text(row: sqlite3.Row, key: str) -> str:
    return str(row[key] or "") if key in row.keys() else ""


def variant_rows(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "variants"):
        return []
    variant_cols = columns(conn, "variants")
    paper_cols = columns(conn, "papers") if table_exists(conn, "papers") else set()
    select_fields = [
        "v.id AS variant_id",
        "v.variant_label AS variant_label" if "variant_label" in variant_cols else "NULL AS variant_label",
        "v.anchor_display AS anchor_display" if "anchor_display" in variant_cols else "NULL AS anchor_display",
        "p.paper_key AS paper_key" if "paper_key" in paper_cols else "NULL AS paper_key",
        "p.enzyme_name AS enzyme_name" if "enzyme_name" in paper_cols else "NULL AS enzyme_name",
    ]
    join = "LEFT JOIN papers p ON p.id = v.paper_id" if "paper_id" in variant_cols and table_exists(conn, "papers") else ""
    rows = conn.execute(
        f"""
        SELECT {", ".join(select_fields)}
        FROM variants v
        {join}
        ORDER BY v.id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    outputs = []
    for row in rows:
        codes = extract_codes(safe_text(row, "variant_label"), safe_text(row, "anchor_display"))
        outputs.append({
            "source": "kwb_lipase_db",
            "dataset_role": "feature_only",
            "label_role": "non_label",
            "usable_as_supervised_label": False,
            "record_type": "variant",
            "variant_id": row["variant_id"],
            "paper_key": safe_text(row, "paper_key"),
            "enzyme_name": safe_text(row, "enzyme_name"),
            "variant_label": safe_text(row, "variant_label"),
            "anchor_display": safe_text(row, "anchor_display"),
            "mutation_codes": codes,
            "has_mutation_code": bool(codes),
        })
    return outputs


def mutation_rows(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "variant_mutations"):
        return []
    cols = columns(conn, "variant_mutations")
    select_fields = [
        "id AS mutation_id" if "id" in cols else "rowid AS mutation_id",
        "variant_id AS variant_id" if "variant_id" in cols else "NULL AS variant_id",
        "mutation_code AS mutation_code" if "mutation_code" in cols else "NULL AS mutation_code",
        "position AS position" if "position" in cols else "NULL AS position",
        "wild_type AS wild_type" if "wild_type" in cols else "NULL AS wild_type",
        "mutant AS mutant" if "mutant" in cols else "NULL AS mutant",
    ]
    rows = conn.execute(
        f'SELECT {", ".join(select_fields)} FROM variant_mutations ORDER BY mutation_id LIMIT ?',
        (limit,),
    ).fetchall()
    outputs = []
    for row in rows:
        code = safe_text(row, "mutation_code").upper()
        if not code:
            wt = safe_text(row, "wild_type").upper()
            pos = safe_text(row, "position")
            mt = safe_text(row, "mutant").upper()
            code = f"{wt}{pos}{mt}" if wt and pos and mt else ""
        outputs.append({
            "source": "kwb_lipase_db",
            "dataset_role": "feature_only",
            "label_role": "non_label",
            "usable_as_supervised_label": False,
            "record_type": "mutation",
            "mutation_id": row["mutation_id"],
            "variant_id": row["variant_id"],
            "mutation": code,
            "position": row["position"],
            "wild_type": safe_text(row, "wild_type"),
            "mutant": safe_text(row, "mutant"),
            "has_mutation_code": bool(code),
        })
    return outputs


def extract(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return [{
            "source": "kwb_lipase_db",
            "dataset_role": "feature_only",
            "label_role": "non_label",
            "usable_as_supervised_label": False,
            "status": "missing",
            "path": str(path),
        }]
    with connect_ro(path) as conn:
        rows = []
        rows.extend(variant_rows(conn, limit))
        rows.extend(mutation_rows(conn, limit))
        return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract read-only KWB lipase features")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    rows = extract(args.db, max(1, args.limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
