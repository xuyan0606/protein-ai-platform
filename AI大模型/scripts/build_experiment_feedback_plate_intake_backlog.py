#!/usr/bin/env python3
"""Build an audit-ready backlog for plate/well-level feedback intake."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFT_DIR = AI_ROOT / "datasets" / "feedback" / "plate_review_drafts"
PACKET_DIR = AI_ROOT / "datasets" / "feedback" / "plate_review_packets"
LOCAL_INTAKE = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.local.jsonl"
PLATE_VALIDATION = AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"
OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate_intake_backlog.jsonl"
REPORT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"

REQUIRED_FIELDS = [
    "plate_id",
    "well_id",
    "variant_id",
    "sample_batch",
    "assay_type",
    "replicate",
    "raw_signal",
    "qc_flag",
    "instrument",
    "protocol_version",
    "operator",
    "recorded_at",
]

QC_USABLE = {"pass", "warning", "fail"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    value = Path(str(path))
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def stable_id(*parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:12]
    return f"plate-intake-backlog-{digest}"


def packet_lookup(packet_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup = {}
    for row in packet_rows:
        key = (str(row.get("packet_id") or ""), str(row.get("source_path") or ""))
        lookup[key] = row
    return lookup


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if row.get(field) in {None, ""}]


def action_list(missing: list[str], row: dict[str, Any]) -> list[str]:
    actions = []
    if row.get("approved_for_plate_intake") is not True:
        actions.append("review the source and set approved_for_plate_intake only if it is genuine wet-lab plate/well data")
    if missing:
        actions.append("complete required schema fields: " + ", ".join(missing))
    if row.get("review_status") != "reviewed":
        actions.append("set review_status to reviewed only after source trace, plate/well, replicate and mutation mapping are checked")
    if row.get("qc_flag") not in QC_USABLE:
        actions.append("classify qc_flag as pass, warning or fail; preserve failed assays when genuine")
    actions.append("copy only completed reviewed rows into experiment_feedback_plate.local.jsonl and rerun the validator")
    return actions


def build_draft_backlog(drafts: list[dict[str, Any]], packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packet_by_key = packet_lookup(packets)
    rows = []
    for row in drafts:
        packet_id = str(row.get("packet_id") or "")
        source_path = str(row.get("source_path") or "")
        packet = packet_by_key.get((packet_id, source_path), {})
        missing = missing_fields(row)
        blockers = []
        if row.get("approved_for_plate_intake") is not True:
            blockers.append("not_approved_for_plate_intake")
        if missing:
            blockers.append("missing_required_schema_fields")
        if row.get("review_status") != "reviewed":
            blockers.append("not_reviewed")
        if row.get("qc_flag") not in QC_USABLE:
            blockers.append("qc_not_usable")
        rows.append({
            "backlog_id": stable_id(packet_id, source_path),
            "source": "plate_review_draft",
            "packet_id": packet_id,
            "source_packet_id": packet.get("source_packet_id"),
            "source_path": source_path,
            "source_review_bucket": packet.get("source_review_bucket"),
            "candidate_score": packet.get("candidate_score"),
            "plate_id": row.get("plate_id"),
            "well_id": row.get("well_id"),
            "variant_id": row.get("variant_id"),
            "assay_type": row.get("assay_type"),
            "replicate": row.get("replicate"),
            "qc_flag": row.get("qc_flag"),
            "review_status": row.get("review_status"),
            "approved_for_plate_intake": row.get("approved_for_plate_intake") is True,
            "missing_required_fields": missing,
            "blockers": blockers,
            "training_eligible": False,
            "claim_eligible_now": False,
            "required_human_actions": action_list(missing, row),
            "policy": "Draft backlog row only; not authorization, not feedback intake, and not a training label.",
        })
    return rows


def build_local_status(local_rows: list[dict[str, Any]], validation_report: dict[str, Any]) -> list[dict[str, Any]]:
    validation_records = validation_report.get("records") or []
    rows = []
    for idx, row in enumerate(local_rows):
        validation = validation_records[idx] if idx < len(validation_records) and isinstance(validation_records[idx], dict) else {}
        errors = validation.get("errors") or []
        rows.append({
            "backlog_id": stable_id("local-intake", idx, row.get("plate_id"), row.get("well_id"), row.get("variant_id")),
            "source": "experiment_feedback_plate.local",
            "plate_id": row.get("plate_id"),
            "well_id": row.get("well_id"),
            "variant_id": row.get("variant_id"),
            "assay_type": row.get("assay_type"),
            "replicate": row.get("replicate"),
            "qc_flag": row.get("qc_flag"),
            "review_status": row.get("review_status"),
            "valid": bool(validation.get("valid")),
            "training_eligible": bool(validation.get("training_eligible")),
            "claim_eligible_now": False,
            "errors": errors,
            "required_human_actions": [] if not errors else ["fix validation errors and rerun validate_experiment_feedback_plate_intake.py"],
            "policy": "Local plate intake status only; model claim remains false until downstream release gates approve it.",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build plate feedback intake backlog")
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--local-intake", type=Path, default=LOCAL_INTAKE)
    parser.add_argument("--plate-validation", type=Path, default=PLATE_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    draft_files = sorted(args.draft_dir.glob("*.jsonl"))
    packet_files = sorted(args.packet_dir.glob("*.jsonl"))
    drafts = [row for path in draft_files for row in load_jsonl(path)]
    packets = [row for path in packet_files for row in load_jsonl(path)]
    local_rows = load_jsonl(args.local_intake)
    validation_report = load_json(args.plate_validation)

    draft_backlog = build_draft_backlog(drafts, packets)
    local_status = build_local_status(local_rows, validation_report)
    rows = [*draft_backlog, *local_status]
    write_jsonl(args.output, rows)

    blocker_counts = Counter(blocker for row in draft_backlog for blocker in row.get("blockers", []))
    missing_counts = Counter(field for row in draft_backlog for field in row.get("missing_required_fields", []))
    source_bucket_counts = Counter(row.get("source_review_bucket") for row in draft_backlog)
    local_training_eligible = sum(1 for row in local_status if row.get("training_eligible") is True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "draft_files": [rel(path) for path in draft_files],
        "packet_files": [rel(path) for path in packet_files],
        "local_intake": rel(args.local_intake),
        "plate_validation_report": rel(args.plate_validation),
        "output": rel(args.output),
        "draft_rows": len(drafts),
        "packet_rows": len(packets),
        "local_intake_rows": len(local_rows),
        "backlog_rows": len(rows),
        "blocked_draft_rows": sum(1 for row in draft_backlog if row.get("blockers")),
        "draft_rows_approved_for_plate_intake": sum(1 for row in draft_backlog if row.get("approved_for_plate_intake") is True),
        "local_valid_rows": validation_report.get("valid_rows") or 0,
        "local_training_eligible_rows": local_training_eligible,
        "ready_for_feedback_intake_rows": local_training_eligible,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "missing_field_counts": dict(sorted(missing_counts.items())),
        "source_bucket_counts": dict(sorted((str(key), value) for key, value in source_bucket_counts.items())),
        "policy": "This backlog is audit-only. It never authorizes source use, never appends plate feedback, and never promotes training labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "draft_rows": report["draft_rows"],
        "local_intake_rows": report["local_intake_rows"],
        "backlog_rows": report["backlog_rows"],
        "ready_for_feedback_intake_rows": report["ready_for_feedback_intake_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
