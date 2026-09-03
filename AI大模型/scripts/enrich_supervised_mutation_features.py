#!/usr/bin/env python3
"""Enrich supervised mutation rows with non-leaky enzyme DB context."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_enriched.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "enzyme_mutation_enrichment_report.json"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def fetch_context(conn: sqlite3.Connection, uniprot_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not uniprot_ids:
        return {}
    placeholders = ",".join("?" for _ in uniprot_ids)
    enzyme_rows = conn.execute(
        f"""
        SELECT
          e.id,
          e.uniprot_id,
          e.is_reviewed,
          e.source_db,
          e.function_annotation,
          e.catalytic_activity,
          COALESCE(pdb.pdb_count, 0) AS pdb_count,
          pdb.best_resolution,
          pdb.xray_count,
          pdb.cryoem_count,
          af.plddt_mean AS alphafold_plddt_mean,
          COALESCE(kp.kinetic_count, 0) AS kinetic_count,
          COALESCE(dom.domain_count, 0) AS domain_count,
          COALESCE(ec.ec_count, 0) AS ec_count,
          ec.ec_level1_values
        FROM enzyme_records e
        LEFT JOIN (
          SELECT
            enzyme_id,
            COUNT(*) AS pdb_count,
            MIN(resolution) AS best_resolution,
            SUM(CASE WHEN lower(COALESCE(method, '')) LIKE '%x-ray%' THEN 1 ELSE 0 END) AS xray_count,
            SUM(CASE WHEN lower(COALESCE(method, '')) LIKE '%electron%' OR lower(COALESCE(method, '')) LIKE '%cryo%' THEN 1 ELSE 0 END) AS cryoem_count
          FROM pdb_structures
          GROUP BY enzyme_id
        ) pdb ON pdb.enzyme_id = e.id
        LEFT JOIN alphafold_structures af ON af.enzyme_id = e.id
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS kinetic_count FROM kinetic_parameters GROUP BY enzyme_id
        ) kp ON kp.enzyme_id = e.id
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS domain_count FROM domain_architecture GROUP BY enzyme_id
        ) dom ON dom.enzyme_id = e.id
        LEFT JOIN (
          SELECT
            l.enzyme_id,
            COUNT(*) AS ec_count,
            GROUP_CONCAT(DISTINCT ec.level1) AS ec_level1_values
          FROM enzyme_ec_links l
          JOIN ec_numbers ec ON ec.id = l.ec_id
          GROUP BY l.enzyme_id
        ) ec ON ec.enzyme_id = e.id
        WHERE e.uniprot_id IN ({placeholders})
        """,
        uniprot_ids,
    ).fetchall()

    context = {}
    for row in enzyme_rows:
        context[row["uniprot_id"]] = dict(row)

    domain_rows = conn.execute(
        f"""
        SELECT e.uniprot_id, d.start_pos, d.end_pos, d.evalue
        FROM domain_architecture d
        JOIN enzyme_records e ON e.id = d.enzyme_id
        WHERE e.uniprot_id IN ({placeholders})
        """,
        uniprot_ids,
    ).fetchall()
    for row in domain_rows:
        context.setdefault(row["uniprot_id"], {}).setdefault("domains", []).append({
            "start_pos": row["start_pos"],
            "end_pos": row["end_pos"],
            "evalue": row["evalue"],
        })
    return context


def capped_log_count(value: Any) -> float:
    count = int(value or 0)
    return round(math.log1p(max(0, count)), 6)


def enrich_row(row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    domains = context.get("domains") or []
    pos = int(row.get("mutation_position") or 0)
    containing = [
        domain for domain in domains
        if int(domain.get("start_pos") or 0) <= pos <= int(domain.get("end_pos") or 0)
    ]
    plddt = context.get("alphafold_plddt_mean")
    best_resolution = context.get("best_resolution")
    ec_levels = {str(item) for item in str(context.get("ec_level1_values") or "").split(",") if item}
    structure_evidence_score = 0.0
    if int(context.get("pdb_count") or 0) > 0:
        structure_evidence_score += 2.0
    if best_resolution is not None and float(best_resolution) <= 2.5:
        structure_evidence_score += 1.0
    if plddt is not None and float(plddt) >= 80:
        structure_evidence_score += 1.0

    output.update({
        "db_record_found": bool(context),
        "is_reviewed_uniprot": bool(context.get("is_reviewed")),
        "has_function_annotation_db": bool(context.get("function_annotation")),
        "has_catalytic_activity_db": bool(context.get("catalytic_activity")),
        "pdb_count": int(context.get("pdb_count") or 0),
        "pdb_log_count": capped_log_count(context.get("pdb_count")),
        "has_pdb_structure": int(context.get("pdb_count") or 0) > 0,
        "best_pdb_resolution": float(best_resolution) if best_resolution is not None else 0.0,
        "has_high_resolution_pdb": bool(best_resolution is not None and float(best_resolution) <= 2.5),
        "pdb_xray_count": int(context.get("xray_count") or 0),
        "pdb_cryoem_count": int(context.get("cryoem_count") or 0),
        "alphafold_plddt_mean": float(plddt) if plddt is not None else 0.0,
        "has_alphafold_model": plddt is not None,
        "alphafold_high_confidence": bool(plddt is not None and float(plddt) >= 90),
        "alphafold_medium_confidence": bool(plddt is not None and 70 <= float(plddt) < 90),
        "alphafold_low_confidence": bool(plddt is not None and float(plddt) < 70),
        "kinetic_count": int(context.get("kinetic_count") or 0),
        "kinetic_log_count": capped_log_count(context.get("kinetic_count")),
        "has_kinetic_records": int(context.get("kinetic_count") or 0) > 0,
        "domain_count": int(context.get("domain_count") or 0),
        "domain_log_count": capped_log_count(context.get("domain_count")),
        "mutation_in_pfam_domain": bool(containing),
        "mutation_domain_count": len(containing),
        "ec_count": int(context.get("ec_count") or 0),
        "ec_log_count": capped_log_count(context.get("ec_count")),
        "has_ec_annotation": int(context.get("ec_count") or 0) > 0,
        "structure_evidence_score": structure_evidence_score,
    })
    for level in ("1", "2", "3", "4", "5", "6", "7"):
        output[f"ec_class_{level}"] = level in ec_levels
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich supervised mutation features")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    uniprot_ids = sorted({row.get("uniprot_id") for row in rows if row.get("uniprot_id")})
    with connect_ro(args.db) as conn:
        context = fetch_context(conn, uniprot_ids)
    enriched = [enrich_row(row, context.get(row.get("uniprot_id"), {})) for row in rows]
    write_jsonl(args.output, enriched)

    report = {
        "rows": len(enriched),
        "groups": len({row.get("group_key") for row in enriched}),
        "db_context_groups_found": len(context),
        "rows_with_pdb": sum(1 for row in enriched if row["has_pdb_structure"]),
        "rows_with_alphafold": sum(1 for row in enriched if row["has_alphafold_model"]),
        "rows_with_pfam_domain_hit": sum(1 for row in enriched if row["mutation_in_pfam_domain"]),
        "rows_with_ec": sum(1 for row in enriched if row["has_ec_annotation"]),
        "output": str(args.output),
        "leakage_guard": "adds enzyme/structure annotation context only; excludes dTm/ddG from model features",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": report["rows"],
        "db_context_groups_found": report["db_context_groups_found"],
        "rows_with_pdb": report["rows_with_pdb"],
        "rows_with_alphafold": report["rows_with_alphafold"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
