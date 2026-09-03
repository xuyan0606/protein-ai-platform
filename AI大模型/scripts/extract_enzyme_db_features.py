#!/usr/bin/env python3
"""Read-only extractor for the local enzyme database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
DEFAULT_ENZYME_OUT = AI_ROOT / "datasets" / "features" / "enzyme_db_features.jsonl"
DEFAULT_MUTATION_OUT = AI_ROOT / "datasets" / "features" / "enzyme_mutation_labels.jsonl"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def extract_enzyme_features(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "enzyme_records"):
        return [{"source": "enzyme_db", "status": "missing_table", "table": "enzyme_records"}]

    rows = conn.execute(
        """
        SELECT
          e.id AS enzyme_id,
          e.uniprot_id,
          e.entry_name,
          e.seq_length,
          e.protein_name,
          e.function_annotation,
          e.catalytic_activity,
          e.is_reviewed,
          e.source_db,
          COALESCE(pdb.cnt, 0) AS pdb_count,
          COALESCE(kp.cnt, 0) AS kinetic_count,
          COALESCE(stab.cnt, 0) AS stability_count,
          COALESCE(evo.cnt, 0) AS directed_evolution_count,
          af.plddt_mean AS alphafold_plddt_mean
        FROM enzyme_records e
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS cnt FROM pdb_structures GROUP BY enzyme_id
        ) pdb ON pdb.enzyme_id = e.id
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS cnt FROM kinetic_parameters GROUP BY enzyme_id
        ) kp ON kp.enzyme_id = e.id
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS cnt FROM stability_records GROUP BY enzyme_id
        ) stab ON stab.enzyme_id = e.id
        LEFT JOIN (
          SELECT enzyme_id, COUNT(*) AS cnt FROM directed_evolution_entries GROUP BY enzyme_id
        ) evo ON evo.enzyme_id = e.id
        LEFT JOIN alphafold_structures af ON af.enzyme_id = e.id
        WHERE pdb.cnt IS NOT NULL OR kp.cnt IS NOT NULL OR stab.cnt IS NOT NULL OR evo.cnt IS NOT NULL OR af.id IS NOT NULL
        ORDER BY (COALESCE(pdb.cnt, 0) + COALESCE(kp.cnt, 0) + COALESCE(stab.cnt, 0) + COALESCE(evo.cnt, 0)) DESC, e.id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "source": "enzyme_db",
            "record_type": "enzyme_feature",
            "enzyme_id": row["enzyme_id"],
            "uniprot_id": row["uniprot_id"],
            "entry_name": row["entry_name"],
            "seq_length": row["seq_length"],
            "protein_name": row["protein_name"],
            "has_function_annotation": bool(row["function_annotation"]),
            "has_catalytic_activity": bool(row["catalytic_activity"]),
            "is_reviewed": bool(row["is_reviewed"]),
            "source_db": row["source_db"],
            "pdb_count": row["pdb_count"],
            "kinetic_count": row["kinetic_count"],
            "stability_count": row["stability_count"],
            "directed_evolution_count": row["directed_evolution_count"],
            "alphafold_plddt_mean": row["alphafold_plddt_mean"],
            "usable_as_evidence": True,
            "usable_as_training_label": False,
        }
        for row in rows
    ]


def extract_mutation_labels(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    if table_exists(conn, "stability_records"):
        rows = conn.execute(
            """
            SELECT
              s.id AS label_id,
              e.uniprot_id,
              e.seq_length,
              s.mutation,
              s.mutation_pos,
              s.wild_type,
              s.mutant,
              s.ddg,
              s.dtm,
              s.ph,
              s.temperature_c,
              s.method,
              s.source_db
            FROM stability_records s
            JOIN enzyme_records e ON e.id = s.enzyme_id
            ORDER BY s.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            decision = "watch"
            if row["dtm"] is not None:
                if float(row["dtm"]) >= 2:
                    decision = "go"
                elif float(row["dtm"]) <= -2:
                    decision = "no_go"
            elif row["ddg"] is not None:
                if float(row["ddg"]) <= -1:
                    decision = "go"
                elif float(row["ddg"]) >= 1:
                    decision = "no_go"
            outputs.append({
                "source": "enzyme_db",
                "record_type": "stability_label",
                "label_id": f"stability:{row['label_id']}",
                "uniprot_id": row["uniprot_id"],
                "seq_length": row["seq_length"],
                "mutation": row["mutation"],
                "mutation_position": row["mutation_pos"],
                "wild_type": row["wild_type"],
                "mutant": row["mutant"],
                "label_stability_delta_tm_c": row["dtm"],
                "label_ddg": row["ddg"],
                "assay_ph": row["ph"],
                "assay_temperature_c": row["temperature_c"],
                "method": row["method"],
                "source_db": row["source_db"],
                "label_decision": decision,
                "dataset_role": "review_draft",
                "label_role": "non_strict_candidate",
                "usable_as_training_label": False,
                "usable_as_supervised_label": False,
                "training_pipeline_unlocked": False,
                "non_exportable_reason": "local enzyme DB labels require reviewed source receipts before supervised training",
            })

    remaining = max(0, limit - len(outputs))
    if remaining and table_exists(conn, "directed_evolution_entries"):
        rows = conn.execute(
            """
            SELECT
              d.id AS label_id,
              e.uniprot_id,
              e.seq_length,
              d.best_variant,
              d.mutations_introduced,
              d.initial_activity,
              d.final_activity,
              d.fold_improvement,
              d.improvement_metric,
              d.mutagenesis_method,
              d.literature_ref
            FROM directed_evolution_entries d
            JOIN enzyme_records e ON e.id = d.enzyme_id
            ORDER BY d.id
            LIMIT ?
            """,
            (remaining,),
        ).fetchall()
        for row in rows:
            fold = row["fold_improvement"]
            decision = "go" if fold is not None and float(fold) >= 1.2 else "watch"
            outputs.append({
                "source": "enzyme_db",
                "record_type": "directed_evolution_label",
                "label_id": f"directed_evolution:{row['label_id']}",
                "uniprot_id": row["uniprot_id"],
                "seq_length": row["seq_length"],
                "best_variant": row["best_variant"],
                "mutations_introduced": row["mutations_introduced"],
                "initial_activity": row["initial_activity"],
                "final_activity": row["final_activity"],
                "fold_improvement": fold,
                "improvement_metric": row["improvement_metric"],
                "mutagenesis_method": row["mutagenesis_method"],
                "literature_ref": row["literature_ref"],
                "label_decision": decision,
                "dataset_role": "review_draft",
                "label_role": "non_strict_candidate",
                "usable_as_training_label": False,
                "usable_as_supervised_label": False,
                "training_pipeline_unlocked": False,
                "non_exportable_reason": "local enzyme DB labels require reviewed source receipts before supervised training",
            })
    return outputs


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract local enzyme DB features")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--enzyme-output", type=Path, default=DEFAULT_ENZYME_OUT)
    parser.add_argument("--mutation-output", type=Path, default=DEFAULT_MUTATION_OUT)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"DB missing: {args.db}")
    with connect_ro(args.db) as conn:
        enzyme_rows = extract_enzyme_features(conn, max(1, args.limit))
        mutation_rows = extract_mutation_labels(conn, max(1, args.limit))
    write_jsonl(args.enzyme_output, enzyme_rows)
    write_jsonl(args.mutation_output, mutation_rows)
    print(json.dumps({
        "enzyme_rows": len(enzyme_rows),
        "mutation_label_rows": len(mutation_rows),
        "enzyme_output": str(args.enzyme_output),
        "mutation_output": str(args.mutation_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
