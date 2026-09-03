#!/usr/bin/env python3
"""Build a source-bound audit of governance review bundle completion gaps."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = AI_ROOT / "datasets" / "governance" / "governance_review_bundle.jsonl"
BUNDLE_REPORT = AI_ROOT / "reports" / "governance_review_bundle_report.json"
BUNDLE_VALIDATION = AI_ROOT / "reports" / "governance_review_bundle_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p478_governance_review_bundle_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p478_governance_review_bundle_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/governance_review_bundle_report.json",
        "source_validation_report": "reports/governance_review_bundle_validation_report.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Governance review bundle audit only; bundle rows are not human approval, training data, model claims, customer delivery, release, or production authorization.",
    }


def main() -> int:
    bundle_rows = load_jsonl(BUNDLE)
    bundle_report = load_json(BUNDLE_REPORT)
    validation = load_json(BUNDLE_VALIDATION)
    validation_by_id = {
        str(row.get("bundle_id")): row
        for row in validation.get("records", [])
        if row.get("bundle_id")
    }
    rows: list[dict[str, Any]] = []

    for row in bundle_rows:
        bundle_id = row.get("bundle_id")
        validation_record = validation_by_id.get(str(bundle_id), {})
        rows.append(base(
            f"p478-governance-review-bundle::{bundle_id}",
            "governance_review_bundle_item_gap",
            {
                "bundle_id": bundle_id,
                "workstream": row.get("workstream"),
                "priority": row.get("priority"),
                "review_order": row.get("review_order"),
                "source_artifact": row.get("source_artifact"),
                "source_row_id": row.get("source_row_id"),
                "decision_input": row.get("decision_input"),
                "validator_report": row.get("validator_report"),
                "current_status": row.get("current_status"),
                "human_review_required": row.get("human_review_required"),
                "no_auto_approval": row.get("no_auto_approval"),
                "bundle_completion_ready": row.get("completion_ready"),
                "validation_valid": validation_record.get("valid"),
                "validation_completion_ready": validation_record.get("completion_ready"),
                "blocking_claims": row.get("blocking_claims") or [],
            },
            "governance review bundle item remains open and requires explicit human completion decision",
        ) | {
            "bundle_id": bundle_id,
            "workstream": row.get("workstream"),
            "priority": row.get("priority"),
            "review_order": row.get("review_order"),
            "current_status": row.get("current_status"),
            "bundle_completion_ready": row.get("completion_ready"),
            "validation_valid": validation_record.get("valid"),
            "validation_completion_ready": validation_record.get("completion_ready"),
            "completion_ready": False,
        })

    workstream_counts = dict(sorted(Counter(str(row.get("workstream")) for row in bundle_rows).items()))
    status_counts = dict(sorted(Counter(str(row.get("current_status")) for row in bundle_rows).items()))
    rows.append(base(
        "p478-governance-review-bundle-summary",
        "governance_review_bundle_summary_gap",
        {
            "bundle_rows": bundle_report.get("bundle_rows"),
            "open_rows": bundle_report.get("open_rows"),
            "completion_ready_rows": bundle_report.get("completion_ready_rows"),
            "human_review_required_rows": bundle_report.get("human_review_required_rows"),
            "no_auto_approval_rows": bundle_report.get("no_auto_approval_rows"),
            "validation_valid_rows": validation.get("valid_rows"),
            "validation_invalid_rows": validation.get("invalid_rows"),
            "validation_open_rows": validation.get("open_rows"),
            "validation_completion_ready_rows": validation.get("completion_ready_rows"),
            "all_source_rows_covered": validation.get("all_source_rows_covered"),
            "all_rows_valid": validation.get("all_rows_valid"),
            "bundle_ready": bundle_report.get("ready"),
            "validation_ready": validation.get("ready"),
            "workstream_counts": workstream_counts,
            "status_counts": status_counts,
        },
        "governance review bundle has no completion-ready rows and cannot unlock claims, delivery, release, or production execution",
    ) | {
        "bundle_rows": bundle_report.get("bundle_rows"),
        "open_rows": bundle_report.get("open_rows"),
        "completion_ready_rows": bundle_report.get("completion_ready_rows"),
        "validation_valid_rows": validation.get("valid_rows"),
        "validation_open_rows": validation.get("open_rows"),
        "workstream_counts": workstream_counts,
        "status_counts": status_counts,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "bundle_audit_rows": len(bundle_rows),
        "summary_audit_rows": 1,
        "bundle_rows": bundle_report.get("bundle_rows"),
        "open_rows": bundle_report.get("open_rows"),
        "completion_ready_rows": bundle_report.get("completion_ready_rows"),
        "human_review_required_rows": bundle_report.get("human_review_required_rows"),
        "no_auto_approval_rows": bundle_report.get("no_auto_approval_rows"),
        "bundle_ready": bundle_report.get("ready"),
        "bundle_safe_for_model_claim": bundle_report.get("safe_for_model_claim"),
        "bundle_release_ready": bundle_report.get("release_ready"),
        "validation_valid_rows": validation.get("valid_rows"),
        "validation_invalid_rows": validation.get("invalid_rows"),
        "validation_open_rows": validation.get("open_rows"),
        "validation_completion_ready_rows": validation.get("completion_ready_rows"),
        "all_source_rows_covered": validation.get("all_source_rows_covered"),
        "all_rows_valid": validation.get("all_rows_valid"),
        "validation_ready": validation.get("ready"),
        "workstream_counts": workstream_counts,
        "status_counts": status_counts,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p478_governance_review_bundle_gap_audit.jsonl",
        "policy": "P478 audit only. Governance review bundle rows remain open until explicit human decisions complete each workstream.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "bundle_audit_rows": report["bundle_audit_rows"],
        "open_rows": report["open_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "validation_ready": report["validation_ready"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
