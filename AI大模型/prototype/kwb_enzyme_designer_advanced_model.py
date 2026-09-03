#!/usr/bin/env python3
"""Advanced local scaffold for KWB-EnzymeDesigner.

This is not a trained top-tier model. It is a dependency-free architecture
prototype that fixes the future model interface: multimodal feature slots,
five-head outputs, uncertainty, Pareto ranking, and fail-closed adapter gates.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MODEL_NAME = "KWB-EnzymeDesigner"
MODEL_VERSION = "2.2.0-advanced-scaffold"
ARCHITECTURE = "plm_gnn_ddg_feedback_multitask_scaffold"
AA = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC = set("AILMFWYV")
CHARGED = set("DEKRH")
CATALYTIC_FLAGS = {"protected_catalytic", "catalytic", "active_site_core"}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def parse_mutation(code: str) -> tuple[str, int | None, str]:
    text = str(code or "").strip().upper()
    match = re.fullmatch(r"([A-Z])([0-9]{1,5})([A-Z])", text)
    if not match:
        return "", None, ""
    return match.group(1), int(match.group(2)), match.group(3)


def evidence_tier(case: dict[str, Any]) -> str:
    sources = {str(item.get("source") or "") for item in case.get("evidence") or []}
    if "kwb_private" in sources:
        return "tier_0_kwb_wet_lab_or_private_context"
    if sources:
        return "tier_2_public_or_tool_context"
    return "tier_4_low_evidence"


def has_tool(case: dict[str, Any], tool_name: str) -> bool:
    return any(
        item.get("tool_name") == tool_name and item.get("status") in {"completed", "ok"}
        for item in case.get("tool_results") or []
    )


def adapter_readiness(case: dict[str, Any]) -> dict[str, bool]:
    structure = case.get("structure") or {}
    sequence = ((case.get("enzyme") or {}).get("sequence") or "")
    return {
        "sequence_plm_embedding": bool(sequence),
        "structure_gnn": bool(structure.get("source_type") not in {None, "", "none"} and structure.get("numbering_verified")),
        "msa_conservation": has_tool(case, "msa_conservation") or has_tool(case, "mmseqs2"),
        "ddg_backend": has_tool(case, "rosetta_ddg") or has_tool(case, "pyrosetta_ddg") or has_tool(case, "foldx_ddg") or has_tool(case, "thermompnn"),
        "wet_lab_feedback": any(str(item.get("source") or "") == "kwb_private" for item in case.get("evidence") or []),
        "ligand_or_substrate_context": bool((case.get("substrate") or {}).get("name") or (case.get("substrate") or {}).get("smiles")),
    }


def sequence_features(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    sequence = ((case.get("enzyme") or {}).get("sequence") or "").upper()
    wt, pos, mt = parse_mutation(mutation.get("code"))
    window = ""
    if pos and sequence and 1 <= pos <= len(sequence):
        start = max(0, pos - 6)
        end = min(len(sequence), pos + 5)
        window = sequence[start:end]
    return {
        "sequence_present": bool(sequence),
        "sequence_length": len(sequence),
        "wild_type_matches_sequence": bool(pos and sequence and 1 <= pos <= len(sequence) and sequence[pos - 1] == wt),
        "window_11": window,
        "wt_hydrophobic": wt in HYDROPHOBIC,
        "mutant_hydrophobic": mt in HYDROPHOBIC,
        "charge_change": (wt in CHARGED) != (mt in CHARGED),
        "proline_introduced": mt == "P",
        "glycine_removed": wt == "G" and mt != "G",
    }


def structure_features(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    structure = case.get("structure") or {}
    risk_flags = set(mutation.get("risk_flags") or [])
    return {
        "structure_source": structure.get("source_type") or "none",
        "numbering_verified": bool(structure.get("numbering_verified")),
        "confidence": structure.get("confidence"),
        "near_active_site": "near_active_site" in risk_flags,
        "near_pocket": "near_pocket" in risk_flags,
        "protected_catalytic": bool(risk_flags & CATALYTIC_FLAGS),
    }


def msa_features(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    summary = next(
        (item.get("summary") or {} for item in case.get("tool_results") or [] if item.get("tool_name") in {"msa_conservation", "mmseqs2"}),
        {},
    )
    return {
        "available": bool(summary),
        "conservation_score": summary.get("conservation_score"),
        "alignment_depth": summary.get("alignment_depth"),
        "source_database": summary.get("source_database"),
    }


def ddg_features(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    for name in ("rosetta_ddg", "pyrosetta_ddg", "foldx_ddg", "thermompnn"):
        for item in case.get("tool_results") or []:
            if item.get("tool_name") != name:
                continue
            summary = item.get("summary") or {}
            code = str(mutation.get("code") or "").upper()
            table = summary.get("mutations") if isinstance(summary.get("mutations"), dict) else {}
            ddg = table.get(code, summary.get("ddg"))
            return {
                "available": ddg is not None,
                "backend": name,
                "ddg_kcal_mol": ddg,
                "negative_is_stabilizing": True,
            }
    return {"available": False, "backend": None, "ddg_kcal_mol": None, "negative_is_stabilizing": True}


def feedback_features(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    status = str(mutation.get("status") or "").lower()
    return {
        "single_mutant_status": status or "unknown",
        "has_kwb_private_context": any(str(item.get("source") or "") == "kwb_private" for item in case.get("evidence") or []),
        "label_decision": (case.get("labels") or {}).get("decision"),
    }


def build_feature_row(case: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    readiness = adapter_readiness(case)
    seq = sequence_features(case, mutation)
    structure = structure_features(case, mutation)
    msa = msa_features(case, mutation)
    ddg = ddg_features(case, mutation)
    feedback = feedback_features(case, mutation)
    missing = [name for name, ready in readiness.items() if not ready]
    return {
        "case_id": case.get("case_id"),
        "mutation": str(mutation.get("code") or "").upper(),
        "feature_version": MODEL_VERSION,
        "evidence_tier": evidence_tier(case),
        "sequence_features": seq,
        "structure_features": structure,
        "msa_features": msa,
        "ddg_features": ddg,
        "feedback_features": feedback,
        "adapter_readiness": readiness,
        "missing_modalities": missing,
    }


def score_heads(feature: dict[str, Any]) -> dict[str, float]:
    seq = feature["sequence_features"]
    structure = feature["structure_features"]
    msa = feature["msa_features"]
    ddg = feature["ddg_features"]
    feedback = feature["feedback_features"]

    mutation_rank = 50.0
    stability = 50.0
    activity_safety = 65.0
    substrate_fit = 50.0
    assay_success = 45.0

    if seq["proline_introduced"]:
        stability += 14
        mutation_rank += 8
    if seq["charge_change"]:
        mutation_rank += 4
    if seq["wild_type_matches_sequence"] is False:
        mutation_rank -= 18
        activity_safety -= 15
    if structure["protected_catalytic"]:
        mutation_rank = 5
        activity_safety = 0
        substrate_fit = 10
    elif structure["near_active_site"]:
        activity_safety -= 18
        substrate_fit += 8
    elif structure["near_pocket"]:
        activity_safety -= 8
        substrate_fit += 12
    if structure["numbering_verified"]:
        mutation_rank += 8
        assay_success += 5
    else:
        mutation_rank -= 12
    if msa.get("available") and isinstance(msa.get("conservation_score"), (int, float)):
        conservation = float(msa["conservation_score"])
        mutation_rank += (5.0 - conservation) * 4.0
        activity_safety -= max(0.0, conservation - 6.0) * 3.0
    if ddg.get("available") and isinstance(ddg.get("ddg_kcal_mol"), (int, float)):
        value = float(ddg["ddg_kcal_mol"])
        if value < -1:
            stability += 18
        elif value > 2:
            stability -= 25
            mutation_rank -= 15
        elif value > 1:
            stability -= 10
    if feedback["single_mutant_status"] == "go":
        mutation_rank += 20
        assay_success += 18
    elif feedback["single_mutant_status"] in {"no_go", "failed"}:
        mutation_rank -= 30
        assay_success -= 22
    if feedback["has_kwb_private_context"]:
        assay_success += 8
        mutation_rank += 6

    return {
        "mutation_rank": round(clamp(mutation_rank), 1),
        "stability": round(clamp(stability), 1),
        "activity_safety": round(clamp(activity_safety), 1),
        "substrate_fit": round(clamp(substrate_fit), 1),
        "assay_success": round(clamp(assay_success), 1),
    }


def uncertainty(feature: dict[str, Any]) -> dict[str, Any]:
    missing = feature.get("missing_modalities") or []
    penalty = min(0.65, len(missing) * 0.09)
    confidence = round(max(0.1, 0.82 - penalty), 2)
    return {
        "confidence": confidence,
        "missing_modalities": missing,
        "ood_flags": [
            flag for flag in [
                "sequence_numbering_mismatch" if feature["sequence_features"]["wild_type_matches_sequence"] is False else None,
                "no_msa_conservation" if "msa_conservation" in missing else None,
                "no_ddg_backend" if "ddg_backend" in missing else None,
                "no_wet_lab_feedback" if "wet_lab_feedback" in missing else None,
            ]
            if flag
        ],
    }


def dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ("mutation_rank", "stability", "activity_safety", "substrate_fit", "assay_success")
    ahead_or_equal = all(a["heads"][key] >= b["heads"][key] for key in keys)
    strictly_ahead = any(a["heads"][key] > b["heads"][key] for key in keys)
    return ahead_or_equal and strictly_ahead


def assign_pareto(candidates: list[dict[str, Any]]) -> None:
    remaining = set(range(len(candidates)))
    rank = 1
    while remaining:
        front = []
        for idx in remaining:
            if not any(dominates(candidates[other], candidates[idx]) for other in remaining if other != idx):
                front.append(idx)
        for idx in front:
            candidates[idx]["pareto_rank"] = rank
        remaining -= set(front)
        rank += 1


def decision(candidate: dict[str, Any]) -> str:
    flags = set(candidate.get("risk_flags") or [])
    heads = candidate["heads"]
    conf = candidate["uncertainty"]["confidence"]
    if flags & CATALYTIC_FLAGS or heads["activity_safety"] < 20:
        return "no_go"
    if conf < 0.45 or candidate["pareto_rank"] > 1:
        return "watch"
    if heads["mutation_rank"] >= 75 and heads["stability"] >= 65 and heads["activity_safety"] >= 50:
        return "go"
    return "watch"


def predict(case: dict[str, Any]) -> dict[str, Any]:
    mutations = case.get("mutations") or []
    feature_rows = [build_feature_row(case, mutation) for mutation in mutations]
    candidates = []
    for mutation, feature in zip(mutations, feature_rows):
        risk_flags = sorted(set(mutation.get("risk_flags") or []) | set(feature["uncertainty_flags"] if "uncertainty_flags" in feature else []))
        row = {
            "mutation": feature["mutation"],
            "heads": score_heads(feature),
            "pareto_rank": 999,
            "uncertainty": uncertainty(feature),
            "risk_flags": risk_flags,
            "evidence_tier": feature["evidence_tier"],
            "feature_row": feature,
        }
        if feature["structure_features"]["protected_catalytic"] and "protected_catalytic" not in row["risk_flags"]:
            row["risk_flags"].append("protected_catalytic")
        candidates.append(row)
    assign_pareto(candidates)
    for row in candidates:
        row["decision"] = decision(row)
    candidates.sort(key=lambda item: (item["pareto_rank"], -item["heads"]["mutation_rank"], -item["uncertainty"]["confidence"]))
    readiness = adapter_readiness(case)
    return {
        "model": {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "architecture": ARCHITECTURE,
        },
        "status": "scaffold_only_fail_closed",
        "candidates": candidates,
        "evidence_summary": {
            "adapter_readiness": readiness,
            "ready_modalities": sorted(name for name, ready in readiness.items() if ready),
            "missing_modalities": sorted(name for name, ready in readiness.items() if not ready),
            "evidence_tier": evidence_tier(case),
            "requires_wet_lab_validation": True,
        },
        "policy": "Advanced scaffold only; no trained neural weights or model-quality claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run advanced KWB model scaffold")
    parser.add_argument("case_file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case = json.loads(args.case_file.read_text(encoding="utf-8"))
    result = predict(case)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
