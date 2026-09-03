#!/usr/bin/env python3
"""Local rule MVP for KWB-EnzymeDesigner.

This prototype is intentionally dependency-free and local-only. It consumes a
KWB-EnzymeCase JSON file and emits a KWB-EnzymeDesigner result object.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MODEL_NAME = "KWB-EnzymeDesigner"
MODEL_VERSION = "0.1.0-rule-mvp"
DATA_VERSION = "local-dev"
CATALYTIC_FLAGS = {"protected_catalytic", "catalytic", "active_site_core"}
WATCH_FLAGS = {
    "near_pocket",
    "near_active_site",
    "numbering_uncertain",
    "low_structure_confidence",
    "activity_tradeoff",
    "substrate_fit_uncertain",
    "needs_activity_validation",
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def mutation_position(code: str) -> int | None:
    match = re.match(r"^[A-Z]([0-9]{1,5})[A-Z]$", str(code).upper())
    return int(match.group(1)) if match else None


def evidence_counts(case: dict[str, Any]) -> tuple[int, int]:
    private_count = 0
    public_count = 0
    for item in case.get("evidence") or []:
        source = str(item.get("source") or "")
        if source == "kwb_private":
            private_count += 1
        elif source:
            public_count += 1
    return private_count, public_count


def structure_evidence(case: dict[str, Any]) -> tuple[str, bool, list[str]]:
    structure = case.get("structure") or {}
    source_type = structure.get("source_type") or "none"
    flags = list(structure.get("quality_flags") or [])
    numbering_verified = bool(structure.get("numbering_verified"))
    sequence_level_only = source_type in {"none", None, ""} or not structure

    if source_type == "uploaded_pdb" and numbering_verified:
        return "uploaded_pdb_numbering_verified", False, flags
    if source_type == "uploaded_pdb" and not numbering_verified:
        return "uploaded_pdb_numbering_unverified", False, flags + ["numbering_uncertain"]
    if source_type in {"pdb", "alphafold", "esmfold"}:
        label = f"{source_type}_structure"
        if not numbering_verified:
            flags.append("numbering_uncertain")
        confidence = structure.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 70:
            flags.append("low_structure_confidence")
        return label, False, flags
    return "sequence_level_only", True, flags


def assay_completeness(case: dict[str, Any]) -> int:
    assay = case.get("assay_condition") or {}
    keys = ["ph", "temperature_c", "buffer", "expression_system", "assay_method"]
    return sum(1 for key in keys if assay.get(key) not in {None, ""})


def evidence_refs(case: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in case.get("evidence") or []:
        evidence_id = item.get("evidence_id")
        if evidence_id:
            refs.append(str(evidence_id))
    for item in case.get("tool_results") or []:
        result_ref = item.get("result_ref")
        if result_ref:
            refs.append(str(result_ref))
    return refs[:8]


def score_mutation(
    mutation: dict[str, Any],
    *,
    case: dict[str, Any],
    structure_flags: list[str],
    private_count: int,
    public_count: int,
    sequence_level_only: bool,
) -> dict[str, Any]:
    code = str(mutation.get("code") or "").upper()
    risk_flags = set(str(flag) for flag in mutation.get("risk_flags") or [])
    status = str(mutation.get("status") or "").lower()
    rationale_parts: list[str] = []

    if risk_flags & CATALYTIC_FLAGS:
        decision = "no_go"
        return {
            "mutation": code,
            "overall_score": 15,
            "stability_score": 20,
            "activity_risk_score": 0,
            "substrate_fit_score": 20,
            "assay_success_score": 10,
            "confidence": 0.85,
            "decision": decision,
            "rationale": "Protected catalytic or active-site-core mutation; not suitable as a default engineering candidate.",
            "risk_flags": sorted(risk_flags | {"protected_catalytic"}),
            "evidence_refs": evidence_refs(case),
            "next_experiment": "Do not advance this mutation unless a specialist override and rescue assay are approved.",
        }

    mutation_rank = 50.0
    stability = 50.0
    activity_safety = 68.0
    substrate_fit = 50.0
    assay_success = 45.0

    if status == "go":
        mutation_rank += 18
        assay_success += 18
        rationale_parts.append("validated single-mutant evidence supports this candidate")
    elif status in {"no_go", "failed"}:
        mutation_rank -= 22
        assay_success -= 20
        risk_flags.add("negative_feedback")
        rationale_parts.append("prior feedback is negative")
    elif status == "watch":
        mutation_rank += 4
        risk_flags.add("needs_wet_lab_validation")

    if private_count:
        mutation_rank += min(16, 8 + private_count * 2)
        assay_success += min(12, 6 + private_count)
        rationale_parts.append("KWB private evidence is available")
    if public_count:
        mutation_rank += min(8, public_count * 2)

    mutant = str(mutation.get("mutant") or code[-1:] or "").upper()
    wild_type = str(mutation.get("wild_type") or code[:1] or "").upper()
    if mutant == "P":
        stability += 16
        risk_flags.add("loop_rigidification")
        rationale_parts.append("proline substitution may improve loop rigidity")
    if wild_type in {"G", "P"} and mutant not in {"G", "P"}:
        stability -= 8
        risk_flags.add("backbone_flexibility_change")
    if mutant in {"D", "E", "K", "R"}:
        stability += 5
        rationale_parts.append("charged substitution may support surface electrostatic tuning")

    if "near_pocket" in risk_flags:
        activity_safety -= 10
        substrate_fit += 8
        rationale_parts.append("near-pocket candidate requires substrate activity check")
    if "near_active_site" in risk_flags:
        activity_safety -= 18
    if "numbering_uncertain" in structure_flags:
        mutation_rank -= 18
        activity_safety -= 18
        risk_flags.add("numbering_uncertain")
    if "low_structure_confidence" in structure_flags:
        stability -= 8
        risk_flags.add("low_structure_confidence")

    substrate = case.get("substrate") or {}
    has_substrate = any(substrate.get(key) for key in ("name", "smiles", "sdf_object"))
    has_ligand_tool = any((tr.get("tool_name") == "ligand_preprocess") for tr in case.get("tool_results") or [])
    if has_substrate and has_ligand_tool:
        substrate_fit += 16
    elif has_substrate:
        substrate_fit += 6
        risk_flags.add("substrate_fit_uncertain")
    else:
        risk_flags.add("substrate_not_evaluated")

    completeness = assay_completeness(case)
    assay_success += completeness * 5
    if completeness < 3:
        risk_flags.add("assay_condition_incomplete")

    if sequence_level_only:
        risk_flags.add("sequence_level_only")
        activity_safety = min(activity_safety, 62)
        substrate_fit = min(substrate_fit, 55)

    mutation_rank = clamp(mutation_rank)
    stability = clamp(stability)
    activity_safety = clamp(activity_safety)
    substrate_fit = clamp(substrate_fit)
    assay_success = clamp(assay_success)
    overall = clamp(
        0.30 * mutation_rank
        + 0.25 * stability
        + 0.20 * activity_safety
        + 0.15 * substrate_fit
        + 0.10 * assay_success
    )

    high_risk = bool(risk_flags & {"negative_feedback", "numbering_uncertain", "near_active_site"})
    if overall >= 80 and not high_risk:
        decision = "go"
    elif overall < 45 or "negative_feedback" in risk_flags:
        decision = "no_go"
    else:
        decision = "watch"

    confidence = 0.45
    confidence += min(0.18, private_count * 0.04)
    confidence += min(0.10, public_count * 0.02)
    confidence += min(0.12, completeness * 0.025)
    if "numbering_uncertain" in risk_flags:
        confidence -= 0.12
    if sequence_level_only:
        confidence -= 0.08
    confidence = round(max(0.1, min(0.9, confidence)), 2)

    if not rationale_parts:
        rationale_parts.append("rule MVP candidate with limited direct evidence")
    next_experiment = (
        f"Test {code} as a single mutant under the stated assay condition before combination."
        if decision != "no_go"
        else f"Do not advance {code} as a default candidate; review risk evidence first."
    )

    return {
        "mutation": code,
        "overall_score": round(overall, 1),
        "stability_score": round(stability, 1),
        "activity_risk_score": round(activity_safety, 1),
        "substrate_fit_score": round(substrate_fit, 1),
        "assay_success_score": round(assay_success, 1),
        "confidence": confidence,
        "decision": decision,
        "rationale": "; ".join(rationale_parts) + ".",
        "risk_flags": sorted(risk_flags),
        "evidence_refs": evidence_refs(case),
        "next_experiment": next_experiment,
    }


def derive_candidates(case: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = list(case.get("mutations") or [])
    if mutations:
        return mutations

    sequence = ((case.get("enzyme") or {}).get("sequence") or "")
    default_positions = [42, 88, 128]
    candidates: list[dict[str, Any]] = []
    for pos in default_positions:
        if 1 <= pos <= len(sequence):
            wt = sequence[pos - 1].upper()
        else:
            wt = "A"
        candidates.append({
            "code": f"{wt}{pos}P",
            "position": pos,
            "wild_type": wt,
            "mutant": "P",
            "source": "rule_mvp",
            "status": "untested",
            "rationale": "default loop-rigidification candidate generated by rule MVP",
            "risk_flags": ["needs_wet_lab_validation"],
        })
    return candidates


def design(case: dict[str, Any]) -> dict[str, Any]:
    private_count, public_count = evidence_counts(case)
    structure_label, sequence_level_only, structure_flags = structure_evidence(case)
    candidates = [
        score_mutation(
            mutation,
            case=case,
            structure_flags=structure_flags,
            private_count=private_count,
            public_count=public_count,
            sequence_level_only=sequence_level_only,
        )
        for mutation in derive_candidates(case)
    ]
    candidates.sort(key=lambda item: item["overall_score"], reverse=True)

    return {
        "model": {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "data_version": DATA_VERSION,
        },
        "candidates": candidates,
        "evidence_summary": {
            "kwb_private_records": private_count,
            "public_database_records": public_count,
            "structure_evidence": structure_label,
            "sequence_level_only": sequence_level_only,
            "requires_wet_lab_validation": True,
            "structure_quality_flags": sorted(set(structure_flags)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local KWB-EnzymeDesigner rule MVP")
    parser.add_argument("case_file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    case = json.loads(args.case_file.read_text(encoding="utf-8"))
    result = design(case)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
