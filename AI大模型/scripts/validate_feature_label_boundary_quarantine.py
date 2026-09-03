#!/usr/bin/env python3
"""Validate legacy site-level feature artifacts stay label-quarantined."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATED_FEATURE_INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
SITE_SEQUENCE_FEATURES = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_site_sequence_features.jsonl"
STRICT_MSA_SITE_FEATURES = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_strict_msa_site_features.jsonl"
INDEX_VALIDATION_REPORT = AI_ROOT / "reports" / "validated_feature_index_validation_report.json"
OUT = AI_ROOT / "reports" / "feature_label_boundary_quarantine_report.json"

BOUNDARY_CONTROL_FIELDS = {
    "training_label_source",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
}


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT.resolve()))
    except ValueError:
        return str(path)


def resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else AI_ROOT / candidate


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return rows, [{"line": None, "error": "missing_file"}]
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_no, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            errors.append({"line": line_no, "error": "jsonl_row_not_object"})
            continue
        rows.append(payload)
    return rows, errors


def boundary_field_name(key: str) -> str | None:
    if key.startswith("label_"):
        return key
    if key in BOUNDARY_CONTROL_FIELDS:
        return key
    return None


def walk_boundary_fields(value: Any, path: str = "") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            field_name = boundary_field_name(str(key))
            if field_name:
                hits.append({"json_path": child_path, "field": field_name})
            hits.extend(walk_boundary_fields(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            hits.extend(walk_boundary_fields(child, f"{path}[{idx}]"))
    return hits


def collect_index_references(index_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    references: dict[str, list[dict[str, Any]]] = {}
    path_fields = ("feature_path", "secondary_artifact_path", "validator_report")
    for idx, row in enumerate(index_rows):
        for field in path_fields:
            value = row.get(field)
            if not value:
                continue
            path = rel(resolve(str(value)))
            references.setdefault(path, []).append({
                "index": idx,
                "feature_index_id": row.get("feature_index_id"),
                "field": field,
            })
    return references


def audit_artifact(path: Path, index_references: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows, errors = load_jsonl(path)
    rel_path = rel(path)
    contaminated_records: list[dict[str, Any]] = []
    field_counts: dict[str, int] = {}
    field_record_counts: dict[str, int] = {}

    for idx, row in enumerate(rows):
        hits = walk_boundary_fields(row)
        if not hits:
            continue
        field_names = sorted({hit["field"] for hit in hits})
        for field in field_names:
            field_record_counts[field] = field_record_counts.get(field, 0) + 1
        for hit in hits:
            field = hit["field"]
            field_counts[field] = field_counts.get(field, 0) + 1
        contaminated_records.append({
            "row_index": idx,
            "record_id": row.get("record_id"),
            "field_names": field_names,
            "json_paths": sorted({hit["json_path"] for hit in hits}),
        })

    index_hits = index_references.get(rel_path, [])
    excluded_from_index = not index_hits
    boundary_safe = not errors and excluded_from_index
    return {
        "path": rel_path,
        "exists": path.exists(),
        "row_count": len(rows),
        "parse_error_count": len(errors),
        "parse_errors": errors,
        "label_contaminated": bool(contaminated_records),
        "contaminated_record_count": len(contaminated_records),
        "field_names": sorted(field_record_counts),
        "field_record_counts": dict(sorted(field_record_counts.items())),
        "field_occurrence_counts": dict(sorted(field_counts.items())),
        "sample_contaminated_records": contaminated_records[:10],
        "excluded_from_validated_feature_index": excluded_from_index,
        "validated_feature_index_references": index_hits,
        "boundary_safe": boundary_safe,
    }


def index_boundary_failures(index_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for idx, row in enumerate(index_rows):
        for hit in walk_boundary_fields(row):
            field = hit["field"]
            value = row
            for part in hit["json_path"].split("."):
                if isinstance(value, dict):
                    value = value.get(part)
            if field.startswith("label_"):
                failures.append({
                    "check": "validated_feature_index_has_no_label_fields",
                    "index": idx,
                    "feature_index_id": row.get("feature_index_id"),
                    "json_path": hit["json_path"],
                    "field": field,
                    "expected": "absent from input-only index rows",
                })
            elif value is not False:
                failures.append({
                    "check": "validated_feature_index_boundary_control_fields_false",
                    "index": idx,
                    "feature_index_id": row.get("feature_index_id"),
                    "json_path": hit["json_path"],
                    "field": field,
                    "observed": value,
                    "expected": False,
                })
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate feature-label boundary quarantine")
    parser.add_argument("--validated-feature-index", type=Path, default=VALIDATED_FEATURE_INDEX)
    parser.add_argument("--site-sequence-features", type=Path, default=SITE_SEQUENCE_FEATURES)
    parser.add_argument("--strict-msa-site-features", type=Path, default=STRICT_MSA_SITE_FEATURES)
    parser.add_argument("--index-validation-report", type=Path, default=INDEX_VALIDATION_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    index_rows, index_errors = load_jsonl(args.validated_feature_index)
    if index_errors:
        failures.append({
            "check": "validated_feature_index_parseable",
            "path": rel(args.validated_feature_index),
            "errors": index_errors,
            "expected": "existing JSONL with object rows",
        })

    index_validation = load_json(args.index_validation_report)
    if not args.index_validation_report.exists():
        failures.append({
            "check": "validated_feature_index_validation_report_exists",
            "path": rel(args.index_validation_report),
            "expected": "existing report",
        })
    elif index_validation.get("success") is not True:
        failures.append({
            "check": "validated_feature_index_validation_success",
            "path": rel(args.index_validation_report),
            "observed": index_validation.get("success"),
            "expected": True,
        })

    failures.extend(index_boundary_failures(index_rows))
    index_references = collect_index_references(index_rows)
    artifact_paths = [args.site_sequence_features, args.strict_msa_site_features]
    scanned_artifacts = [audit_artifact(path, index_references) for path in artifact_paths]

    for artifact in scanned_artifacts:
        if not artifact["exists"]:
            failures.append({
                "check": "site_level_feature_artifact_exists",
                "path": artifact["path"],
                "expected": "existing artifact",
            })
        if artifact["parse_error_count"]:
            failures.append({
                "check": "site_level_feature_artifact_parseable",
                "path": artifact["path"],
                "observed": artifact["parse_errors"],
                "expected": "valid JSONL object rows",
            })
        if artifact["label_contaminated"] and not artifact["excluded_from_validated_feature_index"]:
            failures.append({
                "check": "label_contaminated_artifact_excluded_from_validated_feature_index",
                "path": artifact["path"],
                "field_names": artifact["field_names"],
                "validated_feature_index_references": artifact["validated_feature_index_references"],
                "expected": "no validated_feature_index references",
            })

    label_contaminated_artifacts = [
        artifact for artifact in scanned_artifacts if artifact["label_contaminated"]
    ]
    excluded_from_index_artifacts = [
        {
            "path": artifact["path"],
            "label_contaminated": artifact["label_contaminated"],
            "contaminated_record_count": artifact["contaminated_record_count"],
            "field_names": artifact["field_names"],
        }
        for artifact in scanned_artifacts
        if artifact["excluded_from_validated_feature_index"]
    ]
    boundary_safe_artifacts = [
        {
            "path": artifact["path"],
            "label_contaminated": artifact["label_contaminated"],
            "excluded_from_validated_feature_index": artifact["excluded_from_validated_feature_index"],
            "boundary_safe": artifact["boundary_safe"],
        }
        for artifact in scanned_artifacts
        if artifact["boundary_safe"]
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "input_only_boundary": True,
        "validated_feature_index": rel(args.validated_feature_index),
        "validated_feature_index_rows": len(index_rows),
        "validated_feature_index_validation_report": {
            "path": rel(args.index_validation_report),
            "exists": args.index_validation_report.exists(),
            "success": index_validation.get("success"),
        },
        "scanned_artifacts": scanned_artifacts,
        "boundary_safe_artifacts": boundary_safe_artifacts,
        "label_contaminated_artifacts": label_contaminated_artifacts,
        "excluded_from_index_artifacts": excluded_from_index_artifacts,
        "label_contaminated_artifact_count": len(label_contaminated_artifacts),
        "label_contaminated_record_count": sum(
            artifact["contaminated_record_count"] for artifact in label_contaminated_artifacts
        ),
        "excluded_from_index_artifact_count": len(excluded_from_index_artifacts),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Legacy site-level feature artifacts may carry label_* fields, but they must remain excluded from "
            "the validated_feature_index input-only feature boundary. This validator is read-only and does not "
            "authorize training import, model claims, formal reviewed decisions, or release."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "scanned_artifacts": len(scanned_artifacts),
        "label_contaminated_artifact_count": report["label_contaminated_artifact_count"],
        "label_contaminated_record_count": report["label_contaminated_record_count"],
        "excluded_from_index_artifact_count": report["excluded_from_index_artifact_count"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
