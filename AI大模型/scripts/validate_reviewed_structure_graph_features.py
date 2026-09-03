#!/usr/bin/env python3
"""Validate reviewed structure graph feature cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(path_text: Any) -> Path:
    path = Path(str(path_text or ""))
    return path if path.is_absolute() else AI_ROOT / path


def validate_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    graph_path = resolve(row.get("graph_path"))
    if not row.get("structure_id"):
        errors.append("structure_id_missing")
    if not row.get("selected_chain_id"):
        errors.append("selected_chain_id_missing")
    if not graph_path.exists():
        return errors + ["graph_file_missing"]
    if sha256(graph_path) != str(row.get("graph_sha256") or ""):
        errors.append("graph_sha256_mismatch")
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception:
        return errors + ["graph_json_not_parseable"]
    if graph.get("local_only") is not True:
        errors.append("graph_not_local_only")
    if graph.get("safe_for_model_claim") is not False:
        errors.append("graph_model_claim_not_false")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes_missing")
    if not isinstance(edges, list):
        errors.append("edges_not_list")
    if graph.get("node_count") != row.get("node_count"):
        errors.append("node_count_mismatch")
    if graph.get("edge_count") != row.get("edge_count"):
        errors.append("edge_count_mismatch")
    if row.get("safe_for_model_claim") is not False:
        errors.append("index_model_claim_not_false")
    if row.get("requires_mutation_numbering_review") is not True:
        errors.append("numbering_review_gate_missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reviewed structure graph cache")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.index)
    records = []
    counts: Counter[str] = Counter()
    for row in rows:
        errors = validate_row(row)
        counts.update(errors)
        records.append({
            "structure_id": row.get("structure_id"),
            "valid": not errors,
            "errors": errors,
        })
    valid_rows = sum(1 for row in records if row["valid"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "graph_index_rows": len(rows),
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "error_counts": dict(counts),
        "ready_for_coordinate_feature_use": bool(rows) and valid_rows == len(rows),
        "safe_for_model_claim": False,
        "records": records[:200],
        "policy": "Graph cache validation only; model-quality claims still require numbering, MSA, labels and benchmark gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ready_for_coordinate_feature_use": report["ready_for_coordinate_feature_use"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["ready_for_coordinate_feature_use"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
