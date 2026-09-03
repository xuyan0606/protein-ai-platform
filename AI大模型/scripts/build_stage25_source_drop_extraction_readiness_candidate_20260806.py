#!/usr/bin/env python3
"""Build Stage 25 source-drop extraction readiness candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DROP_REPORT = AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"
TEMPLATES = AI_ROOT / "datasets" / "governance" / "stage25_new_paper_extraction_templates_20260806.jsonl"
DRAFTS = AI_ROOT / "datasets" / "governance" / "stage25_reviewed_extraction_output_drafts_20260806.jsonl"
OUTPUT = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_extraction_readiness_candidates_20260806.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def main() -> int:
    source_report = load_json(SOURCE_DROP_REPORT)
    templates = load_jsonl(TEMPLATES)
    drafts = load_jsonl(DRAFTS)
    source_by_id = {row.get("source_id"): row for row in source_report.get("source_status") or []}
    draft_by_template = {row.get("template_id"): row for row in drafts}

    rows = []
    for template in templates:
        required_sources = []
        missing_sources = []
        ready_sources = 0
        for source_id in template.get("required_source_files") or []:
            source = source_by_id.get(source_id) or {}
            ready = source.get("ready_for_extraction") is True
            ready_sources += 1 if ready else 0
            if not ready:
                missing_sources.append(source_id)
            required_sources.append({
                "source_id": source_id,
                "expected_local_path": source.get("expected_local_path"),
                "exists": source.get("exists") is True,
                "sha256": source.get("sha256"),
                "ready_for_extraction": ready,
            })
        all_sources_ready = bool(required_sources and ready_sources == len(required_sources))
        draft = draft_by_template.get(template.get("template_id")) or {}
        rows.append({
            "candidate_id": f"stage25_source_drop_extract_ready_{template.get('pmid')}",
            "stage": 25,
            "template_id": template.get("template_id"),
            "draft_id": draft.get("draft_id"),
            "pmid": template.get("pmid"),
            "doi": template.get("doi"),
            "family": template.get("family"),
            "target": template.get("target_variant"),
            "template_type": template.get("template_type"),
            "required_source_count": len(required_sources),
            "ready_source_count": ready_sources,
            "missing_source_ids": missing_sources,
            "required_sources": required_sources,
            "all_required_sources_ready": all_sources_ready,
            "ready_for_reviewed_extraction": False,
            "reviewed_extraction_completed": False,
            "ready_for_allowlist_approval": False,
            "ready_for_sqlite_apply": False,
            "external_sqlite_mutated": False,
            "formal_decision_rows_written": 0,
            "export_safe_released": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Source-drop extraction readiness candidate only; source file readiness does not approve reviewed extraction, allowlist approval, SQLite apply, formal decisions, model claims, or release.",
        })

    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "candidate_rows": len(rows), "ready_for_reviewed_extraction_rows": 0, "ready_for_sqlite_apply_rows": 0}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
