#!/usr/bin/env python3
"""Build a fail-closed contract for training label import eligibility."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "training_label_import_contract_report.json"

INPUTS = {
    "strict_supervised_jsonl": "datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl",
    "claim_eligible_jsonl": "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
    "label_provenance_audit": "reports/label_provenance_audit_report.json",
    "fireprot_reviewed_import_candidate": "reports/fireprot_reviewed_import_candidate_report.json",
    "wet_lab_feedback_preflight": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "feedback_training_import_semantic_guard": "reports/feedback_training_import_semantic_guard_report.json",
    "activity_risk_training_import_labels": "datasets/training/activity_risk_training_import_labels.jsonl",
    "activity_risk_training_import_label_validation": "reports/activity_risk_training_import_label_validation_report.json",
}

EVIDENCE_KEYS = ("reviewed", "source", "provenance", "authorization")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def jsonl_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path.relative_to(AI_ROOT)),
            "exists": False,
            "rows": 0,
            "invalid_json_rows": 0,
            "rows_with_reviewed_marker": 0,
            "rows_with_source_marker": 0,
            "rows_with_provenance_marker": 0,
            "rows_with_authorization_marker": 0,
        }

    rows = 0
    invalid_json_rows = 0
    reviewed = 0
    source = 0
    provenance = 0
    authorization = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            invalid_json_rows += 1
            continue
        if has_reviewed_marker(row):
            reviewed += 1
        if has_source_marker(row):
            source += 1
        if has_provenance_marker(row):
            provenance += 1
        if has_authorization_marker(row):
            authorization += 1

    return {
        "path": str(path.relative_to(AI_ROOT)),
        "exists": True,
        "rows": rows,
        "invalid_json_rows": invalid_json_rows,
        "rows_with_reviewed_marker": reviewed,
        "rows_with_source_marker": source,
        "rows_with_provenance_marker": provenance,
        "rows_with_authorization_marker": authorization,
    }


def has_any_key(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key, value in row.items():
        lower_key = key.lower()
        if any(token in lower_key for token in keys) and value not in (None, "", [], {}):
            return True
    return False


def has_reviewed_marker(row: dict[str, Any]) -> bool:
    status_values = {
        str(row.get(key, "")).lower()
        for key in ("review_status", "source_review_status", "curation_status", "validation_status")
    }
    return bool({"reviewed", "approved", "verified", "accepted"} & status_values) or bool(row.get("reviewed"))


def has_source_marker(row: dict[str, Any]) -> bool:
    return has_any_key(row, ("source", "receipt", "checksum", "citation", "doi", "pmid"))


def has_provenance_marker(row: dict[str, Any]) -> bool:
    return has_any_key(row, ("provenance", "lineage", "raw_source", "receipt", "checksum"))


def has_authorization_marker(row: dict[str, Any]) -> bool:
    return has_any_key(row, ("authorization", "authorized", "approved_for_training_import"))


def evidence(reviewed: bool, source: bool, provenance: bool, authorization: bool) -> dict[str, bool]:
    return {
        "reviewed": reviewed,
        "source": source,
        "provenance": provenance,
        "authorization": authorization,
    }


def contract(
    source_id: str,
    observed_rows: int,
    reported_ready_or_eligible_rows: int,
    observed_evidence: dict[str, bool],
    block_reason: str,
    notes: str,
    counted_as_trainable_rows: int = 0,
    training_import_eligible_label_source: bool = False,
) -> dict[str, Any]:
    has_complete_evidence = all(observed_evidence.get(key) is True for key in EVIDENCE_KEYS)
    return {
        "source_id": source_id,
        "observed_rows": observed_rows,
        "reported_ready_or_eligible_rows": reported_ready_or_eligible_rows,
        "counted_as_trainable_rows": counted_as_trainable_rows,
        "training_import_eligible_label_source": training_import_eligible_label_source,
        "evidence_required": list(EVIDENCE_KEYS),
        "evidence_observed": observed_evidence,
        "complete_evidence_observed": has_complete_evidence,
        "block_reason": block_reason,
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build training label import contract report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    paths = {name: AI_ROOT / rel for name, rel in INPUTS.items()}
    strict_profile = jsonl_profile(paths["strict_supervised_jsonl"])
    claim_profile = jsonl_profile(paths["claim_eligible_jsonl"])
    provenance_report = load_json(paths["label_provenance_audit"])
    fireprot_report = load_json(paths["fireprot_reviewed_import_candidate"])
    wet_lab_report = load_json(paths["wet_lab_feedback_preflight"])
    feedback_guard = load_json(paths["feedback_training_import_semantic_guard"])
    activity_risk_import_profile = jsonl_profile(paths["activity_risk_training_import_labels"])
    activity_risk_import_validation = load_json(paths["activity_risk_training_import_label_validation"])

    missing_inputs = [rel for name, rel in INPUTS.items() if not paths[name].exists()]

    observed_current_state = {
        "strict_supervised_jsonl_rows": strict_profile["rows"],
        "claim_eligible_jsonl_rows": claim_profile["rows"],
        "label_provenance_strict_rows": as_int(provenance_report.get("strict_rows")),
        "label_provenance_claim_eligible_rows": as_int(provenance_report.get("claim_eligible_rows")),
        "fireprot_ready_for_training_import_rows": as_int(
            fireprot_report.get("ready_for_training_import_rows")
        ),
        "fireprot_reviewed_import_candidate_rows": as_int(
            fireprot_report.get("reviewed_import_candidate_rows")
        ),
        "wet_lab_preflight_rows": as_int(wet_lab_report.get("preflight_rows")),
        "wet_lab_ready_for_training_import_rows": as_int(
            wet_lab_report.get("ready_for_training_import_rows")
        ),
        "wet_lab_authorized_candidate_rows": as_int(wet_lab_report.get("authorized_candidate_rows")),
        "numeric_feedback_training_import_eligible_rows": as_int(
            feedback_guard.get("numeric_training_import_eligible")
        ),
        "activity_risk_training_import_written_rows": activity_risk_import_profile["rows"],
        "activity_risk_training_import_validated_written_rows": as_int(
            activity_risk_import_validation.get("training_import_written_rows")
        ),
        "feedback_guard_strict_supervised_rows": as_int(feedback_guard.get("strict_supervised_rows")),
        "feedback_guard_claim_eligible_rows": as_int(feedback_guard.get("claim_eligible_rows")),
    }

    source_contracts = [
        contract(
            "strict_supervised_repaired_verified_jsonl",
            strict_profile["rows"],
            strict_profile["rows"],
            evidence(
                strict_profile["rows"] > 0
                and strict_profile["rows_with_reviewed_marker"] == strict_profile["rows"],
                strict_profile["rows"] > 0
                and strict_profile["rows_with_source_marker"] == strict_profile["rows"],
                strict_profile["rows"] > 0
                and strict_profile["rows_with_provenance_marker"] == strict_profile["rows"],
                False,
            ),
            "no rows and no formal training-import authorization recorded",
            "Strict repaired/verified rows are not automatically a training-import authorization.",
        ),
        contract(
            "claim_eligible_supervised_jsonl",
            claim_profile["rows"],
            claim_profile["rows"],
            evidence(
                claim_profile["rows"] > 0
                and claim_profile["rows_with_reviewed_marker"] == claim_profile["rows"],
                claim_profile["rows"] > 0
                and claim_profile["rows_with_source_marker"] == claim_profile["rows"],
                claim_profile["rows"] > 0
                and claim_profile["rows_with_provenance_marker"] == claim_profile["rows"],
                False,
            ),
            "no claim-eligible rows and no formal training-import authorization recorded",
            "Claim eligibility is a hard-gated label provenance state, not a model claim release.",
        ),
        contract(
            "label_provenance_audit",
            as_int(provenance_report.get("strict_rows")) + as_int(provenance_report.get("claim_eligible_rows")),
            as_int(provenance_report.get("claim_eligible_rows")),
            evidence(
                as_int(provenance_report.get("claim_eligible_rows")) > 0,
                bool(provenance_report.get("source_counts")),
                bool(provenance_report.get("provenance_flag_counts")),
                False,
            ),
            str(provenance_report.get("hard_gate_status") or "blocked_no_authorized_claim_eligible_source"),
            "The audit reports provenance state only; it does not perform a supervised import.",
        ),
        contract(
            "fireprot_reviewed_import_candidates",
            as_int(fireprot_report.get("reviewed_import_candidate_rows")),
            as_int(fireprot_report.get("ready_for_training_import_rows")),
            evidence(
                as_int(fireprot_report.get("reviewed_import_candidate_rows")) > 0,
                bool(fireprot_report.get("candidates")),
                bool(fireprot_report.get("validation")),
                False,
            ),
            "blocked_until_separate_formal_supervised_import_authorization",
            str(fireprot_report.get("policy") or "Reviewed candidates are not automatic training labels."),
        ),
        contract(
            "wet_lab_feedback_preflight",
            as_int(wet_lab_report.get("preflight_rows")),
            as_int(wet_lab_report.get("ready_for_training_import_rows")),
            evidence(
                as_int(wet_lab_report.get("authorized_candidate_rows")) > 0,
                bool(wet_lab_report.get("candidates")),
                bool(wet_lab_report.get("authorization_report")),
                as_int(wet_lab_report.get("authorized_candidate_rows")) > 0,
            ),
            "preflight_is_read_only_and_current_ready_rows_are_zero",
            str(wet_lab_report.get("policy") or "Preflight rows never modify training labels automatically."),
        ),
        contract(
            "numeric_feedback_training_import_semantic_guard",
            as_int(feedback_guard.get("numeric_training_import_eligible")),
            as_int(feedback_guard.get("numeric_training_import_eligible")),
            evidence(
                as_int(feedback_guard.get("numeric_training_import_eligible")) > 0,
                bool(feedback_guard.get("checked_reports")),
                bool(feedback_guard.get("source_report_support")),
                as_int(feedback_guard.get("numeric_training_import_eligible")) > 0,
            ),
            "numeric wet-lab feedback import eligible rows are present; qualitative feedback is excluded",
            str(feedback_guard.get("policy") or "Numeric feedback import requires independent source support."),
            counted_as_trainable_rows=as_int(feedback_guard.get("numeric_training_import_eligible")),
            training_import_eligible_label_source=as_int(feedback_guard.get("numeric_training_import_eligible")) > 0,
        ),
    ]

    true_claim_release_flags = []
    for report_name, report in {
        "label_provenance_audit": provenance_report,
        "fireprot_reviewed_import_candidate": fireprot_report,
        "wet_lab_feedback_preflight": wet_lab_report,
        "feedback_training_import_semantic_guard": feedback_guard,
    }.items():
        for key in ("safe_for_model_claim", "release_ready"):
            if report.get(key) is True:
                true_claim_release_flags.append({"report": report_name, "field": key, "observed": True})

    eligible_sources = [
        item["source_id"]
        for item in source_contracts
        if item.get("training_import_eligible_label_source") is True
    ]
    eligible_rows = sum(as_int(item["counted_as_trainable_rows"]) for item in source_contracts)
    contract_totals = {
        "training_import_eligible_label_sources": len(eligible_sources),
        "training_import_eligible_rows": eligible_rows,
        "counted_as_trainable_rows": sum(as_int(item["counted_as_trainable_rows"]) for item in source_contracts),
    }

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input_artifacts": INPUTS,
        "missing_inputs": missing_inputs,
        "jsonl_profiles": {
            "strict_supervised_jsonl": strict_profile,
            "claim_eligible_jsonl": claim_profile,
        },
        "observed_current_state": observed_current_state,
        "source_contracts": source_contracts,
        "contract_totals": contract_totals,
        "training_import_written_rows": activity_risk_import_profile["rows"],
        "training_import_validated_written_rows": as_int(
            activity_risk_import_validation.get("training_import_written_rows")
        ),
        "training_import_eligible_label_sources": eligible_sources,
        "no_training_import_eligible_label_source": not eligible_sources,
        "input_true_claim_release_flags": true_claim_release_flags,
        "safe_for_training_import": bool(eligible_sources) and not missing_inputs,
        "safe_for_model_claim": False,
        "release_ready": False,
        "success": not missing_inputs and not true_claim_release_flags,
        "policy": (
            "This contract is fail-closed and read-only. Strict supervised, claim-eligible, "
            "reviewed external import, wet-lab preflight, or numeric feedback rows become trainable only "
            "with reviewed source evidence, source receipt, provenance, and explicit import authorization. "
            "Training import eligibility remains separate from model-quality and release claims."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "strict_supervised_rows": observed_current_state["strict_supervised_jsonl_rows"],
        "claim_eligible_rows": observed_current_state["claim_eligible_jsonl_rows"],
        "fireprot_ready_for_training_import_rows": observed_current_state[
            "fireprot_ready_for_training_import_rows"
        ],
        "wet_lab_preflight_rows": observed_current_state["wet_lab_preflight_rows"],
        "numeric_feedback_training_import_eligible_rows": observed_current_state[
            "numeric_feedback_training_import_eligible_rows"
        ],
        "training_import_written_rows": activity_risk_import_profile["rows"],
        "training_import_validated_written_rows": as_int(
            activity_risk_import_validation.get("training_import_written_rows")
        ),
        "training_import_eligible_label_sources": len(eligible_sources),
        "safe_for_training_import": bool(eligible_sources) and not missing_inputs,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
