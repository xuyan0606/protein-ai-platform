#!/usr/bin/env python3
"""Validate physical ddG runtime receipt preflight remains fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_report.json"
JSONL = AI_ROOT / "datasets" / "governance" / "ddg_physical_runtime_receipt_preflight.jsonl"
MARKDOWN = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight.md"
OUT = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_validation_report.json"
EXPECTED_BACKENDS = ["rosetta", "pyrosetta", "foldx"]
PROHIBITED_ACTIONS = [
    "do_not_install_or_enable_unapproved_rosetta_pyrosetta_or_foldx",
    "do_not_write_unreviewed_formal_runtime_receipt",
    "do_not_execute_unreceipted_rosetta_pyrosetta_or_foldx",
    "do_not_import_computed_ddg_as_training_label",
    "do_not_set_model_or_release_claims_from_runtime_smoke",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return rows, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(value, dict):
            invalid += 1
            continue
        rows.append(value)
    return rows, invalid


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def md_bool_missing(row: dict[str, Any], key: str) -> str:
    section = row.get(key) if isinstance(row.get(key), dict) else {}
    return "missing" if section.get("missing") else "present"


def expected_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# P145 ddG Physical Runtime Receipt Preflight",
        "",
        f"Created: `{report.get('created_at')}`",
        "",
        "This is a fail-closed scaffold. It does not install Rosetta/PyRosetta/FoldX, enable config, write a formal runtime receipt, run a physical ddG smoke job, or connect the safe pipeline/manifest.",
        "",
        "## Summary",
        "",
        f"- Physical backend rows: {report.get('physical_backend_rows')}",
        f"- Runtime receipt rows: {report.get('runtime_receipt_rows')}",
        f"- Missing license rows: {report.get('missing_license_rows')}",
        f"- Missing install path/module rows: {report.get('missing_install_path_or_module_rows')}",
        f"- Missing config-enabled rows: {report.get('missing_config_enabled_rows')}",
        f"- Missing probe rows: {report.get('missing_probe_rows')}",
        f"- Missing smoke artifact rows: {report.get('missing_smoke_artifact_rows')}",
        f"- Ready to write formal receipt rows: {report.get('ready_to_write_formal_runtime_receipt_rows')}",
        "",
        "| Backend | License | Install path/module | Config enabled | Probe | Smoke artifact | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {backend} | {license} | {install} | {config} | {probe} | {smoke} | {status} |".format(
                backend=row.get("backend"),
                license=md_bool_missing(row, "license"),
                install=md_bool_missing(row, "install_path_or_module"),
                config=md_bool_missing(row, "config_enabled"),
                probe=md_bool_missing(row, "probe"),
                smoke=md_bool_missing(row, "smoke_artifact"),
                status=row.get("status"),
            )
        )
    lines.extend(["", "## Backend Details", ""])
    for row in rows:
        license_section = row.get("license") if isinstance(row.get("license"), dict) else {}
        install_section = row.get("install_path_or_module") if isinstance(row.get("install_path_or_module"), dict) else {}
        config_section = row.get("config_enabled") if isinstance(row.get("config_enabled"), dict) else {}
        probe_section = row.get("probe") if isinstance(row.get("probe"), dict) else {}
        smoke_section = row.get("smoke_artifact") if isinstance(row.get("smoke_artifact"), dict) else {}
        receipt_section = row.get("runtime_receipt") if isinstance(row.get("runtime_receipt"), dict) else {}
        lines.extend([
            f"### {row.get('backend')}",
            "",
            f"- License missing: {', '.join(license_section.get('missing_evidence') or []) or 'none'}",
            f"- Install path/module missing: {', '.join(install_section.get('missing_evidence') or []) or 'none'}",
            f"- Config enabled missing: {', '.join(config_section.get('missing_evidence') or []) or 'none'}",
            f"- Probe missing: {', '.join(probe_section.get('missing_evidence') or []) or 'none'}",
            f"- Smoke artifact missing: {', '.join(smoke_section.get('missing_evidence') or []) or 'none'}",
            f"- Runtime receipt missing: {', '.join(receipt_section.get('missing_evidence') or []) or 'none'}",
            "",
        ])
    lines.extend(["## Policy", "", "Blocked actions: " + ", ".join(PROHIBITED_ACTIONS), ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate physical ddG runtime receipt preflight")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--jsonl", type=Path, default=JSONL)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    rows, invalid = load_jsonl(args.jsonl)
    markdown = load_text(args.markdown)
    failures: list[dict[str, Any]] = []
    backends = [str(row.get("backend")) for row in rows]

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(invalid != 0, failures, "jsonl_valid", invalid, 0)
    fail_if(backends != EXPECTED_BACKENDS, failures, "backend_order", backends, EXPECTED_BACKENDS)
    fail_if(as_int(report.get("physical_backend_rows")) != 3, failures, "physical_backend_rows", report.get("physical_backend_rows"), 3)
    approved_rows = sum(
        1
        for row in rows
        if row.get("runtime_receipt", {}).get("approved_runtime_receipt_rows", 0) > 0
    )
    ready_rows = sum(
        1
        for row in rows
        if isinstance(row.get("missing_categories"), list) and not row.get("missing_categories")
    )
    fail_if(as_int(report.get("runtime_receipt_rows")) != 2, failures, "runtime_receipt_rows_two", report.get("runtime_receipt_rows"), 2)
    fail_if(as_int(report.get("approved_runtime_receipt_rows")) != approved_rows, failures, "approved_runtime_receipt_rows_matches_rows", report.get("approved_runtime_receipt_rows"), approved_rows)
    fail_if(approved_rows != 2, failures, "approved_runtime_receipt_rows_two", approved_rows, 2)
    expected_missing_counts = {
        "missing_license_rows": sum("license" in (row.get("missing_categories") or []) for row in rows),
        "missing_install_path_or_module_rows": sum("install_path_or_module" in (row.get("missing_categories") or []) for row in rows),
        "missing_config_enabled_rows": sum("config_enabled" in (row.get("missing_categories") or []) for row in rows),
        "missing_probe_rows": sum("probe" in (row.get("missing_categories") or []) for row in rows),
        "missing_smoke_artifact_rows": sum("smoke_artifact" in (row.get("missing_categories") or []) for row in rows),
    }
    for key, expected in expected_missing_counts.items():
        fail_if(as_int(report.get(key)) != expected, failures, f"{key}_expected", report.get(key), expected)
    fail_if(as_int(report.get("ready_to_write_formal_runtime_receipt_rows")) != ready_rows, failures, "ready_to_write_formal_runtime_receipt_rows_matches_ready_rows", report.get("ready_to_write_formal_runtime_receipt_rows"), ready_rows)
    fail_if(as_int(report.get("ready_to_enable_config_rows")) != ready_rows, failures, "ready_to_enable_config_rows_matches_ready_rows", report.get("ready_to_enable_config_rows"), ready_rows)
    fail_if(ready_rows != 2, failures, "ready_backend_rows_two", ready_rows, 2)
    fail_if(as_int(report.get("ready_to_run_physical_ddg_smoke_rows")) != 1, failures, "ready_to_run_physical_ddg_smoke_rows_one", report.get("ready_to_run_physical_ddg_smoke_rows"), 1)
    fail_if(report.get("per_backend_physics_ready_rows") != 1, failures, "per_backend_physics_ready_rows_one", report.get("per_backend_physics_ready_rows"), 1)
    fail_if(report.get("all_physical_backends_ready") is not False, failures, "all_physical_backends_ready_false", report.get("all_physical_backends_ready"), False)
    fail_if(report.get("physical_ddg_lane_capability_status") != "blocked", failures, "lane_capability_blocked", report.get("physical_ddg_lane_capability_status"), "blocked")
    fail_if(report.get("physics_ddg_ready") is not False, failures, "physics_ddg_ready_false", report.get("physics_ddg_ready"), False)
    fail_if(report.get("executable_ddg_backend_ready") is not False, failures, "executable_ddg_backend_ready_false", report.get("executable_ddg_backend_ready"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "release_ready_false", report.get("release_ready"), False)
    markdown_expected = expected_markdown(report, rows)
    fail_if(markdown != markdown_expected, failures, "markdown_matches_report_and_rows", markdown, markdown_expected)

    for row in rows:
        backend = row.get("backend")
        fail_if(row.get("thermompnn_proxy_allowed_for_this_preflight") is not False, failures, f"{backend}_no_thermompnn_proxy", row.get("thermompnn_proxy_allowed_for_this_preflight"), False)
        missing_categories = row.get("missing_categories") if isinstance(row.get("missing_categories"), list) else []
        if not missing_categories:
            fail_if(row.get("ready_to_write_formal_runtime_receipt") is not True, failures, f"{backend}_formal_receipt_true", row.get("ready_to_write_formal_runtime_receipt"), True)
            fail_if(row.get("ready_to_enable_config") is not True, failures, f"{backend}_enable_config_true", row.get("ready_to_enable_config"), True)
            fail_if(missing_categories != [], failures, "pyrosetta_missing_categories_empty", missing_categories, [])
            fail_if(row.get("status") != "runtime_receipt_validated_ready", failures, f"{backend}_status_ready", row.get("status"), "runtime_receipt_validated_ready")
            if backend == "pyrosetta":
                fail_if(row.get("physics_ddg_ready") is not True, failures, "pyrosetta_physics_ddg_ready_true", row.get("physics_ddg_ready"), True)
                fail_if(row.get("ready_to_run_physical_ddg_smoke") is not True, failures, "pyrosetta_smoke_true", row.get("ready_to_run_physical_ddg_smoke"), True)
        else:
            fail_if(row.get("physics_ddg_ready") is not False, failures, f"{backend}_physics_ddg_ready_false", row.get("physics_ddg_ready"), False)
            fail_if(row.get("ready_to_write_formal_runtime_receipt") is not False, failures, f"{backend}_formal_receipt_false", row.get("ready_to_write_formal_runtime_receipt"), False)
            fail_if(row.get("ready_to_enable_config") is not False, failures, f"{backend}_enable_config_false", row.get("ready_to_enable_config"), False)
            fail_if(row.get("ready_to_run_physical_ddg_smoke") is not False, failures, f"{backend}_smoke_false", row.get("ready_to_run_physical_ddg_smoke"), False)
            for category in ["license", "install_path_or_module", "config_enabled", "probe", "smoke_artifact", "approved_runtime_receipt"]:
                fail_if(category not in missing_categories, failures, f"{backend}_{category}_missing_category_present", missing_categories, f"contains {category}")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "backends": backends,
        "failures": failures,
        "approved_runtime_receipt_rows": as_int(report.get("approved_runtime_receipt_rows")),
        "physical_ddg_lane_capability_status": report.get("physical_ddg_lane_capability_status"),
        "physics_ddg_ready": report.get("physics_ddg_ready") is True,
        "markdown_matches_report_and_rows": markdown == markdown_expected,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Physical ddG runtime preflight is evidence-only. It must fail if any Rosetta/PyRosetta/FoldX backend becomes ready without license/install/config/probe/smoke/runtime receipt evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "backends": backends, "failures": len(failures), "physics_ddg_ready": validation["physics_ddg_ready"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
