#!/usr/bin/env python3
"""Build wet-lab feedback candidate rows from mutant library database assets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = AI_ROOT / "酶改造突变体库-湿实验数据"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_candidate_report.json"
VENUS_15B_SEQUENCE = AI_ROOT / "Venus-15B淀粉酶项目" / "淀粉酶15B序列.txt"

MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")
CONTROL_NAMES = {"WT", "2A", "PICZa-4G", "PICZA-4G"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def project_id(path: Path) -> str:
    name = path.parent.name
    if name.startswith("15B"):
        return "15B"
    if name.startswith("16B"):
        return "16B"
    if name.startswith("4G"):
        return "4G"
    return name


def parse_mutation_set(variant: str) -> tuple[list[str], list[str]]:
    if not variant or variant in CONTROL_NAMES:
        return [], []
    mutations: list[str] = []
    unresolved: list[str] = []
    for token in variant.split("+"):
        token = token.strip()
        if MUTATION_RE.match(token):
            mutations.append(token)
        else:
            unresolved.append(token)
    return mutations, unresolved


def verify_15b(sequence: str, mutations: list[str]) -> bool:
    if not sequence or not mutations:
        return False
    for mutation in mutations:
        match = MUTATION_RE.match(mutation)
        if not match:
            return False
        wt, pos_text, _mut = match.groups()
        pos = int(pos_text)
        if pos < 1 or pos > len(sequence) or sequence[pos - 1] != wt:
            return False
    return True


def build_sample_variant_maps(source_root: Path) -> dict[str, dict[str, str]]:
    maps: dict[str, dict[str, str]] = {}
    for path in sorted(source_root.rglob("05_*对应表.csv")):
        pid = project_id(path)
        sample_map: dict[str, str] = {}
        for row in read_csv(path):
            sample_id = row.get("样本ID") or row.get("sample_id")
            variant = row.get("突变体") or row.get("variant_name")
            if sample_id and variant:
                sample_map[sample_id] = variant
        maps[pid] = sample_map
    return maps


def normalized_fields(row: dict[str, str], pid: str, sample_variant_maps: dict[str, dict[str, str]]) -> dict[str, Any]:
    if pid == "15B":
        return {
            "measurement_id": row.get("测量ID"),
            "sample_id": row.get("样本ID"),
            "batch_id": row.get("批次ID"),
            "variant": row.get("突变体"),
            "metric_name": row.get("指标名称"),
            "metric_code": row.get("指标代码"),
            "raw_value_numeric": as_float(row.get("raw_value_numeric")),
            "control_value_numeric": as_float(row.get("control_value_numeric")),
            "vs_control_ratio": as_float(row.get("相对2A比值")),
            "vs_control_delta": as_float(row.get("相对2A差值")),
            "vs_control_pct_change": as_float(row.get("相对2A变化百分比")),
            "compare_direction": row.get("相对2A方向"),
            "confidence_tier": row.get("置信度等级"),
            "analysis_use_level": row.get("分析用途层级"),
            "primary_analysis_recommended": row.get("是否推荐主分析") == "是",
            "control_sample_id": row.get("对照样本ID"),
        }
    sample_id = row.get("sample_id")
    return {
        "measurement_id": row.get("measurement_id"),
        "sample_id": sample_id,
        "batch_id": row.get("batch_id"),
        "variant": row.get("variant_name") or sample_variant_maps.get(pid, {}).get(str(sample_id or "")),
        "metric_name": row.get("metric_name"),
        "metric_code": None,
        "raw_value_numeric": as_float(row.get("raw_value_numeric")),
        "control_value_numeric": as_float(row.get("control_value_numeric")),
        "vs_control_ratio": as_float(row.get("vs_control_ratio")),
        "vs_control_delta": as_float(row.get("vs_control_delta")),
        "vs_control_pct_change": as_float(row.get("vs_control_pct_change")),
        "compare_direction": row.get("compare_direction"),
        "confidence_tier": row.get("confidence_tier"),
        "analysis_use_level": None,
        "primary_analysis_recommended": True,
        "control_sample_id": row.get("control_sample_id"),
    }


def assay_type(metric_name: str) -> str:
    if any(token in metric_name for token in ["稳定", "耐温", "Tm", "残率"]):
        return "stability"
    return "activity"


def outcome_from_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "inconclusive"
    if ratio >= 1.15:
        return "go"
    if ratio <= 0.70:
        return "no_go"
    return "watch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab mutant library feedback candidates")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    sequence_15b = VENUS_15B_SEQUENCE.read_text(encoding="utf-8").strip() if VENUS_15B_SEQUENCE.exists() else ""
    sample_variant_maps = build_sample_variant_maps(args.source_root)
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for path in sorted(args.source_root.rglob("03_*派生分析表.csv")):
        pid = project_id(path)
        source_hash = sha256(path)
        for index, source_row in enumerate(read_csv(path), start=1):
            item = normalized_fields(source_row, pid, sample_variant_maps)
            variant = str(item["variant"] or "")
            mutations, unresolved = parse_mutation_set(variant)
            is_control = variant in CONTROL_NAMES
            numbering_verified = pid == "15B" and verify_15b(sequence_15b, mutations)
            numeric = item["raw_value_numeric"] is not None and item["vs_control_ratio"] is not None
            candidate_id = hashlib.sha256(f"{path}:{index}:{item['measurement_id']}".encode("utf-8")).hexdigest()[:20]
            training_candidate = (
                numeric
                and not is_control
                and bool(mutations)
                and not unresolved
                and numbering_verified
                and bool(item["primary_analysis_recommended"])
            )
            row = {
                "feedback_candidate_id": f"wetlab-mutlib-{candidate_id}",
                "source": "kwb_wet_lab",
                "source_project": pid,
                "source_file": str(path.relative_to(AI_ROOT)),
                "source_file_sha256": source_hash,
                "source_row_index": index,
                "measurement_id": item["measurement_id"],
                "sample_id": item["sample_id"],
                "batch_id": item["batch_id"],
                "control_sample_id": item["control_sample_id"],
                "variant": variant,
                "is_control": is_control,
                "mutation_set": mutations,
                "unresolved_variant_tokens": unresolved,
                "numbering_verified": numbering_verified,
                "numbering_verification_basis": "Venus-15B local sequence" if numbering_verified else None,
                "assay_type": assay_type(str(item["metric_name"] or "")),
                "metric_name": item["metric_name"],
                "metric_code": item["metric_code"],
                "raw_value_numeric": item["raw_value_numeric"],
                "control_value_numeric": item["control_value_numeric"],
                "activity_relative_to_wt": item["vs_control_ratio"] if assay_type(str(item["metric_name"] or "")) == "activity" else None,
                "stability_relative_to_wt": item["vs_control_ratio"] if assay_type(str(item["metric_name"] or "")) == "stability" else None,
                "vs_control_ratio": item["vs_control_ratio"],
                "vs_control_delta": item["vs_control_delta"],
                "vs_control_pct_change": item["vs_control_pct_change"],
                "compare_direction": item["compare_direction"],
                "outcome_candidate": outcome_from_ratio(item["vs_control_ratio"]),
                "confidence_tier": item["confidence_tier"],
                "analysis_use_level": item["analysis_use_level"],
                "primary_analysis_recommended": bool(item["primary_analysis_recommended"]),
                "data_granularity": "numeric_relative_to_control_measurement",
                "numeric_training_candidate": training_candidate,
                "ready_for_feedback_intake": False,
                "blocked_from_feedback_intake_reasons": [] if training_candidate else [
                    reason
                    for reason, blocked in [
                        ("control_row", is_control),
                        ("non_numeric_or_missing_ratio", not numeric),
                        ("mutation_not_parseable", not mutations or bool(unresolved)),
                        ("numbering_not_verified", not numbering_verified),
                        ("not_primary_analysis_recommended", not item["primary_analysis_recommended"]),
                    ]
                    if blocked
                ],
                "claim_eligible_now": False,
                "policy": "Wet-lab feedback candidate only; not appended to experiment_feedback.local.jsonl automatically.",
            }
            rows.append(row)
            counts["rows"] += 1
            counts[f"project_{pid}_rows"] += 1
            counts[f"assay_{row['assay_type']}_rows"] += 1
            if training_candidate:
                counts["numeric_training_candidate_rows"] += 1
            if numbering_verified:
                counts["numbering_verified_rows"] += 1
            if is_control:
                counts["control_rows"] += 1
            if mutations and not unresolved:
                counts["parseable_mutation_rows"] += 1
                counts[f"project_{pid}_parseable_mutation_rows"] += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_root": str(args.source_root),
        "output": str(args.output),
        "candidate_rows": len(rows),
        "counts": dict(counts),
        "source_projects": sorted({row["source_project"] for row in rows}),
        "numeric_training_candidate_rows": counts.get("numeric_training_candidate_rows", 0),
        "parseable_mutation_rows": counts.get("parseable_mutation_rows", 0),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "policy": "Candidates are evidence-backed wet-lab numeric observations; formal feedback intake remains blocked until reviewed numbering and intake authorization are complete.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "numeric_training_candidate_rows": report["numeric_training_candidate_rows"],
        "ready_for_feedback_intake_rows": report["ready_for_feedback_intake_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
