#!/usr/bin/env python3
"""Validate the split blocked human target source manifests."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index.json"
SPLIT_DIR = AI_ROOT / "reports" / "human_target_sources"
OUT = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index_validation_report.json"
INPUT = AI_ROOT / "reports" / "human_target_source_runtime_manifest.json"
BUILDER = AI_ROOT / "scripts" / "build_human_target_blocked_source_manifests.py"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_human_target_blocked_source_manifests", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate split blocked source manifests")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    index = load_json(args.index)
    builder = load_builder()
    failures: list[dict[str, Any]] = []
    rows = index.get("source_manifest_index") or []
    split_created_at: dict[str, str] = {}
    split_payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        rel_path = row.get("path")
        path = args.split_dir / Path(rel_path).name if rel_path else None
        split = load_json(path) if path else {}
        source_id = str(row.get("source_id") or split.get("source_id") or "")
        if source_id and split.get("created_at"):
            split_created_at[source_id] = str(split.get("created_at"))
        if source_id:
            split_payloads[source_id] = split

    expected_index, expected_splits = builder.build_manifests(
        input_path=args.input,
        created_at=index.get("created_at"),
        split_created_at=split_created_at,
    )
    expected_paths = {str(row["path"]) for row in expected_index.get("source_manifest_index") or []}
    observed_paths = {str(row.get("path")) for row in rows if isinstance(row, dict)}
    expected_source_ids = set(expected_splits)
    observed_source_ids = set(split_payloads)

    fail_if(not index, failures, "index_present", rel(args.index), "existing JSON report")
    fail_if(index != expected_index, failures, "index_matches_current_builder_projection", index, expected_index)
    fail_if(len(rows) != 7, failures, "split_count", len(rows), 7)
    fail_if(observed_paths != expected_paths, failures, "split_paths_match_builder_contract", sorted(observed_paths), sorted(expected_paths))
    fail_if(observed_source_ids != expected_source_ids, failures, "split_source_ids_match_builder_contract", sorted(observed_source_ids), sorted(expected_source_ids))

    for row in rows:
        rel_path = row.get("path")
        path = args.split_dir / Path(rel_path).name if rel_path else None
        split = load_json(path) if path else {}
        source_id = str(row.get("source_id") or split.get("source_id") or "")
        expected_split = expected_splits.get(source_id)
        if not split:
            failures.append({"check": "split_manifest_exists", "path": rel_path})
            continue
        if split != expected_split:
            failures.append({
                "check": "split_manifest_matches_current_builder_projection",
                "path": rel_path,
                "source_id": source_id,
                "observed": split,
                "expected": expected_split,
            })
        if split.get("source_ready") is not False or split.get("claim_eligible") is not False:
            failures.append({"check": "split_manifest_blocked", "path": rel_path, "observed": split.get("source_ready")})
        if split.get("release_ready") is not False:
            failures.append({"check": "split_release_ready_false", "path": rel_path})
    validation = {
        "local_only": True,
        "success": not failures,
        "checked_index": rel(args.index),
        "checked_split_dir": rel(args.split_dir),
        "checked_input": rel(args.input),
        "builder_contract": rel(BUILDER),
        "index_matches_current_builder_projection": index == expected_index,
        "split_manifests_match_current_builder_projection": all(
            split_payloads.get(source_id) == expected_split
            for source_id, expected_split in expected_splits.items()
        ),
        "expected_split_count": len(expected_splits),
        "split_count": len(rows),
        "failures": failures,
        "failure_count": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation only proves the split manifests are blocked and internally consistent.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "split_count": validation["split_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
