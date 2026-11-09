"""Fail-closed registry for versioned scientific model artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "name", "version", "sha256", "artifact_path", "task", "applicability_domain",
    "metrics", "units", "uncertainty_method",
}

PRODUCTION_EVIDENCE_FIELDS = {
    "row_level_conditions",
    "unit_and_method",
    "license",
    "independent_validation",
    "approval_record",
}


def _independent_validation_ready(manifest: dict[str, Any]) -> bool:
    evidence = manifest.get("production_evidence", {})
    path = evidence.get("independent_validation_manifest")
    if not path:
        return False
    validation_path = Path(str(path)).expanduser()
    if not validation_path.is_file():
        return False
    try:
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    metrics = validation.get("metrics", {})
    reviewer = validation.get("independent_reviewer", {})
    conditions = validation.get("conditions_required", [])
    return (
        validation.get("status") == "completed"
        and bool(validation.get("source_dataset_sha256"))
        and isinstance(validation.get("rows"), int) and validation["rows"] > 0
        and all(metrics.get(key) is not None for key in ("rmse", "mae", "n"))
        and all(isinstance(item, str) and item for item in conditions)
        and all(reviewer.get(key) for key in ("name", "organization", "report_uri", "signature"))
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: str | os.PathLike[str], *, allow_research: bool = False) -> dict[str, Any]:
    """Validate an artifact manifest and return an auditable readiness record."""
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        return {"status": "blocked_missing_manifest", "manifest_path": str(manifest_path)}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "blocked_invalid_manifest", "manifest_path": str(manifest_path), "detail": str(exc)}
    missing = sorted(REQUIRED_FIELDS - set(manifest))
    if missing:
        return {"status": "blocked_invalid_manifest", "manifest_path": str(manifest_path), "missing_fields": missing}
    artifact = Path(str(manifest["artifact_path"])).expanduser()
    if not artifact.is_absolute():
        artifact = (manifest_path.parent / artifact).resolve()
        if not artifact.is_file():
            artifact = (manifest_path.parent.parent / str(manifest["artifact_path"])).resolve()
    if not artifact.is_file():
        return {"status": "blocked_missing_artifact", "manifest_path": str(manifest_path), "artifact_path": str(artifact)}
    actual = _sha256(artifact)
    expected = str(manifest["sha256"]).lower()
    if actual != expected:
        return {"status": "blocked_artifact_hash_mismatch", "manifest_path": str(manifest_path), "artifact_path": str(artifact), "expected_sha256": expected, "actual_sha256": actual}
    if not manifest.get("validation", {}).get("held_out", False):
        return {"status": "blocked_missing_held_out_validation", "manifest_path": str(manifest_path), "artifact_path": str(artifact)}
    # Every production-approved model needs row-level provenance and a
    # redistributable license record; aggregate dataset claims are insufficient.
    # Keeping this task-agnostic prevents future pH/structure models from
    # bypassing the same commercial gate.
    if manifest.get("approved", False):
        evidence = manifest.get("production_evidence", {})
        required_evidence = {"row_level_conditions", "unit_and_method", "license"}
        missing_evidence = sorted(key for key in required_evidence if not evidence.get(key))
        if missing_evidence:
            return {
                "status": "blocked_missing_production_evidence",
                "manifest_path": str(manifest_path),
                "artifact_path": str(artifact),
                "missing_evidence": missing_evidence,
            }
    if not manifest.get("approved", False) and not (allow_research and manifest.get("execution_scope") == "research_only"):
        return {"status": "blocked_model_not_approved", "manifest_path": str(manifest_path), "artifact_path": str(artifact)}
    return {"status": "ready", "manifest_path": str(manifest_path), "artifact_path": str(artifact), "manifest": manifest}


def evaluate_production_gate(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Return an auditable promotion decision without mutating registration state."""
    result = load_manifest(path, allow_research=False)
    if result.get("status") != "ready":
        if result.get("status") == "blocked_missing_production_evidence":
            missing = list(result.get("missing_evidence", []))
            return {"status": "blocked", "reason": "production_evidence_incomplete", "missing": missing, "manifest_path": result.get("manifest_path", str(path))}
        if result.get("status") == "blocked_model_not_approved":
            research = load_manifest(path, allow_research=True)
            manifest = research.get("manifest", {})
            evidence = manifest.get("production_evidence", {})
            missing = sorted(field for field in PRODUCTION_EVIDENCE_FIELDS if not evidence.get(field))
            missing.append("approved")
            if manifest.get("execution_scope") == "research_only":
                missing.append("production_execution_scope")
            return {"status": "blocked", "reason": "production_evidence_incomplete", "missing": sorted(set(missing)), "manifest_path": result.get("manifest_path", str(path))}
        return {"status": "blocked", "reason": result.get("status"), "manifest_path": result.get("manifest_path", str(path))}
    manifest = result["manifest"]
    evidence = manifest.get("production_evidence", {})
    missing = sorted(field for field in PRODUCTION_EVIDENCE_FIELDS if not evidence.get(field))
    if not manifest.get("approved", False):
        missing.append("approved")
    if not _independent_validation_ready(manifest):
        missing.append("independent_validation")
    if manifest.get("execution_scope") == "research_only":
        missing.append("production_execution_scope")
    if missing:
        return {"status": "blocked", "reason": "production_evidence_incomplete", "missing": sorted(set(missing)), "manifest_path": result["manifest_path"]}
    return {"status": "eligible", "manifest_path": result["manifest_path"], "artifact_path": result["artifact_path"], "version": manifest.get("version"), "task": manifest.get("task")}


def configured_model(task: str) -> dict[str, Any]:
    env_name = {"km": "KM_MODEL_MANIFEST", "tm": "TM_MODEL_MANIFEST"}.get(task)
    if not env_name:
        raise ValueError(f"UNSUPPORTED_MODEL_TASK: {task}")
    configured = os.getenv(env_name, "").strip()
    if not configured:
        return {"status": "blocked_missing_validated_model", "task": task, "required_env": env_name}
    result = load_manifest(configured, allow_research=os.getenv("MODEL_EXECUTION_SCOPE", "production").strip() == "research_only")
    if result.get("status") == "ready" and result["manifest"].get("task") != task:
        return {"status": "blocked_model_task_mismatch", "task": task, "manifest_path": configured}
    if result.get("status") == "ready" and result.get("manifest", {}).get("production_registration") == "candidate" and os.getenv("MODEL_EXECUTION_SCOPE", "production").strip() == "research_only":
        return {"status": "blocked_production_candidate_in_research_scope", "task": task, "manifest_path": configured}
    if result.get("status") == "ready" and os.getenv("MODEL_EXECUTION_SCOPE", "production").strip() != "research_only":
        gate = evaluate_production_gate(configured)
        if gate["status"] != "eligible":
            return {"status": "blocked_production_gate", "task": task, "production_gate": gate}
    result["task"] = task
    return result


def run_inference(task: str, payload: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    """Run an approved model through an explicit JSON stdin/stdout contract."""
    runner = os.getenv(f"{task.upper()}_MODEL_RUNNER_BIN", "").strip()
    if not runner:
        return {"status": "blocked_model_runtime_not_configured", "task": task}
    try:
        # Manifests may use repository-relative paths. Pass the validated,
        # resolved artifact path so runners behave identically in containers.
        model_manifest = dict(readiness.get("manifest") or {})
        if readiness.get("artifact_path"):
            model_manifest["artifact_path"] = str(readiness["artifact_path"])
        completed = subprocess.run(
            [runner], input=json.dumps({"task": task, "model": model_manifest, "input": payload}),
            text=True, capture_output=True, timeout=300, check=True,
        )
        output = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"status": "blocked_model_runtime_failed", "task": task, "detail": type(exc).__name__}
    if isinstance(output, dict) and str(output.get("status", "")).startswith("blocked_"):
        return {**output, "task": task}
    if not isinstance(output, dict) or output.get("status") != "completed" or output.get("prediction") is None or output.get("uncertainty") is None:
        return {"status": "blocked_invalid_model_output", "task": task, "output": output}
    configured_scope = os.getenv("MODEL_EXECUTION_SCOPE", "production").strip() or "production"
    output_scope = output.get("execution_scope", "production")
    if output_scope != configured_scope:
        return {
            "status": "blocked_scope_mismatch",
            "task": task,
            "configured_scope": configured_scope,
            "output_scope": output_scope,
        }
    status = "research_completed_model_prediction" if configured_scope == "research_only" else "completed_model_prediction"
    return {"status": status, "task": task, "output": output}
