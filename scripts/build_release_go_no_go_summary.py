#!/usr/bin/env python3
"""Build a read-only go/no-go summary for the release operator packet."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANUAL_INPUT_REPORT = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-input-validation-report.json"
DEFAULT_EVIDENCE_REPORT = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence-validation-report.json"
DEFAULT_OPERATOR_MANIFEST = PROJECT_ROOT / "docs" / "manuals" / "release-operator-packet-manifest-2026-08-17.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "release-go-no-go-summary-2026-08-17.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "release-go-no-go-summary-2026-08-17.md"
DEFAULT_PRODUCTION_ENV_FILES = [
    PROJECT_ROOT / "docker" / ".env",
    PROJECT_ROOT / "docker" / ".env.aliyun.app",
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_exists": True, "_invalid_json": str(exc)}
    if not isinstance(payload, dict):
        return {"_exists": True, "_invalid_shape": "expected object"}
    payload["_exists"] = True
    return payload


def _source(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "exists": bool(payload.get("_exists")),
        "invalid_json": payload.get("_invalid_json"),
        "invalid_shape": payload.get("_invalid_shape"),
    }


def _production_config_check(env_files: list[Path]) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/check_production_config.py",
        "--json",
        "--mode",
        "production",
        "--require-production-safe",
        "--skip-domain-https",
    ]
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])

    proc = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    critical_checks = [
        str(check.get("name"))
        for check in checks
        if isinstance(check, dict) and check.get("status") == "critical"
    ]
    critical = int(summary.get("critical") or len(critical_checks) or 0)
    status = str(summary.get("status") or ("ready" if proc.returncode == 0 else "blocked"))
    return {
        "name": "production_config_gate",
        "status": status,
        "ready": proc.returncode == 0 and critical == 0,
        "missing": critical_checks,
        "returncode": proc.returncode,
        "env_files_checked": [
            str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
            for path in env_files
        ],
    }


def build_summary(
    manual_report: Path,
    evidence_report: Path,
    operator_manifest: Path,
    production_env_files: list[Path] | None = None,
) -> dict[str, Any]:
    manual = _load_json(manual_report)
    evidence = _load_json(evidence_report)
    manifest = _load_json(operator_manifest)
    production_config = _production_config_check(production_env_files or DEFAULT_PRODUCTION_ENV_FILES)

    checks = [
        production_config,
        {
            "name": "manual_gate_inputs",
            "status": manual.get("status", "missing"),
            "ready": bool(manual.get("ready_to_run_final_acceptance")),
            "missing": manual.get("missing_gates") or manual.get("missing_gate_count") or [],
        },
        {
            "name": "manual_gate_evidence",
            "status": evidence.get("status", "missing"),
            "ready": bool(evidence.get("ready_for_go")),
            "missing": evidence.get("missing_sections") or [],
        },
        {
            "name": "operator_packet_manifest",
            "status": (manifest.get("summary") or {}).get("status", "missing") if isinstance(manifest.get("summary"), dict) else "missing",
            "ready": (manifest.get("summary") or {}).get("status") == "ready-for-operator-review" if isinstance(manifest.get("summary"), dict) else False,
            "missing": (manifest.get("summary") or {}).get("missing_files", []) if isinstance(manifest.get("summary"), dict) else [],
        },
    ]
    blocking_items = [check["name"] for check in checks if not check["ready"]]
    status = "ready-for-go-review" if not blocking_items else "manual_required"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_release_go_no_go_summary",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "production_deployed": False,
        "status": status,
        "ready_for_go_review": not blocking_items,
        "blocking_items": blocking_items,
        "checks": checks,
        "sources": {
            "production_config_gate": {
                "env_files_checked": production_config["env_files_checked"],
                "returncode": production_config["returncode"],
            },
            "manual_gate_input_validation": _source(manual_report, manual),
            "manual_gate_evidence_validation": _source(evidence_report, evidence),
            "operator_packet_manifest": _source(operator_manifest, manifest),
        },
        "next_action": (
            "review signed go/no-go evidence before production deployment"
            if not blocking_items
            else "complete production config, manual gate inputs, and evidence; do not deploy production"
        ),
    }


def write_markdown(summary: dict[str, Any], output: Path) -> None:
    rows = [
        "| Check | Status | Ready | Missing |",
        "|---|---|---|---|",
    ]
    for check in summary["checks"]:
        missing = check.get("missing")
        if isinstance(missing, list):
            missing_text = ", ".join(str(item) for item in missing)
        else:
            missing_text = str(missing or "")
        rows.append(f"| `{check['name']}` | `{check['status']}` | `{check['ready']}` | {missing_text} |")

    text = "\n".join([
        "# Release Go/No-Go Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- ready_for_go_review: `{summary['ready_for_go_review']}`",
        f"- production_deployed: `{summary['production_deployed']}`",
        f"- blocking_items: `{', '.join(summary['blocking_items']) if summary['blocking_items'] else 'none'}`",
        "",
        *rows,
        "",
        f"Next action: {summary['next_action']}",
        "",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-report", default=str(DEFAULT_MANUAL_INPUT_REPORT))
    parser.add_argument("--evidence-report", default=str(DEFAULT_EVIDENCE_REPORT))
    parser.add_argument("--operator-manifest", default=str(DEFAULT_OPERATOR_MANIFEST))
    parser.add_argument("--production-env-file", action="append", default=[], help="Production env file checked by the production config gate")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    summary = build_summary(
        Path(args.manual_report).expanduser().resolve(),
        Path(args.evidence_report).expanduser().resolve(),
        Path(args.operator_manifest).expanduser().resolve(),
        [Path(path).expanduser().resolve() for path in args.production_env_file] if args.production_env_file else None,
    )
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(summary, output_md)

    response = {
        "status": summary["status"],
        "ready_for_go_review": summary["ready_for_go_review"],
        "blocking_items": summary["blocking_items"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": summary["network_io"],
        "destructive_actions": summary["destructive_actions"],
        "secrets_printed": summary["secrets_printed"],
    }
    if args.json:
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{response['status']}\tblocking={len(response['blocking_items'])}")
        print(f"output_json\t{response['output_json']}")
        print(f"output_md\t{response['output_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
