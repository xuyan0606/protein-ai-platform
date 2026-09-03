#!/usr/bin/env python3
"""Plan structure-aware enzyme workflows without touching production code.

The planner is intentionally deterministic. It gives the future backend a
small, testable contract for ordering structure parsing, numbering validation,
sequence-only work, and KWB model execution.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable


SEQUENCE_LEVEL_TOOLS = (
    "sequence_basic_analysis",
    "predict_properties",
)

STRUCTURE_DEPENDENT_TOOLS = (
    "annotation_bundle",
    "structure_search_foldseek",
    "pocket_analysis",
    "distance_network",
    "catalytic_network",
    "residue_exposure",
    "kwb_enzyme_designer",
)


@dataclass(frozen=True)
class WorkflowContext:
    session_id: str
    conversation_id: str | None
    request_turn_id: str

    def task_id(self, tool_name: str) -> str:
        raw = "|".join(
            [
                self.session_id,
                self.conversation_id or "",
                self.request_turn_id,
                tool_name,
            ]
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"{tool_name}:{self.session_id}:{self.request_turn_id}:{digest}"


def _has_sequence(case: dict[str, Any]) -> bool:
    sequence = (case.get("enzyme") or {}).get("sequence")
    return isinstance(sequence, str) and bool(sequence.strip())


def _structure_source(case: dict[str, Any]) -> str:
    structure = case.get("structure") or {}
    source_type = structure.get("source_type")
    object_name = str(structure.get("object_name") or "").lower()
    if source_type == "uploaded_pdb" or object_name.endswith((".pdb", ".cif", ".mmcif")):
        return "uploaded_structure"
    if source_type in {"pdb", "alphafold", "esmfold"}:
        return str(source_type)
    return "none"


def _current_result_refs(
    refs: Iterable[dict[str, Any]],
    context: WorkflowContext,
) -> tuple[list[str], list[str]]:
    current: list[str] = []
    stale: list[str] = []
    for ref in refs:
        result_ref = str(ref.get("result_ref") or ref.get("task_id") or "")
        matches = (
            ref.get("session_id") == context.session_id
            and ref.get("conversation_id") == context.conversation_id
            and ref.get("request_turn_id") == context.request_turn_id
        )
        if result_ref and matches:
            current.append(result_ref)
        elif result_ref:
            stale.append(result_ref)
    return current, stale


def _step(
    tool_name: str,
    stage: str,
    status: str,
    context: WorkflowContext,
    depends_on: list[str] | None = None,
    blocked_reason: str | None = None,
    conclusion_scope: str = "sequence",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool_name": tool_name,
        "stage": stage,
        "status": status,
        "task_id": context.task_id(tool_name),
        "depends_on": depends_on or [],
        "conclusion_scope": conclusion_scope,
    }
    if blocked_reason:
        payload["blocked_reason"] = blocked_reason
    return payload


def build_workflow_plan(
    case: dict[str, Any],
    context: WorkflowContext,
    completed_tools: Iterable[str] = (),
    tool_result_refs: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a safe tool order for one conversation turn."""

    completed = set(completed_tools)
    source = _structure_source(case)
    has_sequence = _has_sequence(case)
    structure = case.get("structure") or {}
    numbering_verified = structure.get("numbering_verified") is True
    current_refs, stale_refs = _current_result_refs(tool_result_refs, context)

    if source == "none" and not has_sequence:
        return {
            "status": "blocked",
            "error_code": "missing_sequence_or_structure",
            "structure_source": source,
            "structure_ready": False,
            "numbering_verified": False,
            "steps": [
                _step(
                    "input_parser",
                    "input_parsing",
                    "blocked",
                    context,
                    blocked_reason="missing_sequence_or_structure",
                )
            ],
            "current_result_refs": current_refs,
            "ignored_stale_task_refs": stale_refs,
            "allowed_conclusion_scopes": [],
        }

    steps: list[dict[str, Any]] = []
    if source != "none":
        steps.append(_step("input_parser", "input_parsing", "planned", context))
        structure_parser = (
            "structure_file_parser"
            if source == "uploaded_structure"
            else "structure_reference_resolver"
        )
        steps.append(
            _step(
                structure_parser,
                "structure_gate",
                "planned",
                context,
                depends_on=["input_parser"],
                conclusion_scope="structure",
            )
        )
        numbering_status = "completed" if numbering_verified else "planned"
        steps.append(
            _step(
                "residue_numbering_gate",
                "residue_numbering",
                numbering_status,
                context,
                depends_on=[structure_parser],
                blocked_reason=None if numbering_verified else "numbering_not_verified",
                conclusion_scope="structure",
            )
        )
        if numbering_verified:
            steps.extend(
                [
                    _step(
                        "annotation_bundle",
                        "evidence_retrieval",
                        "planned",
                        context,
                        depends_on=["residue_numbering_gate"],
                        conclusion_scope="structure",
                    ),
                    _step(
                        "structure_search_foldseek",
                        "feature_enrichment",
                        "planned",
                        context,
                        depends_on=["residue_numbering_gate"],
                        conclusion_scope="structure",
                    ),
                    _step(
                        "kwb_enzyme_designer",
                        "multi_head_scoring",
                        "planned",
                        context,
                        depends_on=["annotation_bundle", "structure_search_foldseek"],
                        conclusion_scope="structure",
                    ),
                ]
            )
            status = "planned"
            allowed_scopes = ["sequence", "structure", "experimental"]
        else:
            steps.extend(
                _step(
                    tool_name,
                    "feature_enrichment" if tool_name != "kwb_enzyme_designer" else "multi_head_scoring",
                    "blocked",
                    context,
                    depends_on=["residue_numbering_gate"],
                    blocked_reason="numbering_not_verified",
                    conclusion_scope="structure",
                )
                for tool_name in ("annotation_bundle", "structure_search_foldseek", "kwb_enzyme_designer")
            )
            status = "blocked"
            allowed_scopes = ["sequence"] if has_sequence else []
    else:
        steps.append(_step("input_parser", "input_parsing", "planned", context))
        for tool_name in SEQUENCE_LEVEL_TOOLS:
            steps.append(
                _step(
                    tool_name,
                    "input_parsing" if tool_name == "sequence_basic_analysis" else "feature_enrichment",
                    "planned",
                    context,
                    depends_on=["input_parser"] if tool_name == "sequence_basic_analysis" else ["sequence_basic_analysis"],
                    conclusion_scope="sequence",
                )
            )
        esmfold_status = "completed" if "esmfold_folding" in completed else "planned"
        steps.append(
            _step(
                "esmfold_folding",
                "structure_gate",
                esmfold_status,
                context,
                depends_on=["predict_properties"],
                conclusion_scope="predicted_structure",
            )
        )
        structure_ready = "esmfold_folding" in completed or source in {"pdb", "alphafold", "esmfold"}
        downstream_status = "planned" if structure_ready else "blocked"
        downstream_reason = None if structure_ready else "pending_structure_prediction"
        steps.extend(
            [
                _step(
                    "annotation_bundle",
                    "evidence_retrieval",
                    downstream_status,
                    context,
                    depends_on=["esmfold_folding"],
                    blocked_reason=downstream_reason,
                    conclusion_scope="predicted_structure",
                ),
                _step(
                    "kwb_enzyme_designer",
                    "multi_head_scoring",
                    downstream_status,
                    context,
                    depends_on=["annotation_bundle"],
                    blocked_reason=downstream_reason,
                    conclusion_scope="predicted_structure",
                ),
            ]
        )
        status = "planned" if structure_ready else "pending_structure"
        allowed_scopes = ["sequence"] if not structure_ready else ["sequence", "predicted_structure", "experimental"]

    return {
        "status": status,
        "error_code": None,
        "structure_source": source,
        "structure_ready": (
            (source == "uploaded_structure" and numbering_verified)
            or source in {"pdb", "alphafold", "esmfold"}
            or "esmfold_folding" in completed
        ),
        "numbering_verified": numbering_verified,
        "steps": steps,
        "current_result_refs": current_refs,
        "ignored_stale_task_refs": stale_refs,
        "allowed_conclusion_scopes": allowed_scopes,
        "forbidden_before_structure_ready": list(STRUCTURE_DEPENDENT_TOOLS),
        "policy": {
            "uploaded_structure_precedes_prediction": True,
            "sequence_level_analysis_may_precede_prediction": True,
            "structure_claims_require_current_structure_result": True,
            "task_refs_are_turn_scoped": True,
        },
    }
