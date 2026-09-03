#!/usr/bin/env python3
"""Regression checks for the advanced model scaffold and feature adapter."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ADVANCED_MODEL = AI_ROOT / "prototype" / "kwb_enzyme_designer_advanced_model.py"
ADAPTER = AI_ROOT / "platform_integration" / "advanced_feature_adapter_scaffold.py"
OUT = AI_ROOT / "reports" / "advanced_model_scaffold_regression_report.json"

EXPECTED_HEADS = {"mutation_rank", "stability", "activity_safety", "substrate_fit", "assay_success"}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def sample_case() -> dict[str, Any]:
    sequence = "M" + "A" * 99 + "D" + "A" * 99
    return {
        "case_id": "advanced_scaffold_regression_case",
        "enzyme": {"sequence": sequence},
        "structure": {"source_type": "pdb", "numbering_verified": True, "confidence": 0.9},
        "substrate": {"name": "test_substrate"},
        "evidence": [{"source": "kwb_private", "description": "regression fixture only"}],
        "tool_results": [
            {
                "tool_name": "msa_conservation",
                "status": "completed",
                "summary": {
                    "conservation_score": 3.0,
                    "alignment_depth": 128,
                    "source_database": "fixture",
                },
            },
            {
                "tool_name": "thermompnn",
                "status": "completed",
                "summary": {"mutations": {"A20P": -1.4, "D101N": 0.2}},
            },
        ],
        "mutations": [
            {"code": "A20P", "status": "go", "risk_flags": []},
            {"code": "D101N", "status": "watch", "risk_flags": ["protected_catalytic"]},
        ],
    }


def validate_model_scaffold(failures: list[dict[str, Any]]) -> dict[str, Any]:
    module = load_module(ADVANCED_MODEL, "kwb_enzyme_designer_advanced_model_regression")
    result = module.predict(sample_case())
    candidates = result.get("candidates") or []
    fail_if(result.get("status") != "scaffold_only_fail_closed", failures, "result_status_fail_closed", result.get("status"), "scaffold_only_fail_closed")
    fail_if((result.get("evidence_summary") or {}).get("requires_wet_lab_validation") is not True, failures, "requires_wet_lab_validation_true", (result.get("evidence_summary") or {}).get("requires_wet_lab_validation"), True)
    fail_if(len(candidates) != 2, failures, "candidate_count_two", len(candidates), 2)
    for row in candidates:
        heads = row.get("heads") or {}
        fail_if(set(heads) != EXPECTED_HEADS, failures, "candidate_heads_complete", {"mutation": row.get("mutation"), "heads": sorted(heads)}, sorted(EXPECTED_HEADS))
        for key, value in heads.items():
            fail_if(not isinstance(value, (int, float)) or not 0 <= float(value) <= 100, failures, "head_score_range", {"mutation": row.get("mutation"), "head": key, "value": value}, "0..100")
    protected = next((row for row in candidates if row.get("mutation") == "D101N"), {})
    fail_if(protected.get("decision") != "no_go", failures, "protected_catalytic_no_go", protected.get("decision"), "no_go")
    fail_if("protected_catalytic" not in set(protected.get("risk_flags") or []), failures, "protected_catalytic_flag_present", protected.get("risk_flags"), "protected_catalytic")
    return result


def validate_adapter_scaffold(failures: list[dict[str, Any]]) -> dict[str, Any]:
    module = load_module(ADAPTER, "advanced_feature_adapter_scaffold_regression")
    blocked_context = module.AdapterContext(
        adapter_id="regression_adapter",
        feature_family="regression_family",
        cache_root=AI_ROOT / "cache" / "advanced_features" / "regression",
    )
    blocked_adapter = module.BaseAdvancedFeatureAdapter(blocked_context)
    envelope_a = blocked_adapter.run({"case_id": "case_a", "sequence": "AAA"})
    envelope_b = blocked_adapter.run({"case_id": "case_a", "sequence": "AAA"})
    fail_if(envelope_a.get("status") != "blocked", failures, "adapter_blocked_status", envelope_a.get("status"), "blocked")
    fail_if(envelope_a.get("reason") != "adapter_not_ready", failures, "adapter_blocked_reason", envelope_a.get("reason"), "adapter_not_ready")
    fail_if(envelope_a.get("local_only") is not True, failures, "adapter_blocked_local_only", envelope_a.get("local_only"), True)
    fail_if(envelope_a.get("input_hash") != envelope_b.get("input_hash"), failures, "adapter_input_hash_stable", envelope_a.get("input_hash"), envelope_b.get("input_hash"))
    ready_context = module.AdapterContext(
        adapter_id="ready_regression_adapter",
        feature_family="regression_family",
        cache_root=AI_ROOT / "cache" / "advanced_features" / "regression",
        license_ready=True,
        runtime_ready=True,
        data_ready=True,
        model_weight_ready=True,
    )
    ready_adapter = module.BaseAdvancedFeatureAdapter(ready_context)
    try:
        ready_adapter.run({"case_id": "case_ready"})
    except NotImplementedError:
        ready_base_raises = True
    else:
        ready_base_raises = False
    fail_if(ready_base_raises is not True, failures, "ready_base_adapter_raises_not_implemented", ready_base_raises, True)
    return envelope_a


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate advanced model scaffold regression")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    model_result = validate_model_scaffold(failures)
    adapter_envelope = validate_adapter_scaffold(failures)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "model_version": (model_result.get("model") or {}).get("version"),
        "architecture": (model_result.get("model") or {}).get("architecture"),
        "status": model_result.get("status"),
        "candidate_rows": len(model_result.get("candidates") or []),
        "expected_heads": sorted(EXPECTED_HEADS),
        "adapter_blocked_status": adapter_envelope.get("status"),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Scaffold regression validates interface and fail-closed behavior only. It does not validate model performance, import labels, approve model claims, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "candidate_rows": report["candidate_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
