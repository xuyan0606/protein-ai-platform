#!/usr/bin/env python3
"""Audit user-designated wet-lab mutant library database assets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = AI_ROOT / "酶改造突变体库-湿实验数据"
ROWS_OUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_asset_audit.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "wet_lab_mutant_library_asset_audit_report.json"
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


def project_id(path: Path) -> str:
    name = path.parent.name
    if name.startswith("15B"):
        return "15B"
    if name.startswith("16B"):
        return "16B"
    if name.startswith("4G"):
        return "4G"
    return name


def file_role(path: Path) -> str:
    name = path.name
    if name.startswith("01_"):
        return "variant_summary"
    if name.startswith("02_"):
        return "measurement_judgement"
    if name.startswith("03_"):
        return "derived_vs_control"
    if name.startswith("04_"):
        return "raw_measurement_fact"
    if name.startswith("05_"):
        return "sample_batch_map"
    if name.startswith("06_"):
        return "batch_control_map"
    return "documentation_or_script"


def variant_field(row: dict[str, Any]) -> str:
    return str(row.get("variant_name") or row.get("突变体") or "")


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


def verify_15b_mutation(sequence: str, mutation: str) -> bool | None:
    match = MUTATION_RE.match(mutation)
    if not match:
        return None
    wt, pos_text, _mut = match.groups()
    pos = int(pos_text)
    if pos < 1 or pos > len(sequence):
        return False
    return sequence[pos - 1] == wt


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit wet-lab mutant library assets")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--rows-output", type=Path, default=ROWS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    sequence_15b = VENUS_15B_SEQUENCE.read_text(encoding="utf-8").strip() if VENUS_15B_SEQUENCE.exists() else ""
    audit_rows: list[dict[str, Any]] = []
    project_counts: dict[str, Counter[str]] = defaultdict(Counter)
    variant_sets: dict[str, set[str]] = defaultdict(set)
    metric_sets: dict[str, set[str]] = defaultdict(set)
    mutation_parse = Counter()
    numbering_verified_15b = Counter()

    for path in sorted(args.source_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(args.source_root).parts):
            continue
        rel = str(path.relative_to(AI_ROOT))
        role = file_role(path)
        pid = project_id(path)
        row_count = None
        columns: list[str] = []
        effect_counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {}
        primary_recommended_rows = 0
        control_rows = 0
        numeric_rows = 0
        parseable_variant_rows = 0
        unresolved_variant_rows = 0
        numbering_verified_rows = 0

        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
            row_count = len(rows)
            columns = list(rows[0].keys()) if rows else []
            for row in rows:
                variant = variant_field(row)
                if variant:
                    variant_sets[pid].add(variant)
                    mutations, unresolved = parse_mutation_set(variant)
                    if mutations:
                        parseable_variant_rows += 1
                        mutation_parse["parseable_variant_rows"] += 1
                    if unresolved:
                        unresolved_variant_rows += 1
                        mutation_parse["unresolved_variant_rows"] += 1
                    if pid == "15B" and mutations and sequence_15b and all(verify_15b_mutation(sequence_15b, mut) is True for mut in mutations):
                        numbering_verified_rows += 1
                        numbering_verified_15b["verified_rows"] += 1
                if variant in CONTROL_NAMES or row.get("是否为对照") == "是" or row.get("is_control") == "1":
                    control_rows += 1
                metric = row.get("metric_name") or row.get("指标名称")
                if metric:
                    metric_sets[pid].add(str(metric))
                effect = row.get("overall_effect_judgement") or row.get("总体效应判断") or row.get("effect_judgement") or row.get("效应判断")
                if effect:
                    effect_counts[str(effect)] = effect_counts.get(str(effect), 0) + 1
                conf = row.get("confidence_tier") or row.get("置信度等级")
                if conf:
                    confidence_counts[str(conf)] = confidence_counts.get(str(conf), 0) + 1
                primary = row.get("primary_analysis_recommended") or row.get("是否推荐主分析")
                if str(primary).lower() in {"true", "yes", "1", "是", "纳入后续分析"}:
                    primary_recommended_rows += 1
                raw_value = row.get("raw_value_numeric")
                if raw_value not in {None, ""}:
                    try:
                        float(raw_value)
                        numeric_rows += 1
                    except ValueError:
                        pass

        project_counts[pid][role] += row_count if row_count is not None else 1
        audit_rows.append({
            "project_id": pid,
            "relative_path": rel,
            "file_role": role,
            "suffix": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "csv_rows": row_count,
            "columns": columns,
            "control_rows": control_rows,
            "numeric_rows": numeric_rows,
            "primary_recommended_rows": primary_recommended_rows,
            "parseable_variant_rows": parseable_variant_rows,
            "unresolved_variant_rows": unresolved_variant_rows,
            "numbering_verified_rows": numbering_verified_rows,
            "effect_counts": effect_counts,
            "confidence_counts": confidence_counts,
            "policy": "Asset audit only; no wet-lab row is imported into training by this script.",
        })

    args.rows_output.parent.mkdir(parents=True, exist_ok=True)
    args.rows_output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audit_rows), encoding="utf-8")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_root": str(args.source_root),
        "rows_output": str(args.rows_output),
        "file_count": len(audit_rows),
        "csv_file_count": sum(1 for row in audit_rows if row["suffix"] == ".csv"),
        "project_ids": sorted(set(row["project_id"] for row in audit_rows)),
        "project_role_row_counts": {pid: dict(counter) for pid, counter in project_counts.items()},
        "variant_counts": {pid: len(values) for pid, values in variant_sets.items()},
        "metric_counts": {pid: len(values) for pid, values in metric_sets.items()},
        "metrics_by_project": {pid: sorted(values) for pid, values in metric_sets.items()},
        "mutation_parse_counts": dict(mutation_parse),
        "venus15b_sequence_present": bool(sequence_15b),
        "venus15b_sequence_length": len(sequence_15b) if sequence_15b else 0,
        "venus15b_numbering_verified_rows": numbering_verified_15b.get("verified_rows", 0),
        "safe_for_model_claim": False,
        "policy": "User-designated real wet-lab assets are registered as evidence; training eligibility is handled by downstream validators.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "file_count": report["file_count"],
        "csv_file_count": report["csv_file_count"],
        "project_ids": report["project_ids"],
        "variant_counts": report["variant_counts"],
        "venus15b_numbering_verified_rows": report["venus15b_numbering_verified_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
