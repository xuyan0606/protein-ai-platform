#!/usr/bin/env python3
"""Validate reviewed-chain structure feature model-consumption boundary."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "structure_feature_model_contract_report.json"
VALIDATION_OUT = AI_ROOT / "reports" / "structure_feature_model_contract_validation_report.json"
REQUESTED_REVIEWED_GRAPH_INDEX = AI_ROOT / "datasets" / "curated" / "reviewed_structure_graph_features.jsonl"
FEATURES_REVIEWED_GRAPH_INDEX = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
GRAPH_REPORT = AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
COORDINATE_REPORT = AI_ROOT / "reports" / "structure_coordinate_feature_report.json"


def load_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        return {}, [{"check": "source_exists", "path": rel(path), "observed": False, "expected": True}]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [{"check": "source_json_parseable", "path": rel(path), "observed": str(exc), "expected": "valid_json"}]
    if not isinstance(value, dict):
        return {}, [{"check": "source_json_object", "path": rel(path), "observed": type(value).__name__, "expected": "dict"}]
    return value, []


def load_jsonl(path: Path, *, allow_missing: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        failure = {"check": "source_jsonl_exists", "path": rel(path), "observed": False, "expected": True}
        return [], ([] if allow_missing else [failure])
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [{"check": "source_jsonl_readable", "path": rel(path), "observed": str(exc), "expected": "readable"}]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({
                "check": "source_jsonl_row_parseable",
                "path": rel(path),
                "line": line_number,
                "observed": str(exc),
                "expected": "valid_json",
            })
            continue
        if not isinstance(value, dict):
            failures.append({
                "check": "source_jsonl_row_object",
                "path": rel(path),
                "line": line_number,
                "observed": type(value).__name__,
                "expected": "dict",
            })
            continue
        rows.append(value)
    return rows, failures


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


def resolve_reviewed_graph_index(report: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    source_inputs = report.get("source_inputs") if isinstance(report.get("source_inputs"), dict) else {}
    resolved = source_inputs.get("resolved_reviewed_graph_index")
    if resolved:
        path = Path(str(resolved))
        if not path.is_absolute():
            path = AI_ROOT / path
        if path.exists():
            return path, warnings
        warnings.append({"warning": "reported_resolved_reviewed_graph_index_missing", "path": rel(path)})

    if REQUESTED_REVIEWED_GRAPH_INDEX.exists():
        return REQUESTED_REVIEWED_GRAPH_INDEX, warnings
    warnings.append({"warning": "requested_reviewed_graph_index_missing", "path": rel(REQUESTED_REVIEWED_GRAPH_INDEX)})
    return FEATURES_REVIEWED_GRAPH_INDEX, warnings


def add_failure(
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
    **extra: Any,
) -> None:
    row = {"check": check, "observed": observed, "expected": expected}
    row.update(extra)
    failures.append(row)


def walk_true_flags(value: Any, path: str = "$") -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"training_label_source", "release_ready"} and child is True:
                failures.append({
                    "check": f"{key}_not_true",
                    "path": child_path,
                    "observed": child,
                    "expected": False,
                })
            failures.extend(walk_true_flags(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(walk_true_flags(child, f"{path}[{index}]"))
    return failures


def graph_key(row: dict[str, Any]) -> tuple[str, str]:
    return normalize_structure_id(row.get("structure_id")), str(row.get("selected_chain_id") or "")


def decision_key(row: dict[str, Any]) -> tuple[str, str]:
    return normalize_structure_id(row.get("structure_id")), str(row.get("selected_chain_id") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structure feature model contract report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_OUT)
    parser.add_argument("--reviewed-graph-report", type=Path, default=GRAPH_REPORT)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--coordinate-report", type=Path, default=COORDINATE_REPORT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    contract, load_failures = load_json(args.report)
    failures.extend(load_failures)
    graph_report, graph_report_failures = load_json(args.reviewed_graph_report)
    coordinate_report, coordinate_report_failures = load_json(args.coordinate_report)
    failures.extend(graph_report_failures)
    failures.extend(coordinate_report_failures)

    graph_index_path, graph_index_warnings = resolve_reviewed_graph_index(contract)
    warnings.extend(graph_index_warnings)
    graph_rows, graph_failures = load_jsonl(graph_index_path)
    decision_rows, decision_failures = load_jsonl(args.decisions)
    failures.extend(graph_failures)
    failures.extend(decision_failures)

    formal_decision_rows = [row for row in decision_rows if row.get("decision") == "set_chain_mapping"]
    graph_count = len(graph_rows)
    formal_count = len(formal_decision_rows)
    coordinate_rows = int_value(coordinate_report.get("feature_rows"))
    coordinate_manifest_rows = int_value(coordinate_report.get("manifest_rows"))
    coordinate_parse_failures = int_value(coordinate_report.get("parse_failures"))
    structures_with_atoms = int_value(coordinate_report.get("structures_with_atoms"))
    structures_with_ca_atoms = int_value(coordinate_report.get("structures_with_ca_atoms"))

    if graph_count > formal_count:
        add_failure(
            failures,
            "reviewed_graph_not_greater_than_formal_decisions",
            graph_count,
            f"<= {formal_count}",
        )

    graph_keys = {graph_key(row) for row in graph_rows}
    formal_keys = {decision_key(row) for row in formal_decision_rows}
    graph_without_formal = sorted(f"{sid}:{chain}" for sid, chain in graph_keys - formal_keys)
    if graph_without_formal:
        add_failure(
            failures,
            "reviewed_graph_rows_have_formal_chain_mapping_decisions",
            graph_without_formal,
            [],
        )

    contract_boundary = contract.get("reviewed_chain_graph_boundary") if isinstance(contract.get("reviewed_chain_graph_boundary"), dict) else {}
    consumption = contract.get("model_consumption_contract") if isinstance(contract.get("model_consumption_contract"), dict) else {}
    coordinate_evidence = contract.get("coordinate_file_parse_evidence") if isinstance(contract.get("coordinate_file_parse_evidence"), dict) else {}

    reported_model_consumable = int_value(consumption.get("model_consumable_reviewed_graph_rows"))
    if reported_model_consumable != graph_count:
        add_failure(
            failures,
            "model_consumable_reviewed_graph_rows_match_reviewed_graph_index",
            reported_model_consumable,
            graph_count,
        )
    if reported_model_consumable > formal_count:
        add_failure(
            failures,
            "model_consumable_reviewed_graph_rows_not_greater_than_formal_decisions",
            reported_model_consumable,
            f"<= {formal_count}",
        )

    unreviewed_counted = int_value(consumption.get("unreviewed_coordinate_rows_counted_as_model_consumable_reviewed_graph"))
    if unreviewed_counted != 0:
        add_failure(
            failures,
            "unreviewed_coordinate_rows_not_counted_into_model_consumable_reviewed_graph",
            unreviewed_counted,
            0,
        )

    coordinate_counted = int_value(consumption.get("coordinate_rows_counted_as_model_consumable_reviewed_graph"))
    if coordinate_counted != graph_count:
        add_failure(
            failures,
            "coordinate_rows_counted_as_model_consumable_reviewed_graph_limited_to_reviewed_graph",
            coordinate_counted,
            graph_count,
        )
    if coordinate_rows > graph_count and coordinate_counted == coordinate_rows:
        add_failure(
            failures,
            "unreviewed_coordinate_rows_counted_into_model_consumable_reviewed_graph",
            coordinate_counted,
            graph_count,
        )

    expected_unreviewed_excluded = max(coordinate_rows - graph_count, 0)
    reported_unreviewed_excluded = int_value(consumption.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"))
    if reported_unreviewed_excluded != expected_unreviewed_excluded:
        add_failure(
            failures,
            "unreviewed_coordinate_rows_excluded_count",
            reported_unreviewed_excluded,
            expected_unreviewed_excluded,
        )

    expected_coordinate_complete = (
        coordinate_manifest_rows == 500
        and coordinate_rows == 500
        and coordinate_parse_failures == 0
        and structures_with_atoms == 500
        and structures_with_ca_atoms == 500
    )
    if coordinate_evidence.get("coordinate_parse_complete") is not expected_coordinate_complete:
        add_failure(
            failures,
            "coordinate_parse_complete_matches_500_of_500_source_report",
            coordinate_evidence.get("coordinate_parse_complete"),
            expected_coordinate_complete,
        )
    if not expected_coordinate_complete:
        add_failure(
            failures,
            "source_coordinate_report_proves_500_of_500_parsed",
            {
                "manifest_rows": coordinate_manifest_rows,
                "feature_rows": coordinate_rows,
                "parse_failures": coordinate_parse_failures,
                "structures_with_atoms": structures_with_atoms,
                "structures_with_ca_atoms": structures_with_ca_atoms,
            },
            {
                "manifest_rows": 500,
                "feature_rows": 500,
                "parse_failures": 0,
                "structures_with_atoms": 500,
                "structures_with_ca_atoms": 500,
            },
        )

    if int_value(graph_report.get("graph_rows")) != graph_count:
        add_failure(
            failures,
            "reviewed_graph_report_rows_match_index",
            graph_report.get("graph_rows"),
            graph_count,
        )
    if int_value(graph_report.get("failure_rows")) != 0:
        add_failure(
            failures,
            "reviewed_graph_report_failure_rows_zero",
            graph_report.get("failure_rows"),
            0,
        )
    if int_value(contract_boundary.get("formal_chain_mapping_decision_rows")) != formal_count:
        add_failure(
            failures,
            "contract_formal_decision_rows_match_source",
            contract_boundary.get("formal_chain_mapping_decision_rows"),
            formal_count,
        )
    if int_value(contract_boundary.get("reviewed_graph_index_rows")) != graph_count:
        add_failure(
            failures,
            "contract_reviewed_graph_rows_match_source",
            contract_boundary.get("reviewed_graph_index_rows"),
            graph_count,
        )

    failures.extend(walk_true_flags(contract))
    for key in ("safe_for_model_claim", "model_claim_allowed", "release_or_model_claim_allowed"):
        if consumption.get(key) is not False:
            add_failure(failures, f"{key}_false", consumption.get(key), False)
    if contract.get("safe_for_model_claim") is not False:
        add_failure(failures, "contract_safe_for_model_claim_false", contract.get("safe_for_model_claim"), False)
    if contract.get("release_ready") is not False:
        add_failure(failures, "contract_release_ready_false", contract.get("release_ready"), False)
    if contract.get("training_label_source") is not False:
        add_failure(failures, "contract_training_label_source_false", contract.get("training_label_source"), False)

    success = not failures
    validation = {
        "report_id": "structure_feature_model_contract_validation_report",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": success,
        "status": "passed_fail_closed" if success else "failed_closed",
        "checked_report": rel(args.report),
        "checked_sources": {
            "reviewed_graph_index": rel(graph_index_path),
            "reviewed_structure_graph_feature_report": rel(args.reviewed_graph_report),
            "structure_chain_mapping_decisions": rel(args.decisions),
            "structure_coordinate_feature_report": rel(args.coordinate_report),
        },
        "coordinate_manifest_rows": coordinate_manifest_rows,
        "coordinate_rows_parsed": coordinate_rows,
        "coordinate_parse_failures": coordinate_parse_failures,
        "reviewed_graph_rows": graph_count,
        "formal_chain_mapping_decision_rows": formal_count,
        "model_consumable_reviewed_graph_rows": reported_model_consumable,
        "unreviewed_coordinate_rows_excluded_from_reviewed_graph": expected_unreviewed_excluded,
        "training_label_source": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "warnings": warnings,
        "failures": failures,
        "policy": (
            "Fail-closed validator for reviewed-chain structure graph consumption: "
            "model consumable rows must be formal reviewed graph input features only, "
            "never labels or release/model claims."
        ),
    }
    args.validation_report.parent.mkdir(parents=True, exist_ok=True)
    args.validation_report.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "coordinate_rows_parsed": coordinate_rows,
        "reviewed_graph_rows": graph_count,
        "formal_decision_rows": formal_count,
        "failures": len(failures),
        "output": str(args.validation_report),
    }, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
