#!/usr/bin/env python3
"""Build local MSA/conservation target scaffold without running MSA."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
TARGETS_OUT = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
MANIFEST_OUT = AI_ROOT / "reports" / "msa_conservation_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "msa_conservation_readiness_report.json"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA conservation scaffold")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--targets-output", type=Path, default=TARGETS_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    with connect_ro(args.db) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT e.uniprot_id, e.seq_length
            FROM stability_records s
            JOIN enzyme_records e ON e.id = s.enzyme_id
            ORDER BY e.uniprot_id
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    targets = [
        {
            "uniprot_id": row["uniprot_id"],
            "sequence_length": row["seq_length"],
            "msa_path": None,
            "conservation_feature_path": None,
            "status": "missing",
        }
        for row in rows
    ]
    write_jsonl(args.targets_output, targets)
    manifest = {
        "local_only": True,
        "status": "not_configured",
        "source": "not_configured",
        "targets": targets,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "targets": len(targets),
        "present": sum(1 for row in targets if row["status"] == "present"),
        "missing": sum(1 for row in targets if row["status"] == "missing"),
        "ready": False,
        "targets_output": str(args.targets_output),
        "manifest": str(args.manifest),
        "next_steps": [
            "configure local MSA cache or precomputed conservation features",
            "do not create msa_conservation_features.jsonl until real conservation features exist",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"targets": len(targets), "ready": False, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
