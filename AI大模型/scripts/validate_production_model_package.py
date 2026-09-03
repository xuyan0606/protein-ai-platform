"""Validate a deployable KWB production model package without executing it."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


REQUIRED_EVIDENCE = ("feature_contract", "training", "evaluation", "release")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: Any) -> Optional[Path]:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    candidate = (root / value).resolve()
    return candidate if candidate.is_relative_to(root.resolve()) else None


def _check_artifact(root: Path, row: dict[str, Any], label: str, failures: list[str]) -> bool:
    path = _resolve(root, row.get("path"))
    expected = row.get("sha256")
    if path is None or not path.is_file():
        failures.append(f"{label}: artifact path is missing or outside package root")
        return False
    if not isinstance(expected, str) or len(expected) != 64 or _sha256(path) != expected:
        failures.append(f"{label}: sha256 mismatch")
        return False
    return True


def validate_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        return {"status": "blocked_missing_manifest", "production_model_artifact": False, "artifact_count": 0, "failures": ["manifest is missing"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "blocked_invalid", "production_model_artifact": False, "artifact_count": 0, "failures": ["manifest is not valid JSON"]}
    failures: list[str] = []
    root = manifest_path.parent
    if manifest.get("schema_version") != "production_model_package_v1":
        failures.append("schema_version must be production_model_package_v1")
    model = manifest.get("model") if isinstance(manifest.get("model"), dict) else {}
    if not isinstance(model.get("name"), str) or not isinstance(model.get("version"), str):
        failures.append("model name and version are required")
    entrypoint = manifest.get("inference_entrypoint") if isinstance(manifest.get("inference_entrypoint"), dict) else {}
    artifact_count = 0
    if _check_artifact(root, entrypoint, "inference_entrypoint", failures) and isinstance(entrypoint.get("symbol"), str) and entrypoint["symbol"]:
        artifact_count += 1
    else:
        if not isinstance(entrypoint.get("symbol"), str) or not entrypoint.get("symbol"):
            failures.append("inference_entrypoint symbol is required")
    weights = manifest.get("weights")
    if not isinstance(weights, list) or not weights:
        failures.append("at least one neural weight artifact is required")
    else:
        for index, weight in enumerate(weights):
            if not isinstance(weight, dict) or weight.get("artifact_type") != "neural_weights":
                failures.append(f"weights[{index}] must be a neural_weights artifact")
                continue
            if _check_artifact(root, weight, f"weights[{index}]", failures):
                artifact_count += 1
            if weight.get("size_bytes") != (_resolve(root, weight.get("path")).stat().st_size if _resolve(root, weight.get("path")) and _resolve(root, weight.get("path")).is_file() else None):
                failures.append(f"weights[{index}]: size_bytes mismatch")
    for name in REQUIRED_EVIDENCE:
        row = manifest.get(name)
        if not isinstance(row, dict):
            failures.append(f"{name}: evidence reference is required")
            continue
        if _check_artifact(root, row, name, failures):
            artifact_count += 1
    return {
        "status": "validated" if not failures else "blocked_invalid",
        "production_model_artifact": not failures,
        "artifact_count": artifact_count,
        "failures": failures,
        "manifest": str(manifest_path),
        "model": model,
        "policy": "A production package must contain hash-verified neural weights, an inference entrypoint, and hash-verified feature/training/evaluation/release evidence. Validation does not authorize release by itself.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_manifest(args.manifest)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "validated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
