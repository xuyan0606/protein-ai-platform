#!/usr/bin/env python3
"""Build a fail-closed manifest for provenance-backed five-head training inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
DEFAULT_FEATURES = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
DEFAULT_OUTPUT = AI_ROOT / "reports" / "five_head_training_input_manifest.json"
EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)
MINIMUM_SAMPLES = 100
MINIMUM_GROUPS = 10
MINIMUM_REPLICATES = 3


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        rows.append(value)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_identity(row: dict[str, Any]) -> str:
    explicit = row.get("group_id")
    if explicit not in (None, ""):
        return str(explicit)
    parts = [
        f"{key}={row[key]}"
        for key in ("project_id", "enzyme_id", "uniprot_id", "mutation")
        if row.get(key) not in (None, "")
    ]
    return "|".join(parts) if parts else str(row.get("training_import_label_id") or "unknown")


def replicate_identity(row: dict[str, Any]) -> str | None:
    for key in ("replicate_id", "replicate_group_id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def eligible_label(row: dict[str, Any]) -> bool:
    return (
        row.get("head") in EXPECTED_HEADS
        and row.get("label_value") not in (None, "")
        and row.get("training_label_source") is True
        and row.get("ready_for_training_import") is True
        and row.get("safe_for_training_import") is True
    )


def build_manifest(label_paths: list[Path], feature_index_path: Path) -> dict[str, Any]:
    source_rows = [row for path in label_paths for row in load_jsonl(path)]
    label_rows = [row for row in source_rows if eligible_label(row)]
    feature_rows = [
        row
        for row in load_jsonl(feature_index_path)
        if row.get("model_consumable") is True
        and row.get("training_label_source") is not True
    ]
    features_by_uniprot: dict[str, list[dict[str, Any]]] = {}
    for row in feature_rows:
        uniprot_id = row.get("uniprot_id")
        if uniprot_id not in (None, ""):
            features_by_uniprot.setdefault(str(uniprot_id), []).append(row)

    exact_feature_join_rows = 0
    joined_feature_families: set[str] = set()
    for row in label_rows:
        uniprot_id = row.get("uniprot_id")
        matches = features_by_uniprot.get(str(uniprot_id), []) if uniprot_id not in (None, "") else []
        if matches:
            exact_feature_join_rows += 1
            joined_feature_families.update(
                str(match.get("feature_family"))
                for match in matches
                if match.get("feature_family")
            )

    head_stats: dict[str, dict[str, Any]] = {}
    for head in EXPECTED_HEADS:
        rows = [row for row in label_rows if row.get("head") == head]
        groups = {group_identity(row) for row in rows}
        replicates = {
            value for value in (replicate_identity(row) for row in rows) if value is not None
        }
        thresholds_met = (
            len(rows) >= MINIMUM_SAMPLES
            and len(groups) >= MINIMUM_GROUPS
            and len(replicates) >= MINIMUM_REPLICATES
        )
        head_stats[head] = {
            "label_rows": len(rows),
            "group_count": len(groups),
            "explicit_replicate_count": len(replicates),
            "thresholds_met": thresholds_met,
        }

    rows_without_exact_feature_join = len(label_rows) - exact_feature_join_rows
    all_heads_ready = all(head_stats[head]["thresholds_met"] for head in EXPECTED_HEADS)
    source_artifacts = [
        {
            "path": str(path),
            "present": path.is_file(),
            "sha256": sha256(path) if path.is_file() else None,
            "rows": len(load_jsonl(path)),
        }
        for path in label_paths
    ]
    return {
        "schema_version": "kwb_five_head_training_input_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_artifacts": source_artifacts,
        "dataset_sha256": (
            source_artifacts[0]["sha256"] if len(source_artifacts) == 1 else None
        ),
        "feature_index": {
            "path": str(feature_index_path),
            "present": feature_index_path.is_file(),
            "sha256": sha256(feature_index_path) if feature_index_path.is_file() else None,
            "model_consumable_rows": len(feature_rows),
        },
        "source_rows": len(source_rows),
        "label_rows": len(label_rows),
        "rejected_rows": len(source_rows) - len(label_rows),
        "head_stats": head_stats,
        "exact_feature_join_policy": "exact non-empty uniprot_id only",
        "exact_feature_join_rows": exact_feature_join_rows,
        "rows_without_exact_feature_join": rows_without_exact_feature_join,
        "joined_feature_families": sorted(joined_feature_families),
        "feature_rows_counted_as_labels": 0,
        "all_heads_meet_thresholds": all_heads_ready,
        "ready_for_training_execution": (
            all_heads_ready
            and bool(label_rows)
            and len(source_rows) == len(label_rows)
            and rows_without_exact_feature_join == 0
        ),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Only formally imported label rows are counted. Features join only by exact protein "
            "identity and never become labels. Manifest readiness does not authorize a model claim or release."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head training input manifest")
    parser.add_argument("--labels", type=Path, action="append", default=None)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    label_paths = args.labels or [DEFAULT_LABELS]
    manifest = build_manifest(label_paths, args.features)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "label_rows": manifest["label_rows"],
                "exact_feature_join_rows": manifest["exact_feature_join_rows"],
                "ready_for_training_execution": manifest["ready_for_training_execution"],
                "safe_for_model_claim": False,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
