"""Fail-closed production entry point for KWB-EnzymeDesigner.

This adapter deliberately does not fall back to heuristic/proxy scores.  It
only becomes an inference boundary after the audited production gate and a
validated model package are present.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.tools.registry import ToolRegistry


AI_ROOT = Path(__file__).resolve().parents[3] / "AI大模型"
PRODUCTION_GATE_REPORT = AI_ROOT / "reports" / "production_model_gate_20260829.json"
MODEL_PACKAGE_MANIFEST = AI_ROOT / "reports" / "production_model_package_manifest.json"
MODEL_PACKAGE_VALIDATION = AI_ROOT / "reports" / "production_model_package_validation_report.json"
_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
_GOALS = frozenset({"activity", "thermostability", "specificity", "ph_lowering", "ph_raising", "general"})
_MUTATION_RE = re.compile(r"^[A-Z]\d+[A-Z]$")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _validate_sequence(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("sequence must be a string")
    sequence = value.strip().upper()
    if not 20 <= len(sequence) <= 10_000:
        raise ValueError("sequence length must be between 20 and 10000 residues")
    if any(residue not in _STANDARD_AA for residue in sequence):
        raise ValueError("sequence contains non-standard amino-acid symbols")
    return sequence


def _validate_goal(value: Any) -> str:
    goal = str(value or "").strip().lower()
    if goal not in _GOALS:
        raise ValueError(f"engineering_goal must be one of {sorted(_GOALS)}")
    return goal


def _validate_mutations(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 512:
        raise ValueError("candidate_mutations must be a list with at most 512 entries")
    mutations = []
    for mutation in value:
        if not isinstance(mutation, str) or not _MUTATION_RE.fullmatch(mutation.strip().upper()):
            raise ValueError("candidate_mutations entries must use format A123G")
        mutations.append(mutation.strip().upper())
    return mutations


def _input_hash(sequence: str, engineering_goal: str, candidate_mutations: list[str], uniprot_id: str | None) -> str:
    canonical = json.dumps(
        {
            "sequence": sequence,
            "engineering_goal": engineering_goal,
            "candidate_mutations": candidate_mutations,
            "uniprot_id": uniprot_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _contract(
    *,
    status: str,
    sequence: str,
    engineering_goal: str,
    candidate_mutations: list[str],
    uniprot_id: str | None,
    blockers: list[str],
    failure_reason: str,
    gate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "capability_status": "production_model_gate",
        "model": "KWB-EnzymeDesigner",
        "version": "unreleased",
        "checkpoint_or_weight": None,
        "input_sha256": _input_hash(sequence, engineering_goal, candidate_mutations, uniprot_id),
        "runtime": {
            "local_only": True,
            "inference_executed": False,
            "production_gate_report": str(PRODUCTION_GATE_REPORT),
            "model_package_validation_report": str(MODEL_PACKAGE_VALIDATION),
        },
        "logs": [{"stage": "production_gate", "status": "blocked", "blocker_count": len(blockers)}],
        "artifact_manifest": {"version": 1, "total_count": 0, "artifacts": []},
        "scientific_boundary": "未通过生产级门禁前不执行模型推理；不得把 proxy、规则或候选建议写成模型预测。",
        "evidence_level": "blocked",
        "production_ready": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "training_execution_allowed": False,
        "engineering_goal": engineering_goal,
        "candidate_mutations": candidate_mutations,
        "candidates": [],
        "blockers": blockers,
        "failure_reason": failure_reason,
        "gate_evidence": gate.get("evidence", {}),
    }


def kwb_enzyme_designer(
    sequence: str,
    engineering_goal: str,
    candidate_mutations: list[str] | None = None,
    uniprot_id: str | None = None,
) -> dict[str, Any]:
    normalized_sequence = _validate_sequence(sequence)
    goal = _validate_goal(engineering_goal)
    mutations = _validate_mutations(candidate_mutations)
    accession = str(uniprot_id).strip().upper() if uniprot_id is not None else None
    if accession and not re.fullmatch(r"[A-Z0-9]{1,20}", accession):
        raise ValueError("uniprot_id must be an accession-like identifier")

    gate = _load_json(PRODUCTION_GATE_REPORT)
    blockers = list(gate.get("blockers") or [])
    if gate.get("production_ready") is not True:
        return _contract(
            status="blocked_pending_production_gate",
            sequence=normalized_sequence,
            engineering_goal=goal,
            candidate_mutations=mutations,
            uniprot_id=accession,
            blockers=blockers or ["production gate report is missing or not ready"],
            failure_reason="production model gate is not satisfied",
            gate=gate,
        )

    package = _load_json(MODEL_PACKAGE_MANIFEST)
    package_validation = _load_json(MODEL_PACKAGE_VALIDATION)
    package_ready = (
        package_validation.get("status") == "validated"
        and package_validation.get("production_model_artifact") is True
        and package.get("status") == "validated"
        and package.get("inference_entrypoint")
    )
    if not package_ready:
        return _contract(
            status="blocked_missing_model_package",
            sequence=normalized_sequence,
            engineering_goal=goal,
            candidate_mutations=mutations,
            uniprot_id=accession,
            blockers=["validated production model package/inference entrypoint is missing"],
            failure_reason="production gate passed but no validated model package is installed",
            gate=gate,
        )

    return _contract(
        status="blocked_missing_model_adapter",
        sequence=normalized_sequence,
        engineering_goal=goal,
        candidate_mutations=mutations,
        uniprot_id=accession,
        blockers=["validated model adapter execution is not installed"],
        failure_reason="model package adapter is not available in this local build",
        gate=gate,
    )


ToolRegistry.register(
    name="kwb_enzyme_designer",
    description=(
        "Production-gated KWB enzyme design inference boundary. Requires an audited "
        "production model gate and validated model package; otherwise returns a "
        "structured blocked result and never falls back to proxy or rule scores."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein sequence (20-10000 standard amino acids)."},
            "engineering_goal": {"type": "string", "enum": sorted(_GOALS), "description": "Engineering objective."},
            "candidate_mutations": {"type": "array", "items": {"type": "string"}, "description": "Optional mutations such as A123G."},
            "uniprot_id": {"type": "string", "description": "Optional UniProt accession."},
        },
        "required": ["sequence", "engineering_goal"],
    },
    handler=kwb_enzyme_designer,
    category="prediction",
    timeout_seconds=30,
    annotations={
        "local_only": True,
        "requires_production_gate": True,
        "safe_for_model_claim": False,
        "release_ready": False,
    },
    errors=[
        {"reason": "invalid_input", "code": "INVALID_SEQUENCE", "when": "sequence or mutation input fails whitelist validation", "recovery": "Provide 20-10000 standard amino-acid residues and A123G mutation strings."},
        {"reason": "validation_failed", "code": "PRODUCTION_GATE_BLOCKED", "when": "production evidence is incomplete", "recovery": "Complete audited model, data, evaluation, release, and deployment gates before retrying."},
    ],
)
