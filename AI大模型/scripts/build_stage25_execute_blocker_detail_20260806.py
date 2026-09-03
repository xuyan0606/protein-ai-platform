#!/usr/bin/env python3
"""Build Stage 25 execute-request blocker detail report."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = AI_ROOT.parents[1] / "酶数据库"
APPLY_REPORT = ENZYME_DB_ROOT / "stage25_approved_apply_report_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_blocker_detail_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def main() -> int:
    report = load_json(APPLY_REPORT)
    failures = [row for row in report.get("failures", []) if isinstance(row, dict)]
    by_check = Counter(str(row.get("check")) for row in failures)
    by_proposal: dict[str, list[str]] = defaultdict(list)
    for row in failures:
        proposal_id = str(row.get("proposal_id") or "global")
        by_proposal[proposal_id].append(str(row.get("check")))

    detail = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_blocker_detail",
        "stage": 25,
        "source_report": str(APPLY_REPORT),
        "execute_requested": bool(report.get("execute_requested")),
        "executor_status": report.get("status"),
        "executor_failure_count": len(failures),
        "failure_check_counts": dict(sorted(by_check.items())),
        "proposal_blocker_rows": [
            {
                "proposal_id": proposal_id,
                "blocker_count": len(checks),
                "checks": sorted(checks),
            }
            for proposal_id, checks in sorted(by_proposal.items())
        ],
        "db_before_integrity_ok_count": sum(
            1 for row in (report.get("before") or {}).values()
            if isinstance(row, dict) and row.get("integrity") == "ok"
        ),
        "backup_count": len(report.get("backups") or []),
        "apply_result_count": len(report.get("apply_results") or []),
        "after_present": report.get("after") is not None,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "execute_requested": detail["execute_requested"], "executor_failure_count": detail["executor_failure_count"], "proposal_rows": len(detail["proposal_blocker_rows"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
