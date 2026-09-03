#!/usr/bin/env python3
"""Validate the isolated FoldX technical smoke receipt without opening gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_validation_20260806.json"
ARTIFACTS = ["parameters.json", "input_structure.sha256", "mutation_list.json", "ddg_table.json", "runtime.log"]
PARAMETERIZATION_WARNING = "External parametrized molecules were detected"
ENERGETIC_DEPENDENCY_WARNING = "Final energetic values will depend of the correct parametrization of this molecules."
EXPECTED_WARNING_COMMANDS = ["RepairPDB", "BuildModel"]
EXPECTED_UNRECOGNIZED_MOLECULES = ["5CM", "5NC", "SAH"]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FoldX technical smoke")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    report = load(args.report)
    failures: list[dict[str, Any]] = []
    if not report:
        failures.append({"check": "report_exists", "observed": str(args.report), "expected": "JSON report"})
    if report.get("technical_smoke_passed") is not True:
        failures.append({"check": "technical_smoke_passed", "observed": report.get("technical_smoke_passed"), "expected": True})
    if report.get("parsed_rows") != 1 or report.get("ddg_table_rows") != 1:
        failures.append({"check": "one_parsed_ddg_row", "observed": [report.get("parsed_rows"), report.get("ddg_table_rows")], "expected": [1, 1]})
    if report.get("parse_errors") != []:
        failures.append({"check": "parse_errors_empty", "observed": report.get("parse_errors"), "expected": []})
    output_dir = AI_ROOT / str(report.get("output_dir") or "")
    hashes = report.get("artifact_sha256") if isinstance(report.get("artifact_sha256"), dict) else {}
    for name in ARTIFACTS:
        path = output_dir / name
        if not path.is_file():
            failures.append({"check": f"artifact_exists:{name}", "observed": str(path), "expected": "file"})
        elif hashes.get(str(path.relative_to(AI_ROOT))) != digest(path):
            failures.append({"check": f"artifact_sha256:{name}", "observed": hashes.get(str(path.relative_to(AI_ROOT))), "expected": digest(path)})
    runtime_path = output_dir / "runtime.log"
    runtime = load(runtime_path)
    warning_commands = []
    for key, command_name in (("repair", "RepairPDB"), ("buildmodel", "BuildModel")):
        stdout = str((runtime.get(key) or {}).get("stdout") or "")
        if PARAMETERIZATION_WARNING in stdout and ENERGETIC_DEPENDENCY_WARNING in stdout:
            warning_commands.append(command_name)
    unrecognized_path = output_dir / "Unrecognized_molecules.txt"
    unrecognized_lines = [line.strip() for line in unrecognized_path.read_text(encoding="utf-8").splitlines() if line.strip()] if unrecognized_path.is_file() else []
    unrecognized_names = sorted({line.split()[2] for line in unrecognized_lines if line.startswith("Unrecognised atom:") and len(line.split()) >= 3})
    diagnostic_sha256 = digest(unrecognized_path) if unrecognized_path.is_file() else None
    expected_interpretation_fields = {
        "parameterization_dependency_warning_detected": True,
        "parameterization_warning_commands": EXPECTED_WARNING_COMMANDS,
        "parameterization_warning_command_count": 2,
        "unrecognized_molecule_diagnostic_present": True,
        "unrecognized_atom_rows": 110,
        "unrecognized_molecule_names": EXPECTED_UNRECOGNIZED_MOLECULES,
        "unrecognized_molecule_diagnostic_sha256": diagnostic_sha256,
        "parameterization_review_completed": False,
        "ddg_value_technical_only": True,
        "energetic_interpretation_approved": False,
        "physical_ddg_comparable": False,
        "safe_for_benchmark_intake": False,
    }
    if warning_commands != EXPECTED_WARNING_COMMANDS:
        failures.append({"check": "parameterization_warning_commands_from_runtime", "observed": warning_commands, "expected": EXPECTED_WARNING_COMMANDS})
    if len(unrecognized_lines) != 110:
        failures.append({"check": "unrecognized_atom_rows_from_diagnostic", "observed": len(unrecognized_lines), "expected": 110})
    if unrecognized_names != EXPECTED_UNRECOGNIZED_MOLECULES:
        failures.append({"check": "unrecognized_molecule_names_from_diagnostic", "observed": unrecognized_names, "expected": EXPECTED_UNRECOGNIZED_MOLECULES})
    for field, expected in expected_interpretation_fields.items():
        if report.get(field) != expected:
            failures.append({"check": field, "observed": report.get(field), "expected": expected})
    for field in ("formal_runtime_receipt_written", "approved_for_physical_ddg_runtime", "safe_for_training_import", "safe_for_model_claim", "export_safe_released", "release_ready"):
        if report.get(field) is not False:
            failures.append({"check": f"{field}_false", "observed": report.get(field), "expected": False})
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "technical_smoke_only": True,
        "success": not failures,
        "technical_smoke_passed": report.get("technical_smoke_passed") is True,
        "parsed_rows": report.get("parsed_rows"),
        "artifact_count": len(ARTIFACTS),
        **expected_interpretation_fields,
        "failures": failures,
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "safe_for_training_import": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Technical smoke validation only. Parameterization dependency and unrecognized-molecule diagnostics prohibit energetic interpretation, physical-ddG comparison, benchmark intake, training import, model claim, customer delivery, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "technical_smoke_passed": validation["technical_smoke_passed"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
