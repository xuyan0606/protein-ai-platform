#!/usr/bin/env python3
"""Build a machine-readable manifest for the release operator packet.

The manifest is read-only: it checks expected handoff files, records SHA-256
digests, and summarizes the current release decision boundary. It does not run
network checks, deploy code, restore databases, or print secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "release-operator-packet-manifest-2026-08-17.json"

PACKET_FILES = [
    ("operator_packet", "docs/manuals/release-operator-packet-2026-08-17.md"),
    ("handoff", "docs/manuals/release-handoff-2026-08-17.md"),
    ("manual_gate_inputs_template", "docs/manuals/release-manual-gate-inputs.template.json"),
    ("manual_gate_input_validator", "scripts/validate_release_manual_gate_inputs.py"),
    ("manual_gate_evidence_template", "docs/manuals/release-manual-gate-evidence-template.md"),
    ("manual_gate_evidence_inputs_template", "docs/manuals/release-manual-gate-evidence-inputs.template.json"),
    ("manual_gate_evidence_schema", "docs/manuals/release-manual-gate-evidence.schema.json"),
    ("manual_gate_evidence_example", "docs/manuals/release-manual-gate-evidence.example.json"),
    ("manual_gate_evidence_validator", "scripts/validate_release_manual_gate_evidence.py"),
    ("go_no_go_summary_builder", "scripts/build_release_go_no_go_summary.py"),
    ("worktree_manifest_builder", "scripts/build_release_worktree_manifest.py"),
    ("external_infrastructure_checklist", "docs/manuals/external-infrastructure-acceptance-checklist.md"),
    ("productization_acceptance_manual", "docs/manuals/productization-acceptance-manual.md"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_row(label: str, relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    exists = path.exists()
    return {
        "label": label,
        "path": relative_path,
        "exists": exists,
        "sha256": _sha256(path) if exists and path.is_file() else None,
        "bytes": path.stat().st_size if exists and path.is_file() else None,
    }


def build_manifest() -> dict[str, Any]:
    files = [_file_row(label, rel) for label, rel in PACKET_FILES]
    missing = [row["path"] for row in files if not row["exists"]]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_release_operator_packet_manifest",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "release_status": {
            "local_automated_gates": "passed",
            "enhanced_release_acceptance": "passed-with-manual-gates",
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "manual_required": 3,
            "production_deployed": False,
            "next_decision": "operator must provide manual gate inputs, execute external drills, archive evidence, then decide go/no-go/defer",
        },
        "files": files,
        "summary": {
            "status": "ready-for-operator-review" if not missing else "incomplete",
            "file_count": len(files),
            "missing_files": missing,
        },
    }


def _comparable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(manifest)
    comparable.pop("created_at", None)
    return comparable


def check_manifest(output: Path) -> tuple[bool, dict[str, Any]]:
    if not output.exists():
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_missing",
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }

    try:
        existing = json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_invalid_json",
            "error": str(exc),
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }

    if not isinstance(existing, dict):
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_invalid_shape",
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }

    current = build_manifest()
    existing_cmp = _comparable_manifest(existing)
    current_cmp = _comparable_manifest(current)
    is_current = existing_cmp == current_cmp and current["summary"]["status"] == "ready-for-operator-review"
    stale_sections = []
    for key in ("mode", "network_io", "destructive_actions", "secrets_printed", "release_status", "files", "summary"):
        if existing_cmp.get(key) != current_cmp.get(key):
            stale_sections.append(key)
    if current["summary"]["status"] != "ready-for-operator-review" and "summary" not in stale_sections:
        stale_sections.append("summary")

    return is_current, {
        "status": "current" if is_current else "stale-or-missing",
        "reason": None if is_current else (
            "manifest_differs_from_current_packet"
            if existing_cmp != current_cmp
            else "current_packet_incomplete"
        ),
        "stale_sections": stale_sections,
        "file_count": current["summary"]["file_count"],
        "missing_files": current["summary"]["missing_files"],
        "output": str(output),
        "network_io": current["network_io"],
        "destructive_actions": current["destructive_actions"],
        "secrets_printed": current["secrets_printed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Manifest output JSON path")
    parser.add_argument("--check", action="store_true", help="Verify that the existing manifest is current without writing")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if args.check:
        ok, summary = check_manifest(output)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        else:
            print(f"summary\t{summary['status']}\toutput={summary['output']}")
            if summary.get("reason"):
                print(f"reason\t{summary['reason']}")
            if summary.get("stale_sections"):
                print(f"stale_sections\t{','.join(summary['stale_sections'])}")
        return 0 if ok else 1

    manifest = build_manifest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "status": manifest["summary"]["status"],
        "file_count": manifest["summary"]["file_count"],
        "missing_files": manifest["summary"]["missing_files"],
        "output": str(output),
        "network_io": manifest["network_io"],
        "destructive_actions": manifest["destructive_actions"],
        "secrets_printed": manifest["secrets_printed"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{summary['status']}\tfiles={summary['file_count']}\tmissing={len(summary['missing_files'])}")
        print(f"output\t{summary['output']}")
    return 0 if manifest["summary"]["status"] == "ready-for-operator-review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
