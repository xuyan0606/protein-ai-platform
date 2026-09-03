#!/usr/bin/env python3
"""Audit feedback source packets for training-eligible wet-lab evidence.

The audit is intentionally read-only. It helps decide what a human can review
next, but it never writes experiment_feedback.local.jsonl and never promotes a
conversation, model prediction, or downloaded result into a training label.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
PACKET = AI_ROOT / "datasets" / "feedback" / "source_review_packets" / "feedback_source_historical_feedback_001.jsonl"
JSONL_OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_trainability_audit.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_trainability_audit_report.json"

MUTATION_RE = re.compile(r"\b[A-Z][0-9]{1,5}[A-Z]\b")
URL_RE = re.compile(r"https?://[^\s)\]]+")

WET_LAB_TERMS = [
    "湿实验",
    "实测",
    "实验数据",
    "数据反馈",
    "活性",
    "比活",
    "热稳定",
    "稳定性",
    "Tm",
    "半衰期",
    "表达",
    "可溶性",
]
MEASUREMENT_TERMS = [
    "relative",
    "activity",
    "normalized",
    "retention",
    "kcat",
    "Km",
    "Tm",
    "ΔTm",
    "dTm",
    "%",
    "倍",
    "℃",
    "°C",
    "U/mg",
]
CONDITION_TERMS = ["pH", "温度", "buffer", "缓冲", "底物", "substrate", "重复", "replicate", "QC", "误差"]
PREDICTION_ONLY_TERMS = [
    "venusrem_mutation_prediction",
    "venusx_functional_residue_prediction",
    "预测",
    "推荐",
    "候选",
    "Rosetta",
    "ddG",
    "下载完整的全突变预测结果",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def resolve_source(path_text: str) -> Path:
    source = Path(path_text)
    if source.is_absolute():
        return source
    return PLATFORM_ROOT / source


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(1 for term in terms if term.lower() in lower)


def classify(text: str) -> tuple[str, list[str]]:
    mutation_count = len(set(MUTATION_RE.findall(text)))
    wet_lab_signal = count_terms(text, WET_LAB_TERMS)
    measurement_signal = count_terms(text, MEASUREMENT_TERMS)
    condition_signal = count_terms(text, CONDITION_TERMS)
    prediction_signal = count_terms(text, PREDICTION_ONLY_TERMS)

    blockers: list[str] = []
    if mutation_count == 0:
        blockers.append("no_explicit_mutation_tokens")
    if measurement_signal < 2:
        blockers.append("insufficient_measured_metric_terms")
    if condition_signal < 2:
        blockers.append("missing_condition_replicate_or_qc_context")
    if prediction_signal >= wet_lab_signal:
        blockers.append("prediction_or_consultation_dominates_source")

    if not blockers:
        return "manual_review_required_for_possible_wet_lab_intake", []
    if wet_lab_signal > 0 and mutation_count > 0:
        return "candidate_but_not_training_eligible", blockers
    if prediction_signal > 0:
        return "prediction_or_workflow_source_only", blockers
    return "low_signal_source", blockers


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    source_path = row.get("path") or row.get("source_path") or ""
    resolved = resolve_source(str(source_path))
    exists = resolved.exists()
    text = resolved.read_text(encoding="utf-8", errors="replace") if exists and resolved.is_file() else ""
    status, blockers = classify(text)
    urls = URL_RE.findall(text)
    mutation_tokens = sorted(set(MUTATION_RE.findall(text)))
    return {
        "source_path": source_path,
        "resolved_path": str(resolved),
        "exists": exists,
        "source_review_bucket": row.get("source_review_bucket"),
        "candidate_score": row.get("candidate_score"),
        "character_count": len(text),
        "unique_mutation_tokens": mutation_tokens[:100],
        "unique_mutation_token_count": len(mutation_tokens),
        "url_count": len(urls),
        "download_urls": urls[:20],
        "wet_lab_term_hits": count_terms(text, WET_LAB_TERMS),
        "measurement_term_hits": count_terms(text, MEASUREMENT_TERMS),
        "condition_term_hits": count_terms(text, CONDITION_TERMS),
        "prediction_only_term_hits": count_terms(text, PREDICTION_ONLY_TERMS),
        "trainability_status": status,
        "training_eligible": False,
        "manual_review_required": True,
        "blockers": blockers,
        "policy": "Read-only source audit; source rows are not experiment feedback labels.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit feedback source trainability")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    packet_rows = load_jsonl(args.packet)
    rows = [audit_row(row) for row in packet_rows]
    write_jsonl(args.jsonl, rows)
    status_counts = Counter(row["trainability_status"] for row in rows)
    blocker_counts = Counter(blocker for row in rows for blocker in row["blockers"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet": str(args.packet),
        "source_rows": len(packet_rows),
        "audited_rows": len(rows),
        "training_eligible_rows": 0,
        "manual_review_required_rows": sum(1 for row in rows if row["manual_review_required"]),
        "status_counts": dict(status_counts),
        "blocker_counts": dict(blocker_counts),
        "output_jsonl": str(args.jsonl),
        "ready_for_feedback_intake": False,
        "safe_to_auto_promote": False,
        "policy": "No source is promoted by this audit; schema-valid, numbering-verified wet-lab rows must be manually entered into experiment_feedback.local.jsonl.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audited_rows": report["audited_rows"],
        "training_eligible_rows": report["training_eligible_rows"],
        "ready_for_feedback_intake": report["ready_for_feedback_intake"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
