"""Claim-level evidence gate for scientific reports.

The gate is intentionally small and strict: it does not verify sources by
itself, but it enforces how already-audited claims may appear in a report.
"""

from __future__ import annotations

from typing import Any

from app.tools.human_target_antibody_contracts import schema_audit_record
from app.tools.registry import ToolRegistry

_SUMMARY_ALLOWED = {"SUPPORTED"}
_BODY_ALLOWED = {"SUPPORTED", "WEAK", "DESIGN_HYPOTHESIS"}
_BLOCKING = {"MISSING", "CONFLICTING", "RUNTIME_UNVERIFIED"}


def _normalize_status(value: Any) -> str:
    return str(value or "MISSING").strip().upper()


def scientific_claim_gate(
    claims: list[dict[str, Any]],
    report_section: str = "summary",
    required_schema_contracts: list[str] | None = None,
) -> dict[str, Any]:
    """Gate audited claims before they are promoted into report text.

    Args:
        claims: List of claim records with at least {claim_id, claim, status}.
        report_section: summary, conclusion, body, methods, or appendix.
        required_schema_contracts: Optional contract names that must be backed
            by schema audit records before a claim can be promoted.
    """
    if not isinstance(claims, list):
        raise ValueError("INVALID_CLAIMS: claims must be a list of claim objects")

    section = str(report_section or "summary").strip().lower()
    strict_section = section in {"summary", "conclusion", "executive_summary"}
    allowed_statuses = _SUMMARY_ALLOWED if strict_section else _BODY_ALLOWED
    required_contracts = required_schema_contracts if isinstance(required_schema_contracts, list) else []

    allowed: list[dict[str, Any]] = []
    downgraded: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    audit_table: list[dict[str, Any]] = []

    for index, item in enumerate(claims, start=1):
        if not isinstance(item, dict):
            record = {
                "claim_id": f"C{index:03d}",
                "claim": str(item),
                "status": "MISSING",
                "reason": "claim entry is not an object",
            }
            blocked.append(record)
            audit_table.append({**record, "report_action": "block"})
            continue

        status = _normalize_status(item.get("status"))
        record = {
            "claim_id": item.get("claim_id") or item.get("id") or f"C{index:03d}",
            "claim": item.get("claim") or item.get("text") or "",
            "status": status,
            "source": item.get("source"),
            "evidence_level": item.get("evidence_level"),
            "notes": item.get("notes"),
        }
        contract_payloads = item.get("contract_payloads") if isinstance(item.get("contract_payloads"), dict) else {}
        requires_wt_baseline = item.get("requires_wt_baseline") is True
        wt_baseline = item.get("wt_baseline_registry") if isinstance(item.get("wt_baseline_registry"), dict) else {}
        wt_baseline_status = str(wt_baseline.get("status") or "missing").strip().lower()
        if requires_wt_baseline:
            record["wt_baseline_registry_status"] = wt_baseline_status
        schema_audits = [
            schema_audit_record(contract_name, contract_payloads.get(contract_name))
            for contract_name in required_contracts
        ]
        missing_schema = [audit for audit in schema_audits if audit["status"] != "ready"]
        if schema_audits:
            record["schema_audits"] = schema_audits

        if requires_wt_baseline and wt_baseline_status != "ready":
            action = "block_missing_wt_baseline"
            record["reason"] = "claim requires an exact-condition WT baseline registry with status=ready"
            blocked.append(record)
        elif missing_schema:
            action = "block_missing_schema"
            record["reason"] = "required schema contract is missing or incomplete"
            blocked.append(record)
        elif status in allowed_statuses:
            action = "allow"
            allowed.append(record)
        elif status == "WEAK" and strict_section:
            action = "downgrade_to_body_with_uncertainty"
            downgraded.append(record)
        elif status == "DESIGN_HYPOTHESIS" and strict_section:
            action = "downgrade_to_methods_as_uncalibrated_hypothesis"
            downgraded.append(record)
        elif status in _BLOCKING or status not in _BODY_ALLOWED:
            action = "block"
            blocked.append(record)
        else:
            action = "downgrade"
            downgraded.append(record)

        audit_table.append({**record, "report_action": action})

    gate_status = "ready" if not blocked and not (strict_section and downgraded) else "blocked"
    if not claims:
        gate_status = "blocked"
        blocked.append({
            "claim_id": "NO_CLAIMS",
            "claim": "No audited claims were supplied.",
            "status": "MISSING",
            "reason": "A report cannot promote conclusions without claim audit records.",
        })

    return {
        "status": gate_status,
        "report_section": section,
        "allowed_claims": allowed,
        "downgraded_claims": downgraded,
        "blocked_claims": blocked,
        "audit_table": audit_table,
        "summary": {
            "allowed_count": len(allowed),
            "downgraded_count": len(downgraded),
            "blocked_count": len(blocked),
            "strict_section": strict_section,
        },
        "rules": {
            "summary_or_conclusion": "Only SUPPORTED claims may be promoted.",
            "body": "SUPPORTED, WEAK, and DESIGN_HYPOTHESIS may appear with explicit labels.",
            "blocked": "MISSING, CONFLICTING, and RUNTIME_UNVERIFIED claims must not be written as facts.",
            "wt_baseline": "Claims marked requires_wt_baseline need wt_baseline_registry.status=ready.",
        },
        "model_claim_ready": False,
        "release_ready": False,
    }


ToolRegistry.register(
    name="scientific_claim_gate",
    description=(
        "Gate audited scientific claims before report synthesis. Blocks missing, "
        "conflicting, and runtime-unverified claims from summaries/conclusions and "
        "downgrades weak or design-hypothesis claims to labeled body/methods text."
    ),
    parameters={
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Audited claims with claim_id, claim, status, source, and evidence_level.",
            },
            "report_section": {
                "type": "string",
                "description": "Target report section: summary, conclusion, body, methods, appendix.",
            },
            "required_schema_contracts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional schema-only contracts that each claim must satisfy before promotion.",
            },
        },
        "required": ["claims"],
    },
    handler=scientific_claim_gate,
    category="analysis",
    timeout_seconds=30,
    errors=[
        {
            "reason": "invalid_input",
            "code": "INVALID_CLAIMS",
            "when": "claims is not a list",
            "recovery": "Pass claims as a list of claim audit objects.",
        },
    ],
)
