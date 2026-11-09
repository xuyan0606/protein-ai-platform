"""Single authority for mutation-candidate authorization.

Scoring tools may calculate hypotheses, but only this service decides whether
their rows are allowed to cross the candidate-table boundary.
"""

from __future__ import annotations

from typing import Any


def decide_candidate_output(
    identity_profile: dict[str, Any] | None,
    objective_module_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a deterministic, fail-closed candidate decision contract."""
    identity = identity_profile if isinstance(identity_profile, dict) else {}
    objective = objective_module_plan if isinstance(objective_module_plan, dict) else {}
    identity_status = str(identity.get("identity_status") or "unknown").lower()
    guardrail = identity.get("guardrail") if isinstance(identity.get("guardrail"), dict) else {}
    guardrail_status = str(guardrail.get("status") or "unknown").lower()
    objective_status = str(objective.get("status") or "unknown").lower()
    objective_allowed = objective.get("candidate_output_allowed") is True
    blockers: list[str] = []
    if identity_status != "identified":
        blockers.append("identity_status_must_be_identified")
    if guardrail_status != "ready":
        blockers.append("identity_guardrail_must_be_ready")
    if objective_status != "ready" or not objective_allowed:
        blockers.append("objective_module_must_explicitly_allow_candidate_output")
    ready = not blockers
    status = "ready" if ready else (
        "blocked_by_identity_gate"
        if any(item.startswith("identity_") for item in blockers)
        else "blocked_by_objective_gate"
    )
    return {
        "status": status,
        "candidate_output_allowed": ready,
        "identity_status": identity_status,
        "guardrail_status": guardrail_status,
        "objective_status": objective_status,
        "blockers": blockers,
        "evidence_level": "candidate_decision" if ready else "blocked",
        "contract_version": "candidate_decision_v1",
    }
