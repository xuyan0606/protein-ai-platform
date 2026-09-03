#!/usr/bin/env python3
"""Build a fail-closed benchmark matrix for the five KWB model heads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "benchmark_matrix_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


BENCHMARKS = {
    "mutation_rank": ["ProteinGym", "FLIP/FLIP2-style protein/family/time split", "KWB strict mutation holdout"],
    "stability": ["ThermoMPNN comparison", "ATOM3D MSP", "FireProt/ProTherm reviewed stability set"],
    "activity_risk": [
        "KWB activity numeric feedback smoke",
        "KWB plate-level wet-lab feedback",
        "CatPred/GotEnzymes predicted reference only",
    ],
    "substrate_fit": ["PDBbind/CASF/D3R-style affinity or pose benchmark", "PoseBusters-style pose plausibility", "reviewed substrate identity set"],
    "assay_success": ["KWB plate-level feedback", "replicate consistency", "QC fail-rate calibration"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark matrix report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    heads = multitask.get("heads", {})
    rows = []
    for head, benchmarks in BENCHMARKS.items():
        info = heads.get(head, {})
        rows.append({
            "head": head,
            "label_rows": info.get("rows", 0),
            "minimum_rows": info.get("minimum_rows", 100),
            "training_ready": bool(info.get("ready")),
            "required_benchmarks": benchmarks,
            "benchmark_data_ready": False,
            "scorecard_ready": False,
            "status": "blocked",
            "blockers": [
                "benchmark dataset is not configured locally",
                "head is not training-ready with reviewed labels",
                "external predicted/reference data cannot substitute for wet-lab labels",
            ],
        })
    report = {
        "local_only": True,
        "matrix_artifact_ready": True,
        "ready_for_model_claim": all(row["training_ready"] and row["benchmark_data_ready"] and row["scorecard_ready"] for row in rows),
        "heads": rows,
        "policy": "Smoke tests remain useful, but model claims require head-level benchmark scorecards and leakage-safe splits.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"heads": len(rows), "ready_for_model_claim": report["ready_for_model_claim"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
