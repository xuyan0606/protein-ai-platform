#!/usr/bin/env python3
"""Build the P62 advanced model architecture report and demo output."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ADVANCED_MODEL = AI_ROOT / "prototype" / "kwb_enzyme_designer_advanced_model.py"
SAMPLE_CASE = AI_ROOT / "datasets" / "sample_case.json"
REPORT_OUT = AI_ROOT / "reports" / "advanced_model_architecture_report.json"
DEMO_OUT = AI_ROOT / "reports" / "advanced_model_demo.json"


def load_advanced_module():
    spec = importlib.util.spec_from_file_location("kwb_enzyme_designer_advanced_model", ADVANCED_MODEL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load advanced model from {ADVANCED_MODEL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Build advanced model architecture report")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--demo-output", type=Path, default=DEMO_OUT)
    args = parser.parse_args()

    module = load_advanced_module()
    case = json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))
    demo = module.predict(case)
    args.demo_output.parent.mkdir(parents=True, exist_ok=True)
    args.demo_output.write_text(json.dumps(demo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "model": "KWB-EnzymeDesigner",
        "version": "2.2.0-advanced-scaffold",
        "status": "scaffold_only_fail_closed",
        "architecture_layers": [
            "sequence PLM embedding slot",
            "MSA/conservation feature slot",
            "structure-neighborhood GNN slot",
            "ddG backend feature slot",
            "wet-lab feedback calibration slot",
            "five-head multi-task prediction",
            "Pareto ranking and uncertainty calibration",
        ],
        "heads": [
            "mutation_rank",
            "stability",
            "activity_safety",
            "substrate_fit",
            "assay_success",
        ],
        "advanced_capability_targets": {
            "plm_backends": ["ESM2/ESM C", "SaProt"],
            "structure_backends": ["structure GNN", "SaProt structure-aware tokenization"],
            "ddg_backends": ["ThermoMPNN", "Rosetta/PyRosetta", "FoldX"],
            "ranking": ["Pareto front", "pairwise/listwise ranking later when labels are ready"],
            "uncertainty": ["missing modality flags", "OOD flags", "future calibration on wet-lab feedback"],
        },
        "demo_output": str(args.demo_output.relative_to(AI_ROOT)),
        "demo_candidate_count": len(demo.get("candidates") or []),
        "demo_status": demo.get("status"),
        "ready_modalities": (demo.get("evidence_summary") or {}).get("ready_modalities", []),
        "missing_modalities": (demo.get("evidence_summary") or {}).get("missing_modalities", []),
        "safe_for_model_claim": False,
        "blocked_until": [
            "reviewed numbering decisions raise strict rows to threshold",
            "MSA/conservation runtime or trusted cache is ready",
            "real experiment feedback is imported and validated",
            "ddG backend or approved stability baseline produces auditable artifacts",
            "benchmark and claim readiness pass",
        ],
        "policy": (
            "This report upgrades code architecture only. It does not introduce "
            "trained neural weights, external dependency execution, fabricated MSA, "
            "or model-quality claims."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "demo_candidate_count": report["demo_candidate_count"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
