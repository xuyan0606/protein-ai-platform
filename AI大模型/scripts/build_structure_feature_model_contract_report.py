#!/usr/bin/env python3
"""Build reviewed-chain structure feature model-consumption boundary report.

This report is a contract artifact only. It proves the difference between
parsed coordinate files and reviewed-chain structure graph features, and it
keeps the reviewed graph limited to input-feature use.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REQUESTED_REVIEWED_GRAPH_INDEX = AI_ROOT / "datasets" / "curated" / "reviewed_structure_graph_features.jsonl"
FEATURES_REVIEWED_GRAPH_INDEX = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
GRAPH_REPORT = AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
COORDINATE_REPORT = AI_ROOT / "reports" / "structure_coordinate_feature_report.json"
REPORT_OUT = AI_ROOT / "reports" / "structure_feature_model_contract_report.json"

POLICY = (
    "Reviewed structure graph rows are model input features only. Parsed "
    "coordinate rows are not reviewed-chain graph rows, do not create training "
    "labels, and do not support release or model-quality claims."
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_structure_id(value: Any) -> str:
    return str(value or "").upper()


def reviewed_graph_index_path(requested: Path, graph_report: dict[str, Any]) -> tuple[Path, list[str]]:
    warnings: list[str] = []
    if requested.exists():
        return requested, warnings

    warnings.append(f"requested_reviewed_graph_index_missing:{rel(requested)}")
    report_output = graph_report.get("output")
    if report_output:
        candidate = Path(str(report_output))
        if not candidate.is_absolute():
            candidate = AI_ROOT / candidate
        if candidate.exists():
            warnings.append(f"using_reviewed_graph_index_from_report:{rel(candidate)}")
            return candidate, warnings

    if FEATURES_REVIEWED_GRAPH_INDEX.exists():
        warnings.append(f"using_existing_features_reviewed_graph_index:{rel(FEATURES_REVIEWED_GRAPH_INDEX)}")
        return FEATURES_REVIEWED_GRAPH_INDEX, warnings
    return requested, warnings


def decision_key(row: dict[str, Any]) -> tuple[str, str]:
    return normalize_structure_id(row.get("structure_id")), str(row.get("selected_chain_id") or "")


def graph_key(row: dict[str, Any]) -> tuple[str, str]:
    return normalize_structure_id(row.get("structure_id")), str(row.get("selected_chain_id") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure feature model contract report")
    parser.add_argument("--reviewed-graph-index", type=Path, default=REQUESTED_REVIEWED_GRAPH_INDEX)
    parser.add_argument("--reviewed-graph-report", type=Path, default=GRAPH_REPORT)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--coordinate-report", type=Path, default=COORDINATE_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    graph_report = load_json(args.reviewed_graph_report)
    coordinate_report = load_json(args.coordinate_report)
    graph_index_path, warnings = reviewed_graph_index_path(args.reviewed_graph_index, graph_report)
    graph_rows = load_jsonl(graph_index_path)
    decision_rows = load_jsonl(args.decisions)
    formal_decision_rows = [row for row in decision_rows if row.get("decision") == "set_chain_mapping"]

    graph_keys = {graph_key(row) for row in graph_rows}
    formal_keys = {decision_key(row) for row in formal_decision_rows}
    graph_structure_ids = {key[0] for key in graph_keys if key[0]}
    formal_structure_ids = {key[0] for key in formal_keys if key[0]}
    graph_not_in_formal_decisions = sorted(
        f"{structure_id}:{chain_id}" for structure_id, chain_id in graph_keys - formal_keys
    )

    coordinate_rows = int_value(coordinate_report.get("feature_rows"))
    coordinate_manifest_rows = int_value(coordinate_report.get("manifest_rows"))
    coordinate_parse_failures = int_value(coordinate_report.get("parse_failures"))
    structures_with_atoms = int_value(coordinate_report.get("structures_with_atoms"))
    structures_with_ca_atoms = int_value(coordinate_report.get("structures_with_ca_atoms"))
    reviewed_graph_rows = len(graph_rows)
    formal_count = len(formal_decision_rows)
    unreviewed_coordinate_rows = max(coordinate_rows - reviewed_graph_rows, 0)
    graph_report_rows = int_value(graph_report.get("graph_rows"))
    graph_report_failure_rows = int_value(graph_report.get("failure_rows"))
    model_consumable_reviewed_graph_rows = min(reviewed_graph_rows, formal_count)

    mapping_status_counts = Counter(str(row.get("sequence_to_structure_mapping_status") or "missing") for row in graph_rows)
    report = {
        "report_id": "structure_feature_model_contract_report",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "input_feature_boundary_only",
        "source_inputs": {
            "requested_reviewed_graph_index": rel(args.reviewed_graph_index),
            "resolved_reviewed_graph_index": rel(graph_index_path),
            "requested_reviewed_graph_index_available": args.reviewed_graph_index.exists(),
            "reviewed_structure_graph_feature_report": rel(args.reviewed_graph_report),
            "structure_chain_mapping_decisions": rel(args.decisions),
            "structure_coordinate_feature_report": rel(args.coordinate_report),
        },
        "coordinate_file_parse_evidence": {
            "manifest_rows": coordinate_manifest_rows,
            "parsed_coordinate_feature_rows": coordinate_rows,
            "parse_failures": coordinate_parse_failures,
            "structures_with_atoms": structures_with_atoms,
            "structures_with_ca_atoms": structures_with_ca_atoms,
            "coordinate_parse_complete": (
                coordinate_manifest_rows == 500
                and coordinate_rows == 500
                and coordinate_parse_failures == 0
                and structures_with_atoms == 500
                and structures_with_ca_atoms == 500
            ),
            "proves": "structure coordinate files were parsed",
            "does_not_prove": [
                "reviewed chain mapping for every coordinate row",
                "training label availability",
                "release readiness",
                "model quality claim readiness",
            ],
        },
        "reviewed_chain_graph_boundary": {
            "reviewed_graph_index_rows": reviewed_graph_rows,
            "reviewed_graph_report_rows": graph_report_rows,
            "reviewed_graph_report_failure_rows": graph_report_failure_rows,
            "formal_chain_mapping_decision_rows": formal_count,
            "formal_chain_mapping_decision_file_rows": len(decision_rows),
            "unique_reviewed_graph_structures": len(graph_structure_ids),
            "unique_formal_decision_structures": len(formal_structure_ids),
            "reviewed_graph_rows_not_in_formal_decisions": graph_not_in_formal_decisions,
            "reviewed_graph_not_greater_than_formal_decisions": reviewed_graph_rows <= formal_count,
            "mapping_status_counts": dict(sorted(mapping_status_counts.items())),
            "graph_feature_scope": "reviewed_chain_residue_neighborhood_graph",
        },
        "model_consumption_contract": {
            "model_consumable_reviewed_graph_rows": model_consumable_reviewed_graph_rows,
            "coordinate_rows_counted_as_model_consumable_reviewed_graph": model_consumable_reviewed_graph_rows,
            "unreviewed_coordinate_rows_excluded_from_reviewed_graph": unreviewed_coordinate_rows,
            "unreviewed_coordinate_rows_counted_as_model_consumable_reviewed_graph": 0,
            "model_consumable_role": "input_feature_only",
            "allowed_uses": [
                "offline model input feature experiments",
                "feature coverage accounting",
                "reviewed-chain structure graph joins",
            ],
            "forbidden_uses": [
                "training_label_source",
                "release_ready_artifact",
                "model_quality_claim",
                "customer_or_release_claim",
                "automatic expansion from unreviewed coordinate rows",
            ],
            "training_label_source": False,
            "training_label_source_rows": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
            "model_claim_allowed": False,
            "release_or_model_claim_allowed": False,
        },
        "reviewed_graph_records": [
            {
                "structure_id": normalize_structure_id(row.get("structure_id")),
                "uniprot_id": row.get("uniprot_id"),
                "selected_chain_id": row.get("selected_chain_id"),
                "node_count": row.get("node_count"),
                "edge_count": row.get("edge_count"),
                "sequence_to_structure_mapping_status": row.get("sequence_to_structure_mapping_status"),
                "safe_for_structure_graph_feature_use": row.get("safe_for_structure_graph_feature_use"),
                "safe_for_model_claim": False,
                "training_label_source": False,
                "release_ready": False,
            }
            for row in graph_rows
        ],
        "warnings": warnings,
        "safe_for_training_pipeline": False,
        "training_label_source": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "policy": POLICY,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "coordinate_rows_parsed": coordinate_rows,
        "reviewed_graph_rows": reviewed_graph_rows,
        "formal_decision_rows": formal_count,
        "training_label_source": report["training_label_source"],
        "release_ready": report["release_ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
