#!/usr/bin/env python3
"""Build a local gap report for human target / antibody contract readiness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ROOT.parent
OUT = AI_ROOT / "reports" / "human_target_contract_gap_report.json"
BIO_SPECIALTY_GATE = AI_ROOT / "reports" / "bio_specialty_input_gate_report.json"
SCIENTIFIC_CLAIM_GATE = AI_ROOT / "reports" / "scientific_claim_gate_report.json"


EXPECTED_CONTRACTS = {
    "human_target_intelligence": [
        "HumanProteinProfile",
        "ExpressionSafetyProfile",
        "PathwayRelation",
        "OffTargetRisk",
    ],
    "antibody_humanization": [
        "AntibodyChainProfile",
        "GermlineMatch",
        "HumanizationProposal",
        "DevelopabilityProfile",
    ],
}

IMPLEMENTED_SCHEMA_ONLY = {
    "HumanProteinProfile",
    "ExpressionSafetyProfile",
    "PathwayRelation",
    "AntibodyChainProfile",
    "GermlineMatch",
    "HumanizationProposal",
    "DevelopabilityProfile",
    "EpitopeSimilarity",
    "OffTargetRisk",
    "ExtracellularAccessibility",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def backend_contracts_present() -> dict[str, bool]:
    module_path = REPO_ROOT / "backend" / "app" / "tools" / "human_target_antibody_contracts.py"
    if not module_path.exists():
        return {name: False for name in IMPLEMENTED_SCHEMA_ONLY}
    spec = importlib.util.spec_from_file_location("human_target_antibody_contracts_local", module_path)
    if spec is None or spec.loader is None:
        return {name: False for name in IMPLEMENTED_SCHEMA_ONLY}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    contracts = getattr(module, "CONTRACTS", {})
    return {name: name in contracts for name in sorted(IMPLEMENTED_SCHEMA_ONLY)}


def build_report(created_at: str | None = None) -> dict:
    gate = load_json(BIO_SPECIALTY_GATE)
    claim_gate = load_json(SCIENTIFIC_CLAIM_GATE)
    present = backend_contracts_present()
    human_missing_schema = [
        name for name in EXPECTED_CONTRACTS["human_target_intelligence"] if not present.get(name)
    ]
    antibody_missing_schema = [
        name for name in EXPECTED_CONTRACTS["antibody_humanization"] if not present.get(name)
    ]
    return {
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "product_lines": {
            "human_target_intelligence": {
                "status": (
                    "schema_only_contracts_partial"
                    if human_missing_schema
                    else "schema_only_contracts_present_no_runtime"
                ),
                "schema_only_contracts_present": [
                    name for name in EXPECTED_CONTRACTS["human_target_intelligence"] if present.get(name)
                ],
                "missing_schema_contracts": human_missing_schema,
                "missing_runtime_or_source_contracts": [
                    "HPA/GTEx expression source manifest",
                    "Reactome/GO pathway source manifest",
                    "ligand-receptor evidence graph",
                    "OffTargetRisk execution contract",
                ],
            },
            "antibody_humanization": {
                "status": (
                    "schema_only_contracts_partial"
                    if antibody_missing_schema
                    else "schema_only_contracts_present_no_runtime"
                ),
                "schema_only_contracts_present": [
                    name for name in EXPECTED_CONTRACTS["antibody_humanization"] if present.get(name)
                ],
                "missing_schema_contracts": antibody_missing_schema,
                "missing_runtime_or_source_contracts": [
                    "ANARCI/IMGT runtime receipt",
                    "human germline database manifest",
                    "numbered VH/VL residue mapping artifact",
                    "humanization proposal validation report",
                ],
            },
        },
        "backend_schema_contracts": present,
        "gate_snapshot": {
            "bio_specialty_input_gate_present": bool(gate),
            "scientific_claim_gate_present": bool(claim_gate),
            "bio_specialty_ready": gate.get("status") if gate else None,
            "scientific_claim_gate_status": claim_gate.get("status") if claim_gate else None,
        },
        "policy": "Schema-only contracts may be present, but this report does not imply real source retrieval, target intelligence, antibody numbering, humanization, model claim, or release readiness.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human target / antibody contract gap report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    contract_gap = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract_gap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
