#!/usr/bin/env python3
"""Validate the Stage 25 FoldX provision manifest candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = AI_ROOT / "datasets" / "governance" / "stage25_foldx_provision_manifest_candidate_20260806.jsonl"
ACTIVE_MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_foldx_provision_manifest_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_provision_manifest_candidate_validation_20260806.json"
TECHNICAL_SMOKE_PREFIX = "cache/advanced_features/ddg_physical_smoke/foldx/stage25_technical_smoke_20260806/"
TECHNICAL_SMOKE_REPORT = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_20260806.json"
TECHNICAL_SMOKE_VALIDATION = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_validation_20260806.json"
TECHNICAL_SMOKE_DIR = "cache/advanced_features/ddg_physical_smoke/foldx/stage25_technical_smoke_20260806"

EXPECTED_IDS = {
    "stage25_foldx_executable",
    "stage25_foldx_parameters",
    "stage25_foldx_input_structure_sha256",
    "stage25_foldx_mutation_list",
    "stage25_foldx_ddg_table",
    "stage25_foldx_runtime_log",
}
TECHNICAL_COUNTERPARTS = {
    "stage25_foldx_parameters": f"{TECHNICAL_SMOKE_DIR}/parameters.json",
    "stage25_foldx_input_structure_sha256": f"{TECHNICAL_SMOKE_DIR}/input_structure.sha256",
    "stage25_foldx_mutation_list": f"{TECHNICAL_SMOKE_DIR}/mutation_list.json",
    "stage25_foldx_ddg_table": f"{TECHNICAL_SMOKE_DIR}/ddg_table.json",
    "stage25_foldx_runtime_log": f"{TECHNICAL_SMOKE_DIR}/runtime.log",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not CANDIDATE.exists(), failures, "candidate_exists", "missing", str(CANDIDATE))
    fail_if(not ACTIVE_MANIFEST.exists(), failures, "active_manifest_exists", "missing", str(ACTIVE_MANIFEST))
    fail_if(not TECHNICAL_SMOKE_VALIDATION.exists(), failures, "technical_smoke_validation_exists", "missing", str(TECHNICAL_SMOKE_VALIDATION))
    rows = load_jsonl(CANDIDATE) if CANDIDATE.exists() else []
    active_rows = load_jsonl(ACTIVE_MANIFEST) if ACTIVE_MANIFEST.exists() else []
    technical_smoke_report = load_json(TECHNICAL_SMOKE_REPORT)
    technical_validation = load_json(TECHNICAL_SMOKE_VALIDATION)
    ids = {str(row.get("provision_id")) for row in rows}
    active_ids = {str(row.get("provision_id")) for row in active_rows}
    fail_if(ids != EXPECTED_IDS, failures, "candidate_ids", sorted(ids), sorted(EXPECTED_IDS))
    fail_if(active_ids != EXPECTED_IDS, failures, "active_ids_unchanged_shape", sorted(active_ids), sorted(EXPECTED_IDS))
    fail_if(technical_validation.get("success") is not True, failures, "technical_smoke_validation_success", technical_validation.get("success"), True)
    fail_if(technical_validation.get("technical_smoke_only") is not True, failures, "technical_smoke_only", technical_validation.get("technical_smoke_only"), True)
    fail_if(technical_validation.get("artifact_count") != 5, failures, "technical_smoke_artifact_count", technical_validation.get("artifact_count"), 5)

    formal_paths = {str(row.get("expected_local_path") or "") for row in rows}
    technical_paths = {
        f"{TECHNICAL_SMOKE_PREFIX}{name}"
        for name in ("parameters.json", "input_structure.sha256", "mutation_list.json", "ddg_table.json", "runtime.log")
    }
    path_overlap = sorted(formal_paths & technical_paths)
    fail_if(bool(path_overlap), failures, "technical_formal_path_overlap_empty", path_overlap, [])

    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("required") is not True, failures, f"{prefix}.required_true", row.get("required"), True)
        fail_if(row.get("status") not in {"present", "missing"}, failures, f"{prefix}.status_known", row.get("status"), ["missing", "present"])
        fail_if(row.get("present") is not (row.get("status") == "present"), failures, f"{prefix}.present_matches_status", row.get("present"), row.get("status") == "present")
        fail_if(row.get("evidence_class") != "formal_runtime_provision", failures, f"{prefix}.evidence_class", row.get("evidence_class"), "formal_runtime_provision")
        expected_technical_path = TECHNICAL_COUNTERPARTS.get(str(row.get("provision_id")))
        fail_if(row.get("technical_smoke_counterpart_path") != expected_technical_path, failures, f"{prefix}.technical_counterpart_path", row.get("technical_smoke_counterpart_path"), expected_technical_path)
        if expected_technical_path:
            technical_path = AI_ROOT / expected_technical_path
            expected_sha256 = sha256(technical_path) if technical_path.is_file() else None
            receipted_sha256 = (technical_smoke_report.get("artifact_sha256") or {}).get(expected_technical_path)
            fail_if(row.get("technical_smoke_counterpart_present") is not True, failures, f"{prefix}.technical_counterpart_present", row.get("technical_smoke_counterpart_present"), True)
            fail_if(row.get("technical_smoke_counterpart_sha256") != expected_sha256, failures, f"{prefix}.technical_counterpart_sha256", row.get("technical_smoke_counterpart_sha256"), expected_sha256)
            fail_if(row.get("technical_smoke_counterpart_checksum_matches_receipt") is not True, failures, f"{prefix}.technical_counterpart_checksum_matches", row.get("technical_smoke_counterpart_checksum_matches_receipt"), True)
            fail_if(expected_sha256 != receipted_sha256, failures, f"{prefix}.technical_receipt_checksum_parity", expected_sha256, receipted_sha256)
        else:
            fail_if(row.get("technical_smoke_counterpart_present") is not False, failures, f"{prefix}.technical_counterpart_present_false", row.get("technical_smoke_counterpart_present"), False)
            fail_if(row.get("technical_smoke_counterpart_sha256") is not None, failures, f"{prefix}.technical_counterpart_sha256_none", row.get("technical_smoke_counterpart_sha256"), None)
            fail_if(row.get("technical_smoke_counterpart_checksum_matches_receipt") is not False, failures, f"{prefix}.technical_counterpart_checksum_false", row.get("technical_smoke_counterpart_checksum_matches_receipt"), False)
        fail_if(row.get("technical_smoke_validation_success") is not True, failures, f"{prefix}.technical_smoke_validation_success", row.get("technical_smoke_validation_success"), True)
        fail_if(row.get("technical_smoke_can_satisfy_formal_requirement") is not False, failures, f"{prefix}.technical_smoke_cannot_satisfy_formal", row.get("technical_smoke_can_satisfy_formal_requirement"), False)
        for flag in ("ready_for_runtime_receipt", "formal_runtime_receipt_written", "completion_ready", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(not isinstance(row.get("missing_reason"), dict), failures, f"{prefix}.missing_reason_object", type(row.get("missing_reason")).__name__, "object")
        reason = row.get("missing_reason") if isinstance(row.get("missing_reason"), dict) else {}
        candidate_rows = reason.get("foldx_candidate_rows")
        fail_if(
            not isinstance(candidate_rows, int) or isinstance(candidate_rows, bool) or candidate_rows < 0,
            failures,
            f"{prefix}.foldx_candidate_rows_nonnegative_integer",
            candidate_rows,
            ">=0 integer",
        )
        fail_if(not reason.get("bootstrap_blockers"), failures, f"{prefix}.bootstrap_blockers_present", reason.get("bootstrap_blockers"), "non-empty")
        policy = str(row.get("policy") or "")
        for term in ("Formal provision candidate only", "technical-smoke counterparts", "cannot satisfy", "formal runtime receipt"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains.{term}", policy, f"contains {term}")

    present_rows = sum(1 for row in rows if row.get("status") == "present")
    executable_rows = [row for row in rows if row.get("provision_id") == "stage25_foldx_executable"]
    fail_if(not executable_rows or executable_rows[0].get("status") != "present", failures, "foldx_executable_present", executable_rows[0].get("status") if executable_rows else "missing", "present")
    for row in rows:
        if row.get("status") == "present":
            fail_if(not isinstance(row.get("sha256"), str) or len(row.get("sha256")) != 64, failures, f"{row.get('provision_id')}.sha256_present", row.get("sha256"), "64-char sha256")

    formal_smoke_rows = [row for row in rows if row.get("artifact_kind") == "physical_smoke_artifact"]
    technical_smoke_artifact_rows = sum(1 for row in formal_smoke_rows if row.get("technical_smoke_counterpart_present") is True)
    technical_smoke_checksum_verified_rows = sum(1 for row in formal_smoke_rows if row.get("technical_smoke_counterpart_checksum_matches_receipt") is True)
    formal_smoke_artifact_present_rows = sum(1 for row in formal_smoke_rows if row.get("present") is True)
    fail_if(technical_validation.get("success") is not True, failures, "technical_smoke_validation_success", technical_validation.get("success"), True)
    fail_if(technical_validation.get("technical_smoke_only") is not True, failures, "technical_smoke_only", technical_validation.get("technical_smoke_only"), True)
    fail_if(technical_smoke_artifact_rows != 5, failures, "technical_smoke_artifact_rows", technical_smoke_artifact_rows, 5)
    fail_if(technical_smoke_checksum_verified_rows != 5, failures, "technical_smoke_checksum_verified_rows", technical_smoke_checksum_verified_rows, 5)
    fail_if(formal_smoke_artifact_present_rows != 0, failures, "formal_smoke_artifact_present_rows_zero", formal_smoke_artifact_present_rows, 0)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_provision_manifest_candidate_validation",
        "stage": 25,
        "candidate_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "candidate_rows": len(rows),
        "present_rows": present_rows,
        "missing_rows": len(rows) - present_rows,
        "executable_present": bool(executable_rows and executable_rows[0].get("status") == "present"),
        "technical_smoke_validation_success": technical_validation.get("success") is True,
        "technical_smoke_only": technical_validation.get("technical_smoke_only") is True,
        "technical_smoke_artifact_count": technical_validation.get("artifact_count"),
        "technical_formal_path_overlap_rows": len(path_overlap),
        "technical_evidence_substitutes_formal_provision": False,
        "ready_for_runtime_receipt_rows": 0,
        "technical_smoke_evidence_present": technical_smoke_artifact_rows == 5,
        "technical_smoke_artifact_rows": technical_smoke_artifact_rows,
        "technical_smoke_checksum_verified_rows": technical_smoke_checksum_verified_rows,
        "technical_smoke_substitution_allowed": False,
        "formal_smoke_artifact_present_rows": formal_smoke_artifact_present_rows,
        "formal_smoke_artifact_missing_rows": len(formal_smoke_rows) - formal_smoke_artifact_present_rows,
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "completion_ready": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "candidate_valid": report["candidate_valid"], "failure_count": report["failure_count"], "candidate_rows": report["candidate_rows"], "present_rows": report["present_rows"], "ready_for_runtime_receipt_rows": report["ready_for_runtime_receipt_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["candidate_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
