#!/usr/bin/env python3
"""Compare production schema inventory with Alembic migration objects (read-only)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "backend" / "alembic" / "versions"


def _assignment(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value) if node.value is not None else None
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def _literal_string(node: ast.AST) -> str | None:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _migration_objects(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tables: list[str] = []
    indexes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"create_table", "create_index"} or not node.args:
            continue
        value = _literal_string(node.args[0])
        if value:
            (tables if node.func.attr == "create_table" else indexes).append(value)
    return {
        "revision": _assignment(tree, "revision"),
        "down_revision": _assignment(tree, "down_revision"),
        "file": path.name,
        "tables": sorted(set(tables)),
        "indexes": sorted(set(indexes)),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    actual_tables = set(inventory.get("tables", []))
    actual_indexes = {str(row.get("indexname")) for row in inventory.get("indexes", [])}
    rows = []
    for path in sorted(VERSIONS.glob("*.py")):
        item = _migration_objects(path)
        missing_tables = sorted(set(item["tables"]) - actual_tables)
        missing_indexes = sorted(set(item["indexes"]) - actual_indexes)
        item.update({
            "tables_present": not missing_tables,
            "indexes_present": not missing_indexes,
            "missing_tables": missing_tables,
            "missing_indexes": missing_indexes,
            "schema_status": "complete" if not missing_tables and not missing_indexes else "incomplete",
        })
        rows.append(item)
    payload = {
        "read_only": True,
        "production_alembic_versions": inventory.get("alembic_versions", []),
        "revision_count": len(rows),
        "migrations": rows,
        "summary": {
            "complete_migrations": sum(row["schema_status"] == "complete" for row in rows),
            "incomplete_migrations": sum(row["schema_status"] == "incomplete" for row in rows),
            "pending_objects": sorted({obj for row in rows for obj in row["missing_tables"] + row["missing_indexes"]}),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
