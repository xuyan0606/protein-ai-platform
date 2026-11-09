"""Run the local, tool-free v2 property routing replay."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.property_workflow_governance import evaluate_shadow_cases


def main() -> int:
    cases_path = Path(__file__).resolve().parents[1] / "tests" / "property_workflow_shadow_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    report = evaluate_shadow_cases(cases)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 and report["constraint_leak_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
