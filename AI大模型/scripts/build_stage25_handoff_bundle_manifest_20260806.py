#!/usr/bin/env python3
"""Build Stage 25 handoff bundle manifest with checksums."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
OVERALL = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_20260806.json"

AI_REQUIRED = [
    "scripts/run_stage25_fail_closed_validation_20260806.py",
    "scripts/build_stage25_overall_fail_closed_index_20260806.py",
    "reports/stage25_fail_closed_validation_run_report_20260806.json",
    "reports/stage25_overall_fail_closed_index_20260806.json",
    "reports/next_operator_packet_20260806.md",
    "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.md",
    "datasets/governance/stage25_cm5_l262v_adjudication_decisions.local.json",
    "datasets/governance/stage25_cm5_l262v_external_request_authorizations.local.json",
    "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json",
    "datasets/governance/stage25_cm5_l262v_external_evidence_reviews.local.json",
    "reports/stage25_cm5_l262v_adjudication_evidence_intake_20260807.md",
    "reports/stage25_cm5_l262v_external_evidence_request_packet_20260807.md",
    "reports/stage25_cm5_l262v_external_request_message_drafts_20260807.md",
    "../docs/manuals/2026-08-06-daily-report.md",
    "task_plan.md",
    "progress.md",
    "findings.md",
]
GOVERNANCE_GLOBS = [
    "datasets/governance/stage25_*_202608*.jsonl",
    "reports/stage25_*_202608*.json",
    "scripts/*stage25*202608*.py",
]
ENZYME_REQUIRED = [
    "new_paper_candidates_dry_run_importer_20260805.py",
    "test_new_paper_candidates_dry_run_importer_20260805.py",
    "stage25_paper_only_apply_plan_20260806.json",
    "stage25_paper_only_apply_plan_validation_20260806.json",
    "stage25_sqlite_backup_preflight_20260806.json",
    "stage25_sqlite_backup_preflight_validation_20260806.json",
    "new_paper_stage25_fail_closed_validation_summary_20260806.json",
    "build_stage25_paper_metadata_only_plan_20260806.py",
    "stage25_paper_metadata_only_plan_20260806.json",
    "validate_new_paper_proposal_set_consistency_20260806.py",
    "new_paper_proposal_set_consistency_validation_report_20260806.json",
]
EXCLUDED_GOVERNANCE_RELATIVE_PATHS = {
    "reports/stage25_handoff_bundle_manifest_20260806.json",
    "reports/stage25_handoff_bundle_manifest_validation_20260806.json",
}
VOLATILE_AI_RELATIVE_PATHS = {
    "reports/stage25_fail_closed_validation_run_report_20260806.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_file(rows: list[dict], root: Path, rel: str, role: str, freshness_check_mode: str = "current_filesystem") -> None:
    path = (root / rel).resolve()
    exists = path.exists() and path.is_file()
    rows.append({
        "role": role,
        "root": str(root),
        "relative_path": rel,
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": sha256(path) if exists else None,
        "freshness_check_mode": freshness_check_mode,
    })


def current_runner_command_count() -> int:
    runner_path = AI_ROOT / "scripts" / "run_stage25_fail_closed_validation_20260806.py"
    spec = importlib.util.spec_from_file_location("stage25_runner_for_handoff", runner_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load runner module from {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.COMMANDS)


def collect_rows() -> list[dict]:
    rows: list[dict] = []
    for rel in AI_REQUIRED:
        freshness_mode = "post_run_volatile_existence_only" if rel in VOLATILE_AI_RELATIVE_PATHS else "current_filesystem"
        add_file(rows, AI_ROOT, rel, "ai_required", freshness_mode)
    seen = {row["path"] for row in rows}
    for pattern in GOVERNANCE_GLOBS:
        for path in sorted(AI_ROOT.glob(pattern)):
            relative_path = str(path.relative_to(AI_ROOT))
            if relative_path in EXCLUDED_GOVERNANCE_RELATIVE_PATHS:
                continue
            resolved = str(path.resolve())
            if resolved in seen or not path.is_file():
                continue
            rows.append({
                "role": "stage25_governance_artifact",
                "root": str(AI_ROOT),
                "relative_path": str(path.relative_to(AI_ROOT)),
                "path": resolved,
                "exists": True,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "freshness_check_mode": "current_filesystem",
            })
            seen.add(resolved)
    for rel in ENZYME_REQUIRED:
        add_file(rows, ENZYME_DB_ROOT, rel, "enzyme_required")
    return rows


def main() -> int:
    rows = collect_rows()

    overall = json.loads(OVERALL.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_handoff_bundle_manifest",
        "stage": 25,
        "bundle_rows": len(rows),
        "unique_path_rows": len({row["path"] for row in rows}),
        "duplicate_paths": sorted({row["path"] for row in rows if sum(1 for item in rows if item["path"] == row["path"]) > 1}),
        "freshness_check_rows": sum(1 for row in rows if row["freshness_check_mode"] == "current_filesystem"),
        "freshness_exempt_rows": sum(1 for row in rows if row["freshness_check_mode"] != "current_filesystem"),
        "self_referential_rows": sum(1 for row in rows if row["relative_path"] in EXCLUDED_GOVERNANCE_RELATIVE_PATHS),
        "excluded_self_referential_paths": sorted(EXCLUDED_GOVERNANCE_RELATIVE_PATHS),
        "missing_rows": sum(1 for row in rows if not row["exists"]),
        "overall_summary_count": len(overall.get("summaries") or []),
        "runner_command_count": current_runner_command_count(),
        "files": rows,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Handoff manifest only. Self-referential manifest/validation JSON files are excluded. Current-filesystem rows require live size/SHA parity; the enclosing runner report is post-run volatile and existence-only. This does not mutate databases, create decisions, or open claims.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "bundle_rows": report["bundle_rows"], "missing_rows": report["missing_rows"], "overall_summary_count": report["overall_summary_count"], "runner_command_count": report["runner_command_count"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
