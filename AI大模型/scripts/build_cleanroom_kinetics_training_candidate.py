#!/usr/bin/env python3
"""Build a fail-closed report for the clean-room kinetics candidate layer.

The clean-room normalizer and replicate summarizer are source/data-governance
adapters. This script may inspect their JSONL products, but it never writes a
training JSONL row or promotes a candidate to training eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
NORMALIZER_SOURCE = AI_ROOT / "scripts" / "normalize_kinetics_records_cleanroom.py"
SUMMARIZER_SOURCE = AI_ROOT / "scripts" / "summarize_kinetics_replicates_cleanroom.py"
DEFAULT_NORMALIZED_INPUTS = (
    AI_ROOT / "datasets" / "curation" / "cleanroom_kinetics_normalized.jsonl",
    AI_ROOT / "datasets" / "curation" / "kinetics_normalized_cleanroom.jsonl",
    AI_ROOT / "output" / "cleanroom_kinetics_normalized.jsonl",
    AI_ROOT / "tmp" / "cleanroom_kinetics_normalized.jsonl",
)
DEFAULT_SUMMARY_INPUTS = (
    AI_ROOT / "datasets" / "curation" / "cleanroom_kinetics_replicate_summaries.jsonl",
    AI_ROOT / "datasets" / "curation" / "kinetics_replicate_summaries_cleanroom.jsonl",
    AI_ROOT / "output" / "cleanroom_kinetics_replicate_summaries.jsonl",
    AI_ROOT / "tmp" / "cleanroom_kinetics_replicate_summaries.jsonl",
)
REPORT = AI_ROOT / "reports" / "cleanroom_kinetics_training_candidate_report.json"


def path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_profile(path: Path, required_markers: dict[str, str]) -> dict[str, Any]:
    exists = path.is_file()
    text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
    return {
        "path": path_text(path),
        "exists": exists,
        "sha256": sha256_file(path),
        "checks": {name: marker in text for name, marker in required_markers.items()},
    }


def choose_input(explicit: Path | None, candidates: tuple[Path, ...]) -> Path:
    if explicit is not None:
        return explicit
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_jsonl_profile(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if path.is_file():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_number, "error": str(exc)})
                continue
            if not isinstance(value, dict):
                errors.append({"line": line_number, "error": "row must be a JSON object"})
                continue
            rows.append(value)

    profile = {
        "path": path_text(path),
        "exists": path.is_file(),
        "rows": len(rows),
        "parse_errors": errors[:50],
        "training_eligible_true_rows": sum(row.get("training_eligible") is True for row in rows),
        "training_import_written_true_rows": sum(row.get("training_import_written") is True for row in rows),
        "ready_for_training_import_true_rows": sum(row.get("ready_for_training_import") is True for row in rows),
    }
    return rows, profile


def non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fail-closed clean-room kinetics training candidate report")
    parser.add_argument("--normalized", type=Path, default=None, help="Existing normalized kinetics JSONL, if available")
    parser.add_argument("--summaries", type=Path, default=None, help="Existing replicate summary JSONL, if available")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    normalized_path = choose_input(args.normalized, DEFAULT_NORMALIZED_INPUTS)
    summary_path = choose_input(args.summaries, DEFAULT_SUMMARY_INPUTS)
    normalized_rows, normalized_profile = load_jsonl_profile(normalized_path)
    summary_rows, summary_profile = load_jsonl_profile(summary_path)

    normalized_quality_clean_rows = sum(
        row.get("value") is not None and not row.get("quality_flags") for row in normalized_rows
    )
    retained_observation_rows = sum(
        non_negative_int(row.get("observation_count")) for row in summary_rows
    )
    artifacts_read = [
        profile["path"]
        for profile in (normalized_profile, summary_profile)
        if profile["exists"]
    ]
    source_contract = {
        "normalizer_training_eligible_false": source_profile(
            NORMALIZER_SOURCE,
            {"training_eligible_false": '"training_eligible": False'},
        )["checks"]["training_eligible_false"],
        "normalizer_rows_training_eligible_zero": source_profile(
            NORMALIZER_SOURCE,
            {"rows_training_eligible_zero": '"rows_training_eligible": 0'},
        )["checks"]["rows_training_eligible_zero"],
        "summarizer_training_eligible_false": source_profile(
            SUMMARIZER_SOURCE,
            {"training_eligible_false": '"training_eligible": False'},
        )["checks"]["training_eligible_false"],
        "summarizer_training_eligible_rows_zero": source_profile(
            SUMMARIZER_SOURCE,
            {"training_eligible_rows_zero": '"training_eligible_rows": 0'},
        )["checks"]["training_eligible_rows_zero"],
    }
    source_profiles = {
        "normalizer": source_profile(
            NORMALIZER_SOURCE,
            {
                "training_eligible_false": '"training_eligible": False',
                "rows_training_eligible_zero": '"rows_training_eligible": 0',
            },
        ),
        "summarizer": source_profile(
            SUMMARIZER_SOURCE,
            {
                "training_eligible_false": '"training_eligible": False',
                "training_eligible_rows_zero": '"training_eligible_rows": 0',
            },
        ),
    }

    report = {
        "schema_version": "cleanroom_kinetics_training_candidate.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_mode": "artifact_and_source_contract",
        "source_scripts": source_profiles,
        "source_contract": source_contract,
        "normalized_input": normalized_profile,
        "summary_input": summary_profile,
        "artifacts_read": artifacts_read,
        "normalized_rows": len(normalized_rows),
        "normalized_quality_clean_rows": normalized_quality_clean_rows,
        "summary_rows": len(summary_rows),
        "summary_observation_rows_retained": retained_observation_rows,
        "replicate_summary_candidate_rows": len(summary_rows),
        "training_candidate_rows": len(summary_rows),
        "formal_training_rows": 0,
        "training_import_written_rows": 0,
        "training_eligible_rows": 0,
        "training_eligible": False,
        "ready_for_training_import_rows": 0,
        "ready_for_training_import": False,
        "training_output_written": False,
        "training_output_path": None,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": [
            "candidate_layer_only",
            "external_data_license_review_not_authorized",
            "numbering_and_identity_review_not_authorized",
            "dedup_and_qc_review_not_authorized",
            "replicate_and_head_threshold_gate_not_satisfied",
        ],
        "policy": (
            "Clean-room kinetics normalization and replicate summaries are "
            "candidate-layer evidence only. This report never writes training "
            "rows and cannot authorize training, model claims, or release."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "normalized_rows": report["normalized_rows"],
                "summary_rows": report["summary_rows"],
                "training_candidate_rows": report["training_candidate_rows"],
                "training_import_written_rows": report["training_import_written_rows"],
                "training_eligible": report["training_eligible"],
                "output": path_text(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
