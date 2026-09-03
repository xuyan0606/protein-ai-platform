#!/usr/bin/env python3
"""Validate human-review summaries across launch, closeout, customer and release reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH = AI_ROOT / "reports" / "human_review_launch_board_report.json"
LAUNCH_VALIDATION = AI_ROOT / "reports" / "human_review_launch_board_validation_report.json"
CLOSEOUT = AI_ROOT / "reports" / "human_review_closeout_board_report.json"
CLOSEOUT_VALIDATION = AI_ROOT / "reports" / "human_review_closeout_board_validation_report.json"
CUSTOMER = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
MANIFEST = AI_ROOT / "reports" / "local_release_manifest.json"
OUT = AI_ROOT / "reports" / "human_review_release_consistency_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human review release consistency")
    parser.add_argument("--report", type=Path, default=OUT)
    args = parser.parse_args()

    launch = load_json(LAUNCH)
    launch_validation = load_json(LAUNCH_VALIDATION)
    closeout = load_json(CLOSEOUT)
    closeout_validation = load_json(CLOSEOUT_VALIDATION)
    customer = load_json(CUSTOMER)
    manifest = load_json(MANIFEST)
    customer_summary = customer.get("human_review_prepared_summary") or {}
    readiness = manifest.get("readiness_summary") or {}

    checks = [
        check("launch validation success", launch_validation.get("success") is True, launch_validation.get("success"), True),
        check("closeout validation success", closeout_validation.get("success") is True, closeout_validation.get("success"), True),
        check("launch rows match closeout rows", launch.get("launch_rows") == closeout.get("closeout_rows"), {"launch": launch.get("launch_rows"), "closeout": closeout.get("closeout_rows")}, "same"),
        check("launch packets match closeout prepared packets", launch.get("total_packet_rows") == closeout.get("total_prepared_packet_rows"), {"launch": launch.get("total_packet_rows"), "closeout": closeout.get("total_prepared_packet_rows")}, "same"),
        check("customer launch rows match", customer_summary.get("launch_rows") == launch.get("launch_rows"), customer_summary.get("launch_rows"), launch.get("launch_rows")),
        check("customer packet rows match", customer_summary.get("total_packet_rows") == launch.get("total_packet_rows"), customer_summary.get("total_packet_rows"), launch.get("total_packet_rows")),
        check("customer closeout rows match", customer_summary.get("closeout_rows") == closeout.get("closeout_rows"), customer_summary.get("closeout_rows"), closeout.get("closeout_rows")),
        check("customer formal rows match", customer_summary.get("total_formal_decision_rows") == closeout.get("total_formal_decision_rows"), customer_summary.get("total_formal_decision_rows"), closeout.get("total_formal_decision_rows")),
        check("manifest launch rows match", readiness.get("human_review_launch_rows") == launch.get("launch_rows"), readiness.get("human_review_launch_rows"), launch.get("launch_rows")),
        check("manifest launch packet rows match", readiness.get("human_review_launch_total_packet_rows") == launch.get("total_packet_rows"), readiness.get("human_review_launch_total_packet_rows"), launch.get("total_packet_rows")),
        check("manifest closeout rows match", readiness.get("human_review_closeout_rows") == closeout.get("closeout_rows"), readiness.get("human_review_closeout_rows"), closeout.get("closeout_rows")),
        check("manifest closeout prepared rows match", readiness.get("human_review_closeout_total_prepared_packet_rows") == closeout.get("total_prepared_packet_rows"), readiness.get("human_review_closeout_total_prepared_packet_rows"), closeout.get("total_prepared_packet_rows")),
        check("manifest closeout formal rows match", readiness.get("human_review_closeout_total_formal_decision_rows") == closeout.get("total_formal_decision_rows"), readiness.get("human_review_closeout_total_formal_decision_rows"), closeout.get("total_formal_decision_rows")),
        check("completion remains blocked", (launch.get("completion_ready_rows") or 0) == 0 and (closeout.get("completion_ready_rows") or 0) == 0 and (customer_summary.get("completion_ready_rows") or 0) == 0 and (readiness.get("human_review_closeout_completion_ready_rows") or 0) == 0, {"launch": launch.get("completion_ready_rows"), "closeout": closeout.get("completion_ready_rows"), "customer": customer_summary.get("completion_ready_rows"), "manifest": readiness.get("human_review_closeout_completion_ready_rows")}, 0),
        check("customer delivery remains blocked", customer.get("ready") is False and readiness.get("customer_delivery_ready") is False, {"customer": customer.get("ready"), "manifest": readiness.get("customer_delivery_ready")}, False),
        check("release remains blocked", manifest.get("release_ready") is False, manifest.get("release_ready"), False),
    ]
    failures = [row for row in checks if not row["passed"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checks": checks,
        "failures": failures,
        "launch_rows": launch.get("launch_rows"),
        "closeout_rows": closeout.get("closeout_rows"),
        "total_prepared_packet_rows": closeout.get("total_prepared_packet_rows"),
        "total_formal_decision_rows": closeout.get("total_formal_decision_rows"),
        "completion_ready_rows": closeout.get("completion_ready_rows"),
        "customer_ready": False,
        "release_ready": False,
        "policy": "Consistency validation only. Human-review preparation does not grant formal decisions, customer delivery, claims, training, ordering, or release readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "failures": len(failures), "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
