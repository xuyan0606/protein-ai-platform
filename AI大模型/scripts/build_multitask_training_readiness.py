#!/usr/bin/env python3
"""Build a fail-closed readiness report for the five KWB model heads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
AUDITED = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl"
ACTIVITY_RISK_TRAINING_IMPORT = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
ACTIVITY_RISK_TRAINING_IMPORT_VALIDATION = (
    AI_ROOT / "reports" / "activity_risk_training_import_label_validation_report.json"
)
OUT = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
SCAFFOLD_OUT = AI_ROOT / "prototype" / "kwb_enzyme_designer_multitask_scaffold.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def count_present(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> int:
    return sum(1 for row in rows if any(row.get(key) is not None for key in keys))


def filter_activity_risk_training_import_label_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("head") == "activity_risk"
        and row.get("ready_for_training_import") is True
        and row.get("training_label_source") is True
        and row.get("label_value") not in (None, "")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build multi-task training readiness report")
    parser.add_argument("--strict", type=Path, default=STRICT)
    parser.add_argument("--audited", type=Path, default=AUDITED)
    parser.add_argument("--activity-risk-training-import", type=Path, default=ACTIVITY_RISK_TRAINING_IMPORT)
    parser.add_argument(
        "--activity-risk-training-import-validation",
        type=Path,
        default=ACTIVITY_RISK_TRAINING_IMPORT_VALIDATION,
    )
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--scaffold-output", type=Path, default=SCAFFOLD_OUT)
    args = parser.parse_args()

    strict_rows = load_jsonl(args.strict)
    audited_rows = load_jsonl(args.audited)
    activity_risk_import_rows = load_jsonl(args.activity_risk_training_import)
    activity_risk_import_label_rows = filter_activity_risk_training_import_label_rows(activity_risk_import_rows)
    activity_risk_import_validation = load_json(args.activity_risk_training_import_validation)
    activity_risk_import_report_rows = (
        activity_risk_import_validation.get("training_import_label_rows")
        if "training_import_label_rows" in activity_risk_import_validation
        else activity_risk_import_validation.get("training_import_written_rows")
    )
    activity_risk_import_report_rows = int(activity_risk_import_report_rows or 0)
    activity_risk_import_consistent = (
        bool(activity_risk_import_validation)
        and activity_risk_import_validation.get("success") is True
        and activity_risk_import_report_rows == len(activity_risk_import_label_rows)
        and activity_risk_import_validation.get("training_execution_allowed") is False
    )
    heads = {
        "mutation_rank": {
            "label_fields": ("label_decision",),
            "rows": count_present(strict_rows, ("label_decision",)),
            "minimum_rows": 100,
        },
        "stability": {
            "label_fields": ("label_stability_delta_tm_c", "label_ddg"),
            "rows": count_present(strict_rows, ("label_stability_delta_tm_c", "label_ddg")),
            "minimum_rows": 100,
        },
        "activity_risk": {
            "label_fields": ("activity_relative_to_wt", "activity_risk_label"),
            "rows": len(activity_risk_import_label_rows),
            "minimum_rows": 100,
            "source_rows": {
                "audited_training_table_label_rows": count_present(
                    audited_rows,
                    ("activity_relative_to_wt", "activity_risk_label"),
                ),
                "training_import_label_rows": len(activity_risk_import_label_rows),
                "training_import_jsonl_rows": len(activity_risk_import_rows),
                "training_import_validation_report_rows": activity_risk_import_report_rows,
            },
            "training_import_validation_success": activity_risk_import_validation.get("success") is True,
            "training_import_source_consistent": activity_risk_import_consistent,
            "training_execution_allowed": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "substrate_fit": {
            "label_fields": ("substrate_fit_label",),
            "rows": count_present(audited_rows, ("substrate_fit_label",)),
            "minimum_rows": 100,
        },
        "assay_success": {
            "label_fields": ("assay_success",),
            "rows": count_present(audited_rows, ("assay_success",)),
            "minimum_rows": 100,
        },
    }
    for head in heads.values():
        head["ready"] = head["rows"] >= head["minimum_rows"]
    scaffold = {
        "model": "KWB-EnzymeDesigner",
        "version": "0.2.0-multitask-scaffold",
        "status": "scaffold_only",
        "heads": {
            name: {
                "objective": "multi_task_prediction",
                "label_fields": info["label_fields"],
                "requires_verified_numbering": True,
                "requires_structure_features_for_structure_claims": True,
            }
            for name, info in heads.items()
        },
        "data_policy": "do not train or claim predictive quality until every required head meets its threshold",
    }
    args.scaffold_output.parent.mkdir(parents=True, exist_ok=True)
    args.scaffold_output.write_text(json.dumps(scaffold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "ready_for_multitask_training" if all(head["ready"] for head in heads.values()) else "blocked",
        "strict_rows": len(strict_rows),
        "audited_rows": len(audited_rows),
        "source_counts": {
            "strict_supervised_rows": len(strict_rows),
            "audited_training_rows": len(audited_rows),
            "activity_risk_training_import_jsonl_rows": len(activity_risk_import_rows),
            "activity_risk_training_import_label_rows": len(activity_risk_import_label_rows),
            "activity_risk_training_import_validation_report_rows": activity_risk_import_report_rows,
        },
        "source_consistency": {
            "activity_risk_training_import": {
                "validation_report_present": bool(activity_risk_import_validation),
                "validation_success": activity_risk_import_validation.get("success") is True,
                "jsonl_label_rows": len(activity_risk_import_label_rows),
                "validation_report_rows": activity_risk_import_report_rows,
                "training_execution_allowed": activity_risk_import_validation.get("training_execution_allowed") is True,
                "consistent": activity_risk_import_consistent,
            },
        },
        "heads": heads,
        "missing_head_labels": [name for name, head in heads.items() if not head["ready"]],
        "scaffold": str(args.scaffold_output),
        "ready_head_count": sum(1 for head in heads.values() if head["ready"]),
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "fail closed; this report never converts missing labels into synthetic supervision",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "strict_rows": report["strict_rows"],
        "missing_head_labels": report["missing_head_labels"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
