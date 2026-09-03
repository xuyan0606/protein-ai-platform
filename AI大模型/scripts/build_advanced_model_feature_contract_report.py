#!/usr/bin/env python3
"""Build the advanced model feature-index consumption contract report."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURE_INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
ADVANCED_MODEL = AI_ROOT / "prototype" / "kwb_enzyme_designer_advanced_model.py"
OUT = AI_ROOT / "reports" / "advanced_model_feature_contract_report.json"
EXPECTED_HEADS = {"mutation_rank", "stability", "activity_safety", "substrate_fit", "assay_success"}
BASE_FEATURE_FAMILY_COUNTS = {"msa_conservation": 158, "structure_graph": 34}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line_number"] = line_number
        rows.append(row)
    return rows


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: str | Path) -> str:
    p = Path(path)
    return str(p.relative_to(AI_ROOT)) if p.is_absolute() else str(p)


def load_advanced_module():
    spec = importlib.util.spec_from_file_location("kwb_advanced_model_feature_contract", ADVANCED_MODEL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load advanced model from {ADVANCED_MODEL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_model_input_only(row: dict[str, Any]) -> bool:
    return (
        row.get("model_consumable") is True
        and row.get("training_label_source") is False
        and row.get("safe_for_training_import") is False
        and row.get("safe_for_model_claim") is False
        and row.get("release_ready") is False
    )


def is_ready_feature_ref(row: dict[str, Any]) -> bool:
    return is_model_input_only(row) and row.get("validator_ready") is True


def feature_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "feature_index_id": row.get("feature_index_id"),
        "feature_family": row.get("feature_family"),
        "feature_path": row.get("feature_path"),
        "validator_report": row.get("validator_report"),
        "model_consumable": row.get("model_consumable"),
        "training_label_source": row.get("training_label_source"),
        "safe_for_training_import": row.get("safe_for_training_import"),
        "safe_for_model_claim": row.get("safe_for_model_claim"),
        "release_ready": row.get("release_ready"),
        "feature_group_id": row.get("feature_group_id"),
        "group_execution_policy": row.get("group_execution_policy"),
        "independent_training_sample": row.get("independent_training_sample"),
    }


def family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("feature_family") or "unknown")
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def physical_ddg_group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    physical_rows = [row for row in rows if row.get("feature_family") == "pyrosetta_ddg_reu_input"]
    group_ids = {row.get("feature_group_id") for row in physical_rows if row.get("feature_group_id")}
    return {
        "feature_rows": len(physical_rows),
        "unique_mutation_groups": len(group_ids),
        "independent_training_sample_rows": sum(
            1 for row in physical_rows if row.get("independent_training_sample") is True
        ),
        "policy": "Multi-chain contexts stay grouped and are never counted as independent training samples.",
    }


def no_label_no_adapter_case() -> dict[str, Any]:
    return {
        "case_id": "advanced_feature_contract_no_label_no_adapter_fixture",
        "enzyme": {"sequence": "M" + "A" * 80},
        "structure": {"source_type": "none", "numbering_verified": False, "confidence": None},
        "substrate": {},
        "evidence": [],
        "tool_results": [],
        "mutations": [{"code": "A20P", "status": "unknown", "risk_flags": []}],
    }


def scaffold_contract() -> dict[str, Any]:
    module = load_advanced_module()
    result = module.predict(no_label_no_adapter_case())
    candidates = result.get("candidates") or []
    observed_heads = set()
    if candidates:
        observed_heads = set((candidates[0].get("heads") or {}).keys())
    evidence_summary = result.get("evidence_summary") or {}
    missing_modalities = sorted(evidence_summary.get("missing_modalities") or [])
    ready_modalities = sorted(evidence_summary.get("ready_modalities") or [])
    five_head_complete = observed_heads == EXPECTED_HEADS
    fail_closed_without_real_label_or_adapter = (
        result.get("status") == "scaffold_only_fail_closed"
        and evidence_summary.get("requires_wet_lab_validation") is True
        and "wet_lab_feedback" in missing_modalities
        and "ddg_backend" in missing_modalities
        and "msa_conservation" in missing_modalities
    )
    return {
        "prototype": rel(ADVANCED_MODEL),
        "prototype_sha256": sha256(ADVANCED_MODEL),
        "model": result.get("model"),
        "status": result.get("status"),
        "expected_heads": sorted(EXPECTED_HEADS),
        "observed_heads": sorted(observed_heads),
        "five_head_scaffold_complete": five_head_complete,
        "no_label_no_adapter_fixture": {
            "candidate_rows": len(candidates),
            "ready_modalities": ready_modalities,
            "missing_modalities": missing_modalities,
            "requires_wet_lab_validation": evidence_summary.get("requires_wet_lab_validation"),
            "true_label_present": False,
            "trained_adapter_present": False,
            "model_claim_allowed": False,
        },
        "fail_closed_without_real_label_or_adapter": fail_closed_without_real_label_or_adapter,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build advanced model feature contract report")
    parser.add_argument("--feature-index", type=Path, default=FEATURE_INDEX)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    rows = load_jsonl(args.feature_index)
    ready_rows = [row for row in rows if is_ready_feature_ref(row)]
    model_input_only_rows = [row for row in rows if is_model_input_only(row)]
    training_label_source_rows = [row for row in rows if row.get("training_label_source") is True]
    non_consumable_rows = [row for row in rows if row.get("model_consumable") is not True]
    blocked_rows = [row for row in rows if not is_ready_feature_ref(row)]
    scaffold = scaffold_contract()
    counts = family_counts(rows)
    base_features_intact = all(counts.get(family) == expected for family, expected in BASE_FEATURE_FAMILY_COUNTS.items())

    report = {
        "created_at": created_at,
        "local_only": True,
        "success": (
            base_features_intact
            and len(rows) == len(ready_rows)
            and len(rows) == len(model_input_only_rows)
            and not training_label_source_rows
            and not non_consumable_rows
            and scaffold["five_head_scaffold_complete"]
            and scaffold["fail_closed_without_real_label_or_adapter"]
        ),
        "feature_index_contract": {
            "index": rel(args.feature_index),
            "index_sha256": sha256(args.feature_index),
            "feature_ref_count": len(rows),
            "advanced_model_ready_feature_ref_count": len(ready_rows),
            "model_input_only_feature_ref_count": len(model_input_only_rows),
            "training_label_source_feature_ref_count": len(training_label_source_rows),
            "non_model_consumable_feature_ref_count": len(non_consumable_rows),
            "blocked_feature_ref_count": len(blocked_rows),
            "base_feature_family_counts": BASE_FEATURE_FAMILY_COUNTS,
            "base_feature_refs_intact": base_features_intact,
            "optional_physical_ddg_feature_ref_count": counts.get("pyrosetta_ddg_reu_input", 0),
            "optional_physical_ddg_group_summary": physical_ddg_group_summary(rows),
            "family_counts": family_counts(rows),
            "ready_family_counts": family_counts(ready_rows),
            "ready_feature_refs": [feature_ref(row) for row in ready_rows],
            "blocked_feature_refs": [feature_ref(row) for row in blocked_rows],
        },
        "advanced_model_contract": scaffold,
        "negative_protection_contract": {
            "ready_refs_must_be_model_consumable": True,
            "ready_refs_must_not_be_training_label_source": True,
            "ready_refs_must_not_authorize_training_import": True,
            "ready_refs_must_not_authorize_model_claim": True,
        },
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validated feature-index refs are admitted only as advanced model inputs. "
            "They are not training labels, do not authorize training import, do not prove "
            "model quality, and do not lift the advanced scaffold fail-closed claim gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "feature_refs": len(rows),
        "ready_feature_refs": len(ready_rows),
        "training_label_source_refs": len(training_label_source_rows),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
