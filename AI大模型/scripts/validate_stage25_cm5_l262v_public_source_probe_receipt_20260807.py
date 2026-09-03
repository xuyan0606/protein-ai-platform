#!/usr/bin/env python3
"""Validate the recorded public-source probe remains evidence-neutral."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports/stage25_cm5_l262v_public_source_probe_receipt_20260807.json"
EVIDENCE_INTAKE = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"
QUALITY_AUDIT = AI_ROOT / "reports/stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_public_source_probe_receipt_validation_20260807.json"
EXPECTED_IDS = ["europe_pmc_search", "pubmed_summary", "crossref_work", "zenodo_record"]
NEGATIVE_FLAGS = ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("receipt", RECEIPT), ("evidence_intake", EVIDENCE_INTAKE), ("quality_audit", QUALITY_AUDIT)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    receipt = load_json(RECEIPT) if RECEIPT.is_file() else {}
    intake = load_json(EVIDENCE_INTAKE) if EVIDENCE_INTAKE.is_file() else {}
    quality = load_json(QUALITY_AUDIT) if QUALITY_AUDIT.is_file() else {}
    probes = receipt.get("probes") if isinstance(receipt.get("probes"), list) else []
    fail_if(receipt.get("mode") != "stage25_cm5_l262v_public_source_probe_receipt", failures, "mode", receipt.get("mode"), "stage25_cm5_l262v_public_source_probe_receipt")
    for field, expected in (("schema_version", 1), ("stage", 25), ("pmid", "42235695"), ("doi", "10.1016/j.biortech.2026.135069"), ("probe_rows", 4), ("public_source_artifact_rows", 0), ("slot_artifact_rows", 0), ("metadata_only_rows", 3), ("zenodo_archive_only_rows", 1), ("formal_decision_rows_written", 0)):
        fail_if(receipt.get(field) != expected, failures, field, receipt.get(field), expected)
    fail_if([item.get("probe_id") for item in probes if isinstance(item, dict)] != EXPECTED_IDS, failures, "probe_ids_exact", [item.get("probe_id") for item in probes if isinstance(item, dict)], EXPECTED_IDS)
    fail_if(len(probes) != 4, failures, "probe_rows_len", len(probes), 4)
    for index, probe in enumerate(probes, 1):
        prefix = f"probes[{index}]"
        fail_if(probe.get("http_status") != 200, failures, f"{prefix}.http_status", probe.get("http_status"), 200)
        fail_if(probe.get("slot_artifact_rows") != 0, failures, f"{prefix}.slot_artifact_rows", probe.get("slot_artifact_rows"), 0)
        fail_if(probe.get("fulltext_url_present") is not False, failures, f"{prefix}.fulltext_url_present_false", probe.get("fulltext_url_present"), False)
    by_id = {item.get("probe_id"): item for item in probes if isinstance(item, dict)}
    europe = by_id.get("europe_pmc_search", {})
    fail_if(europe.get("pmcid") is not None, failures, "europe_pmc.pmcid_null", europe.get("pmcid"), None)
    fail_if(europe.get("is_open_access") != "N", failures, "europe_pmc.is_open_access", europe.get("is_open_access"), "N")
    zenodo = by_id.get("zenodo_record", {})
    for field, expected in (("result_class", "already_audited_archive_only"), ("public_file_rows", 1), ("archive_size_bytes", 49144286), ("archive_md5", "d30dcf8029567cbc792c156d0d8f9bfc")):
        fail_if(zenodo.get(field) != expected, failures, f"zenodo.{field}", zenodo.get(field), expected)
    fail_if(intake.get("intake_valid") is not True, failures, "evidence_intake_valid", intake.get("intake_valid"), True)
    for field, expected in (("slot_rows", 4), ("present_rows", 0), ("missing_rows", 4), ("reviewed_evidence_rows", 0), ("ready_for_adjudication_rows", 0)):
        fail_if(intake.get(field) != expected, failures, f"evidence_intake.{field}", intake.get(field), expected)
    fail_if(quality.get("audit_valid") is not True, failures, "quality_audit_valid", quality.get("audit_valid"), True)
    fail_if(quality.get("quality_bearing_artifact_rows") != 0, failures, "quality_bearing_artifact_rows", quality.get("quality_bearing_artifact_rows"), 0)
    for field in NEGATIVE_FLAGS:
        fail_if(receipt.get(field) is not False, failures, f"{field}_false", receipt.get(field), False)
    policy = str(receipt.get("policy") or "")
    for term in ("metadata", "do not supply", "No paywall bypass", "publisher content endpoint"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_public_source_probe_receipt_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "probe_rows": len(probes),
        "metadata_only_rows": receipt.get("metadata_only_rows"),
        "zenodo_archive_only_rows": receipt.get("zenodo_archive_only_rows"),
        "slot_artifact_rows": receipt.get("slot_artifact_rows"),
        "evidence_slot_rows": intake.get("slot_rows"),
        "evidence_slot_present_rows": intake.get("present_rows"),
        "evidence_slot_missing_rows": intake.get("missing_rows"),
        "discrepancy_resolved": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "receipt_valid": report["receipt_valid"], "failure_count": report["failure_count"], "probe_rows": report["probe_rows"], "slot_artifact_rows": report["slot_artifact_rows"]}, sort_keys=True))
    return 0 if report["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
