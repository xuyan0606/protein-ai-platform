#!/usr/bin/env python3
"""Validate explicit human claim-promotion decisions fail-closed."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from claim_readiness_policy_contract import BLOCKED_CLAIM_IDS


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "claim_promotion_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "claim_promotion_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "claim_promotion_decision_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_promotion_decision_validation.lock"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
CLAIM_POLICY_CURRENT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json"
POLICY_ANCHOR = AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
LOCAL_RELEASE_GUARD_COVERAGE = AI_ROOT / "reports" / "local_release_guard_coverage_validation_report.json"
MASTER_READINESS_VALIDATION = AI_ROOT / "reports" / "master_readiness_board_validation_report.json"

VALID_DECISIONS = {"approved", "blocked", "rejected", "needs_more_info"}
TARGET_CLAIM_IDS = tuple(sorted(BLOCKED_CLAIM_IDS))
REQUIRED_VALIDATION_REPORTS = [
    "reports/claim_readiness_matrix.json",
    "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
    "reports/claim_readiness_policy_anchor_validation_report.json",
    "reports/local_release_guard_coverage_validation_report.json",
    "reports/local_release_manifest.json",
    "reports/master_readiness_board_validation_report.json",
]
REQUIRED_EVIDENCE_ARTIFACTS = [
    "reports/claim_readiness_matrix.json",
    "reports/local_release_manifest.json",
    "reports/master_readiness_board.json",
]
HUMAN_TARGET_PROJECTION_FIELDS = [
    "human_target_projection_gap_report_valid",
    "human_target_projection_runtime_manifest_valid",
    "human_target_projection_runtime_receipts_valid",
    "human_target_projection_blocked_source_index_valid",
    "human_target_projection_blocked_split_manifests_valid",
    "human_target_projection_unlock_checklist_valid",
    "human_target_projection_unlock_report_valid",
]
CLAIM_PROMOTION_REQUIREMENT_NAME = "claim-promotion evidence contract valid"
CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS = [
    "claim_promotion_decision_validation_success",
    "claim_promotion_decision_validation_failures",
    "claim_promotion_template_rows",
    "claim_promotion_template_matches_expected_contract",
    "claim_promotion_target_claim_rows",
    "claim_promotion_required_evidence_artifact_count",
    "claim_promotion_required_evidence_artifacts",
    "claim_promotion_required_validation_report_count",
    "claim_promotion_required_validation_reports",
    "claim_promotion_decision_rows",
    "claim_promotion_approved_rows",
    "claim_promotion_missing_decisions",
    "claim_promotion_decision_success",
    "claim_promotion_validation_failures",
]
CLAIM_PROMOTION_CONTRACT_EVIDENCE_LIST_FIELDS = [
    "claim_promotion_required_evidence_artifacts",
    "claim_promotion_required_validation_reports",
]
CLAIM_PROMOTION_CONTRACT_EVIDENCE_BOOL_FIELDS = [
    "claim_promotion_decision_validation_success",
    "claim_promotion_template_matches_expected_contract",
    "claim_promotion_decision_success",
]
CLAIM_PROMOTION_CONTRACT_EVIDENCE_COUNT_FIELDS = [
    "claim_promotion_decision_validation_failures",
    "claim_promotion_template_rows",
    "claim_promotion_target_claim_rows",
    "claim_promotion_required_evidence_artifact_count",
    "claim_promotion_required_validation_report_count",
    "claim_promotion_decision_rows",
    "claim_promotion_approved_rows",
    "claim_promotion_missing_decisions",
    "claim_promotion_validation_failures",
]
CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS = [
    "claim_promotion_requirement_name",
    "claim_promotion_target_claim_rows_with_contract_requirement",
    "claim_promotion_target_claim_rows_with_contract_requirement_passed",
    "claim_promotion_target_claim_contract_requirement_complete",
    "claim_promotion_target_claim_rows_with_contract_requirement_evidence",
    "claim_promotion_target_claim_contract_requirement_evidence_complete",
]
CLAIM_PROMOTION_REQUIREMENT_COVERAGE_STRING_FIELDS = [
    "claim_promotion_requirement_name",
]
CLAIM_PROMOTION_REQUIREMENT_COVERAGE_BOOL_FIELDS = [
    "claim_promotion_target_claim_contract_requirement_complete",
    "claim_promotion_target_claim_contract_requirement_evidence_complete",
]
CLAIM_PROMOTION_REQUIREMENT_COVERAGE_COUNT_FIELDS = [
    "claim_promotion_target_claim_rows_with_contract_requirement",
    "claim_promotion_target_claim_rows_with_contract_requirement_passed",
    "claim_promotion_target_claim_rows_with_contract_requirement_evidence",
]
INVALID_JSONL_ROW_KEY = "__invalid_jsonl_parse_error__"
MISSING_JSONL_INPUT_KEY = "__missing_jsonl_input__"
MISSING_JSON_REPORT_KEY = "__missing_json_report__"
INVALID_JSON_REPORT_KEY = "__invalid_json_report_parse_error__"
INVALID_JSON_REPORT_TYPE_KEY = "__invalid_json_report_type_error__"
UNREADABLE_JSON_REPORT_KEY = "__unreadable_json_report__"
UNREADABLE_JSONL_INPUT_KEY = "__unreadable_jsonl_input__"
SOURCE_REPORT_SUCCESS_REQUIRED_LABELS = {
    "anchor",
    "local_release_guard_coverage",
    "master_readiness",
    "policy_current",
}

TEMPLATE_BASE_ROW = {
    "promotion_decision": "needs_more_info",
    "reviewer": "human-claim-promotion-reviewer",
    "reviewed_at": "2026-08-12T00:00:00+08:00",
    "decision_basis": "template only; replace with an explicit human review",
    "evidence_artifacts": [],
    "validation_reports": REQUIRED_VALIDATION_REPORTS,
    "approved_for_promotion": False,
    "residual_risks": ["template only"],
    "notes": "template only; this is not a promotion decision",
}


def build_template_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim_id in TARGET_CLAIM_IDS:
        row = {
            "claim_id": claim_id,
            "promotion_decision": TEMPLATE_BASE_ROW["promotion_decision"],
            "reviewer": TEMPLATE_BASE_ROW["reviewer"],
            "reviewed_at": TEMPLATE_BASE_ROW["reviewed_at"],
            "decision_basis": TEMPLATE_BASE_ROW["decision_basis"],
            "evidence_artifacts": list(TEMPLATE_BASE_ROW["evidence_artifacts"]),
            "validation_reports": list(TEMPLATE_BASE_ROW["validation_reports"]),
            "approved_for_promotion": TEMPLATE_BASE_ROW["approved_for_promotion"],
            "residual_risks": list(TEMPLATE_BASE_ROW["residual_risks"]),
            "notes": TEMPLATE_BASE_ROW["notes"],
        }
        rows.append(row)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            MISSING_JSON_REPORT_KEY: True,
            "path": str(path),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        return {
            UNREADABLE_JSON_REPORT_KEY: str(exc),
            "path": str(path),
        }
    except json.JSONDecodeError as exc:
        return {
            INVALID_JSON_REPORT_KEY: str(exc),
            "path": str(path),
        }
    if not isinstance(data, dict):
        return {
            INVALID_JSON_REPORT_TYPE_KEY: type(data).__name__,
            "path": str(path),
        }
    return data


def load_jsonl(path: Path) -> list[Any]:
    if not path.is_file():
        return [{
            MISSING_JSONL_INPUT_KEY: True,
            "path": str(path),
        }]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [{
            UNREADABLE_JSONL_INPUT_KEY: str(exc),
            "path": str(path),
        }]
    rows: list[Any] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            rows.append({
                INVALID_JSONL_ROW_KEY: str(exc),
                "line_number": line_number,
                "raw_preview": line[:200],
            })
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def source_report_errors(label: str, report: dict[str, Any]) -> list[str]:
    if report.get(MISSING_JSON_REPORT_KEY):
        return [f"missing_source_json_{label}"]
    if report.get(INVALID_JSON_REPORT_KEY):
        return [f"invalid_source_json_{label}"]
    if report.get(INVALID_JSON_REPORT_TYPE_KEY):
        return [f"invalid_source_json_type_{label}"]
    if report.get(UNREADABLE_JSON_REPORT_KEY):
        return [f"unreadable_source_json_{label}"]
    if label in SOURCE_REPORT_SUCCESS_REQUIRED_LABELS and report.get("success") is not True:
        return [f"source_report_not_success_{label}"]
    return []


def local_release_summary(local_release: dict[str, Any]) -> dict[str, Any]:
    summary = local_release.get("readiness_summary") or {}
    return summary if isinstance(summary, dict) else {}


def local_release_summary_errors(local_release: dict[str, Any]) -> list[str]:
    if any(
        local_release.get(marker)
        for marker in (
            MISSING_JSON_REPORT_KEY,
            INVALID_JSON_REPORT_KEY,
            INVALID_JSON_REPORT_TYPE_KEY,
            UNREADABLE_JSON_REPORT_KEY,
        )
    ):
        return []
    if "readiness_summary" not in local_release:
        return ["missing_local_release_readiness_summary"]
    summary = local_release.get("readiness_summary")
    if isinstance(summary, dict):
        return []
    return ["invalid_local_release_readiness_summary"]


def claim_matrix_claims(claim_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows = claim_matrix.get("claims") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def claim_matrix_claims_errors(claim_matrix: dict[str, Any]) -> list[str]:
    rows = claim_matrix.get("claims")
    if rows is None:
        return ["missing_claim_matrix_claims"]
    if isinstance(rows, list):
        errors = [
            "invalid_claim_matrix_claim_rows"
            for row in rows
            if not isinstance(row, dict)
        ]
        claim_ids = [
            row.get("claim_id")
            for row in rows
            if isinstance(row, dict)
        ]
        errors.extend(
            "invalid_claim_matrix_claim_id"
            for claim_id in claim_ids
            if not isinstance(claim_id, str) or not claim_id
        )
        valid_claim_ids = [claim_id for claim_id in claim_ids if isinstance(claim_id, str) and claim_id]
        duplicate_claim_ids = {
            claim_id
            for claim_id, count in Counter(valid_claim_ids).items()
            if count > 1
        }
        errors.extend("duplicate_claim_matrix_claim_id" for _ in duplicate_claim_ids)
        if not errors and set(TARGET_CLAIM_IDS) - set(valid_claim_ids):
            errors.append("missing_claim_matrix_target_claims")
        return errors
    return ["invalid_claim_matrix_claims"]


def promotion_contract_list_errors(evidence: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if evidence.get("claim_promotion_required_evidence_artifacts") != list(REQUIRED_EVIDENCE_ARTIFACTS):
        errors.append(f"invalid_claim_promotion_{prefix}_required_evidence_artifacts")
    if evidence.get("claim_promotion_required_validation_reports") != list(REQUIRED_VALIDATION_REPORTS):
        errors.append(f"invalid_claim_promotion_{prefix}_required_validation_reports")
    return errors


def promotion_contract_scalar_type_errors(evidence: dict[str, Any], prefix: str) -> list[str]:
    if any(not isinstance(evidence.get(field), bool) for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_BOOL_FIELDS):
        return [f"invalid_claim_promotion_{prefix}_evidence_scalar_types"]
    if any(
        not isinstance(evidence.get(field), int) or isinstance(evidence.get(field), bool)
        for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_COUNT_FIELDS
    ):
        return [f"invalid_claim_promotion_{prefix}_evidence_scalar_types"]
    return []


def promotion_contract_source_binding_errors(
    evidence: dict[str, Any],
    prefix: str,
    release_summary: dict[str, Any] | None,
) -> list[str]:
    if release_summary is None:
        return []
    expected = {
        field: release_summary.get(field)
        for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS
    }
    if evidence != expected:
        return [f"invalid_claim_promotion_{prefix}_evidence_source_binding"]
    return []


def promotion_requirement_coverage_scalar_type_errors(
    coverage: dict[str, Any], prefix: str
) -> list[str]:
    if any(
        not isinstance(coverage.get(field), str) or not coverage.get(field)
        for field in CLAIM_PROMOTION_REQUIREMENT_COVERAGE_STRING_FIELDS
    ):
        return [f"invalid_claim_promotion_{prefix}_scalar_types"]
    if any(
        not isinstance(coverage.get(field), bool)
        for field in CLAIM_PROMOTION_REQUIREMENT_COVERAGE_BOOL_FIELDS
    ):
        return [f"invalid_claim_promotion_{prefix}_scalar_types"]
    if any(
        not isinstance(coverage.get(field), int) or isinstance(coverage.get(field), bool)
        for field in CLAIM_PROMOTION_REQUIREMENT_COVERAGE_COUNT_FIELDS
    ):
        return [f"invalid_claim_promotion_{prefix}_scalar_types"]
    return []


def promotion_requirement_coverage_source_binding_errors(
    coverage: dict[str, Any],
    prefix: str,
    release_summary: dict[str, Any] | None,
) -> list[str]:
    if release_summary is None:
        return []
    expected = {
        field: release_summary.get(field)
        for field in CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS
    }
    if coverage != expected:
        return [f"invalid_claim_promotion_{prefix}_source_binding"]
    return []


def claim_requirement_errors(
    claims: dict[str, dict[str, Any]],
    release_summary: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    for claim_id in TARGET_CLAIM_IDS:
        claim = claims.get(claim_id, {})
        requirements = claim.get("requirements")
        if "requirements" not in claim:
            errors.append("missing_claim_requirements")
            continue
        if not isinstance(requirements, list):
            errors.append("invalid_claim_requirements")
            continue
        if isinstance(requirements, list):
            invalid_requirement_rows = any(
                not isinstance(requirement, dict)
                for requirement in requirements
            )
            errors.extend(
                "invalid_claim_requirement_rows"
                for requirement in requirements
                if not isinstance(requirement, dict)
            )
            invalid_requirement_names = any(
                isinstance(requirement, dict)
                and (
                    not isinstance(requirement.get("name"), str)
                    or not requirement.get("name")
                )
                for requirement in requirements
            )
            errors.extend(
                "invalid_claim_requirement_name"
                for requirement in requirements
                if isinstance(requirement, dict)
                and (
                    not isinstance(requirement.get("name"), str)
                    or not requirement.get("name")
                )
            )
            promotion_requirement_count = sum(
                1
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("name") == CLAIM_PROMOTION_REQUIREMENT_NAME
            )
            if (
                promotion_requirement_count == 0
                and not invalid_requirement_rows
                and not invalid_requirement_names
            ):
                errors.append("missing_claim_promotion_requirement")
            if promotion_requirement_count > 1:
                errors.append("duplicate_claim_promotion_requirement")
            errors.extend(
                "missing_claim_promotion_requirement_passed"
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("name") == CLAIM_PROMOTION_REQUIREMENT_NAME
                and "passed" not in requirement
            )
            errors.extend(
                "invalid_claim_promotion_requirement_passed"
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("name") == CLAIM_PROMOTION_REQUIREMENT_NAME
                and "passed" in requirement
                and not isinstance(requirement.get("passed"), bool)
            )
            errors.extend(
                "missing_claim_promotion_requirement_evidence"
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("name") == CLAIM_PROMOTION_REQUIREMENT_NAME
                and "evidence" not in requirement
            )
            errors.extend(
                "invalid_claim_promotion_requirement_evidence"
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("name") == CLAIM_PROMOTION_REQUIREMENT_NAME
                and "evidence" in requirement
                and not isinstance(requirement.get("evidence"), dict)
            )
            for requirement in requirements:
                if (
                    not isinstance(requirement, dict)
                    or requirement.get("name") != CLAIM_PROMOTION_REQUIREMENT_NAME
                    or not isinstance(requirement.get("evidence"), dict)
                ):
                    continue
                evidence = requirement["evidence"]
                if "release_summary" not in evidence:
                    errors.append("missing_claim_promotion_release_summary_evidence")
                elif not isinstance(evidence.get("release_summary"), dict):
                    errors.append("invalid_claim_promotion_release_summary_evidence")
                if "master_governance_release" not in evidence:
                    errors.append("missing_claim_promotion_master_governance_evidence")
                elif not isinstance(evidence.get("master_governance_release"), dict):
                    errors.append("invalid_claim_promotion_master_governance_evidence")
                expected_evidence_fields = set(CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS)
                release_summary_evidence = evidence.get("release_summary")
                if isinstance(release_summary_evidence, dict):
                    if set(release_summary_evidence) != expected_evidence_fields:
                        errors.append("invalid_claim_promotion_release_summary_evidence_fields")
                    elif any(not isinstance(release_summary_evidence.get(field), list) for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_LIST_FIELDS):
                        errors.append("invalid_claim_promotion_release_summary_evidence_lists")
                    else:
                        list_errors = promotion_contract_list_errors(release_summary_evidence, "release_summary")
                        scalar_errors = promotion_contract_scalar_type_errors(release_summary_evidence, "release_summary")
                        errors.extend(list_errors)
                        errors.extend(scalar_errors)
                        if not list_errors and not scalar_errors:
                            errors.extend(
                                promotion_contract_source_binding_errors(
                                    release_summary_evidence,
                                    "release_summary",
                                    release_summary,
                                )
                            )
                master_governance_release = evidence.get("master_governance_release")
                if isinstance(master_governance_release, dict):
                    if set(master_governance_release) != expected_evidence_fields:
                        errors.append("invalid_claim_promotion_master_governance_evidence_fields")
                    elif any(not isinstance(master_governance_release.get(field), list) for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_LIST_FIELDS):
                        errors.append("invalid_claim_promotion_master_governance_evidence_lists")
                    else:
                        list_errors = promotion_contract_list_errors(master_governance_release, "master_governance")
                        scalar_errors = promotion_contract_scalar_type_errors(master_governance_release, "master_governance")
                        errors.extend(list_errors)
                        errors.extend(scalar_errors)
                        if not list_errors and not scalar_errors:
                            errors.extend(
                                promotion_contract_source_binding_errors(
                                    master_governance_release,
                                    "master_governance",
                                    release_summary,
                                )
                            )
                expected_coverage_fields = set(CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS)
                if "release_requirement_coverage" not in evidence:
                    errors.append("missing_claim_promotion_release_requirement_coverage")
                elif not isinstance(evidence.get("release_requirement_coverage"), dict):
                    errors.append("invalid_claim_promotion_release_requirement_coverage")
                release_requirement_coverage = evidence.get("release_requirement_coverage")
                if isinstance(release_requirement_coverage, dict):
                    if set(release_requirement_coverage) != expected_coverage_fields:
                        errors.append("invalid_claim_promotion_release_requirement_coverage_fields")
                    else:
                        scalar_errors = promotion_requirement_coverage_scalar_type_errors(
                            release_requirement_coverage,
                            "release_requirement_coverage",
                        )
                        errors.extend(scalar_errors)
                        if not scalar_errors:
                            errors.extend(
                                promotion_requirement_coverage_source_binding_errors(
                                    release_requirement_coverage,
                                    "release_requirement_coverage",
                                    release_summary,
                                )
                            )
                if "master_requirement_coverage" not in evidence:
                    errors.append("missing_claim_promotion_master_requirement_coverage")
                elif not isinstance(evidence.get("master_requirement_coverage"), dict):
                    errors.append("invalid_claim_promotion_master_requirement_coverage")
                master_requirement_coverage = evidence.get("master_requirement_coverage")
                if isinstance(master_requirement_coverage, dict):
                    if set(master_requirement_coverage) != expected_coverage_fields:
                        errors.append("invalid_claim_promotion_master_requirement_coverage_fields")
                    else:
                        scalar_errors = promotion_requirement_coverage_scalar_type_errors(
                            master_requirement_coverage,
                            "master_requirement_coverage",
                        )
                        errors.extend(scalar_errors)
                        if not scalar_errors:
                            errors.extend(
                                promotion_requirement_coverage_source_binding_errors(
                                    master_requirement_coverage,
                                    "master_requirement_coverage",
                                    release_summary,
                                )
                            )
    return errors


def exists_rel(value: Any, root: Path = AI_ROOT) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        path = Path(value)
        if path.is_absolute():
            path = path.resolve()
            path.relative_to(root.resolve())
            return path.is_file()
        return (root / path).is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def requirement_by_name(claim: dict[str, Any], name: str) -> dict[str, Any]:
    requirements = claim.get("requirements") or []
    if not isinstance(requirements, list):
        return {}
    for requirement in requirements:
        if isinstance(requirement, dict) and requirement.get("name") == name:
            return requirement
    return {}


def release_promotion_contract_valid(release_summary: dict[str, Any]) -> bool:
    return (
        release_summary.get("claim_promotion_decision_validation_success") is True
        and release_summary.get("claim_promotion_decision_validation_failures") == 0
        and release_summary.get("claim_promotion_template_rows") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_template_matches_expected_contract") is True
        and release_summary.get("claim_promotion_target_claim_rows") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_requirement_name") == CLAIM_PROMOTION_REQUIREMENT_NAME
        and release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement_passed") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_target_claim_contract_requirement_complete") is True
        and release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement_evidence") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_target_claim_contract_requirement_evidence_complete") is True
        and release_summary.get("claim_promotion_required_evidence_artifact_count") == len(REQUIRED_EVIDENCE_ARTIFACTS)
        and release_summary.get("claim_promotion_required_evidence_artifacts") == list(REQUIRED_EVIDENCE_ARTIFACTS)
        and release_summary.get("claim_promotion_required_validation_report_count") == len(REQUIRED_VALIDATION_REPORTS)
        and release_summary.get("claim_promotion_required_validation_reports") == list(REQUIRED_VALIDATION_REPORTS)
        and release_summary.get("claim_promotion_decision_rows") == 0
        and release_summary.get("claim_promotion_approved_rows") == 0
        and release_summary.get("claim_promotion_missing_decisions") == len(TARGET_CLAIM_IDS)
        and release_summary.get("claim_promotion_decision_success") is False
        and release_summary.get("claim_promotion_validation_failures") == 0
    )


def promotion_requirement_evidence_valid(requirement: dict[str, Any], release_summary: dict[str, Any]) -> bool:
    evidence = requirement.get("evidence")
    if not isinstance(evidence, dict):
        return False
    release_evidence = evidence.get("release_summary")
    master_evidence = evidence.get("master_governance_release")
    if not isinstance(release_evidence, dict) or not isinstance(master_evidence, dict):
        return False
    release_coverage = evidence.get("release_requirement_coverage")
    master_coverage = evidence.get("master_requirement_coverage")
    if not isinstance(release_coverage, dict) or not isinstance(master_coverage, dict):
        return False
    expected = {field: release_summary.get(field) for field in CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS}
    if release_evidence != expected or master_evidence != expected:
        return False
    expected_coverage = {
        field: release_summary.get(field)
        for field in CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS
    }
    if release_coverage != expected_coverage or master_coverage != expected_coverage:
        return False
    return True


def validation_report_contract_errors(validation_reports: Any) -> list[str]:
    if not isinstance(validation_reports, list):
        return ["approved_validation_reports_contract_not_exact"]
    if any(not isinstance(report, str) or not report for report in validation_reports):
        return ["approved_invalid_validation_report_entries"]
    required_counts = Counter(REQUIRED_VALIDATION_REPORTS)
    observed_counts = Counter(validation_reports)
    errors: list[str] = []
    if any(observed_counts[report] < required_counts[report] for report in REQUIRED_VALIDATION_REPORTS):
        errors.append("approved_missing_required_validation_reports")
    if any(report not in required_counts for report in observed_counts):
        errors.append("approved_unexpected_validation_reports")
    if any(observed_counts[report] > required_counts[report] for report in REQUIRED_VALIDATION_REPORTS):
        errors.append("approved_duplicate_validation_reports")
    if not errors and validation_reports != list(REQUIRED_VALIDATION_REPORTS):
        errors.append("approved_validation_reports_wrong_order")
    return errors


def evidence_artifact_contract_errors(evidence_artifacts: Any) -> list[str]:
    if not isinstance(evidence_artifacts, list):
        return ["approved_evidence_artifacts_contract_not_exact"]
    if any(not isinstance(artifact, str) or not artifact for artifact in evidence_artifacts):
        return ["approved_invalid_evidence_artifact_entries"]
    required_counts = Counter(REQUIRED_EVIDENCE_ARTIFACTS)
    observed_counts = Counter(evidence_artifacts)
    errors: list[str] = []
    if any(observed_counts[artifact] < required_counts[artifact] for artifact in REQUIRED_EVIDENCE_ARTIFACTS):
        errors.append("approved_missing_required_evidence_artifacts")
    if any(artifact not in required_counts for artifact in observed_counts):
        errors.append("approved_unexpected_evidence_artifacts")
    if any(observed_counts[artifact] > required_counts[artifact] for artifact in REQUIRED_EVIDENCE_ARTIFACTS):
        errors.append("approved_duplicate_evidence_artifacts")
    if not errors and evidence_artifacts != list(REQUIRED_EVIDENCE_ARTIFACTS):
        errors.append("approved_evidence_artifacts_wrong_order")
    return errors


def validate(row: Any, claim_rows: dict[str, dict[str, Any]], reports: dict[str, dict[str, Any]], root: Path = AI_ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(row, dict):
        return ["invalid_decision_row"]
    if row.get(MISSING_JSONL_INPUT_KEY):
        return ["missing_decision_input"]
    if row.get(UNREADABLE_JSONL_INPUT_KEY):
        return ["unreadable_decision_input"]
    if row.get(INVALID_JSONL_ROW_KEY):
        return ["invalid_decision_json"]
    for field in [
        "claim_id",
        "promotion_decision",
        "reviewer",
        "reviewed_at",
        "decision_basis",
        "evidence_artifacts",
        "validation_reports",
        "approved_for_promotion",
        "residual_risks",
    ]:
        if field not in row or row.get(field) in (None, ""):
            errors.append(f"missing_{field}")
    for field in ["claim_id", "reviewer", "reviewed_at", "decision_basis"]:
        if field in row and row.get(field) not in (None, "") and not isinstance(row.get(field), str):
            errors.append(f"invalid_{field}")
    claim_id = row.get("claim_id") if isinstance(row.get("claim_id"), str) else ""
    if claim_id not in set(TARGET_CLAIM_IDS):
        errors.append("unknown_or_non_high_risk_claim")
    if row.get("promotion_decision") not in VALID_DECISIONS:
        errors.append("invalid_promotion_decision")
    if not isinstance(row.get("approved_for_promotion"), bool):
        errors.append("invalid_approved_for_promotion")
    for field in ["evidence_artifacts", "validation_reports", "residual_risks"]:
        if not isinstance(row.get(field), list):
            errors.append(f"invalid_{field}")
        elif any(not isinstance(value, str) or not value for value in row.get(field) or []):
            errors.append(f"invalid_{field}_entries")
        elif field != "residual_risks" and any(not exists_rel(value, root) for value in row.get(field) or []):
            errors.append(f"missing_{field}_paths")
    if row.get("promotion_decision") == "approved":
        if row.get("approved_for_promotion") is not True:
            errors.append("approved_decision_without_approval_flag")
        claim = claim_rows.get(claim_id, {})
        if claim.get("ready") is not True:
            errors.append("approved_claim_not_dynamically_ready")
        promotion_requirement = requirement_by_name(claim, CLAIM_PROMOTION_REQUIREMENT_NAME)
        if not promotion_requirement:
            errors.append("approved_claim_missing_promotion_evidence_requirement")
        elif promotion_requirement.get("passed") is not True:
            errors.append("approved_claim_promotion_evidence_contract_not_valid")
        if reports.get("policy_current", {}).get("success") is not True:
            errors.append("approved_claim_policy_current_not_valid")
        if reports.get("anchor", {}).get("success") is not True:
            errors.append("approved_claim_policy_anchor_not_valid")
        release_summary = local_release_summary(reports.get("local_release", {}))
        if reports.get("local_release_guard_coverage", {}).get("success") is not True:
            errors.append("approved_local_release_guard_coverage_not_valid")
        if reports.get("master_readiness", {}).get("success") is not True:
            errors.append("approved_master_readiness_validation_not_valid")
        if not release_promotion_contract_valid(release_summary):
            errors.append("approved_release_promotion_contract_not_valid")
        if promotion_requirement and not promotion_requirement_evidence_valid(promotion_requirement, release_summary):
            errors.append("approved_claim_promotion_evidence_not_source_bound")
        if not all(release_summary.get(field) is True for field in HUMAN_TARGET_PROJECTION_FIELDS):
            errors.append("approved_human_target_projection_chain_not_valid")
        if release_summary.get("human_target_source_runtime_ready_sources") != 0:
            errors.append("approved_human_target_runtime_sources_not_fail_closed")
        if release_summary.get("human_target_source_unlock_ready_rows") != 0:
            errors.append("approved_human_target_unlock_rows_not_fail_closed")
        errors.extend(evidence_artifact_contract_errors(row.get("evidence_artifacts")))
        errors.extend(validation_report_contract_errors(row.get("validation_reports")))
        if not row.get("evidence_artifacts"):
            errors.append("approved_without_evidence_artifacts")
        if row.get("residual_risks"):
            errors.append("approved_with_residual_risks")
    elif row.get("approved_for_promotion") is True:
        errors.append("non_approved_decision_with_approval_flag")
    return errors


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.claim-promotion-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate explicit claim promotion decisions")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    input_path = args.input.resolve()
    report_path = args.report.resolve()
    lock_path = args.lock_path.resolve()
    template_rows = build_template_rows()
    write_jsonl(args.template, template_rows)

    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "claim_promotion_lock_timeout", "output_preserved": report_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    claim_matrix = load_json(CLAIM_MATRIX)
    claims = {str(row.get("claim_id")): row for row in claim_matrix_claims(claim_matrix)}
    reports = {
        "policy_current": load_json(CLAIM_POLICY_CURRENT),
        "anchor": load_json(POLICY_ANCHOR),
        "local_release": load_json(LOCAL_RELEASE),
        "local_release_guard_coverage": load_json(LOCAL_RELEASE_GUARD_COVERAGE),
        "master_readiness": load_json(MASTER_READINESS_VALIDATION),
    }
    decisions = load_jsonl(input_path)
    records: list[dict[str, Any]] = []
    errors = Counter()
    errors.update(source_report_errors("claim_matrix", claim_matrix))
    source_report_errors_by_label: dict[str, list[str]] = {}
    for label, report_source in reports.items():
        report_errors = source_report_errors(label, report_source)
        source_report_errors_by_label[label] = report_errors
        errors.update(report_errors)
    errors.update(claim_matrix_claims_errors(claim_matrix))
    release_summary = local_release_summary(reports.get("local_release", {}))
    local_release_errors = local_release_summary_errors(reports.get("local_release", {}))
    errors.update(local_release_errors)
    errors.update(
        claim_requirement_errors(
            claims,
            release_summary
            if not local_release_errors and not source_report_errors_by_label.get("local_release")
            else None,
        )
    )
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in decisions:
        if not isinstance(row, dict):
            row_errors = validate(row, claims, reports)
            errors.update(row_errors)
            records.append({
                "claim_id": None,
                "promotion_decision": None,
                "valid": False,
                "approved_for_promotion": False,
                "errors": row_errors,
            })
            continue
        if row.get(INVALID_JSONL_ROW_KEY):
            row_errors = validate(row, claims, reports)
            errors.update(row_errors)
            records.append({
                "claim_id": None,
                "promotion_decision": None,
                "valid": False,
                "approved_for_promotion": False,
                "line_number": row.get("line_number"),
                "errors": row_errors,
            })
            continue
        claim_id = str(row.get("claim_id"))
        if claim_id in seen:
            duplicates.add(claim_id)
        seen.add(claim_id)
        row_errors = validate(row, claims, reports)
        errors.update(row_errors)
        records.append({
            "claim_id": row.get("claim_id"),
            "promotion_decision": row.get("promotion_decision"),
            "valid": not row_errors,
            "approved_for_promotion": row.get("promotion_decision") == "approved" and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_claim_id": len(duplicates)})
        for record in records:
            if str(record.get("claim_id")) in duplicates:
                record["valid"] = False
                record["approved_for_promotion"] = False
                record["errors"].append("duplicate_claim_id")

    approved_ids = sorted({str(record["claim_id"]) for record in records if record["approved_for_promotion"]})
    decided_ids = sorted({str(record["claim_id"]) for record in records if record["valid"]})
    missing_ids = sorted(set(TARGET_CLAIM_IDS) - set(decided_ids))
    template_claim_ids = [str(row.get("claim_id")) for row in template_rows]
    template_matches_contract = template_claim_ids == list(TARGET_CLAIM_IDS) and len(template_rows) == len(TARGET_CLAIM_IDS)
    target_claims_with_promotion_contract_requirement = [
        claim_id
        for claim_id in TARGET_CLAIM_IDS
        if requirement_by_name(claims.get(claim_id, {}), CLAIM_PROMOTION_REQUIREMENT_NAME)
    ]
    target_claims_with_promotion_contract_requirement_passed = [
        claim_id
        for claim_id in TARGET_CLAIM_IDS
        if requirement_by_name(claims.get(claim_id, {}), CLAIM_PROMOTION_REQUIREMENT_NAME).get("passed") is True
    ]
    release_summary = local_release_summary(reports.get("local_release", {}))
    target_claims_with_promotion_contract_requirement_evidence = [
        claim_id
        for claim_id in TARGET_CLAIM_IDS
        if promotion_requirement_evidence_valid(
            requirement_by_name(claims.get(claim_id, {}), CLAIM_PROMOTION_REQUIREMENT_NAME),
            release_summary,
        )
    ]
    report = {
        "schema_version": 1,
        "mode": "claim_promotion_decision_validation",
        "local_only": True,
        "success": not errors,
        "failure_count": len(errors),
        "input": str(input_path),
        "template": str(args.template.resolve()),
        "template_rows": len(template_rows),
        "template_claim_ids": template_claim_ids,
        "template_matches_expected_contract": template_matches_contract,
        "required_evidence_artifacts": list(REQUIRED_EVIDENCE_ARTIFACTS),
        "required_evidence_artifact_count": len(REQUIRED_EVIDENCE_ARTIFACTS),
        "required_validation_reports": list(REQUIRED_VALIDATION_REPORTS),
        "required_validation_report_count": len(REQUIRED_VALIDATION_REPORTS),
        "target_claim_ids": list(TARGET_CLAIM_IDS),
        "target_claim_rows": len(TARGET_CLAIM_IDS),
        "claim_promotion_requirement_name": CLAIM_PROMOTION_REQUIREMENT_NAME,
        "target_claims_with_promotion_contract_requirement": target_claims_with_promotion_contract_requirement,
        "target_claim_rows_with_promotion_contract_requirement": len(target_claims_with_promotion_contract_requirement),
        "target_claims_with_promotion_contract_requirement_passed": target_claims_with_promotion_contract_requirement_passed,
        "target_claim_rows_with_promotion_contract_requirement_passed": len(target_claims_with_promotion_contract_requirement_passed),
        "target_claims_with_promotion_contract_requirement_evidence": target_claims_with_promotion_contract_requirement_evidence,
        "target_claim_rows_with_promotion_contract_requirement_evidence": len(target_claims_with_promotion_contract_requirement_evidence),
        "target_claim_promotion_contract_requirement_complete": (
            set(target_claims_with_promotion_contract_requirement) == set(TARGET_CLAIM_IDS)
            and set(target_claims_with_promotion_contract_requirement_passed) == set(TARGET_CLAIM_IDS)
        ),
        "target_claim_promotion_contract_requirement_evidence_complete": (
            set(target_claims_with_promotion_contract_requirement_evidence) == set(TARGET_CLAIM_IDS)
        ),
        "decision_rows": len(decisions),
        "valid_rows": sum(1 for record in records if record["valid"]),
        "invalid_rows": sum(1 for record in records if not record["valid"]),
        "decided_claim_ids": decided_ids,
        "approved_claim_ids": approved_ids,
        "approved_rows": len(approved_ids),
        "missing_promotion_decisions": missing_ids,
        "all_high_risk_decisions_present": len(missing_ids) == 0 and not errors,
        "all_high_risk_claims_promoted": set(approved_ids) == set(TARGET_CLAIM_IDS) and not errors,
        "ready_for_claim_promotion": set(approved_ids) == set(TARGET_CLAIM_IDS) and not errors,
        "error_counts": dict(errors),
        "records": records[:200],
        "validator_path": str(Path(__file__).resolve()),
        "validator_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
        "output_path": str(report_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Promotion requires explicit human evidence and validation; empty or draft inputs never promote claims.",
    }
    try:
        write_json_atomic(report_path, report)
    finally:
        lock_handle.close()
    print(json.dumps({
        "decision_rows": len(decisions),
        "approved_rows": len(approved_ids),
        "missing_promotion_decisions": len(missing_ids),
        "ready_for_claim_promotion": report["ready_for_claim_promotion"],
        "output": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
