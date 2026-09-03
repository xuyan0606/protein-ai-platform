#!/usr/bin/env python3
"""Read-only discovery for local KWB model data sources."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = AI_ROOT / "reports" / "local_data_discovery.json"


def file_info(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
    }


def sqlite_info(path: Path) -> dict[str, Any]:
    info = file_info(path)
    info["read_only"] = True
    if not path.exists() or not path.is_file():
        info.update({"status": "missing", "tables": {}, "integrity_check": "missing"})
        return info
    try:
        uri = f"file:{path}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            ]
            counts = {}
            for table in tables:
                try:
                    row = conn.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
                    counts[table] = int(row["count"] if row else 0)
                except sqlite3.Error:
                    counts[table] = None
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
        info.update({
            "status": "ready",
            "tables": counts,
            "integrity_check": str(integrity[0]) if integrity else "unknown",
        })
    except sqlite3.Error as exc:
        info.update({"status": "error", "tables": {}, "integrity_check": "error", "error": str(exc)})
    return info


def count_files(root: Path, patterns: list[str]) -> dict[str, int]:
    result = {}
    for pattern in patterns:
        result[pattern] = len(list(root.glob(pattern))) if root.exists() else 0
    return result


def discover(project_root: Path) -> dict[str, Any]:
    deploy_data = project_root / "deploy_data"
    lipase_db = deploy_data / "lipase" / "lipase.db"
    sqlite_candidates = sorted(project_root.glob("**/*.db"))
    sqlite_candidates = [
        path
        for path in sqlite_candidates
        if ".git" not in path.parts and "node_modules" not in path.parts and "AI大模型" not in path.parts
    ]
    return {
        "project_root": str(project_root),
        "read_only": True,
        "deploy_data": {
            "root": file_info(deploy_data),
            "counts": {
                "pdb_cif": count_files(deploy_data / "pdb", ["*.cif", "*.pdb", "local_cases/*.pdb"]),
                "alphafold": count_files(deploy_data / "alphafold", ["*.cif", "*.json"]),
                "sifts": count_files(deploy_data / "sifts", ["*.json"]),
                "annotations": count_files(deploy_data / "annotations", ["*.json"]),
                "benchmarks": count_files(deploy_data / "benchmarks", ["*.tar.gz", "*/*.json", "*/README.md"]),
                "foldseek_lookup": count_files(deploy_data / "foldseek", ["*/*.lookup", "*/*.dbtype"]),
            },
        },
        "lipase_db": sqlite_info(lipase_db),
        "sqlite_candidates": [sqlite_info(path) for path in sqlite_candidates],
        "next_extractors": [
            "extract_lipase_features.py",
            "extract_feedback_features.py",
            "extract_tool_audit_features.py",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover local KWB data sources")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = discover(args.project_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "lipase_status": report["lipase_db"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

