from datetime import datetime
import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
import io
import json
from pathlib import Path, PurePosixPath
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote
import zipfile
from app.core.database import get_session
from app.tools.registry import ToolRegistry
from app.core.security import get_current_user, require_admin
from app.services.scheduler import (
    ASYNC_TOOLS,
    cancel_task,
    dispatch_tool,
    get_execution_mode,
    get_task_profile,
    get_task_status,
)
from app.services.md_protocols import get_md_protocol, list_md_protocols, resolve_md_protocol_parameters
from app.services import storage
from app.services.tool_task_audit import (
    get_task_audit as get_persisted_task_audit,
    get_any_task_audit,
    list_md_replicate_batch_audits,
    list_all_task_audits,
    list_all_task_audits_filtered,
    list_task_audits,
    mark_task_cancel_requested,
    record_task_submitted,
    serialize_task_audits_csv,
    summarize_task_audits,
    ToolTaskAuditFilters,
    update_task_audit_from_status,
)
from app.services.tool_diagnostics import collect_tool_diagnostics
from app.services.tool_orchestration_contract import TOOL_PROVIDES, TOOL_REQUIRES, evidence_from_completed_tasks, validate_tool_plan
from app.services.property_workflow_governance import PropertyWorkflowRouter, WorkflowPolicyValidator
from app.services.property_workflow_audit import list_shadow_audits
from app.tools.tool_capability_audit import _CAPABILITIES
from app.services.analysis_recompute import build_recompute_decision
from app.services.analysis_recompute import persist_recompute_snapshot
from app.services.tool_baseline_manifest import DEFAULT_FALLBACKS, load_catalog_tool_names, reconcile_tool_baseline
from app.services.model_runtime_readiness import collect_model_runtime_readiness
from app.services.remediation_readiness import collect_remediation_readiness
from app.models.conversation import Conversation
from app.models.strategy_checkpoint import AnalysisEvidenceSnapshot
from app.services.tool_task_store import (
    record_tool_artifact_owner,
    get_tool_task_owner,
    record_tool_task_cancel_requested,
    record_tool_task_owner,
    record_tool_task_runtime_policy,
    record_tool_task_terminal_state,
)

router = APIRouter()


class ToolCallRequest(BaseModel):
    params: dict = {}


class WorkflowShadowRouteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    plan: list[dict] = Field(default_factory=list, max_length=100)


class ToolPreflightRequest(BaseModel):
    evidence: dict[str, bool] = {}
    task_ids: list[str] = Field(default_factory=list, max_length=50)
    snapshot_id: str | None = Field(default=None, max_length=64)


class AnalysisRecomputeDecisionRequest(BaseModel):
    """Explicit request to build a new analysis evidence snapshot.

    This request is deliberately separate from normal task polling.  It never
    edits an existing chat response, published report, or strategy checkpoint.
    """

    analysis_fingerprint: str | None = Field(default=None, max_length=128)
    conversation_id: int | None = Field(default=None, ge=1)
    task_ids: list[str] = Field(min_length=1, max_length=50)


class MdProtocolResolveRequest(BaseModel):
    overrides: dict = {}


class MdReplicateBatchSubmitRequest(BaseModel):
    protocol_id: str | None = "engineering_short"
    overrides: dict = {}
    pdb_object_name: str | None = None
    pdb_data: str | None = None
    pdb_path: str | None = None
    replicate_count: int = 3
    replicate_variants: list = []
    replicate_seed_base: int = 1000
    mutant_inputs: dict = {}
    dry_run: bool = True
    confirmation: str | None = None
    require_mutant_topology_validation: bool = False


class MdMutantPrepareRequest(BaseModel):
    pdb_object_name: str | None = None
    pdb_data: str | None = None
    pdb_path: str | None = None
    variants: list = []
    store: bool = False
    validate_topology: bool = False
    force_field: str = "amber99sb-ildn"
    water_model: str = "tip3p"
    topology_timeout_seconds: int = 120


class MdTopologyValidateRequest(BaseModel):
    pdb_object_name: str | None = None
    pdb_data: str | None = None
    pdb_path: str | None = None
    force_field: str = "amber99sb-ildn"
    water_model: str = "tip3p"
    timeout_seconds: int = 120


_LIGAND_OBJECT_PARAM_KEYS = {
    "sdf_object_name",
    "ligand_3d_object_name",
    "ligand_pdbqt_object_name",
    "receptor_pdbqt_object_name",
}
_LIGAND_PATH_PARAM_KEYS = {"sdf_path", "ligand_3d_path", "ligand_pdbqt_path", "receptor_pdbqt_path"}


def _user_upload_prefix(user_id: int | str) -> str:
    return f"uploads/user_{int(user_id)}/"


def _validate_ligand_preprocess_params(params: dict, current_user: dict) -> None:
    for key in _LIGAND_PATH_PARAM_KEYS:
        if str(params.get(key) or "").strip():
            raise HTTPException(400, f"{key} is not accepted through the HTTP API; upload the file and pass the object name")

    prefix = _user_upload_prefix(current_user["id"])
    for key in _LIGAND_OBJECT_PARAM_KEYS:
        object_name = str(params.get(key) or "").strip()
        if object_name and not object_name.startswith(prefix):
            raise HTTPException(403, f"Access denied for {key}")


def _validate_tool_submission_params(canonical: str, params: dict, current_user: dict) -> None:
    if canonical == "ligand_preprocess":
        _validate_ligand_preprocess_params(params, current_user)


def _coerce_cancel_requested_terminal_status(owner: dict, status: dict) -> None:
    """Normalize revoke/terminate failures into canceled when user requested cancel."""
    if not owner.get("cancel_requested"):
        return
    normalized = str(status.get("status") or "").lower()
    if normalized != "failed":
        return
    error_text = str(status.get("error") or "").lower()
    if "revoke" in error_text or "terminated" in error_text:
        status["status"] = "canceled"
        status["error"] = None


def _extract_artifact_payload(status: dict) -> dict | None:
    payload = status.get("result")
    if not isinstance(payload, dict):
        return None

    nested_result = payload.get("result")
    artifact_payload = nested_result if isinstance(nested_result, dict) else payload
    return artifact_payload if isinstance(artifact_payload, dict) else None


def _extract_task_artifacts(status: dict) -> list[dict]:
    artifact_payload = _extract_artifact_payload(status)
    artifacts = artifact_payload.get("artifacts") if isinstance(artifact_payload, dict) else None
    return artifacts if isinstance(artifacts, list) else []


def _build_task_audit(task_id: str, owner: dict, status: dict) -> dict:
    """Return a compact audit view for task polling and future admin screens."""
    return {
        "task_id": task_id,
        "tool": owner.get("tool"),
        "submitted_at": owner.get("submitted_at"),
        "terminal_status": owner.get("terminal_status"),
        "terminal_recorded_at": owner.get("terminal_recorded_at"),
        "queue": owner.get("queue"),
        "runtime_policy": {
            "soft_time_limit": owner.get("soft_time_limit"),
            "time_limit": owner.get("time_limit"),
        },
        "cancellation": {
            "requested": bool(owner.get("cancel_requested")),
            "requested_at": owner.get("cancel_requested_at"),
            "effective_at": owner.get("cancel_effective_at"),
        },
        "result_status": status.get("status"),
        "progress": status.get("progress"),
        "stage": status.get("stage"),
    }


def _parse_admin_audit_filters(
    tool: str | None,
    status: str | None,
    queue: str | None,
    failure_class: str | None,
    submitted_after: str | None,
    submitted_before: str | None,
    failed_only: bool,
    slow_only: bool,
) -> ToolTaskAuditFilters:
    def clean(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def parse_dt(value: str | None, label: str) -> datetime | None:
        value = clean(value)
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, f"Invalid {label}; expected ISO-8601 datetime")

    return ToolTaskAuditFilters(
        tool=clean(tool),
        status=clean(status),
        queue=clean(queue),
        failure_class=clean(failure_class),
        submitted_after=parse_dt(submitted_after, "submitted_after"),
        submitted_before=parse_dt(submitted_before, "submitted_before"),
        failed_only=failed_only,
        slow_only=slow_only,
    )


async def _submit_async_tool_task(
    *,
    canonical: str,
    params: dict,
    current_user: dict,
    session: AsyncSession,
) -> dict:
    _validate_tool_submission_params(canonical, params, current_user)
    try:
        task_id = dispatch_tool(canonical, params)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

    await record_tool_task_owner(task_id, current_user["id"], canonical)
    profile = get_task_profile(canonical)
    await record_tool_task_runtime_policy(
        task_id,
        queue=profile.queue,
        soft_time_limit=profile.soft_time_limit,
        time_limit=profile.time_limit,
    )
    await record_task_submitted(
        session,
        task_id=task_id,
        user_id=current_user["id"],
        tool_name=canonical,
        params=params,
        queue=profile.queue,
        soft_time_limit=profile.soft_time_limit,
        time_limit=profile.time_limit,
    )
    return {"status": "submitted", "task_id": task_id, "tool": canonical, "queue": profile.queue}


async def _record_task_artifact_access(task_id: str, owner: dict, status: dict) -> None:
    """Bind generated tool artifact downloads to the task owner."""
    artifacts = _extract_task_artifacts(status)
    if not artifacts:
        return

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        object_name = artifact.get("object_name")
        if not isinstance(object_name, str) or not object_name.strip():
            continue
        name = artifact.get("name")
        if isinstance(name, str) and name.strip():
            download_url = artifact.get("download_url")
            if isinstance(download_url, str) and download_url and "filename=" not in download_url:
                artifact["download_url"] = f"{download_url}?filename={quote(name)}"
        await record_tool_artifact_owner(
            object_name,
            owner["user_id"],
            tool_name=owner.get("tool") or "unknown",
            task_id=task_id,
        )


def _artifact_archive_path(artifact: dict, category_lookup: dict[str, str], seen_paths: set[str]) -> str:
    object_name = str(artifact.get("object_name") or "")
    filename = str(artifact.get("name") or "") or PurePosixPath(object_name).name or "artifact.bin"
    category = category_lookup.get(object_name) or category_lookup.get(filename) or str(artifact.get("category") or "other")
    category = (category or "other").strip().lower()
    archive_path = f"{category}/{filename}"
    if archive_path not in seen_paths:
        seen_paths.add(archive_path)
        return archive_path

    stem = PurePosixPath(filename).stem or "artifact"
    suffix = PurePosixPath(filename).suffix
    index = 2
    while True:
        candidate = f"{category}/{stem}-{index}{suffix}"
        if candidate not in seen_paths:
            seen_paths.add(candidate)
            return candidate
        index += 1


async def _require_task_owner(task_id: str, current_user: dict) -> dict:
    owner = await get_tool_task_owner(task_id)
    if owner is None:
        raise HTTPException(404, "Tool task not found")
    if owner["user_id"] != int(current_user["id"]):
        raise HTTPException(403, "Task does not belong to current user")
    return owner


async def _load_owned_task_results_for_recompute(
    *,
    task_ids: list[str],
    current_user: dict,
    session: AsyncSession,
) -> list[dict]:
    """Poll owned tasks and return scheduler records for an explicit recompute.

    Polling is retained here solely to obtain a reproducible terminal snapshot;
    it does not invoke report generation or alter an analysis revision.
    """
    records: list[dict] = []
    for task_id in dict.fromkeys(str(item).strip() for item in task_ids if str(item).strip()):
        owner = await _require_task_owner(task_id, current_user)
        try:
            status = get_task_status(task_id)
        except Exception as exc:
            raise HTTPException(500, f"Failed to read task {task_id}: {exc}")
        status["tool"] = owner.get("tool")
        _coerce_cancel_requested_terminal_status(owner, status)
        if status.get("status") in {"completed", "failed", "canceled"}:
            owner = await record_tool_task_terminal_state(task_id, status["status"]) or owner
        await update_task_audit_from_status(session, task_id=task_id, owner=owner, status=status)
        records.append({
            "task_id": task_id,
            "tool_name": owner.get("tool"),
            "status": status.get("status"),
            "result": status.get("result"),
        })
    if not records:
        raise HTTPException(400, "Provide at least one non-empty task id")
    return records


@router.get("")
async def list_tools(current_user: dict = Depends(get_current_user)):
    """List all available tools with their schemas and category groupings."""
    tools = []
    for t in ToolRegistry._tools.values():
        tools.append({
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "is_async": t.is_async,
            # ``is_async`` is retained for compatibility; dispatch truth is
            # the scheduler allowlist used by /submit and worker execution.
            "execution_mode": get_execution_mode(t.name),
            "parameters": t.parameters,
            "requires": sorted(TOOL_REQUIRES.get(t.name, frozenset())),
            "provides": sorted(TOOL_PROVIDES.get(t.name, frozenset())),
            "evidence_level": (
                "runtime_or_source_evidence"
                if str((_CAPABILITIES.get(t.name) or {}).get("capability_status") or "").lower()
                in {"real", "live", "evidence_synthesis"}
                else "proxy_or_ranking_only"
                if _CAPABILITIES.get(t.name)
                else "unverified"
            ),
            "runtime_mode": "async_worker" if t.name in ASYNC_TOOLS else "inline_sync",
            "license_status": (
                "review_required"
                if not (_CAPABILITIES.get(t.name) or {}).get("license_class")
                else str((_CAPABILITIES.get(t.name) or {}).get("commercial_use_status") or "review_required")
            ),
        })
    return {
        "tools": tools,
        "categories": ToolRegistry.list_by_category(),
        "manifest": {
            "version": "tools-manifest-v1",
            "tool_count": len(tools),
            "tool_names_sha256": hashlib.sha256(
                "\n".join(sorted(item["name"] for item in tools)).encode("utf-8")
            ).hexdigest(),
            "source": "runtime_tool_registry",
            "baseline": reconcile_tool_baseline(
                desired_tools=load_catalog_tool_names(
                    Path(__file__).resolve().parents[3]
                    / "AI酶工程平台三层架构_交付包_v2_20260827"
                    / "03_执行控制层/enzyme-property-workflow-router/references/platform_tool_catalog.md"
                ) or [item["name"] for item in tools],
                runtime_tools=ToolRegistry._tools.keys(),
                fallback_map=DEFAULT_FALLBACKS,
            ),
        },
    }


@router.get("/diagnostics")
async def get_diagnostics(
    include_table_counts: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Runtime diagnostics for registered tools and core dependencies."""
    payload = await collect_tool_diagnostics(include_table_counts=include_table_counts)
    payload["model_runtime"] = collect_model_runtime_readiness()
    payload["remediation_readiness"] = collect_remediation_readiness(Path(__file__).resolve().parents[3])
    return payload


@router.post("/workflows/shadow-route")
async def shadow_route_workflow(
    req: WorkflowShadowRouteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Evaluate the v2 workflow route without dispatching any tool."""
    route = PropertyWorkflowRouter.route(req.message)
    validation = None
    if route.get("workflow_id") and req.plan:
        validation = WorkflowPolicyValidator.validate(route["workflow_id"], req.plan)
    return {"mode": "shadow", "route": route, "validation": validation, "dispatch_performed": False}


@router.get("/workflows/shadow-audits")
async def get_shadow_workflow_audits(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    audits = await list_shadow_audits(session, user_id=current_user["id"], limit=limit)
    return {"count": len(audits), "audits": audits}


@router.get("/md/protocols")
async def get_md_protocols(current_user: dict = Depends(get_current_user)):
    """List curated MD protocol templates."""
    return list_md_protocols()


@router.get("/md/protocols/{protocol_id}")
async def get_md_protocol_template(
    protocol_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return one curated MD protocol template."""
    protocol = get_md_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(404, f"MD protocol not found: {protocol_id}")
    return protocol


@router.post("/md/protocols/{protocol_id}/resolve")
async def resolve_md_protocol_template(
    protocol_id: str,
    req: MdProtocolResolveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Return a protocol parameter payload with safe user overrides applied."""
    try:
        return resolve_md_protocol_parameters(protocol_id, req.overrides)
    except KeyError:
        raise HTTPException(404, f"MD protocol not found: {protocol_id}")


@router.get("/tasks/audits")
async def list_tool_task_audits(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List persisted task audit records owned by the current user."""
    audits = await list_task_audits(session, user_id=current_user["id"], limit=limit)
    return {"count": len(audits), "audits": audits}


@router.post("/analysis/recompute-decision")
async def request_analysis_recompute_decision(
    req: AnalysisRecomputeDecisionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Build an explicit evidence snapshot before creating a new analysis revision.

    Completing an async BLAST, MD, or other task never rewrites the report that
    launched it.  The client must call this endpoint after reviewing the task
    state, then create a new strategy/report revision from the returned snapshot.
    """
    if req.conversation_id is not None:
        conversation = (
            await session.execute(
                select(Conversation).where(
                    Conversation.id == req.conversation_id,
                    Conversation.user_id == current_user["id"],
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(404, "Conversation not found")

    records = await _load_owned_task_results_for_recompute(
        task_ids=req.task_ids,
        current_user=current_user,
        session=session,
    )
    decision = build_recompute_decision(
        analysis_fingerprint=req.analysis_fingerprint,
        tool_results=records,
        requested=True,
    )
    decision["task_snapshot"] = records
    decision["report_revision_created"] = False
    decision["snapshot"] = None
    if decision["status"] == "recompute_ready":
        decision["snapshot"] = await persist_recompute_snapshot(
            session,
            user_id=current_user["id"],
            conversation_id=req.conversation_id,
            decision=decision,
            task_snapshot=records,
        )
    decision["report_revision_policy"] = (
        "This endpoint does not modify an existing report. Create a new revision "
        "only when status is recompute_ready."
    )
    return decision


@router.get("/tasks/{task_id}/audit")
async def get_tool_task_audit(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return one persisted task audit record owned by the current user."""
    audit = await get_persisted_task_audit(session, task_id=task_id, user_id=current_user["id"])
    if audit is None:
        raise HTTPException(404, "Tool task audit not found")
    return audit


@router.get("/admin/tasks/audits")
async def list_all_tool_task_audits(
    limit: int = 100,
    tool: str | None = Query(default=None),
    status: str | None = Query(default=None),
    queue: str | None = Query(default=None),
    failure_class: str | None = Query(default=None),
    submitted_after: str | None = Query(default=None),
    submitted_before: str | None = Query(default=None),
    failed_only: bool = Query(default=False),
    slow_only: bool = Query(default=False),
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List persisted task audit records across users. Admin only."""
    filters = _parse_admin_audit_filters(
        tool,
        status,
        queue,
        failure_class,
        submitted_after,
        submitted_before,
        failed_only,
        slow_only,
    )
    audits = await list_all_task_audits_filtered(session, limit=limit, filters=filters)
    return {"count": len(audits), "audits": audits, "summary": summarize_task_audits(audits)}


@router.get("/admin/tasks/audits/summary")
async def summarize_all_tool_task_audits(
    limit: int = 500,
    tool: str | None = Query(default=None),
    status: str | None = Query(default=None),
    queue: str | None = Query(default=None),
    failure_class: str | None = Query(default=None),
    submitted_after: str | None = Query(default=None),
    submitted_before: str | None = Query(default=None),
    failed_only: bool = Query(default=False),
    slow_only: bool = Query(default=False),
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Return derived task audit statistics across users. Admin only."""
    filters = _parse_admin_audit_filters(
        tool,
        status,
        queue,
        failure_class,
        submitted_after,
        submitted_before,
        failed_only,
        slow_only,
    )
    audits = await list_all_task_audits_filtered(session, limit=limit, filters=filters)
    return summarize_task_audits(audits)


@router.get("/admin/tasks/audits/export")
async def export_all_tool_task_audits(
    limit: int = 500,
    tool: str | None = Query(default=None),
    status: str | None = Query(default=None),
    queue: str | None = Query(default=None),
    failure_class: str | None = Query(default=None),
    submitted_after: str | None = Query(default=None),
    submitted_before: str | None = Query(default=None),
    failed_only: bool = Query(default=False),
    slow_only: bool = Query(default=False),
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Export sanitized persisted task audits across users as CSV. Admin only."""
    filters = _parse_admin_audit_filters(
        tool,
        status,
        queue,
        failure_class,
        submitted_after,
        submitted_before,
        failed_only,
        slow_only,
    )
    audits = await list_all_task_audits_filtered(session, limit=limit, filters=filters)
    csv_text = serialize_task_audits_csv(audits)
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tool-task-audits.csv"'},
    )


@router.get("/admin/tasks/{task_id}/audit")
async def get_any_tool_task_audit(
    task_id: str,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Return one persisted task audit record across users. Admin only."""
    audit = await get_any_task_audit(session, task_id=task_id)
    if audit is None:
        raise HTTPException(404, "Tool task audit not found")
    return audit


def _has_md_structure_input(payload: dict) -> bool:
    return any(str(payload.get(key) or "").strip() for key in ("pdb_object_name", "pdb_data", "pdb_path"))


def _has_safe_topology_validation(payload: dict) -> bool:
    validation = payload.get("topology_validation") if isinstance(payload, dict) else None
    return bool(
        isinstance(validation, dict)
        and validation.get("topology_validated") is True
        and validation.get("safe_for_ranking") is True
    )


async def _load_pdb_text_async(*, pdb_data: str | None, pdb_object_name: str | None, pdb_path: str | None) -> str:
    if pdb_data and pdb_data.strip():
        return pdb_data
    if pdb_path:
        path = Path(pdb_path)
        if not path.exists():
            raise HTTPException(400, f"PDB path not found: {pdb_path}")
        return path.read_text(encoding="utf-8", errors="replace")
    if pdb_object_name:
        try:
            return (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
        except Exception as e:
            raise HTTPException(400, f"Failed to load PDB object: {e}")
    raise HTTPException(400, "Provide pdb_data, pdb_path, or pdb_object_name")


def _replicate_task_params(
    *,
    base_params: dict,
    protocol_id: str | None,
    batch_id: str,
    task: dict,
    structure_input: dict,
) -> dict:
    params = dict(base_params)
    params.update({
        "protocol_id": protocol_id,
        "run_seed": task["seed"],
        "batch_id": batch_id,
        "replicate_variant": task["variant"],
        "replicate_index": task["replicate_index"],
    })
    for key in ("pdb_object_name", "pdb_data", "pdb_path"):
        if structure_input.get(key):
            params[key] = structure_input[key]
    return params


def _coerce_summary_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _mean_summary_metric(rows: list[dict], metric: str) -> float | None:
    values = [_coerce_summary_float(row.get(metric)) for row in rows]
    clean_values = [value for value in values if value is not None]
    return sum(clean_values) / len(clean_values) if clean_values else None


def _md_replicate_row_from_audit(audit: dict) -> tuple[dict | None, list[str]]:
    input_summary = audit.get("input_summary") if isinstance(audit.get("input_summary"), dict) else {}
    input_values = input_summary.get("values") if isinstance(input_summary.get("values"), dict) else {}
    result_summary = audit.get("result_summary") if isinstance(audit.get("result_summary"), dict) else {}
    md_metrics = result_summary.get("md_replicate") if isinstance(result_summary.get("md_replicate"), dict) else {}
    variant = str(input_values.get("replicate_variant") or md_metrics.get("replicate_variant") or "WT").strip() or "WT"
    row = {
        "task_id": audit.get("task_id"),
        "job_id": result_summary.get("job_id"),
        "variant": variant,
        "replicate_id": result_summary.get("job_id") or audit.get("task_id"),
        "replicate_index": input_values.get("replicate_index") or md_metrics.get("replicate_index"),
        "run_seed": input_values.get("run_seed") or md_metrics.get("run_seed"),
        "rmsd_drift_nm": md_metrics.get("rmsd_drift_nm"),
        "mean_rmsf_nm": md_metrics.get("mean_rmsf_nm"),
        "rg_change_nm": md_metrics.get("rg_change_nm"),
        "sasa_change_nm2": md_metrics.get("sasa_change_nm2"),
        "is_stable": md_metrics.get("is_stable") if isinstance(md_metrics.get("is_stable"), bool) else None,
    }
    missing = [
        metric
        for metric in ("rmsd_drift_nm", "mean_rmsf_nm", "rg_change_nm", "sasa_change_nm2")
        if _coerce_summary_float(row.get(metric)) is None
    ]
    if missing:
        return None, missing
    return row, []


def _split_md_replicate_rows(audits: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    wild_type_rows: list[dict] = []
    mutant_rows: list[dict] = []
    missing_metrics: list[dict] = []
    for audit in audits:
        row, missing = _md_replicate_row_from_audit(audit)
        if row is None:
            missing_metrics.append({"task_id": audit.get("task_id"), "missing": missing})
            continue
        if str(row.get("variant") or "WT") == "WT":
            wild_type_rows.append(row)
        else:
            mutant_rows.append(row)
    wt_rmsd_mean = _mean_summary_metric(wild_type_rows, "rmsd_drift_nm")
    wt_rmsf_mean = _mean_summary_metric(wild_type_rows, "mean_rmsf_nm")
    for row in mutant_rows:
        rmsd = _coerce_summary_float(row.get("rmsd_drift_nm"))
        rmsf = _coerce_summary_float(row.get("mean_rmsf_nm"))
        row["stability_delta"] = round(rmsd - wt_rmsd_mean, 4) if rmsd is not None and wt_rmsd_mean is not None else None
        row["rmsf_change_mean"] = round(rmsf - wt_rmsf_mean, 4) if rmsf is not None and wt_rmsf_mean is not None else None
        row["delta_reference"] = "wt_batch_mean" if wt_rmsd_mean is not None and wt_rmsf_mean is not None else "missing_wt_metrics"
    return wild_type_rows, mutant_rows, missing_metrics


def _summarize_md_replicate_batch_from_audits(audits: list[dict], minimum_replicates: int) -> dict:
    from app.tools.gromacs_md import _build_md_batch_replicate_summary

    terminal_success = {"completed", "success"}
    terminal_failed = {"failed", "failure", "canceled", "revoked", "cancel_requested"}
    completed = [audit for audit in audits if str(audit.get("status") or "").lower() in terminal_success]
    pending = [
        audit
        for audit in audits
        if str(audit.get("status") or "").lower() not in terminal_success | terminal_failed
    ]
    failed = [audit for audit in audits if str(audit.get("status") or "").lower() in terminal_failed]
    wild_type_rows, mutant_rows, missing_metrics = _split_md_replicate_rows(completed)
    batch_summary = _build_md_batch_replicate_summary(
        wild_type_replicates=wild_type_rows,
        mutant_replicates=mutant_rows,
        minimum_replicates=minimum_replicates,
    )
    status = batch_summary.get("status") or "ranking_blocked"
    blocked_reason = None
    if not audits:
        status = "no_tasks"
        blocked_reason = "no_audits_for_batch"
    elif pending:
        status = "incomplete"
        blocked_reason = "tasks_not_terminal"
    elif failed:
        status = "ranking_blocked"
        blocked_reason = "terminal_failures_present"
    elif missing_metrics:
        status = "ranking_blocked"
        blocked_reason = "completed_metrics_missing"
    return {
        "status": status,
        "task_count": len(audits),
        "completed_count": len(completed),
        "pending_count": len(pending),
        "failed_count": len(failed),
        "wild_type_replicates": wild_type_rows,
        "mutant_replicates": mutant_rows,
        "missing_metrics": missing_metrics,
        "blocked_reason": blocked_reason,
        "batch_replicate_summary": batch_summary,
    }


@router.post("/md/replicates/submit")
async def submit_md_replicate_batch(
    req: MdReplicateBatchSubmitRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Plan or submit a controlled batch of real GROMACS replicate tasks.

    Default is dry-run. Real submission requires confirmation=SUBMIT_MD_REPLICATES.
    Mutant replicates are submitted only when a prepared mutant PDB input is
    supplied for that variant; this endpoint does not generate mutant structures.
    """
    from app.tools.gromacs_md import _build_replicate_execution_plan

    protocol_id = req.protocol_id or "engineering_short"
    try:
        resolved = resolve_md_protocol_parameters(protocol_id, req.overrides or {})
    except KeyError:
        raise HTTPException(404, f"MD protocol not found: {protocol_id}")
    base_params = dict(resolved["parameters"])
    batch_id = f"mdrep_{uuid.uuid4().hex[:12]}"
    plan = _build_replicate_execution_plan(
        protocol_id=protocol_id,
        parameters=base_params,
        variants=req.replicate_variants or [],
        replicate_count=req.replicate_count,
        seed_base=req.replicate_seed_base,
    )

    wt_input = {
        "pdb_object_name": req.pdb_object_name,
        "pdb_data": req.pdb_data,
        "pdb_path": req.pdb_path,
    }
    mutant_inputs = req.mutant_inputs if isinstance(req.mutant_inputs, dict) else {}
    submissions: list[dict] = []
    blocked: list[dict] = []

    for task in plan["tasks"]:
        variant = str(task["variant"])
        structure_input = wt_input if variant == "WT" else dict(mutant_inputs.get(variant) or {})
        if not _has_md_structure_input(structure_input):
            blocked.append({
                "planned_task_id": task["task_id"],
                "variant": variant,
                "replicate_index": task["replicate_index"],
                "reason": "missing_prepared_mutant_structure" if variant != "WT" else "missing_wt_structure",
                "requires_mutant_structure": bool(task.get("requires_mutant_structure")),
            })
            continue
        if variant != "WT" and req.require_mutant_topology_validation and not _has_safe_topology_validation(structure_input):
            blocked.append({
                "planned_task_id": task["task_id"],
                "variant": variant,
                "replicate_index": task["replicate_index"],
                "reason": "mutant_topology_not_validated",
                "requires_mutant_structure": True,
                "requires_topology_validation": True,
            })
            continue
        params = _replicate_task_params(
            base_params=base_params,
            protocol_id=protocol_id,
            batch_id=batch_id,
            task=task,
            structure_input=structure_input,
        )
        submissions.append({
            "planned_task_id": task["task_id"],
            "variant": variant,
            "replicate_index": task["replicate_index"],
            "seed": task["seed"],
            "params": params,
        })

    if req.dry_run:
        return {
            "status": "planned",
            "dry_run": True,
            "batch_id": batch_id,
            "protocol_id": protocol_id,
            "replicate_execution_plan": plan,
            "submittable_count": len(submissions),
            "blocked_count": len(blocked),
            "submittable_tasks": [
                {key: value for key, value in item.items() if key != "params"}
                for item in submissions
            ],
            "blocked_tasks": blocked,
            "confirmation_required": "SUBMIT_MD_REPLICATES",
            "note": "No Celery tasks were submitted.",
        }

    if req.confirmation != "SUBMIT_MD_REPLICATES":
        raise HTTPException(400, "Real MD replicate submission requires confirmation=SUBMIT_MD_REPLICATES")
    if not submissions:
        raise HTTPException(400, "No replicate tasks are submittable; provide WT and/or prepared mutant PDB inputs")

    submitted: list[dict] = []
    for item in submissions:
        result = await _submit_async_tool_task(
            canonical="gromacs_md",
            params=item["params"],
            current_user=current_user,
            session=session,
        )
        submitted.append({
            "planned_task_id": item["planned_task_id"],
            "task_id": result["task_id"],
            "tool": result["tool"],
            "queue": result.get("queue"),
            "variant": item["variant"],
            "replicate_index": item["replicate_index"],
            "seed": item["seed"],
            "status_url": f"/api/tools/tasks/{result['task_id']}",
        })

    return {
        "status": "submitted" if not blocked else "partially_submitted",
        "dry_run": False,
        "batch_id": batch_id,
        "protocol_id": protocol_id,
        "submitted_count": len(submitted),
        "blocked_count": len(blocked),
        "submitted_tasks": submitted,
        "blocked_tasks": blocked,
        "replicate_execution_plan": plan,
        "next_steps": [
            "Poll each status_url until terminal.",
            "Use completed task metrics as wild_type_replicates/mutant_replicates for batch replicate ranking.",
            "Do not rank blocked mutant variants until prepared mutant structures are supplied.",
        ],
    }


@router.post("/md/mutants/prepare")
async def prepare_md_mutant_structures(
    req: MdMutantPrepareRequest,
    current_user: dict = Depends(get_current_user),
):
    """Prepare conservative point-mutant PDB candidates for later MD submission.

    The generated PDBs are coordinate-level candidates only. They must pass
    topology validation before report-grade MD ranking.
    """
    from app.tools.gromacs_md import _prepare_point_mutant_pdbs, _validate_pdb_topology

    if not req.variants:
        raise HTTPException(400, "At least one mutation variant is required")
    pdb_text = await _load_pdb_text_async(
        pdb_data=req.pdb_data,
        pdb_object_name=req.pdb_object_name,
        pdb_path=req.pdb_path,
    )
    try:
        result = _prepare_point_mutant_pdbs(pdb_text, req.variants)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(400, str(e))

    stored_count = 0
    for item in result.get("mutants", []):
        if not isinstance(item, dict) or item.get("status") != "prepared" or not item.get("pdb_data"):
            continue
        topology_validation = None
        if req.validate_topology:
            topology_validation = _validate_pdb_topology(
                str(item["pdb_data"]),
                force_field=req.force_field,
                water_model=req.water_model,
                timeout=req.topology_timeout_seconds,
            )
            item["topology_validation"] = topology_validation
            item["topology_readiness"] = (
                "validated_for_replicate_submit"
                if topology_validation.get("safe_for_ranking") is True
                else "topology_validation_not_safe_for_ranking"
            )
        if not req.store:
            item["mutant_input"] = {"pdb_data": item["pdb_data"]}
            if topology_validation is not None:
                item["mutant_input"]["topology_validation"] = topology_validation
            continue
        safe_variant = str(item.get("variant") or "mutant").replace("/", "_").replace(" ", "_")
        stored = await storage.upload_file(
            str(item["pdb_data"]).encode("utf-8"),
            filename=f"{safe_variant}.pdb",
            content_type="chemical/x-pdb",
            folder="md-mutants",
        )
        await record_tool_artifact_owner(
            stored["object_name"],
            current_user["id"],
            tool_name="gromacs_md_mutant_prepare",
            task_id=None,
        )
        item["stored"] = stored
        item["mutant_input"] = {"pdb_object_name": stored["object_name"]}
        if topology_validation is not None:
            item["mutant_input"]["topology_validation"] = topology_validation
        item.pop("pdb_data", None)
        stored_count += 1

    result["store"] = {"enabled": bool(req.store), "stored_count": stored_count}
    result["topology_validation"] = {
        "enabled": bool(req.validate_topology),
        "force_field": req.force_field,
        "water_model": req.water_model,
        "timeout_seconds": req.topology_timeout_seconds,
        "safe_count": sum(
            1
            for item in result.get("mutants", [])
            if isinstance(item, dict)
            and isinstance(item.get("topology_validation"), dict)
            and item["topology_validation"].get("safe_for_ranking") is True
        ),
    }
    result["next_steps"] = [
        "Review topology_readiness and warnings for each mutant.",
        "Run GROMACS pdb2gmx/topology validation before production MD ranking.",
        "Pass each mutant_input under mutant_inputs[variant] when calling /api/tools/md/replicates/submit.",
    ]
    return result


@router.post("/md/topology/validate")
async def validate_md_topology(
    req: MdTopologyValidateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run a lightweight real GROMACS pdb2gmx topology precheck."""
    from app.tools.gromacs_md import _validate_pdb_topology

    pdb_text = await _load_pdb_text_async(
        pdb_data=req.pdb_data,
        pdb_object_name=req.pdb_object_name,
        pdb_path=req.pdb_path,
    )
    result = _validate_pdb_topology(
        pdb_text,
        force_field=req.force_field,
        water_model=req.water_model,
        timeout=req.timeout_seconds,
    )
    result["requested_by_user_id"] = int(current_user["id"])
    result["next_steps"] = (
        ["Topology precheck passed; this PDB can be submitted to replicate MD subject to protocol review."]
        if result.get("topology_validated")
        else ["Resolve topology validation errors before submitting this structure to production MD ranking."]
    )
    return result


@router.get("/md/replicates/{batch_id}/summary")
async def summarize_md_replicate_batch(
    batch_id: str,
    minimum_replicates: int = Query(default=3, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Summarize completed MD replicate tasks for one current-user batch."""
    audits = await list_md_replicate_batch_audits(
        session,
        user_id=current_user["id"],
        batch_id=batch_id,
        limit=1000,
    )
    summary = _summarize_md_replicate_batch_from_audits(audits, minimum_replicates)
    return {
        "batch_id": batch_id,
        "minimum_replicates": minimum_replicates,
        **summary,
        "audits": [
            {
                "task_id": audit.get("task_id"),
                "status": audit.get("status"),
                "tool": audit.get("tool"),
                "updated_at": audit.get("updated_at"),
                "result_summary": audit.get("result_summary"),
            }
            for audit in audits
        ],
        "next_steps": (
            ["Wait for all submitted replicate tasks to reach a terminal state."]
            if summary["status"] == "incomplete"
            else ["Review batch_replicate_summary before ranking candidates."]
        ),
    }


@router.get("/{name}")
async def get_tool(name: str, current_user: dict = Depends(get_current_user)):
    """Get a specific tool's schema."""
    tool = ToolRegistry.get_tool(name)
    if not tool:
        raise HTTPException(404, f"Tool not found: {name}")
    return {
        "name": tool.name,
        "description": tool.description,
        "category": tool.category,
        "is_async": tool.is_async,
        "parameters": tool.parameters,
    }


@router.post("/{name}/call")
async def call_tool(name: str, req: ToolCallRequest, current_user: dict = Depends(get_current_user)):
    """Directly call a tool by name."""
    try:
        canonical = ToolRegistry._aliases.get(name, name)
        if canonical in ASYNC_TOOLS:
            raise HTTPException(400, f"Tool '{canonical}' is async-only; use /api/tools/{canonical}/submit")
        result = await ToolRegistry.execute(canonical, req.params)
        return {"status": "completed", "result": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{name}/preflight")
async def preflight_tool(
    name: str,
    req: ToolPreflightRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Validate one tool against explicit evidence before dispatch.

    Evidence is intentionally caller-supplied and defaults to empty. This
    endpoint never infers scientific readiness from the tool name or params.
    """
    canonical = ToolRegistry._aliases.get(name, name)
    if ToolRegistry.get_tool(canonical) is None:
        raise HTTPException(404, f"Tool not found: {name}")
    audits = []
    for task_id in req.task_ids:
        task_id = str(task_id).strip()
        if not task_id:
            continue
        audit = await get_persisted_task_audit(session, task_id=task_id, user_id=current_user["id"])
        if audit is not None:
            audits.append(audit)
    snapshot_tasks: list[dict] = []
    if req.snapshot_id:
        snapshot = (
            await session.execute(
                select(AnalysisEvidenceSnapshot).where(
                    AnalysisEvidenceSnapshot.snapshot_id == req.snapshot_id,
                    AnalysisEvidenceSnapshot.user_id == int(current_user["id"]),
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(404, "Evidence snapshot not found")
        snapshot_tasks = snapshot.evidence_payload if isinstance(snapshot.evidence_payload, list) else []
    evidence = {
        **evidence_from_completed_tasks(snapshot_tasks),
        **evidence_from_completed_tasks(audits),
        **req.evidence,
    }
    result = validate_tool_plan(
        [{"tool_name": canonical}],
        evidence=evidence,
        enforce_candidate_gates=True,
        enforce_dependency_order=True,
    )
    result["tool"] = canonical
    result["evidence"] = evidence
    result["task_ids_considered"] = len(audits)
    result["snapshot_id"] = req.snapshot_id
    result["snapshot_tasks_considered"] = len(snapshot_tasks)
    return result


@router.post("/{name}/submit")
async def submit_tool(
    name: str,
    req: ToolCallRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Submit an async-capable tool to Celery and return a task id."""
    canonical = ToolRegistry._aliases.get(name, name)
    tool = ToolRegistry.get_tool(canonical)
    if not tool:
        raise HTTPException(404, f"Tool not found: {name}")
    if canonical not in ASYNC_TOOLS:
        raise HTTPException(400, f"Tool '{canonical}' is not configured for async submission")

    return await _submit_async_tool_task(
        canonical=canonical,
        params=req.params,
        current_user=current_user,
        session=session,
    )


@router.get("/tasks/{task_id}")
async def get_tool_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Poll the status of an async tool task."""
    owner = await _require_task_owner(task_id, current_user)

    try:
        status = get_task_status(task_id)
    except Exception as e:
        raise HTTPException(500, str(e))

    status["tool"] = owner.get("tool")
    status["queue"] = owner.get("queue")
    status["soft_time_limit"] = owner.get("soft_time_limit")
    status["time_limit"] = owner.get("time_limit")
    status["cancel_requested"] = bool(owner.get("cancel_requested"))
    status["cancel_requested_at"] = owner.get("cancel_requested_at")
    status["cancel_effective_at"] = owner.get("cancel_effective_at")
    status["terminal_status"] = owner.get("terminal_status")
    _coerce_cancel_requested_terminal_status(owner, status)
    await _record_task_artifact_access(task_id, owner, status)
    if status["status"] in {"completed", "failed", "canceled"}:
        owner = await record_tool_task_terminal_state(task_id, status["status"]) or owner
        status["terminal_status"] = owner.get("terminal_status")
        status["cancel_effective_at"] = owner.get("cancel_effective_at")
    await update_task_audit_from_status(session, task_id=task_id, owner=owner, status=status)
    status["audit"] = _build_task_audit(task_id, owner, status)
    return status


@router.get("/tasks/{task_id}/artifacts/download")
async def download_tool_task_artifacts(task_id: str, current_user: dict = Depends(get_current_user)):
    """Download all generated artifacts for a completed async tool task as a zip archive."""
    owner = await _require_task_owner(task_id, current_user)

    try:
        status = get_task_status(task_id)
    except Exception as e:
        raise HTTPException(500, str(e))

    await _record_task_artifact_access(task_id, owner, status)
    artifacts = [artifact for artifact in _extract_task_artifacts(status) if isinstance(artifact, dict)]
    if not artifacts:
        raise HTTPException(404, "No downloadable artifacts found for this task")

    normalized_status = str(status.get("status") or "").lower()
    if normalized_status not in {"completed", "success"}:
        raise HTTPException(409, "Artifacts are available only after the task completes successfully")

    artifact_payload = _extract_artifact_payload(status) or {}
    manifest = artifact_payload.get("artifact_manifest") if isinstance(artifact_payload.get("artifact_manifest"), dict) else None
    category_lookup: dict[str, str] = {}
    if manifest:
        for category, grouped_artifacts in manifest.get("groups", {}).items():
            if not isinstance(grouped_artifacts, list):
                continue
            for artifact in grouped_artifacts:
                if not isinstance(artifact, dict):
                    continue
                object_name = artifact.get("object_name")
                name = artifact.get("name")
                if isinstance(object_name, str) and object_name:
                    category_lookup[object_name] = category
                if isinstance(name, str) and name:
                    category_lookup.setdefault(name, category)

    archive_buffer = io.BytesIO()
    seen_paths: set[str] = set()
    with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for artifact in artifacts:
            object_name = artifact.get("object_name")
            if not isinstance(object_name, str) or not object_name.strip():
                continue
            content = await storage.download_file(object_name)
            zf.writestr(_artifact_archive_path(artifact, category_lookup, seen_paths), content)

        if manifest:
            zf.writestr("manifest/artifact_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))

    archive_name = f"{owner.get('tool') or 'tool'}-{task_id[:8]}-artifacts.zip"
    return Response(
        content=archive_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_tool_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Request cancellation of an async tool task owned by the current user."""
    owner = await _require_task_owner(task_id, current_user)

    try:
        cancel_task(task_id)
    except Exception as e:
        raise HTTPException(500, str(e))
    owner = await record_tool_task_cancel_requested(task_id, current_user["id"]) or owner
    await mark_task_cancel_requested(session, task_id=task_id, owner=owner)

    return {
        "task_id": task_id,
        "tool": owner.get("tool"),
        "status": "cancel_requested",
        "cancel_requested_at": owner.get("cancel_requested_at"),
    }
