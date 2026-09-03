#!/usr/bin/env python3
"""Build human review packets for candidate experiment feedback sources."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_candidates.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "feedback" / "source_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "feedback" / "source_review_drafts"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def classify(row: dict[str, Any]) -> str:
    rel = str(row.get("relative_path") or "").lower()
    name = Path(rel).name
    hits = set(row.get("keyword_hits") or [])
    if ".tmp/" in rel or rel in {"task_plan.md", "progress.md", "findings.md"}:
        return "development_or_noise"
    if "backend/app/skills" in rel or "docs/designs" in rel or "roadmap" in rel:
        return "development_or_noise"
    if "benchmark" in rel or "fixtures" in rel or "deploy_data/annotations" in rel:
        return "fixture_or_reference"
    if "matvenus-research" in rel or rel.startswith("matvenus-session"):
        if any(token in rel for token in ["数据反馈", "feedback", "湿实验", "实验数据"]):
            return "historical_feedback_candidate"
        if {"实验", "活性", "突变"} & hits:
            return "historical_session_candidate"
    if name.endswith(".docx") and "实验方案" in name:
        return "assay_protocol_reference"
    if {"实验", "活性", "突变", "底物"} & hits:
        return "manual_feedback_triage"
    return "low_signal_candidate"


def draft_for(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return {
        "source_path": row.get("relative_path"),
        "decision": "keep_unvalidated",
        "source_type_guess": row.get("source_review_bucket"),
        "extractability": "unreviewed",
        "candidate_feedback_rows": 0,
        "approved_for_feedback_intake": False,
        "required_checks": [
            "confirm this is wet-lab or historical KWB experimental feedback, not a plan or generated recommendation",
            "extract mutation, assay type, condition, outcome, source, and recorded date",
            "verify mutation numbering before writing experiment_feedback.local.jsonl",
            "preserve failed/inconclusive results as real feedback when source is genuine",
        ],
        "notes": f"Draft from {packet_id}; not a feedback record and not training data.",
        "reviewer": "local-reviewer",
        "reviewed_at": "2026-07-25T00:00:00+08:00",
        "draft_policy": "draft_only; source review is not experiment feedback intake",
    }


def packet_prefix(bucket: str) -> str:
    return "feedback_source_" + bucket.replace("_candidate", "").replace("_reference", "")


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def write_markdown(path: Path, packet_id: str, rows: list[dict[str, Any]], draft_path: Path) -> None:
    lines = [
        f"# {packet_id}",
        "",
        "Policy: source review packets are not feedback intake and cannot train any model.",
        "",
        f"Decision draft template: `{draft_path}`",
        "",
        "| rank | bucket | score | type | size | relative path | hits | action |",
        "|---:|---|---:|---|---:|---|---|---|",
    ]
    for index, row in enumerate(rows, start=1):
        hits = ", ".join((row.get("keyword_hits") or [])[:12])
        rel = str(row.get("relative_path") or "").replace("|", "/")
        lines.append(
            f"| {index} | {row.get('source_review_bucket')} | {row.get('candidate_score')} | "
            f"{row.get('extension')} | {row.get('size_bytes')} | {rel} | {hits} | "
            "confirm_source_then_extract_or_keep_unvalidated |"
        )
    lines.extend([
        "",
        "Required checks:",
        "- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.",
        "- Import only genuine KWB wet-lab or historical experimental outcomes.",
        "- Keep failed and inconclusive outcomes if they are real experiments.",
        "- Numbering must be verified before a row becomes training eligible.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build experiment feedback source review packets")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    enriched = []
    for row in rows:
        item = {**row, "source_review_bucket": classify(row)}
        enriched.append(item)

    bucket_order = {
        "historical_feedback_candidate": 0,
        "historical_session_candidate": 1,
        "assay_protocol_reference": 2,
        "manual_feedback_triage": 3,
        "fixture_or_reference": 4,
        "development_or_noise": 5,
        "low_signal_candidate": 6,
    }
    enriched.sort(key=lambda row: (bucket_order.get(row["source_review_bucket"], 99), -int(row.get("candidate_score") or 0), row.get("relative_path") or ""))

    reports = []
    for bucket in sorted({row["source_review_bucket"] for row in enriched}, key=lambda item: bucket_order.get(item, 99)):
        bucket_rows = [row for row in enriched if row["source_review_bucket"] == bucket]
        for index, packet_rows in enumerate(chunks(bucket_rows, args.batch_size), start=1):
            packet_id = f"{packet_prefix(bucket)}_{index:03d}"
            packet_jsonl = args.out_dir / f"{packet_id}.jsonl"
            packet_md = args.out_dir / f"{packet_id}.md"
            draft_jsonl = args.draft_dir / f"{packet_id}.source_review.draft.jsonl"
            write_jsonl(packet_jsonl, packet_rows)
            write_jsonl(draft_jsonl, [draft_for(row, packet_id) for row in packet_rows])
            write_markdown(packet_md, packet_id, packet_rows, draft_jsonl)
            reports.append({
                "packet_id": packet_id,
                "bucket": bucket,
                "rows": len(packet_rows),
                "jsonl": str(packet_jsonl),
                "markdown": str(packet_md),
                "decision_draft": str(draft_jsonl),
            })

    report = {
        "input_rows": len(rows),
        "packets": len(reports),
        "packet_rows": sum(item["rows"] for item in reports),
        "draft_rows": sum(item["rows"] for item in reports),
        "bucket_counts": dict(Counter(row["source_review_bucket"] for row in enriched)),
        "packet_reports": reports,
        "policy": "review packets and drafts are not experiment feedback; only schema-valid rows in experiment_feedback.local.jsonl can enter intake validation",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "packets": report["packets"],
        "packet_rows": report["packet_rows"],
        "bucket_counts": report["bucket_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
