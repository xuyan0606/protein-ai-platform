#!/usr/bin/env python3
"""Validate wet-lab mutant-library operator packets without approving them."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
AUTH_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
SEQ_PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_sequence_request_packets.jsonl"
FEEDBACK_PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_review_packets.jsonl"
UNLOCK_ACTIONS = AI_ROOT / "datasets" / "governance" / "wet_lab_mutant_library_unlock_actions.jsonl"
STATUS = AI_ROOT / "datasets" / "governance" / "wet_lab_mutant_library_operator_packet_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_operator_packet_validation_report.json"

MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")
EXPECTED_SEQUENCE_PROJECTS = {"16B", "4G"}
EXPECTED_ACTIONS = {
    "wetlab-mutlib-A001",
    "wetlab-mutlib-A002",
    "wetlab-mutlib-A003",
    "wetlab-mutlib-A004",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def exists_rel(rel: Any) -> bool:
    if not isinstance(rel, str) or not rel:
        return False
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def mutation_sort_key(mutation: str) -> tuple[int, str]:
    match = MUTATION_RE.match(str(mutation))
    return (int(match.group(2)), str(mutation)) if match else (10**9, str(mutation))


def project_mutations(candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        project = str(row.get("source_project") or "")
        for mutation in row.get("mutation_set") or []:
            if MUTATION_RE.match(str(mutation)):
                found[project].add(str(mutation))
    return {project: sorted(values, key=mutation_sort_key) for project, values in found.items()}


def required_check_for(mutation: str) -> str | None:
    match = MUTATION_RE.match(str(mutation))
    if not match:
        return None
    wt, position, _mutant = match.groups()
    return f"parent_sequence[{position}] == {wt}"


def validate_sequence_packet(row: dict[str, Any], mutations_by_project: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    required = [
        "packet_id",
        "workstream",
        "source_project",
        "status",
        "known_mutations",
        "mutation_wild_type_checks_required",
        "sequence_intake_target",
        "sequence_intake_template_row",
        "required_fields",
        "validator_command",
        "next_audit_command",
        "completion_condition",
        "policy",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    project = str(row.get("source_project") or "")
    if project not in EXPECTED_SEQUENCE_PROJECTS:
        errors.append("unexpected_sequence_project")
    if row.get("workstream") != "wet_lab_parent_sequence_review":
        errors.append("invalid_workstream")
    if row.get("status") != "blocked_waiting_for_reviewed_parent_sequence":
        errors.append("status_not_blocked_waiting_for_reviewed_parent_sequence")

    expected_mutations = mutations_by_project.get(project, [])
    observed_mutations = list(row.get("known_mutations") or [])
    if observed_mutations != expected_mutations:
        errors.append("known_mutations_do_not_match_candidates")

    checks = row.get("mutation_wild_type_checks_required")
    if not isinstance(checks, list):
        errors.append("invalid_mutation_wild_type_checks_required")
        checks = []
    if len(checks) != len(expected_mutations):
        errors.append("mutation_check_count_mismatch")
    checks_by_mutation = {str(check.get("mutation")): check for check in checks if isinstance(check, dict)}
    for mutation in expected_mutations:
        check = checks_by_mutation.get(mutation)
        if not check:
            errors.append("missing_mutation_check")
            continue
        if check.get("required_check") != required_check_for(mutation):
            errors.append("invalid_required_check")

    if not exists_rel(row.get("sequence_intake_target")):
        errors.append("sequence_intake_target_missing")
    template = row.get("sequence_intake_template_row")
    if not isinstance(template, dict) or template.get("project_id") != project:
        errors.append("sequence_intake_template_project_mismatch")

    if row.get("validator_command") != "python3 scripts/validate_wet_lab_mutant_library_project_sequence_intake.py":
        errors.append("invalid_validator_command")
    if row.get("next_audit_command") != "python3 scripts/build_wet_lab_mutant_library_numbering_audit_from_project_sequences.py":
        errors.append("invalid_next_audit_command")
    policy = str(row.get("policy") or "").lower()
    if "does not" not in policy or "training" not in policy:
        errors.append("policy_missing_fail_closed_language")
    return errors


def validate_feedback_packet(
    row: dict[str, Any],
    candidates_by_id: dict[str, dict[str, Any]],
    auth_template_by_candidate_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    required = [
        "packet_id",
        "workstream",
        "source_project",
        "variant",
        "metric_name",
        "candidate_rows",
        "feedback_candidate_ids",
        "candidate_summaries",
        "authorization_target",
        "authorization_template",
        "required_review_checks",
        "validator_command",
        "preflight_command",
        "completion_condition",
        "status",
        "policy",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    if row.get("workstream") != "wet_lab_feedback_authorization_review":
        errors.append("invalid_workstream")
    if row.get("status") != "blocked_waiting_for_human_authorization":
        errors.append("status_not_blocked_waiting_for_human_authorization")
    if row.get("source_project") != "15B":
        errors.append("unexpected_feedback_project")
    if not exists_rel(row.get("authorization_target")):
        errors.append("authorization_target_missing")
    if not exists_rel(row.get("authorization_template")):
        errors.append("authorization_template_missing")
    if row.get("validator_command") != "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py":
        errors.append("invalid_validator_command")
    if row.get("preflight_command") != "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py":
        errors.append("invalid_preflight_command")

    candidate_ids = [str(cid) for cid in (row.get("feedback_candidate_ids") or [])]
    summaries = row.get("candidate_summaries")
    if not isinstance(summaries, list):
        errors.append("invalid_candidate_summaries")
        summaries = []
    if row.get("candidate_rows") != len(candidate_ids) or len(summaries) != len(candidate_ids):
        errors.append("candidate_row_count_mismatch")

    summary_by_id = {str(item.get("feedback_candidate_id")): item for item in summaries if isinstance(item, dict)}
    for cid in candidate_ids:
        candidate = candidates_by_id.get(cid)
        if not candidate:
            errors.append("feedback_candidate_id_not_found")
            continue
        if candidate.get("numeric_training_candidate") is not True:
            errors.append("candidate_not_numeric_training_candidate")
        if candidate.get("source_project") != row.get("source_project"):
            errors.append("candidate_project_mismatch")
        if candidate.get("variant") != row.get("variant"):
            errors.append("candidate_variant_mismatch")
        if candidate.get("metric_name") != row.get("metric_name"):
            errors.append("candidate_metric_mismatch")
        template = auth_template_by_candidate_id.get(cid)
        summary = summary_by_id.get(cid)
        if not template:
            errors.append("authorization_template_row_missing")
        elif summary and summary.get("authorization_template_id") != template.get("authorization_id"):
            errors.append("authorization_template_id_mismatch")
        if summary and summary.get("source_file") and not exists_rel(summary.get("source_file")):
            errors.append("candidate_source_file_missing")

    review_checks = set(row.get("required_review_checks") or [])
    for token in ["source_trace_reviewed", "numbering_reviewed", "replicate_policy_reviewed"]:
        if not any(token in check for check in review_checks):
            errors.append(f"required_review_check_missing_{token}")
    policy = str(row.get("policy") or "").lower()
    if "does not authorize" not in policy or "does not append" not in policy:
        errors.append("policy_missing_fail_closed_language")
    return errors


def validate_unlock_action(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "unlock_action_id",
        "execution_order",
        "workstream",
        "status",
        "packet_source",
        "decision_input",
        "validator_command",
        "completion_condition",
        "requires_human_input",
        "policy",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")
    if row.get("unlock_action_id") not in EXPECTED_ACTIONS:
        errors.append("unexpected_unlock_action_id")
    if row.get("status") != "started_blocked":
        errors.append("status_not_started_blocked")
    if row.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if not exists_rel(row.get("packet_source")):
        errors.append("packet_source_missing")
    if not exists_rel(row.get("decision_input")):
        errors.append("decision_input_missing")
    if not str(row.get("validator_command") or "").startswith("python3 scripts/"):
        errors.append("invalid_validator_command")
    policy = str(row.get("policy") or "").lower()
    for phrase in ["not a reviewed decision", "not approval", "not model claim readiness", "not a production sync"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab mutant-library operator packets")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--authorization-template", type=Path, default=AUTH_TEMPLATE)
    parser.add_argument("--sequence-packets", type=Path, default=SEQ_PACKETS)
    parser.add_argument("--feedback-packets", type=Path, default=FEEDBACK_PACKETS)
    parser.add_argument("--unlock-actions", type=Path, default=UNLOCK_ACTIONS)
    parser.add_argument("--status-output", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    auth_template_rows = load_jsonl(args.authorization_template)
    sequence_packets = load_jsonl(args.sequence_packets)
    feedback_packets = load_jsonl(args.feedback_packets)
    unlock_actions = load_jsonl(args.unlock_actions)

    candidates_by_id = {str(row.get("feedback_candidate_id")): row for row in candidates}
    auth_template_by_candidate_id = {str(row.get("feedback_candidate_id")): row for row in auth_template_rows}
    numeric_candidate_ids = sorted(
        str(row.get("feedback_candidate_id"))
        for row in candidates
        if row.get("numeric_training_candidate") is True
    )
    mutations_by_project = project_mutations(candidates)

    status_rows: list[dict[str, Any]] = []
    error_counts = Counter()

    seen_packet_ids = set()
    duplicate_packet_ids = set()
    sequence_projects = set()
    for row in sequence_packets:
        packet = str(row.get("packet_id"))
        if packet in seen_packet_ids:
            duplicate_packet_ids.add(packet)
        seen_packet_ids.add(packet)
        sequence_projects.add(str(row.get("source_project") or ""))
        errors = validate_sequence_packet(row, mutations_by_project)
        error_counts.update(errors)
        status_rows.append({
            "record_type": "sequence_request_packet",
            "record_id": row.get("packet_id"),
            "source_project": row.get("source_project"),
            "valid": not errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": errors,
            "policy": "Validation only; not reviewed sequence evidence and not a numbering-flag update.",
        })

    feedback_candidate_coverage = []
    for row in feedback_packets:
        packet = str(row.get("packet_id"))
        if packet in seen_packet_ids:
            duplicate_packet_ids.add(packet)
        seen_packet_ids.add(packet)
        ids = [str(cid) for cid in (row.get("feedback_candidate_ids") or [])]
        feedback_candidate_coverage.extend(ids)
        errors = validate_feedback_packet(row, candidates_by_id, auth_template_by_candidate_id)
        error_counts.update(errors)
        status_rows.append({
            "record_type": "feedback_review_packet",
            "record_id": row.get("packet_id"),
            "source_project": row.get("source_project"),
            "feedback_candidate_ids": ids,
            "valid": not errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": errors,
            "policy": "Validation only; not authorization and not feedback intake.",
        })

    seen_action_ids = set()
    duplicate_action_ids = set()
    for row in unlock_actions:
        action_id = str(row.get("unlock_action_id"))
        if action_id in seen_action_ids:
            duplicate_action_ids.add(action_id)
        seen_action_ids.add(action_id)
        errors = validate_unlock_action(row)
        error_counts.update(errors)
        status_rows.append({
            "record_type": "unlock_action",
            "record_id": row.get("unlock_action_id"),
            "workstream": row.get("workstream"),
            "valid": not errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": errors,
            "policy": "Validation only; not approval, not claim readiness, and not production sync.",
        })

    if duplicate_packet_ids:
        error_counts.update({"duplicate_packet_id": len(duplicate_packet_ids)})
        for row in status_rows:
            if str(row.get("record_id")) in duplicate_packet_ids:
                row["valid"] = False
                row["errors"].append("duplicate_packet_id")
    if duplicate_action_ids:
        error_counts.update({"duplicate_unlock_action_id": len(duplicate_action_ids)})
        for row in status_rows:
            if str(row.get("record_id")) in duplicate_action_ids:
                row["valid"] = False
                row["errors"].append("duplicate_unlock_action_id")

    coverage_counts = Counter(feedback_candidate_coverage)
    missing_numeric_candidates = sorted(set(numeric_candidate_ids) - set(feedback_candidate_coverage))
    duplicate_candidate_coverage = sorted([cid for cid, count in coverage_counts.items() if count > 1])
    if missing_numeric_candidates:
        error_counts.update({"missing_numeric_candidate_packet_coverage": len(missing_numeric_candidates)})
    if duplicate_candidate_coverage:
        error_counts.update({"duplicate_numeric_candidate_packet_coverage": len(duplicate_candidate_coverage)})
    if sequence_projects != EXPECTED_SEQUENCE_PROJECTS:
        error_counts.update({"sequence_packet_project_set_mismatch": 1})
    if seen_action_ids != EXPECTED_ACTIONS:
        error_counts.update({"unlock_action_set_mismatch": 1})

    global_errors = []
    if missing_numeric_candidates:
        global_errors.append("missing_numeric_candidate_packet_coverage")
    if duplicate_candidate_coverage:
        global_errors.append("duplicate_numeric_candidate_packet_coverage")
    if sequence_projects != EXPECTED_SEQUENCE_PROJECTS:
        global_errors.append("sequence_packet_project_set_mismatch")
    if seen_action_ids != EXPECTED_ACTIONS:
        global_errors.append("unlock_action_set_mismatch")
    for row in status_rows:
        if global_errors:
            row["valid"] = False
            row["errors"].extend(global_errors)

    valid_rows = sum(1 for row in status_rows if row["valid"])
    invalid_rows = len(status_rows) - valid_rows
    write_jsonl(args.status_output, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "numeric_training_candidate_rows": len(numeric_candidate_ids),
        "sequence_packet_rows": len(sequence_packets),
        "feedback_packet_rows": len(feedback_packets),
        "unlock_action_rows": len(unlock_actions),
        "status_rows": len(status_rows),
        "valid_status_rows": valid_rows,
        "invalid_status_rows": invalid_rows,
        "all_operator_packets_valid": invalid_rows == 0,
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "missing_numeric_candidate_packet_coverage_rows": len(missing_numeric_candidates),
        "duplicate_numeric_candidate_packet_coverage_rows": len(duplicate_candidate_coverage),
        "sequence_packet_projects": sorted(sequence_projects),
        "expected_sequence_packet_projects": sorted(EXPECTED_SEQUENCE_PROJECTS),
        "unlock_action_ids": sorted(seen_action_ids),
        "expected_unlock_action_ids": sorted(EXPECTED_ACTIONS),
        "error_counts": dict(error_counts),
        "status_output": str(args.status_output),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validator checks operator packet consistency only; valid packets still require human review and do not unlock training, claims, deployment, or release.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status_rows": report["status_rows"],
        "valid_status_rows": report["valid_status_rows"],
        "invalid_status_rows": report["invalid_status_rows"],
        "all_operator_packets_valid": report["all_operator_packets_valid"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
