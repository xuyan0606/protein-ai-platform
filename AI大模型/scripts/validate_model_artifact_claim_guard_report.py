#!/usr/bin/env python3
"""Validate model artifacts cannot be mistaken for claimable trained weights."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "model_artifact_claim_guard_report.json"
OUT = AI_ROOT / "reports" / "model_artifact_claim_guard_validation_report.json"
BUILDER = AI_ROOT / "scripts" / "build_model_artifact_claim_guard_report.py"


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_model_artifact_claim_guard_report", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def expected_report(builder: Any, created_at: str) -> dict[str, Any]:
    artifacts = [builder.build_row(rel_path) for rel_path in builder.MODEL_ARTIFACTS]
    missing = [row["path"] for row in artifacts if not row["exists"]]
    claimable = [row for row in artifacts if row["claimable_model_artifact"]]
    trained_neural = [row for row in artifacts if row["trained_neural_weights"]]
    production = [row for row in artifacts if row["production_model_artifact"]]
    class_counts: dict[str, int] = {}
    for row in artifacts:
        class_counts[row["artifact_class"]] = class_counts.get(row["artifact_class"], 0) + 1
    return {
        "created_at": created_at,
        "local_only": True,
        "success": not missing,
        "artifact_count": len(artifacts),
        "missing_artifacts": missing,
        "class_counts": class_counts,
        "artifacts": artifacts,
        "claimable_model_artifact_count": len(claimable),
        "trained_neural_weight_artifact_count": len(trained_neural),
        "production_model_artifact_count": len(production),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Existing prototype artifacts are retained for audit and local regression only. "
            "Legacy baselines, empty-train baselines, and scaffolds are not claimable top-tier model weights."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate model artifact claim guard report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    builder = load_builder()
    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), list) else []
    expected = expected_report(builder, str(report.get("created_at") or ""))
    expected_artifact_count = len(builder.MODEL_ARTIFACTS)

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report != expected, failures, "report_matches_current_artifact_sources", report, expected)
    fail_if(report.get("success") is not True, failures, "report_success_true", report.get("success"), True)
    fail_if(report.get("artifact_count") != expected_artifact_count, failures, "artifact_count_expected", report.get("artifact_count"), expected_artifact_count)
    fail_if(len(artifacts) != expected_artifact_count, failures, "artifact_rows_expected", len(artifacts), expected_artifact_count)
    fail_if(report.get("missing_artifacts") not in ([], None), failures, "missing_artifacts_empty", report.get("missing_artifacts"), [])
    fail_if(report.get("class_counts") != expected.get("class_counts"), failures, "class_counts_match_current_artifacts", report.get("class_counts"), expected.get("class_counts"))

    for key in ("claimable_model_artifact_count", "trained_neural_weight_artifact_count", "production_model_artifact_count"):
        fail_if(report.get(key) != 0, failures, f"{key}_zero", report.get(key), 0)
    for key in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(key) is not False, failures, f"report_{key}_false", report.get(key), False)

    allowed_classes = {
        "legacy_baseline_not_claimable",
        "rule_or_baseline_not_neural_weights",
        "blocked_empty_training_baseline",
        "scaffold_only_not_trained_weights",
        "code_scaffold_not_weights",
    }
    for idx, row in enumerate(artifacts):
        if not isinstance(row, dict):
            failures.append({"check": "artifact_row_object", "index": idx, "observed": type(row).__name__, "expected": "object"})
            continue
        fail_if(row.get("exists") is not True, failures, "artifact_exists", {"index": idx, "path": row.get("path"), "observed": row.get("exists")}, True)
        fail_if(not row.get("sha256"), failures, "artifact_sha256_present", {"index": idx, "path": row.get("path")}, "sha256")
        fail_if(row.get("artifact_class") not in allowed_classes, failures, "artifact_class_allowed", {"index": idx, "path": row.get("path"), "class": row.get("artifact_class")}, sorted(allowed_classes))
        for key in ("claimable_model_artifact", "trained_neural_weights", "production_model_artifact", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(key) is not False, failures, f"artifact_{key}_false", {"index": idx, "path": row.get("path"), "observed": row.get(key)}, False)
        fail_if(not row.get("blocked_reasons"), failures, "artifact_blocked_reasons_present", {"index": idx, "path": row.get("path")}, "non-empty blocked reasons")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checked_report": rel(args.report),
        "builder_contract": rel(BUILDER),
        "builder_artifact_paths": list(builder.MODEL_ARTIFACTS),
        "artifact_count": report.get("artifact_count"),
        "expected_artifact_count": expected_artifact_count,
        "class_counts": report.get("class_counts"),
        "report_matches_current_artifact_sources": report == expected,
        "claimable_model_artifact_count": report.get("claimable_model_artifact_count"),
        "trained_neural_weight_artifact_count": report.get("trained_neural_weight_artifact_count"),
        "production_model_artifact_count": report.get("production_model_artifact_count"),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validation for model artifact claim isolation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "artifact_count": validation["artifact_count"],
        "claimable_model_artifact_count": validation["claimable_model_artifact_count"],
        "trained_neural_weight_artifact_count": validation["trained_neural_weight_artifact_count"],
        "production_model_artifact_count": validation["production_model_artifact_count"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
