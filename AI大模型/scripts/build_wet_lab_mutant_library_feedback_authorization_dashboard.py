#!/usr/bin/env python3
"""Build a human-facing dashboard for wet-lab feedback authorization review."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist_status.jsonl"
VALIDATION_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_validation_report.json"
DASHBOARD_ITEMS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_dashboard_items.jsonl"
DASHBOARD_JSON = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard.json"
DASHBOARD_MD = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard.md"

PRIORITY_ORDER = {
    "critical_tradeoff_review": 0,
    "medium_mixed_benefit_review": 1,
    "standard_multi_property_review": 2,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def ratio_sort_value(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else -1.0


def row_priority(row: dict[str, Any]) -> tuple[int, str, str]:
    qc = row.get("qc_context") if isinstance(row.get("qc_context"), dict) else {}
    priority = str(qc.get("review_priority") or "")
    return (PRIORITY_ORDER.get(priority, 99), str(row.get("variant") or ""), str(row.get("metric_name") or ""))


def build_variant_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[str(row.get("variant") or "")].append(row)

    summaries: list[dict[str, Any]] = []
    for variant, variant_rows in by_variant.items():
        priority_counts = Counter(
            str((row.get("qc_context") or {}).get("review_priority"))
            for row in variant_rows
            if isinstance(row.get("qc_context"), dict)
        )
        outcome_counts = Counter(str(row.get("outcome_candidate") or "") for row in variant_rows)
        ratios = [ratio_sort_value(row.get("vs_control_ratio")) for row in variant_rows]
        top_priority = min(
            (str((row.get("qc_context") or {}).get("review_priority") or "") for row in variant_rows),
            key=lambda priority: PRIORITY_ORDER.get(priority, 99),
        )
        summaries.append({
            "variant": variant,
            "source_project": variant_rows[0].get("source_project"),
            "review_priority": top_priority,
            "metric_rows": len(variant_rows),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "ratio_min": min(ratios) if ratios else None,
            "ratio_max": max(ratios) if ratios else None,
            "authorized_rows": sum(1 for row in variant_rows if row.get("authorized_for_feedback_intake") is True),
            "blocked_rows": sum(1 for row in variant_rows if row.get("worklist_status") != "authorized_ready_for_preflight"),
            "requires_human_input": True,
            "completion_ready": False,
            "metric_review_rows": [
                {
                    "feedback_candidate_id": row.get("feedback_candidate_id"),
                    "authorization_template_id": row.get("authorization_template_id"),
                    "metric_name": row.get("metric_name"),
                    "metric_class": row.get("metric_class"),
                    "outcome_candidate": row.get("outcome_candidate"),
                    "vs_control_ratio": row.get("vs_control_ratio"),
                    "worklist_status": row.get("worklist_status"),
                    "source_file": row.get("source_file"),
                    "source_row_index": row.get("source_row_index"),
                }
                for row in sorted(variant_rows, key=lambda item: str(item.get("metric_name") or ""))
            ],
        })
    return sorted(summaries, key=lambda row: (PRIORITY_ORDER.get(str(row.get("review_priority")), 99), str(row.get("variant"))))


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Variant | Priority | Metrics | Outcomes | Ratio range | Authorized | Status |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for row in rows:
        outcomes = ", ".join(f"{key}:{value}" for key, value in (row.get("outcome_counts") or {}).items())
        ratio_min = row.get("ratio_min")
        ratio_max = row.get("ratio_max")
        ratio_range = ""
        if ratio_min is not None and ratio_max is not None:
            ratio_range = f"{ratio_min:.4f}-{ratio_max:.4f}"
        status = "blocked_human_authorization_required"
        lines.append(
            f"| {row.get('variant')} | {row.get('review_priority')} | {row.get('metric_rows')} | "
            f"{outcomes} | {ratio_range} | {row.get('authorized_rows')} | {status} |"
        )
    return "\n".join(lines)


def build_markdown(report: dict[str, Any], variant_rows: list[dict[str, Any]]) -> str:
    commands = report["recommended_operator_commands"]
    lines = [
        "# Wet-lab Feedback Authorization Dashboard",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This dashboard is local review navigation only. It is not an authorization, not feedback preflight, and not a training label.",
        "",
        "## Summary",
        "",
        f"- Worklist rows: {report['authorization_worklist_rows']}",
        f"- Valid worklist rows: {report['valid_worklist_rows']}",
        f"- Authorized rows: {report['authorized_rows']}",
        f"- Critical tradeoff rows: {report['critical_tradeoff_worklist_rows']}",
        f"- Requires human input rows: {report['requires_human_input_rows']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Variant Queue",
        "",
        markdown_table(variant_rows),
        "",
        "## Local Commands",
        "",
    ]
    lines.extend(f"1. `{command}`" for command in commands)
    lines.extend([
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization dashboard")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--dashboard-items", type=Path, default=DASHBOARD_ITEMS)
    parser.add_argument("--dashboard-json", type=Path, default=DASHBOARD_JSON)
    parser.add_argument("--dashboard-md", type=Path, default=DASHBOARD_MD)
    args = parser.parse_args()

    worklist = sorted(load_jsonl(args.worklist), key=row_priority)
    status_rows = load_jsonl(args.status)
    validation = load_json(args.validation_report)
    variant_rows = build_variant_summary(worklist)

    commands = [
        "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "python3 scripts/build_wet_lab_mutant_library_feedback_authorization_worklist.py",
        "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_worklist.py",
        "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
        "python3 scripts/run_safe_training_pipeline.py",
    ]

    write_jsonl(args.dashboard_items, variant_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "authorization_worklist_rows": len(worklist),
        "valid_worklist_rows": validation.get("valid_worklist_rows"),
        "invalid_worklist_rows": validation.get("invalid_worklist_rows"),
        "all_numeric_candidates_covered": bool(validation.get("all_numeric_candidates_covered")),
        "variant_review_rows": len(variant_rows),
        "authorized_rows": sum(1 for row in worklist if row.get("authorized_for_feedback_intake") is True),
        "critical_tradeoff_worklist_rows": sum(
            1
            for row in worklist
            if isinstance(row.get("qc_context"), dict)
            and row["qc_context"].get("review_priority") == "critical_tradeoff_review"
        ),
        "completion_ready_rows": sum(1 for row in status_rows if row.get("completion_ready") is True),
        "requires_human_input_rows": sum(1 for row in status_rows if row.get("requires_human_input") is True),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": [row["variant"] for row in variant_rows],
        "recommended_operator_commands": commands,
        "dashboard_items": str(args.dashboard_items),
        "dashboard_md": str(args.dashboard_md),
        "policy": "Dashboard only; not an authorization, not feedback preflight, and not a training label. Human authorization decisions must be written separately and validated before any preflight or intake can proceed.",
    }
    args.dashboard_json.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.dashboard_md.write_text(build_markdown(report, variant_rows), encoding="utf-8")
    print(json.dumps({
        "variant_review_rows": report["variant_review_rows"],
        "authorization_worklist_rows": report["authorization_worklist_rows"],
        "authorized_rows": report["authorized_rows"],
        "dashboard": str(args.dashboard_md),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
