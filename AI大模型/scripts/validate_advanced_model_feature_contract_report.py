#!/usr/bin/env python3
"""Validate the advanced model feature-index consumption contract report."""

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
REPORT = AI_ROOT / "reports" / "advanced_model_feature_contract_report.json"
OUT = AI_ROOT / "reports" / "advanced_model_feature_contract_validation_report.json"
EXPECTED_HEADS = {"mutation_rank", "stability", "activity_safety", "substrate_fit", "assay_success"}
BASE_FEATURE_FAMILY_COUNTS = {"msa_conservation": 158, "structure_graph": 34}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def load_advanced_module():
    spec = importlib.util.spec_from_file_location("kwb_advanced_model_feature_contract_validation", ADVANCED_MODEL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load advanced model from {ADVANCED_MODEL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


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


def ready_feature_ids(report: dict[str, Any]) -> list[str]:
    refs = ((report.get("feature_index_contract") or {}).get("ready_feature_refs") or [])
    ids: list[str] = []
    for ref in refs:
        if isinstance(ref, dict):
            ids.append(str(ref.get("feature_index_id") or ""))
        else:
            ids.append(str(ref or ""))
    return ids


def family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("feature_family") or "unknown")
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


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


def validate_scaffold(report: dict[str, Any], failures: list[dict[str, Any]]) -> dict[str, Any]:
    module = load_advanced_module()
    result = module.predict(no_label_no_adapter_case())
    candidates = result.get("candidates") or []
    observed_heads = set()
    if candidates:
        observed_heads = set((candidates[0].get("heads") or {}).keys())
    evidence_summary = result.get("evidence_summary") or {}
    missing_modalities = set(evidence_summary.get("missing_modalities") or [])
    contract = report.get("advanced_model_contract") or {}
    fixture = contract.get("no_label_no_adapter_fixture") or {}

    fail_if(result.get("status") != "scaffold_only_fail_closed", failures, "scaffold_status_fail_closed", result.get("status"), "scaffold_only_fail_closed")
    fail_if(observed_heads != EXPECTED_HEADS, failures, "five_head_scaffold_complete", sorted(observed_heads), sorted(EXPECTED_HEADS))
    fail_if(evidence_summary.get("requires_wet_lab_validation") is not True, failures, "requires_wet_lab_validation_true", evidence_summary.get("requires_wet_lab_validation"), True)
    fail_if(not {"wet_lab_feedback", "ddg_backend", "msa_conservation"}.issubset(missing_modalities), failures, "missing_label_adapter_modalities_block_claim", sorted(missing_modalities), "wet_lab_feedback, ddg_backend, msa_conservation missing")
    fail_if(contract.get("fail_closed_without_real_label_or_adapter") is not True, failures, "report_fail_closed_without_real_label_or_adapter", contract.get("fail_closed_without_real_label_or_adapter"), True)
    fail_if(fixture.get("model_claim_allowed") is not False, failures, "no_label_adapter_model_claim_blocked", fixture.get("model_claim_allowed"), False)
    fail_if(fixture.get("true_label_present") is not False, failures, "fixture_true_label_absent", fixture.get("true_label_present"), False)
    fail_if(fixture.get("trained_adapter_present") is not False, failures, "fixture_trained_adapter_absent", fixture.get("trained_adapter_present"), False)
    return {
        "status": result.get("status"),
        "candidate_rows": len(candidates),
        "observed_heads": sorted(observed_heads),
        "missing_modalities": sorted(missing_modalities),
        "requires_wet_lab_validation": evidence_summary.get("requires_wet_lab_validation"),
    }


def validate_feature_contract(rows: list[dict[str, Any]], report: dict[str, Any], failures: list[dict[str, Any]]) -> dict[str, Any]:
    contract = report.get("feature_index_contract") or {}
    ids = [str(row.get("feature_index_id") or "") for row in rows]
    row_by_id = {str(row.get("feature_index_id") or ""): row for row in rows}
    ready_ids = ready_feature_ids(report)
    ready_id_set = set(ready_ids)
    eligible_ids = {str(row.get("feature_index_id") or "") for row in rows if is_ready_feature_ref(row)}
    training_label_source_ids = {str(row.get("feature_index_id") or "") for row in rows if row.get("training_label_source") is True}
    non_consumable_ids = {str(row.get("feature_index_id") or "") for row in rows if row.get("model_consumable") is not True}
    model_input_only_ids = {str(row.get("feature_index_id") or "") for row in rows if is_model_input_only(row)}

    fail_if(len(ids) != len(set(ids)), failures, "feature_index_ids_unique", len(ids), len(set(ids)))
    fail_if(contract.get("index_sha256") != sha256(FEATURE_INDEX), failures, "feature_index_sha256_current", contract.get("index_sha256"), sha256(FEATURE_INDEX))
    fail_if(contract.get("feature_ref_count") != len(rows), failures, "feature_ref_count_matches_index", contract.get("feature_ref_count"), len(rows))
    fail_if(contract.get("advanced_model_ready_feature_ref_count") != len(ready_ids), failures, "ready_feature_ref_count_matches_list", contract.get("advanced_model_ready_feature_ref_count"), len(ready_ids))
    fail_if(contract.get("model_input_only_feature_ref_count") != len(model_input_only_ids), failures, "model_input_only_count_matches_index", contract.get("model_input_only_feature_ref_count"), len(model_input_only_ids))
    fail_if(contract.get("training_label_source_feature_ref_count") != len(training_label_source_ids), failures, "training_label_source_count_matches_index", contract.get("training_label_source_feature_ref_count"), len(training_label_source_ids))
    fail_if(contract.get("non_model_consumable_feature_ref_count") != len(non_consumable_ids), failures, "non_consumable_count_matches_index", contract.get("non_model_consumable_feature_ref_count"), len(non_consumable_ids))
    fail_if(set(ready_ids) != eligible_ids, failures, "ready_refs_equal_recomputed_eligible_refs", {"missing_from_report": sorted(eligible_ids - ready_id_set)[:20], "extra_in_report": sorted(ready_id_set - eligible_ids)[:20]}, "exact recomputed eligible set")

    for ref_id in sorted(ready_id_set):
        row = row_by_id.get(ref_id)
        if row is None:
            failures.append({"check": "ready_ref_exists_in_index", "observed": ref_id, "expected": "feature_index_id in index"})
            continue
        fail_if(row.get("model_consumable") is not True, failures, "negative_guard_ready_ref_model_consumable_true", {"feature_index_id": ref_id, "model_consumable": row.get("model_consumable")}, True)
        fail_if(row.get("training_label_source") is not False, failures, "negative_guard_ready_ref_not_training_label_source", {"feature_index_id": ref_id, "training_label_source": row.get("training_label_source")}, False)
        fail_if(row.get("safe_for_training_import") is not False, failures, "ready_ref_not_training_import", {"feature_index_id": ref_id, "safe_for_training_import": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "ready_ref_not_model_claim", {"feature_index_id": ref_id, "safe_for_model_claim": row.get("safe_for_model_claim")}, False)

    fail_if(bool(training_label_source_ids & ready_id_set), failures, "negative_guard_training_label_source_not_counted_ready", sorted(training_label_source_ids & ready_id_set), [])
    fail_if(bool(non_consumable_ids & ready_id_set), failures, "negative_guard_non_consumable_not_counted_ready", sorted(non_consumable_ids & ready_id_set), [])
    counts = family_counts(rows)
    for family, expected in BASE_FEATURE_FAMILY_COUNTS.items():
        fail_if(
            counts.get(family) != expected,
            failures,
            f"base_feature_family_count_{family}",
            counts.get(family),
            expected,
        )
    fail_if(
        contract.get("base_feature_refs_intact") is not True,
        failures,
        "base_feature_refs_intact",
        contract.get("base_feature_refs_intact"),
        True,
    )
    fail_if(
        contract.get("optional_physical_ddg_feature_ref_count") != counts.get("pyrosetta_ddg_reu_input", 0),
        failures,
        "optional_physical_ddg_feature_count_matches_index",
        contract.get("optional_physical_ddg_feature_ref_count"),
        counts.get("pyrosetta_ddg_reu_input", 0),
    )
    physical_rows = [row for row in rows if row.get("feature_family") == "pyrosetta_ddg_reu_input"]
    physical_summary = contract.get("optional_physical_ddg_group_summary") or {}
    physical_groups = {row.get("feature_group_id") for row in physical_rows if row.get("feature_group_id")}
    fail_if(
        physical_summary.get("feature_rows") != len(physical_rows),
        failures,
        "physical_ddg_feature_rows_match_index",
        physical_summary.get("feature_rows"),
        len(physical_rows),
    )
    fail_if(
        physical_summary.get("unique_mutation_groups") != len(physical_groups),
        failures,
        "physical_ddg_unique_mutation_groups_match_index",
        physical_summary.get("unique_mutation_groups"),
        len(physical_groups),
    )
    fail_if(
        any(row.get("independent_training_sample") is not False for row in physical_rows),
        failures,
        "physical_ddg_not_independent_training_samples",
        [row.get("feature_index_id") for row in physical_rows if row.get("independent_training_sample") is not False],
        [],
    )
    fail_if(len(rows) != len(ready_ids), failures, "all_feature_refs_ready", len(ready_ids), len(rows))
    fail_if(len(rows) != len(model_input_only_ids), failures, "all_feature_refs_model_input_only", len(model_input_only_ids), len(rows))
    fail_if(len(training_label_source_ids) != 0, failures, "training_label_source_feature_ref_count_zero", len(training_label_source_ids), 0)

    return {
        "feature_refs": len(rows),
        "ready_feature_refs": len(ready_ids),
        "model_input_only_feature_refs": len(model_input_only_ids),
        "training_label_source_feature_refs": len(training_label_source_ids),
        "non_model_consumable_feature_refs": len(non_consumable_ids),
        "family_counts": family_counts(rows),
        "ready_family_counts": family_counts([row_by_id[ref_id] for ref_id in ready_ids if ref_id in row_by_id]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate advanced model feature contract report")
    parser.add_argument("--feature-index", type=Path, default=FEATURE_INDEX)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.feature_index)
    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    feature_summary = validate_feature_contract(rows, report, failures)
    scaffold_summary = validate_scaffold(report, failures)

    fail_if(report.get("success") is not True, failures, "source_report_success_true", report.get("success"), True)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "feature_contract": feature_summary,
        "advanced_model_scaffold": scaffold_summary,
        "negative_protection_checks": {
            "training_label_source_true_ready_refs_fail_validation": True,
            "model_consumable_false_ready_refs_fail_validation": True,
        },
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Advanced model feature contract validation proves feature refs are model-input-only. "
            "Any training-label source or non-consumable feature counted as ready fails validation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "feature_refs": feature_summary["feature_refs"],
        "ready_feature_refs": feature_summary["ready_feature_refs"],
        "training_label_source_refs": feature_summary["training_label_source_feature_refs"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
