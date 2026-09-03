#!/usr/bin/env python3
"""Validate PyRosetta install probe evidence remains fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json"
OUT = AI_ROOT / "reports" / "pyrosetta_local_install_probe_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    report = load_json(INPUT)
    failures: list[str] = []
    if not report:
        failures.append("probe_report_missing")
    if report.get("backend") not in {None, "pyrosetta"}:
        failures.append("backend_not_pyrosetta")
    for field in [
        "formal_license_decision_written",
        "formal_runtime_receipt_written",
        "backend_config_enabled",
        "approved_for_physical_ddg_runtime",
        "ready_for_ddg_smoke",
        "ddg_protocol_executed",
        "physics_ddg_ready",
        "safe_for_training_import",
        "safe_for_model_claim",
        "release_ready",
    ]:
        if report.get(field) is True:
            failures.append(f"{field}_must_remain_false")
    if (report.get("import_probe") or {}).get("pyrosetta_init_executed") is True:
        failures.append("pyrosetta_init_must_not_execute_in_install_probe")
    if (report.get("import_probe") or {}).get("ddg_protocol_executed") is True:
        failures.append("ddg_protocol_must_not_execute_in_install_probe")
    if (report.get("wheel") or {}).get("present") and not (report.get("wheel") or {}).get("sha256"):
        failures.append("present_wheel_missing_sha256")
    if (report.get("install") or {}).get("path_exists") and not (report.get("module_spec") or {}).get("available"):
        failures.append("install_path_present_but_module_spec_unavailable")
    if (report.get("module_spec") or {}).get("available") and not (report.get("import_probe") or {}).get("succeeded"):
        failures.append("module_spec_available_but_import_failed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(INPUT),
        "success": not failures,
        "failures": failures,
        "wheel_present": bool((report.get("wheel") or {}).get("present")),
        "install_path_exists": bool((report.get("install") or {}).get("path_exists")),
        "module_spec_available": bool((report.get("module_spec") or {}).get("available")),
        "import_succeeded": bool((report.get("import_probe") or {}).get("succeeded")),
        "physics_ddg_ready": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation confirms the install probe is evidence only and cannot approve runtime, ddG execution, training import, model claim, or release readiness.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "failures": failures, "output": str(OUT)}, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
