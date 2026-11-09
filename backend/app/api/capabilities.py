"""Runtime status for scientific model and data capabilities."""

from __future__ import annotations

import os
import shutil

import httpx
from fastapi import APIRouter

from app.tools.registry import ToolRegistry


router = APIRouter()


def _commercial_gate(env_name: str) -> dict[str, str]:
    """Expose a separate commercial gate; runtime health is not approval."""
    approved = os.getenv(env_name, "").strip().lower() == "true"
    return {
        "status": "approved" if approved else "blocked",
        "required_env": env_name,
        "detail": "Commercial evidence and approval recorded." if approved else "Runtime may be research-only; commercial evidence and approval are not recorded.",
    }


def _interproscan_status() -> dict[str, str | bool]:
    configured = bool(os.getenv("INTERPROSCAN_EMAIL", "").strip())
    return {
        "status": "configured" if configured else "missing_contact_email",
        "configured": configured,
        "external_service": "InterProScan REST",
        "detail": "External submissions can be attempted." if configured else "Set INTERPROSCAN_EMAIL before external submissions.",
    }


def _binary_status(env_names: tuple[str, ...], command: str, capability: str, approval_env: str) -> dict:
    configured = next((os.getenv(name, "").strip() for name in env_names if os.getenv(name, "").strip()), "")
    executable = None
    if configured:
        candidate = shutil.which(configured) if "/" not in configured else configured
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            executable = candidate
    else:
        executable = shutil.which(command)
    if not executable:
        return {
            "status": "missing_executable",
            "evidence_level": "none",
            "commercial_gate": _commercial_gate(approval_env),
            "capability": capability,
            "detail": f"No executable {command} runtime was detected.",
        }
    digest = None
    try:
        digest = _sha256_file(executable)
    except (OSError, ValueError):
        pass
    return {
        "status": "available",
        "evidence_level": "pocket_prediction",
        "commercial_gate": _commercial_gate(approval_env),
        "capability": capability,
        "executable": executable,
        "sha256": digest,
        "version": os.getenv("FPOCKET_VERSION" if command == "fpocket" else "P2RANK_VERSION"),
    }


def _sha256_file(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _thermompnn_status() -> dict:
    url = os.getenv("THERMOMPNN_SERVICE_URL", "").rstrip("/")
    if not url:
        return {
            "status": "not_configured",
            "evidence_level": "model_inference",
            "commercial_gate": _commercial_gate("THERMOMPNN_COMMERCIAL_APPROVED"),
            "detail": "THERMOMPNN_SERVICE_URL is not configured.",
        }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "unavailable",
            "evidence_level": "model_inference",
            "commercial_gate": _commercial_gate("THERMOMPNN_COMMERCIAL_APPROVED"),
            "service_url": url,
            "detail": f"ThermoMPNN health request failed: {type(exc).__name__}",
        }
    return {
        "status": payload.get("status", "unknown"),
        "evidence_level": "model_inference",
        "commercial_gate": _commercial_gate("THERMOMPNN_COMMERCIAL_APPROVED"),
        "service_url": url,
        "model": payload.get("model"),
        "model_version": payload.get("model_version"),
        "model_sha256": payload.get("model_sha256"),
        "device": payload.get("device"),
    }


async def _enzyme_assistant_status() -> dict:
    """Report the research-only assistant service without implying prediction power."""
    url = os.getenv("ENZYME_ASSISTANT_SERVICE_URL", "").rstrip("/")
    boundary = {
        "evidence_level": "research_only_heuristic",
        "scientific_boundary": (
            "Unranked heuristic candidates; no thermostability predictive power "
            "(ESM2/ThermoMPNN rho~0) and no success probability."
        ),
        "manual_review_required": True,
    }
    if not url:
        return {**boundary, "status": "not_configured", "detail": "ENZYME_ASSISTANT_SERVICE_URL is not configured."}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            **boundary,
            "status": "unavailable",
            "service_url": url,
            "detail": f"Enzyme assistant health request failed: {type(exc).__name__}",
        }
    return {
        **boundary,
        # The service reports "ok" rather than the "ready" used by the
        # structure servers; map it explicitly instead of leaking the token.
        "status": "available" if payload.get("status") == "ok" else "unavailable",
        "service_url": url,
        "service_version": payload.get("service_version"),
    }


async def _p2rank_status() -> dict:
    """Report P2Rank only when its configured service is actually reachable."""
    status = _binary_status(("P2RANK_BIN", "P2RANK_BINARY"), "prank", "ligand_binding_pocket_prediction", "P2RANK_COMMERCIAL_APPROVED")
    service_url = os.getenv("P2RANK_SERVICE_URL", "").rstrip("/")
    if not service_url or status["status"] == "missing_executable":
        return status
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{service_url}/health")
            response.raise_for_status()
            payload = response.json()
        if payload.get("status") != "ready":
            raise ValueError("service_not_ready")
    except (httpx.HTTPError, ValueError) as exc:
        return {**status, "status": "unavailable", "service_url": service_url, "detail": f"P2Rank health request failed: {type(exc).__name__}"}
    return {**status, "service_url": service_url, "service_status": payload.get("status"), "service_engine": payload.get("engine")}


@router.get("")
async def capability_status():
    """Report installed capability boundaries without making scientific claims."""
    ToolRegistry.discover()
    return {
        "interproscan": _interproscan_status(),
        "thermompnn": await _thermompnn_status(),
        "enzyme_assistant": await _enzyme_assistant_status(),
        "pocket_prediction": {
            "fpocket": await _fpocket_status(),
            "p2rank": await _p2rank_status(),
            "scientific_boundary": "Pocket predictors do not calculate continuous substrate tunnels, catalytic function, affinity, or mutation benefit.",
        },
        "km_prediction": {
            "status": "missing_validated_model",
            "evidence_level": "runtime_smoke_unapproved",
            "detail": "CatPred official Km ensemble, held-out benchmark evidence, and an isolated ARM64 single-sample smoke are available; the production inference adapter and deployable artifact manifest are not yet approved.",
            "research_execution": {
                "status": "available_when_configured",
                "scope": "research_only",
                "entrypoint": "AI大模型/scripts/run_km_research_smoke.sh",
                "boundary": "Research predictions must not be used as production decisions or exported as approved model results.",
            },
            "benchmark": {"target": "log10(Km[mM])", "rmse": 0.4520690707719872, "mae": 0.2902074657947688, "r2": 0.8733187583498294},
        },
        "tm_prediction": {
            "status": "missing_validated_model",
            "evidence_level": "runtime_smoke_unapproved",
            "detail": "TemBERTure official Test split has been reproduced in research mode; production license and deployable base-model evidence remain incomplete.",
            "research_execution": {"status": "available_when_configured", "scope": "research_only", "entrypoint": "AI大模型/scripts/run_tm_research_smoke.sh", "boundary": "Research predictions must not be used as production decisions or exported as approved model results."},
            "benchmark": {"target": "Tm", "unit": "degC", "sample_count": 531, "rmse_c": 8.043051064296563, "mae_c": 6.420139510246654, "r2": 0.7783864197964949},
        },
        "substrate_database": {
            "status": "network_required",
            "evidence_level": "database_record",
            "detail": "PubChem lookup is installed; availability depends on HTTPS egress.",
        },
        "tunnel_analysis": await _caver_status(),
        "rosetta_ddg": await _rosetta_status(),
        "registered_tool_count": len(ToolRegistry._tools),
}

async def _caver_status() -> dict:
    service_url = os.getenv("CAVER_SERVICE_URL", "").rstrip("/")
    alternative = {"status": "available_with_different_claim", "tools": ["pocket_residue_lookup", "expert_structure_review"], "boundary": "Pocket prediction and review do not calculate continuous tunnels."}
    if not service_url:
        return {"status": "missing_validated_engine", "evidence_level": "geometry_prediction", "commercial_gate": _commercial_gate("CAVER_COMMERCIAL_APPROVED"), "alternative_path": alternative, "detail": "CAVER service is not configured."}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{service_url}/health"); response.raise_for_status(); payload = response.json()
        if payload.get("status") != "ready": raise ValueError("service_not_ready")
        return {"status":"available", "evidence_level":"geometry_prediction", "commercial_gate": _commercial_gate("CAVER_COMMERCIAL_APPROVED"), "alternative_path": alternative, "service_url":service_url, "service_status":payload.get("status"), "engine":payload.get("engine"), "version":payload.get("version")}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status":"unavailable", "evidence_level":"geometry_prediction", "commercial_gate": _commercial_gate("CAVER_COMMERCIAL_APPROVED"), "alternative_path": alternative, "service_url":service_url, "detail":f"CAVER health request failed: {type(exc).__name__}"}

async def _fpocket_status() -> dict:
    url = os.getenv("FPOCKET_SERVICE_URL", "").rstrip("/")
    if not url: return _binary_status(("FPOCKET_BIN", "FPOCKET_BINARY"), "fpocket", "ligand_binding_pocket_prediction", "FPOCKET_COMMERCIAL_APPROVED")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health"); response.raise_for_status(); payload=response.json()
        if payload.get("status") != "ready": raise ValueError("service_not_ready")
        return {"status":"available","evidence_level":"pocket_prediction","commercial_gate":_commercial_gate("FPOCKET_COMMERCIAL_APPROVED"),"capability":"ligand_binding_pocket_prediction","service_url":url,"service_status":payload.get("status"),"engine":payload.get("engine"),"version":payload.get("version"),"architecture":payload.get("architecture")}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status":"unavailable","evidence_level":"pocket_prediction","commercial_gate":_commercial_gate("FPOCKET_COMMERCIAL_APPROVED"),"service_url":url,"detail":f"fpocket health request failed: {type(exc).__name__}"}

async def _rosetta_status() -> dict:
    url = os.getenv("ROSETTA_SERVICE_URL", "").rstrip("/")
    alternative = {"status": "available_with_different_claim", "tools": ["mutation_priority_score", "disulfide_saltbridge_scan", "thermompnn_predict"], "boundary": "These tools do not produce Rosetta ddG or experimentally calibrated stability changes."}
    if not url:
        executable = shutil.which("rosetta_scripts") or shutil.which("cartesian_ddg")
        return {
            "status": "available" if executable else "missing_executable",
            "evidence_level": "physics_energy" if executable else "none",
            "commercial_gate": _commercial_gate("ROSETTA_COMMERCIAL_APPROVED"),
            "alternative_path": alternative,
            "executable": executable,
            "detail": "Rosetta host service is not configured." if not executable else "Rosetta executable detected; benchmark validation remains required.",
        }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}/health")
            response.raise_for_status()
            payload = response.json()
        return {
            "status": "available" if payload.get("status") == "ready" else "unavailable",
            "evidence_level": "physics_energy",
            "commercial_gate": _commercial_gate("ROSETTA_COMMERCIAL_APPROVED"),
            "alternative_path": alternative,
            "service_url": url,
            "engine": payload.get("engine"),
            "version": payload.get("version"),
            "architecture": payload.get("architecture"),
            "binary_sha256": payload.get("binary_sha256"),
            "detail": payload.get("detail"),
            "scientific_boundary": "Rosetta cartesian_ddg reports a physics score difference; it is not an experimentally calibrated affinity, Km, Tm, or stability guarantee.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "evidence_level": "physics_energy", "commercial_gate": _commercial_gate("ROSETTA_COMMERCIAL_APPROVED"), "alternative_path": alternative, "service_url": url, "detail": f"Rosetta health request failed: {type(exc).__name__}"}
