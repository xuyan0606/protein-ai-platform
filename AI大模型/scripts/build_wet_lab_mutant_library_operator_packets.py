#!/usr/bin/env python3
"""Build operator-facing review packets for wet-lab mutant-library unlocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
AUTH_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
SEQ_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.template.jsonl"
SEQ_EVIDENCE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_sequence_evidence_audit.jsonl"
SEQ_PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_sequence_request_packets.jsonl"
FEEDBACK_PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_review_packets.jsonl"
UNLOCK_ACTIONS = AI_ROOT / "datasets" / "governance" / "wet_lab_mutant_library_unlock_actions.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_operator_packet_report.json"

MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def mutation_sort_key(mutation: str) -> tuple[int, str]:
    match = MUTATION_RE.match(str(mutation))
    return (int(match.group(2)), mutation) if match else (10**9, str(mutation))


def project_mutations(candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        project = str(row.get("source_project") or "")
        for mutation in row.get("mutation_set") or []:
            if MUTATION_RE.match(str(mutation)):
                found[project].add(str(mutation))
    return {project: sorted(values, key=mutation_sort_key) for project, values in found.items()}


def mutation_checks_required(mutations: list[str]) -> list[dict[str, Any]]:
    checks = []
    for mutation in mutations:
        match = MUTATION_RE.match(mutation)
        if not match:
            continue
        wt, position, mutant = match.groups()
        checks.append({
            "mutation": mutation,
            "reported_wild_type": wt,
            "position": int(position),
            "reported_mutant": mutant,
            "required_check": f"parent_sequence[{position}] == {wt}",
        })
    return checks


def packet_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def source_rejection_summary(sequence_evidence_rows: list[dict[str, Any]], project: str) -> list[dict[str, Any]]:
    rows = []
    for row in sequence_evidence_rows:
        if row.get("project_id") not in {project, None}:
            continue
        rows.append({
            "sequence_evidence_id": row.get("sequence_evidence_id"),
            "source_type": row.get("source_type"),
            "source_path": row.get("source_path"),
            "decision": row.get("decision"),
            "sequence_length": row.get("sequence_length"),
            "wild_type_match_count": row.get("wild_type_match_count"),
            "mutation_count": row.get("mutation_count"),
            "blockers": row.get("blockers") or [],
            "failed_mutation_checks_preview": (row.get("failed_mutation_checks") or [])[:5],
        })
    return rows[:12]


def build_sequence_packets(
    candidates: list[dict[str, Any]],
    sequence_template_rows: list[dict[str, Any]],
    sequence_evidence_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mutations_by_project = project_mutations(candidates)
    candidate_counts = Counter(str(row.get("source_project") or "") for row in candidates)
    parseable_counts = Counter()
    blocked_counts = Counter()
    for row in candidates:
        project = str(row.get("source_project") or "")
        if row.get("mutation_set") and not row.get("unresolved_variant_tokens"):
            parseable_counts[project] += 1
        if "numbering_not_verified" in (row.get("blocked_from_feedback_intake_reasons") or []):
            blocked_counts[project] += 1

    template_by_project = {str(row.get("project_id")): row for row in sequence_template_rows}
    packets = []
    for project in ["16B", "4G"]:
        mutations = mutations_by_project.get(project, [])
        template = template_by_project.get(project, {})
        packets.append({
            "packet_id": f"wetlab-sequence-request-{project.lower()}-001",
            "workstream": "wet_lab_parent_sequence_review",
            "source_project": project,
            "status": "blocked_waiting_for_reviewed_parent_sequence",
            "candidate_rows": candidate_counts.get(project, 0),
            "parseable_mutation_rows": parseable_counts.get(project, 0),
            "numbering_blocked_candidate_rows": blocked_counts.get(project, 0),
            "known_mutation_count": len(mutations),
            "known_mutations": mutations,
            "mutation_wild_type_checks_required": mutation_checks_required(mutations),
            "sequence_intake_target": "datasets/feedback/wet_lab_mutant_library_project_sequences.local.jsonl",
            "sequence_intake_template_row": template,
            "required_fields": [
                "project_id",
                "sequence_id",
                "sequence_version",
                "sequence",
                "sequence_source",
                "source_file",
                "reviewer",
                "reviewed_at",
                "review_basis",
                "approved_for_numbering_audit=true",
                "residual_risks=[]",
            ],
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_project_sequence_intake.py",
            "next_audit_command": "python3 scripts/build_wet_lab_mutant_library_numbering_audit_from_project_sequences.py",
            "rejected_or_unaccepted_sequence_evidence_preview": source_rejection_summary(sequence_evidence_rows, project),
            "completion_condition": "Validator accepts a reviewed parent sequence and all project mutation WT residues match; numbering audit still must run before any candidate flag can change.",
            "policy": "Operator packet only; does not create reviewed sequence evidence, update numbering flags, or add training labels.",
        })
    return packets


def build_feedback_packets(candidates: list[dict[str, Any]], auth_template_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    auth_by_candidate = {str(row.get("feedback_candidate_id")): row for row in auth_template_rows}
    numeric_candidates = [row for row in candidates if row.get("numeric_training_candidate") is True]
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in numeric_candidates:
        grouped[(str(row.get("source_project")), str(row.get("variant")), str(row.get("metric_name")))].append(row)

    packets = []
    for (project, variant, metric), rows in sorted(grouped.items(), key=lambda item: (item[0][0], mutation_sort_key(item[0][1]), item[0][2])):
        candidate_summaries = []
        for row in sorted(rows, key=lambda value: str(value.get("feedback_candidate_id"))):
            cid = str(row.get("feedback_candidate_id"))
            candidate_summaries.append({
                "feedback_candidate_id": cid,
                "authorization_template_id": (auth_by_candidate.get(cid) or {}).get("authorization_id"),
                "mutation_set": row.get("mutation_set"),
                "assay_type": row.get("assay_type"),
                "metric_name": row.get("metric_name"),
                "raw_value_numeric": row.get("raw_value_numeric"),
                "control_value_numeric": row.get("control_value_numeric"),
                "vs_control_ratio": row.get("vs_control_ratio"),
                "outcome_candidate": row.get("outcome_candidate"),
                "confidence_tier": row.get("confidence_tier"),
                "batch_id": row.get("batch_id"),
                "sample_id": row.get("sample_id"),
                "control_sample_id": row.get("control_sample_id"),
                "source_file": row.get("source_file"),
                "source_row_index": row.get("source_row_index"),
            })
        packets.append({
            "packet_id": packet_id("wetlab-feedback-review", project, variant, metric),
            "workstream": "wet_lab_feedback_authorization_review",
            "source_project": project,
            "variant": variant,
            "metric_name": metric,
            "candidate_rows": len(rows),
            "feedback_candidate_ids": [row.get("feedback_candidate_id") for row in rows],
            "candidate_summaries": candidate_summaries,
            "authorization_target": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "authorization_template": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "required_review_checks": [
                "source_trace_reviewed",
                "numbering_reviewed",
                "unit_condition_reviewed",
                "batch_control_reviewed",
                "replicate_policy_reviewed",
                "qc_decision pass/pass_with_conditions",
                "reviewer/reviewed_at/authorization_basis filled",
                "residual_risks=[] for approved rows",
            ],
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "completion_condition": "A copied authorization row validates as approved_for_feedback_intake; later preflight/apply-plan still remain separate gates.",
            "status": "blocked_waiting_for_human_authorization",
            "policy": "Review packet only; does not authorize intake and does not append to experiment_feedback.local.jsonl.",
        })
    return packets


def build_unlock_actions(sequence_packets: list[dict[str, Any]], feedback_packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = [
        {
            "unlock_action_id": "wetlab-mutlib-A001",
            "execution_order": 1,
            "workstream": "wet_lab_feedback_authorization_review",
            "status": "started_blocked",
            "packet_source": "datasets/feedback/wet_lab_mutant_library_feedback_review_packets.jsonl",
            "decision_input": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "target_rows": len(feedback_packets),
            "completion_condition": "approved authorization rows validate and generate preflight rows; no direct training append.",
            "requires_human_input": True,
        },
        {
            "unlock_action_id": "wetlab-mutlib-A002",
            "execution_order": 2,
            "workstream": "wet_lab_parent_sequence_review",
            "status": "started_blocked",
            "packet_source": "datasets/feedback/wet_lab_mutant_library_sequence_request_packets.jsonl",
            "decision_input": "datasets/feedback/wet_lab_mutant_library_project_sequences.local.jsonl",
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_project_sequence_intake.py",
            "target_rows": len(sequence_packets),
            "completion_condition": "16B and 4G reviewed parent sequences pass WT mutation checks.",
            "requires_human_input": True,
        },
        {
            "unlock_action_id": "wetlab-mutlib-A003",
            "execution_order": 3,
            "workstream": "wet_lab_numbering_audit",
            "status": "started_blocked",
            "packet_source": "datasets/feedback/wet_lab_mutant_library_numbering_audit_from_project_sequences.jsonl",
            "decision_input": "datasets/feedback/wet_lab_mutant_library_project_sequences.local.jsonl",
            "validator_command": "python3 scripts/build_wet_lab_mutant_library_numbering_audit_from_project_sequences.py",
            "target_rows": 0,
            "completion_condition": "Approved project sequence rows produce numbering audit rows; candidate flag update remains a separate reviewed apply gate.",
            "requires_human_input": True,
        },
        {
            "unlock_action_id": "wetlab-mutlib-A004",
            "execution_order": 4,
            "workstream": "wet_lab_feedback_apply_plan",
            "status": "started_blocked",
            "packet_source": "datasets/feedback/wet_lab_mutant_library_feedback_intake_apply_plan.jsonl",
            "decision_input": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
            "validator_command": "python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
            "target_rows": 0,
            "completion_condition": "Preflight rows become apply-plan rows only after explicit user authorization; experiment_feedback.local.jsonl is not modified by this action.",
            "requires_human_input": True,
        },
    ]
    for action in actions:
        action["policy"] = "Local operator action only; not a reviewed decision, not approval, not model claim readiness, and not a production sync."
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab mutant-library operator packets")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--authorization-template", type=Path, default=AUTH_TEMPLATE)
    parser.add_argument("--sequence-template", type=Path, default=SEQ_TEMPLATE)
    parser.add_argument("--sequence-evidence", type=Path, default=SEQ_EVIDENCE)
    parser.add_argument("--sequence-packets", type=Path, default=SEQ_PACKETS)
    parser.add_argument("--feedback-packets", type=Path, default=FEEDBACK_PACKETS)
    parser.add_argument("--unlock-actions", type=Path, default=UNLOCK_ACTIONS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    auth_template_rows = load_jsonl(args.authorization_template)
    sequence_template_rows = load_jsonl(args.sequence_template)
    sequence_evidence_rows = load_jsonl(args.sequence_evidence)

    sequence_packets = build_sequence_packets(candidates, sequence_template_rows, sequence_evidence_rows)
    feedback_packets = build_feedback_packets(candidates, auth_template_rows)
    unlock_actions = build_unlock_actions(sequence_packets, feedback_packets)

    write_jsonl(args.sequence_packets, sequence_packets)
    write_jsonl(args.feedback_packets, feedback_packets)
    write_jsonl(args.unlock_actions, unlock_actions)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "sequence_request_packet_rows": len(sequence_packets),
        "feedback_review_packet_rows": len(feedback_packets),
        "unlock_action_rows": len(unlock_actions),
        "source_projects": sorted({row.get("source_project") for row in candidates if row.get("source_project")}),
        "sequence_request_packets": str(args.sequence_packets),
        "feedback_review_packets": str(args.feedback_packets),
        "unlock_actions": str(args.unlock_actions),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Operator packets organize human review; they do not approve intake, alter numbering, train a model, deploy, sync, or release.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequence_request_packet_rows": report["sequence_request_packet_rows"],
        "feedback_review_packet_rows": report["feedback_review_packet_rows"],
        "unlock_action_rows": report["unlock_action_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
