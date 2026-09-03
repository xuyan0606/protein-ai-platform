"""Fail-closed execution contract for long-running tool tasks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

LONG_TASK_TOOLS = {
    "gromacs_md",
    "rfdiffusion_design",
    "proteinmpnn_design",
    "diffdock_docking",
    "alphafold2_folding",
    "ligand_preprocess",
}


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_task_execution_quote(
    *,
    tool_name: str,
    params: dict[str, Any],
    queue: str,
    soft_time_limit: int,
    time_limit: int,
) -> dict[str, Any]:
    """Return a quote/confirmation contract without approving execution.

    The quote is deliberately not a billing authorization. It is a deterministic
    audit packet that can be stored beside the task audit row and later compared
    with the final runtime receipt.
    """
    long_task = tool_name in LONG_TASK_TOOLS or int(time_limit) >= 30 * 60
    quote_components = [
        {
            "component": "queue_reservation",
            "unit": "seconds",
            "estimated_quantity": int(time_limit),
            "billable": False,
            "note": "capacity estimate only; no billing adapter connected",
        },
        {
            "component": "artifact_storage",
            "unit": "artifact_bundle",
            "estimated_quantity": 1,
            "billable": False,
            "note": "artifact manifest and checksums required before completion can be claimed",
        },
    ]
    if tool_name == "gromacs_md":
        quote_components.append({
            "component": "md_runtime",
            "unit": "replicate",
            "estimated_quantity": int(params.get("replicates") or 1),
            "billable": False,
            "note": "real runtime requires explicit worker/runtime evidence",
        })

    quote = {
        "contract_version": "long_task_quote_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "queue": queue,
        "long_task": long_task,
        "requires_user_confirmation": long_task,
        "confirmation_status": "missing",
        "execution_allowed": not long_task,
        "soft_time_limit": int(soft_time_limit),
        "time_limit": int(time_limit),
        "input_sha256": _stable_hash(params),
        "quote_components": quote_components,
        "estimated_total": None,
        "currency": None,
        "billing_adapter_connected": False,
        "cancel_supported": True,
        "final_cost": None,
        "cost_delta_reason": None,
        "prohibited_claims": [
            "charged_customer",
            "refund_processed",
            "real_runtime_completed",
            "artifact_manifest_verified",
        ],
        "policy": "Quote-only contract. It does not authorize long-task execution, billing, refund, or scientific completion.",
    }
    return quote


def validate_task_execution_quote(quote: dict[str, Any]) -> list[str]:
    """Return validation errors for a quote contract."""
    errors: list[str] = []
    if quote.get("contract_version") != "long_task_quote_v1":
        errors.append("invalid_contract_version")
    if not quote.get("tool_name"):
        errors.append("missing_tool_name")
    if not quote.get("queue"):
        errors.append("missing_queue")
    if not isinstance(quote.get("quote_components"), list) or not quote.get("quote_components"):
        errors.append("missing_quote_components")
    if quote.get("billing_adapter_connected") is not False:
        errors.append("billing_adapter_must_be_false")
    if quote.get("final_cost") is not None:
        errors.append("final_cost_must_be_null_before_execution_receipt")
    if quote.get("long_task") is True:
        if quote.get("requires_user_confirmation") is not True:
            errors.append("long_task_requires_confirmation")
        if quote.get("execution_allowed") is not False:
            errors.append("long_task_execution_must_be_fail_closed_without_confirmation")
    return errors
