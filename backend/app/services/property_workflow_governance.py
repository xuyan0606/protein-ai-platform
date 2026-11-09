"""Deterministic enzyme-property routing and workflow policy checks.

This module is intentionally side-effect free.  It is the first governance
layer used by shadow mode before the existing agent executor is changed.
"""

from __future__ import annotations

import re
from typing import Any
from app.services.engineering_goal_semantics import property_goal_text, activity_goal_text, is_heat_objective


_WORKFLOWS = {
    "stability": "WF-STABILITY",
    "ph": "WF-PH",
    "activity": "WF-ACTIVITY",
    "specificity": "WF-SPECIFICITY",
    "expression": "WF-EXPRESSION",
}

_TARGET_PATTERNS = {
    "stability": r"稳定性|耐热|热稳定|半衰期|溶剂耐受|蛋白酶耐受|thermostability|thermal stability|melting temperature|half[- ]life",
    "ph": r"pH|酸碱耐受|酸性耐受|碱性耐受|最适.?pH",
    "activity": r"活性|酶活|催化效率|\bkcat\b|\bKm\b|比活|转化率|反应速率|\bactivity\b|catalytic efficiency",
    "specificity": r"特异性|选择性|底物谱|底物偏好|区域选择性|立体选择性",
    "expression": r"表达量|可溶性|分泌|聚集|宿主适配|折叠",
}

_PRESERVATION_PATTERNS = {
    "activity_not_drop": r"(?:活性|酶活|比活力).*(?:不能|不要|不应|不).*?(?:下降|降低|受影响)|(?:保持.*(?:活性|酶活|比活力)|(?:活性|酶活|比活力).*保持不变)",
    "stability_not_drop": r"稳定性.*(?:不能|不要|不应|不).*?(?:下降|降低)|(?:保持.*稳定性|稳定性.*保持不变)",
    "expression_not_drop": r"表达.*(?:不能|不要|不应|不).*?(?:下降|降低)|(?:保持.*表达|表达.*保持不变)",
    "specificity_not_drop": r"特异性.*(?:不能|不要|不应|不).*?(?:下降|降低)|(?:保持.*特异性|特异性.*保持不变)",
}

_EXCLUSION_PATTERNS = {
    "activity_not_optimize": r"(?:不要|无需|不需要|禁止)(?:再)?(?:优化|提高|提升|改善).*?(?:活性|酶活|比活力)|(?:活性|酶活|比活力).*?(?:不要|无需|不需要)(?:优化|提高|提升)",
    "stability_not_optimize": r"(?:不要|无需|不需要|禁止)(?:再)?(?:优化|提高|提升|改善).*?稳定性|稳定性.*?(?:不要|无需|不需要)(?:优化|提高|提升)",
    "expression_not_optimize": r"(?:不要|无需|不需要|禁止)(?:再)?(?:优化|提高|提升|改善).*?表达|表达.*?(?:不要|无需|不需要)(?:优化|提高|提升)",
    "specificity_not_optimize": r"(?:不要|无需|不需要|禁止)(?:再)?(?:优化|提高|提升|改善).*?特异性|特异性.*?(?:不要|无需|不需要)(?:优化|提高|提升)",
}

_STABILITY_MUST = ("ST-01", "ST-02", "ST-03", "ST-04", "ST-05", "ST-06", "ST-07", "ST-11", "ST-12")
_COMMON_CONTROL_TOOLS = {
    "intake_review", "enzyme_objective_module_plan", "tool_capability_audit", "scientific_claim_gate",
    "report_generator",
}
_STRUCTURE_EVIDENCE_TOOLS = {
    "build_site_structure_function_features",
    "ligand_contact_analysis", "structure_pocket_interface_analysis",
}
_STABILITY_STRUCTURE_TOOLS = _STRUCTURE_EVIDENCE_TOOLS | {"disulfide_saltbridge_scan"}
_STABILITY_ALLOWED = _COMMON_CONTROL_TOOLS | _STABILITY_STRUCTURE_TOOLS | {
    "enzyme_sequence_identity",
    "thermostability_candidate_workflow", "ddgun_predict", "colabfold_predict", "evcouplings_analyze",
    "enzyme_identity_profile", "sequence_search",
    "blast_search", "lookup_protein", "protein_benchmark", "annotation_bundle", "get_stability_data",
    "literature_live_search", "external_research_evidence", "predict_properties", "residue_numbering_gate",
    "residue_mapping_sifts", "mutation_scan", "mutation_priority_score", "protssn_score", "esm1v_predict",
    "esm2_predict", "rosetta_ddg", "mutation_epistasis_check", "esmfold_folding", "alphafold_folding",
    "alphafold2_folding", "rosettafold_folding", "rosettafold_allatom", "structure_search_foldseek",
    "gromacs_md", "catalytic_site_lookup", "enzyme_function", "kcat_predict", "get_kinetic_params",
    "enzyme_assistant_recommend", "enzyme_assistant_build",
}
_STABILITY_FORBIDDEN = {
    "signal_peptide_predict", "soluble_mpnn_design", "ligandmpnn_design", "diffdock_docking",
    "rfdiffusion_design", "chroma_design", "progen2_generate", "evodiff_generate", "esm3_generate",
}
_IDENTITY_AND_EVIDENCE_TOOLS = {
    "enzyme_identity_profile", "sequence_search", "blast_search", "lookup_protein", "list_ec_proteins",
    "protein_benchmark", "annotation_bundle", "interpro_annotation", "interpro_live_lookup",
    "interproscan_sequence_submit", "interproscan_sequence_status", "enzyme_function",
    "literature_live_search", "external_connectivity_check", "external_research_evidence",
    "residue_mapping_sifts", "residue_numbering_gate", "catalytic_site_lookup",
}
_ACTIVITY_ALLOWED = _COMMON_CONTROL_TOOLS | _IDENTITY_AND_EVIDENCE_TOOLS | _STRUCTURE_EVIDENCE_TOOLS | {
    "search_substrate", "get_kinetic_params", "mutation_priority_score", "mutation_scan", "kcat_predict",
    "protssn_score", "esm1v_predict", "esm2_predict", "mutation_epistasis_check", "ligand_preprocess",
    "diffdock_docking", "boltz1_predict", "esmfold_folding", "alphafold_folding", "rosetta_ddg",
    "gromacs_md", "structure_search_foldseek", "predict_properties",
}
_PH_ALLOWED = _COMMON_CONTROL_TOOLS | _IDENTITY_AND_EVIDENCE_TOOLS | _STRUCTURE_EVIDENCE_TOOLS | {
    "enzyme_assistant_recommend", "enzyme_assistant_build",
    "get_kinetic_params", "get_stability_data", "structure_search_foldseek", "predict_properties",
    "esmfold_folding", "alphafold_folding", "protssn_score", "mutation_priority_score", "mutation_scan",
    "esm1v_predict", "esm2_predict", "gromacs_md", "rosetta_ddg", "kcat_predict",
    "mutation_epistasis_check", "feedback_iteration_planner", "signal_peptide_predict",
}
_SPECIFICITY_ALLOWED = _COMMON_CONTROL_TOOLS | _IDENTITY_AND_EVIDENCE_TOOLS | _STRUCTURE_EVIDENCE_TOOLS | {
    "search_substrate", "get_kinetic_params", "mutation_priority_score", "mutation_scan", "ligandmpnn_design",
    "protssn_score", "esm1v_predict", "esm2_predict", "ligand_preprocess", "diffdock_docking",
    "boltz1_predict", "kcat_predict", "rosetta_ddg", "get_stability_data", "structure_search_foldseek",
    "predict_properties",
}
_EXPRESSION_ALLOWED = _COMMON_CONTROL_TOOLS | _IDENTITY_AND_EVIDENCE_TOOLS | _STRUCTURE_EVIDENCE_TOOLS | {
    "predict_properties", "get_stability_data", "soluble_mpnn_design", "proteinmpnn_design", "esm_if1_design",
    "mutation_scan", "mutation_priority_score", "protssn_score", "esm1v_predict", "esm2_predict",
    "signal_peptide_predict", "esmfold_folding", "alphafold_folding", "rosettafold_folding",
    "rosettafold_allatom", "structure_search_foldseek", "kcat_predict", "get_kinetic_params", "rosetta_ddg",
}
_WORKFLOW_ALLOWED = {
    "WF-STABILITY": _STABILITY_ALLOWED,
    "WF-ACTIVITY": _ACTIVITY_ALLOWED,
    "WF-PH": _PH_ALLOWED,
    "WF-SPECIFICITY": _SPECIFICITY_ALLOWED,
    "WF-EXPRESSION": _EXPRESSION_ALLOWED,
}
_WORKFLOW_FORBIDDEN = {
    "WF-STABILITY": _STABILITY_FORBIDDEN,
    "WF-ACTIVITY": {
        "soluble_mpnn_design", "signal_peptide_predict", "rfdiffusion_design", "chroma_design",
        "progen2_generate", "evodiff_generate", "esm3_generate", "proteinmpnn_design", "esm_if1_design",
    },
    "WF-PH": {"rfdiffusion_design", "chroma_design", "progen2_generate", "evodiff_generate", "esm3_generate"},
    "WF-SPECIFICITY": {
        "signal_peptide_predict", "soluble_mpnn_design", "rfdiffusion_design", "chroma_design",
        "progen2_generate", "evodiff_generate", "esm3_generate",
    },
    "WF-EXPRESSION": {
        "rfdiffusion_design", "chroma_design", "progen2_generate", "evodiff_generate", "esm3_generate",
        "diffdock_docking", "gromacs_md",
    },
}


class PropertyWorkflowRouter:
    """Route explicit enzyme-property goals without invoking tools."""

    @staticmethod
    def route(message: str) -> dict[str, Any]:
        # The frontend appends machine-generated PDB metadata after the request.
        # Crystal-cell "alpha" is not a pH objective, nor are annotations goals.
        text = property_goal_text(message)
        if re.search(r"是什么意思|什么是|请解释|有何区别|有什么区别|为什么|为何", text, re.I) and not re.search(
            r"提高|提升|优化|改造|设计|分析|预测|评估|拓宽|收窄", text, re.I
        ):
            return {"intent": "NON_EXECUTION", "status": "NOT_APPLICABLE", "workflow_id": None,
                    "primary_property": None, "optimization_targets": [], "secondary_properties": [],
                    "preservation_constraints": [], "input_gaps": []}
        targets = [name for name, pattern in _TARGET_PATTERNS.items()
                   if re.search(pattern, activity_goal_text(text) if name == 'activity' else text, re.I)]
        if is_heat_objective(text) and 'stability' not in targets:
            targets.insert(0, 'stability')
        if ('stability' in targets and 'ph' in targets
                and re.search(r'pH\s*[:：=为]?\s*\d', text, re.I)
                and not re.search(r'(?:提高|降低|优化|改变|拓宽|调整)\s*(?:最适\s*)?pH|pH\s*(?:稳定|耐受|活性谱|范围)|最适\s*pH', text, re.I)):
            targets.remove('ph')
        # A property mentioned only in a keep/don't-drop clause is a constraint.
        constraint_only = {
            "activity": _PRESERVATION_PATTERNS["activity_not_drop"],
            "stability": _PRESERVATION_PATTERNS["stability_not_drop"],
            "expression": _PRESERVATION_PATTERNS["expression_not_drop"],
            "specificity": _PRESERVATION_PATTERNS["specificity_not_drop"],
        }
        clauses = re.split(r"[，。,；;、]|但|而且|同时", text)
        exclusions = {
            key.removesuffix("_not_optimize"): key
            for key, pattern in _EXCLUSION_PATTERNS.items()
            if any(re.search(pattern, clause, re.I) for clause in clauses)
        }
        targets = [name for name in targets if name not in exclusions]
        targets = [
            name for name in targets
            if not (
                re.search(constraint_only.get(name, r"$^"), text, re.I)
                and not any(
                    re.search(r"提高|提升|优化|改善|拓宽|收窄", clause, re.I)
                    and re.search(_TARGET_PATTERNS[name], clause, re.I)
                    for clause in clauses
                )
            )
        ]
        # Activity measured at a requested pH is the pH objective's metric,
        # unless the user explicitly declares activity as a separate goal.
        if "ph" in targets and "activity" in targets and not re.search(
            r"同时.*(?:活性|催化效率)|(?:活性|催化效率).*同时", text, re.I
        ):
            targets.remove("activity")
        explicit_primary = None
        explicit_prefix = re.search(r"(?:主目标|优先|主要目标)\s*(?:是|为|：|:)?\s*(提高|提升|优化|改善|拓宽|收窄)?", text, re.I)
        if explicit_prefix:
            tail = text[explicit_prefix.end():explicit_prefix.end() + 12]
            explicit_primary = next((n for n, p in _TARGET_PATTERNS.items() if re.search(p, tail, re.I)), None)
        primary_match = re.search(r"(?:主目标|优先|主要目标)\s*(?:是|为|：|:)\s*([^，。,；;。\s]+)", text, re.I)
        if primary_match and explicit_primary is None:
            value = primary_match.group(1)
            explicit_primary = next((n for n, p in _TARGET_PATTERNS.items() if re.search(p, value, re.I)), None)
        if explicit_primary and explicit_primary not in targets:
            targets.insert(0, explicit_primary)
        if not targets:
            return {"intent": "NEW_TASK", "status": "NEEDS_INPUT", "workflow_id": None, "primary_property": None,
                    "optimization_targets": [], "secondary_properties": [],
                    "preservation_constraints": [], "input_gaps": ["optimization_target"]}
        if len(targets) > 1 and explicit_primary is None:
            return {"intent": "NEW_TASK", "status": "NEEDS_INPUT", "workflow_id": None, "primary_property": None,
                    "optimization_targets": targets, "secondary_properties": [],
                    "preservation_constraints": [], "input_gaps": ["primary_property"]}
        primary = explicit_primary or targets[0]
        secondary = [name for name in targets if name != primary] if re.search(r"同时|还要|第二目标|并且提高|并提升", text) else []
        constraints = []
        constraints.extend(exclusions.values())
        for name, pattern in _PRESERVATION_PATTERNS.items():
            if any(re.search(pattern, clause, re.I) for clause in clauses):
                constraints.append(name)
        return {"intent": "NEW_TASK", "status": "READY", "workflow_id": _WORKFLOWS[primary], "primary_property": primary,
                "optimization_targets": [primary] + secondary, "secondary_properties": secondary,
                "preservation_constraints": constraints, "input_gaps": [], "route_confidence": "high"}


class WorkflowPolicyValidator:
    """Validate a workflow execution trace against its declared policy."""

    @staticmethod
    def validate(workflow_id: str, plan: list[dict[str, Any]] | None) -> dict[str, Any]:
        rows = plan if isinstance(plan, list) else []
        missing = []
        forbidden = []
        invalid_status = []
        optional_without_reason = []
        if workflow_id == "WF-STABILITY":
            seen = {str(row.get("step_id")) for row in rows if isinstance(row, dict)}
            missing = [step for step in _STABILITY_MUST if step not in seen]
            for row in rows:
                if not isinstance(row, dict):
                    invalid_status.append(row)
                    continue
                tool_id = row.get("tool_id")
                if tool_id in _STABILITY_FORBIDDEN or (tool_id and tool_id not in _STABILITY_ALLOWED):
                    forbidden.append({"step_id": row.get("step_id"), "tool_id": tool_id})
                status = row.get("status")
                if status not in {"completed", "skipped", "blocked", "failed"}:
                    invalid_status.append(row.get("step_id"))
                if status == "skipped" and not row.get("skip_reason"):
                    optional_without_reason.append(row.get("step_id"))
        else:
            return {"status": "NEEDS_REVIEW", "workflow_id": workflow_id,
                    "reason": "workflow policy is not enabled in shadow mode",
                    "missing_must_steps": [], "forbidden_tool_calls": []}
        status = "READY" if not (missing or forbidden or invalid_status or optional_without_reason) else "NEEDS_REVIEW"
        return {"status": status, "workflow_id": workflow_id, "missing_must_steps": missing,
                "forbidden_tool_calls": forbidden, "invalid_status_steps": invalid_status,
                "optional_without_skip_reason": optional_without_reason}

    @staticmethod
    def validate_declared_tools(workflow_id: str, tool_names: list[str] | None) -> dict[str, Any]:
        """Enforce tool allow/deny policy before a plan can be confirmed.

        This deliberately does not require every legacy must-step yet: existing
        plans are compact and the full workflow adapter is a separate migration.
        Unknown and forbidden tools are unsafe immediately and fail closed.
        """
        names = [str(name) for name in (tool_names or []) if str(name)]
        allowed = _WORKFLOW_ALLOWED.get(workflow_id)
        if allowed is None:
            # Only workflows with an explicit allow/deny catalog are enforced
            # here.  Keep legacy routes executable until their catalogs are
            # migrated; their policy gap remains visible in the contract.
            return {"status": "READY", "workflow_id": workflow_id,
                    "reason": "workflow policy is not enabled; execution allowed under legacy policy",
                    "forbidden_tool_calls": [], "unknown_tool_calls": []}
        forbidden_tools = _WORKFLOW_FORBIDDEN[workflow_id]
        forbidden = sorted({name for name in names if name in forbidden_tools})
        unknown = sorted({name for name in names if name not in allowed and name not in forbidden_tools})
        status = "READY" if not forbidden and not unknown else "NEEDS_REVIEW"
        return {
            "status": status,
            "workflow_id": workflow_id,
            "reason": "declared tool policy check against versioned workflow catalog",
            "forbidden_tool_calls": forbidden,
            "unknown_tool_calls": unknown,
        }


def compare_legacy_plan(message: str, tool_names: list[str] | None) -> dict[str, Any]:
    """Compare a legacy plan to v2 policy without influencing dispatch."""
    route = PropertyWorkflowRouter.route(message)
    observed = [str(name) for name in (tool_names or []) if str(name)]
    forbidden: list[str] = []
    unknown: list[str] = []
    if route.get("workflow_id") == "WF-STABILITY":
        forbidden = sorted({name for name in observed if name in _STABILITY_FORBIDDEN})
        unknown = sorted({name for name in observed if name not in _STABILITY_ALLOWED and name not in _STABILITY_FORBIDDEN})
    return {
        "mode": "shadow",
        "route": route,
        "observed_tool_count": len(observed),
        "observed_tools": observed,
        "forbidden_tools": forbidden,
        "unmapped_tools": unknown,
        "dispatch_blocked": False,
    }


def evaluate_shadow_cases(cases: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Score deterministic property routes against a versioned replay set."""
    results: list[dict[str, Any]] = []
    constraint_leaks = 0
    for case in cases or []:
        route = PropertyWorkflowRouter.route(str(case.get("message") or ""))
        expected_workflow = case.get("workflow_id")
        expected_status = case.get("status", "READY")
        failures: list[str] = []
        if route.get("status") != expected_status:
            failures.append("status")
        if expected_workflow is not None and route.get("workflow_id") != expected_workflow:
            failures.append("workflow_id")
        for field in ("primary_property", "secondary_properties", "preservation_constraints"):
            if field in case and route.get(field) != case.get(field):
                failures.append(field)
        leaked = {
            item.removesuffix("_not_drop")
            for item in route.get("preservation_constraints", [])
            if str(item).endswith("_not_drop")
        }.intersection(route.get("optimization_targets", []))
        if leaked:
            constraint_leaks += 1
            failures.append("constraint_leak")
        results.append({
            "id": case.get("id"),
            "passed": not failures,
            "failures": failures,
            "route": route,
        })
    passed = sum(1 for item in results if item["passed"])
    return {
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "constraint_leak_count": constraint_leaks,
        "results": results,
    }
