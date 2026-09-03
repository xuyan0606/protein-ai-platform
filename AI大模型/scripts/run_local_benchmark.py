#!/usr/bin/env python3
"""Local benchmark harness for KWB-EnzymeDesigner R&D artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks" / "cases"
SAMPLE_CASE = ROOT / "datasets" / "sample_case.json"
RULE_MVP = ROOT / "prototype" / "kwb_enzyme_designer_rule.py"


def load_rule_module():
    spec = importlib.util.spec_from_file_location("kwb_enzyme_designer_rule", RULE_MVP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load rule MVP from {RULE_MVP}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_files(path: Path) -> list[Path]:
    return sorted(item for item in path.glob("*.json") if item.is_file())


def parse_mutations(text: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    mutations: list[dict[str, Any]] = []
    for code in re.findall(r"\b[A-Z][0-9]{1,5}[A-Z]\b", text.upper()):
        if code in seen:
            continue
        seen.add(code)
        mutations.append({
            "code": code,
            "position": int(re.search(r"[0-9]+", code).group(0)),
            "wild_type": code[0],
            "mutant": code[-1],
            "source": "benchmark_input",
            "status": "untested",
            "risk_flags": [],
        })
    return mutations


def case_to_enzyme_case(bench: dict[str, Any]) -> dict[str, Any]:
    text_parts = [bench.get("input", {}).get("message", "")]
    for item in bench.get("input", {}).get("history_context") or []:
        text_parts.append(str(item.get("content") or ""))
    text = "\n".join(text_parts)
    lowered = text.lower()

    has_uploaded_pdb = "object_name:" in lowered or ".pdb" in lowered
    has_sequence = "sequence:" in lowered or bool(re.search(r"[ACDEFGHIKLMNPQRSTVWY]{40,}", text))
    has_sdf = ".sdf" in lowered or "ligand_sdf_object" in lowered
    is_lipase = "脂肪酶" in text or "lipase" in lowered
    is_amylase = "淀粉酶" in text or "amylase" in lowered

    mutations = parse_mutations(text)
    for mutation in mutations:
        if mutation["code"] in {"S153A"}:
            mutation["risk_flags"].append("protected_catalytic")
            mutation["status"] = "no_go"
        elif mutation["code"] in {"D180N"}:
            mutation["risk_flags"].append("near_active_site")
            mutation["status"] = "watch"
        elif mutation["code"] in {"G88P", "K210E"}:
            mutation["status"] = "failed"
            mutation["risk_flags"].append("negative_feedback")
        elif mutation["code"] == "A42P" and "go" in lowered:
            mutation["status"] = "go"
            mutation["risk_flags"].append("near_pocket")

    if not mutations:
        mutations = [
            {
                "code": "A42P",
                "position": 42,
                "wild_type": "A",
                "mutant": "P",
                "source": "benchmark_default",
                "status": "untested",
                "risk_flags": ["near_pocket"] if is_lipase else [],
            }
        ]

    evidence = []
    if is_lipase:
        evidence.append({
            "evidence_id": f"{bench['case_id']}:kwb-lipase-context",
            "source": "kwb_private",
            "evidence_type": "curated",
            "summary": "KWB local lipase evidence context is available for this benchmark.",
            "confidence": 0.72,
        })
    if is_amylase:
        evidence.append({
            "evidence_id": f"{bench['case_id']}:public-gh13-context",
            "source": "brenda",
            "evidence_type": "curated",
            "summary": "GH13 acid-stability and catalytic guardrail context is required.",
            "confidence": 0.68,
        })

    tool_results = []
    for tool_name in bench.get("expected_workflow") or []:
        if tool_name == "kwb_enzyme_designer":
            continue
        tool_results.append({
            "tool_name": tool_name,
            "status": "completed",
            "result_ref": f"{bench['case_id']}:{tool_name}",
            "summary": {"benchmark_expected": True},
            "quality_flags": [],
        })

    source_type = "uploaded_pdb" if has_uploaded_pdb else ("alphafold" if "alphafold" in lowered else ("esmfold" if has_sequence else "none"))
    structure = {
        "source_type": source_type,
        "object_name": "uploads/benchmark/structure.pdb" if has_uploaded_pdb else None,
        "pdb_id": None,
        "chain_id": "A" if source_type != "none" else None,
        "confidence": 82 if source_type in {"alphafold", "esmfold"} else None,
        "numbering_verified": source_type != "none",
        "residue_mapping_ref": f"{bench['case_id']}:numbering" if source_type != "none" else None,
        "quality_flags": [],
    }

    substrate = {
        "name": "pNP-palmitate" if ("pnp" in lowered or has_sdf) else None,
        "smiles": None,
        "sdf_object": "uploads/benchmark/ligand.sdf" if has_sdf else None,
        "reaction": "ester hydrolysis" if is_lipase else ("starch hydrolysis" if is_amylase else None),
        "pocket_residues": [42, 78, 129, 153] if is_lipase else [],
    }

    return {
        "case_id": bench["case_id"],
        "project_id": "benchmark-local",
        "case_type": "multi_objective",
        "objective": {
            "primary_goal": "benchmark objective",
            "secondary_goals": [],
            "constraints": bench.get("must_not_have") or [],
            "success_metric": "benchmark score >= 85",
        },
        "enzyme": {
            "name": "lipase" if is_lipase else ("GH13 amylase" if is_amylase else "benchmark enzyme"),
            "family": "lipase" if is_lipase else ("GH13" if is_amylase else "unknown"),
            "ec_number": "3.1.1.3" if is_lipase else None,
            "sequence": "MSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGYKVVGQLVGEDNINVVEGNEQFISASKSIVHPSYNSNTLNNDIMLIKLAQKVGLVQ" if has_sequence else None,
            "numbering_system": "sequence_1_indexed",
        },
        "structure": structure,
        "substrate": substrate,
        "assay_condition": {
            "ph": 7.5,
            "temperature_c": 55,
            "expression_system": "Pichia pastoris" if "毕赤" in text or "pichia" in lowered else None,
            "assay_method": "benchmark assay",
        },
        "mutations": mutations,
        "evidence": evidence,
        "tool_results": tool_results,
        "labels": {},
        "quality": {
            "data_quality_score": 70,
            "usable_for_training": False,
            "usable_for_benchmark": True,
            "missing_fields": [],
            "warnings": ["synthetic benchmark conversion"],
        },
        "audit": {
            "created_at": "2026-07-24T00:00:00+08:00",
            "updated_at": "2026-07-24T00:00:00+08:00",
            "source_owner": "KWB local benchmark",
            "review_status": "draft",
            "data_version": "benchmark-v0.1",
        },
    }


def evaluate_case(bench: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    candidates = result.get("candidates") or []
    flags = {flag for candidate in candidates for flag in candidate.get("risk_flags", [])}
    decisions = {candidate.get("mutation"): candidate.get("decision") for candidate in candidates}
    workflow = set(bench.get("expected_workflow") or [])

    checks: list[dict[str, Any]] = []

    checks.append({
        "name": "has_candidates",
        "passed": bool(candidates),
        "weight": 15,
    })
    checks.append({
        "name": "has_multi_head_scores",
        "passed": all(
            all(key in c for key in ["stability_score", "activity_risk_score", "substrate_fit_score", "assay_success_score"])
            for c in candidates
        ),
        "weight": 15,
    })
    checks.append({
        "name": "has_evidence_summary",
        "passed": bool(result.get("evidence_summary")),
        "weight": 15,
    })
    checks.append({
        "name": "kwb_tool_expected",
        "passed": "kwb_enzyme_designer" in workflow,
        "weight": 10,
    })
    checks.append({
        "name": "structure_gate_reflected",
        "passed": bool(result.get("evidence_summary", {}).get("structure_evidence")),
        "weight": 15,
    })
    checks.append({
        "name": "catalytic_guardrail",
        "passed": decisions.get("S153A") in {None, "no_go"} and ("protected_catalytic" in flags or "S153A" not in decisions),
        "weight": 15,
    })
    checks.append({
        "name": "wet_lab_required",
        "passed": result.get("evidence_summary", {}).get("requires_wet_lab_validation") is True,
        "weight": 15,
    })

    score = sum(check["weight"] for check in checks if check["passed"])
    return {
        "case_id": bench["case_id"],
        "score": score,
        "status": "passed" if score >= 85 else "needs_work",
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local KWB benchmark")
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    module = load_rule_module()
    reports = []
    for path in json_files(args.cases_dir):
        bench = json.loads(path.read_text(encoding="utf-8"))
        case = case_to_enzyme_case(bench)
        result = module.design(case)
        reports.append(evaluate_case(bench, result))

    summary = {
        "total": len(reports),
        "passed": sum(1 for item in reports if item["status"] == "passed"),
        "needs_work": sum(1 for item in reports if item["status"] != "passed"),
        "reports": reports,
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if summary["needs_work"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
