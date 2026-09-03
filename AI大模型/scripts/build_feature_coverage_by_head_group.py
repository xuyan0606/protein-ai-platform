#!/usr/bin/env python3
"""Build input-feature coverage by five-head target and protein group."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURE_INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
FEATURE_REPORT = AI_ROOT / "reports" / "validated_feature_index_report.json"
FEATURE_VALIDATION = AI_ROOT / "reports" / "validated_feature_index_validation_report.json"
FIVE_HEAD_CONTRACT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_by_head_group.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "feature_coverage_by_head_group_report.json"

EXPECTED_HEADS = [
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
]

FEATURE_FAMILY_HEADS = {
    "msa_conservation": EXPECTED_HEADS,
    "structure_graph": ["mutation_rank", "stability", "substrate_fit"],
    "pyrosetta_ddg_reu_input": ["stability"],
    "structure_site": ["mutation_rank", "stability", "substrate_fit"],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def protein_group_id(uniprot_id: Any) -> str:
    value = str(uniprot_id or "unknown_uniprot")
    return f"uniprot:{value}"


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    feature_rows = load_jsonl(FEATURE_INDEX)
    feature_report = load_json(FEATURE_REPORT)
    feature_validation = load_json(FEATURE_VALIDATION)
    five_head_contract = load_json(FIVE_HEAD_CONTRACT)

    groups = sorted({protein_group_id(row.get("uniprot_id")) for row in feature_rows})
    features_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        features_by_group[protein_group_id(row.get("uniprot_id"))].append(row)

    coverage_rows: list[dict[str, Any]] = []
    for head in EXPECTED_HEADS:
        for group_id in groups:
            group_features = features_by_group[group_id]
            supported_features = [
                row for row in group_features
                if head in FEATURE_FAMILY_HEADS.get(str(row.get("feature_family")), [])
            ]
            family_counts = Counter(str(row.get("feature_family")) for row in supported_features)
            uniprot_id = group_id.split(":", 1)[1]
            coverage_rows.append({
                "created_at": created_at,
                "local_only": True,
                "head": head,
                "protein_group_id": group_id,
                "uniprot_id": uniprot_id if uniprot_id != "unknown_uniprot" else None,
                "input_feature_rows": len(supported_features),
                "model_consumable_feature_rows": sum(
                    1 for row in supported_features if row.get("model_consumable") is True
                ),
                "training_label_source_rows": sum(
                    1 for row in supported_features if row.get("training_label_source") is True
                ),
                "feature_rows_counted_as_labels": 0,
                "feature_family_counts": dict(sorted(family_counts.items())),
                "feature_index_ids": sorted(
                    str(row.get("feature_index_id")) for row in supported_features if row.get("feature_index_id")
                ),
                "coverage_status": (
                    "has_input_feature_coverage" if supported_features else "no_input_feature_coverage"
                ),
                "source_feature_index": "datasets/features/validated_feature_index.jsonl",
                "source_feature_report": "reports/validated_feature_index_report.json",
                "source_feature_validation_report": "reports/validated_feature_index_validation_report.json",
                "input_only": True,
                "training_import_allowed": False,
                "safe_for_model_claim": False,
                "release_ready": False,
                "production_execution_allowed": False,
                "policy": (
                    "Coverage row describes model input feature availability only. It is not a label, "
                    "training import approval, model-quality claim, release approval, or production authorization."
                ),
            })

    covered_by_head = {
        head: sum(
            1 for row in coverage_rows
            if row["head"] == head and row["coverage_status"] == "has_input_feature_coverage"
        )
        for head in EXPECTED_HEADS
    }
    missing_by_head = {
        head: sum(
            1 for row in coverage_rows
            if row["head"] == head and row["coverage_status"] == "no_input_feature_coverage"
        )
        for head in EXPECTED_HEADS
    }
    input_feature_rows_by_head = {
        head: sum(row["input_feature_rows"] for row in coverage_rows if row["head"] == head)
        for head in EXPECTED_HEADS
    }

    report = {
        "created_at": created_at,
        "local_only": True,
        "expected_heads": EXPECTED_HEADS,
        "feature_family_head_mapping": FEATURE_FAMILY_HEADS,
        "source_feature_index": "datasets/features/validated_feature_index.jsonl",
        "source_feature_report": "reports/validated_feature_index_report.json",
        "source_feature_validation_report": "reports/validated_feature_index_validation_report.json",
        "source_feature_rows": len(feature_rows),
        "source_feature_report_rows": feature_report.get("feature_rows"),
        "source_feature_validation_success": feature_validation.get("success") is True,
        "source_training_label_source_rows": sum(
            1 for row in feature_rows if row.get("training_label_source") is True
        ),
        "source_feature_rows_counted_as_labels": 0,
        "source_family_counts": dict(sorted(Counter(str(row.get("feature_family")) for row in feature_rows).items())),
        "protein_group_definition": "uniprot:<uniprot_id> derived from validated_feature_index.uniprot_id",
        "protein_group_count": len(groups),
        "coverage_row_count": len(coverage_rows),
        "covered_group_count_by_head": covered_by_head,
        "missing_group_count_by_head": missing_by_head,
        "input_feature_rows_by_head": input_feature_rows_by_head,
        "five_head_ready_head_count": five_head_contract.get("ready_head_count"),
        "five_head_training_execution_allowed": five_head_contract.get("training_execution_allowed"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "coverage_jsonl": "datasets/features/feature_coverage_by_head_group.jsonl",
        "policy": (
            "Feature coverage is an input-only audit for P27-A003. It does not convert features into labels, "
            "does not train models, does not promote claims, and does not open release or production gates."
        ),
    }

    write_jsonl(OUT_JSONL, coverage_rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "coverage_rows": report["coverage_row_count"],
        "protein_group_count": report["protein_group_count"],
        "input_feature_rows_by_head": report["input_feature_rows_by_head"],
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
