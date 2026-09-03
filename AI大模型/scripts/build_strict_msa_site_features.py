#!/usr/bin/env python3
"""Join validated MSA/conservation cache onto strict supervised mutation rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
CACHE_VALIDATION = AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"
CONSERVATION_ROOT = AI_ROOT / "datasets" / "curation" / "msa_conservation"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_strict_msa_site_features.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "strict_msa_site_feature_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def conservation_payload(uniprot_id: str, root: Path) -> dict[str, Any]:
    return load_json(root / f"{uniprot_id}.conservation.json")


def window_values(values: list[float], position: int, radius: int) -> list[float]:
    start = max(1, position - radius)
    end = min(len(values), position + radius)
    return values[start - 1:end]


def enrich(row: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    position = int(row.get("mutation_position") or 0)
    values = payload.get("position_conservation") or []
    if not isinstance(values, list) or position < 1 or position > len(values):
        return None, "missing_or_out_of_range_conservation"

    output = dict(row)
    site_value = float(values[position - 1])
    summary = payload.get("summary") or {}
    output.update({
        "msa_feature_available": True,
        "msa_source": payload.get("source"),
        "msa_source_database": payload.get("source_database"),
        "msa_database_version": payload.get("database_version"),
        "msa_hit_count": int(payload.get("hit_count") or 0),
        "msa_raw_hit_count": int(payload.get("raw_hit_count") or 0),
        "msa_positions_with_homolog_coverage": int(summary.get("positions_with_homolog_coverage") or 0),
        "msa_mean_homolog_depth": float(summary.get("mean_homolog_depth") or 0.0),
        "msa_max_homolog_depth": int(summary.get("max_homolog_depth") or 0),
        "msa_site_conservation": round(site_value, 6),
        "msa_site_low_conservation": site_value < 0.25,
        "msa_site_moderate_conservation": 0.25 <= site_value < 0.75,
        "msa_site_high_conservation": site_value >= 0.75,
        "msa_feature_scope": "strict_verified_numbering_only",
    })
    for radius in (3, 7, 15):
        values_window = window_values([float(value) for value in values], position, radius)
        output[f"msa_window_{radius}_mean_conservation"] = round(mean(values_window), 6) if values_window else 0.0
        output[f"msa_window_{radius}_min_conservation"] = round(min(values_window), 6) if values_window else 0.0
        output[f"msa_window_{radius}_max_conservation"] = round(max(values_window), 6) if values_window else 0.0
    return output, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strict MSA site-level features")
    parser.add_argument("--input", type=Path, default=STRICT)
    parser.add_argument("--cache-validation", type=Path, default=CACHE_VALIDATION)
    parser.add_argument("--conservation-root", type=Path, default=CONSERVATION_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    cache_validation = load_json(args.cache_validation)
    enriched: list[dict[str, Any]] = []
    errors = Counter()
    payload_cache: dict[str, dict[str, Any]] = {}
    if not cache_validation.get("ready"):
        errors["msa_cache_validation_not_ready"] = len(rows)
    else:
        for row in rows:
            uniprot_id = str(row.get("uniprot_id") or "")
            payload = payload_cache.setdefault(uniprot_id, conservation_payload(uniprot_id, args.conservation_root))
            if not payload:
                errors["missing_conservation_payload"] += 1
                continue
            item, error = enrich(row, payload)
            if error:
                errors[error] += 1
                continue
            if item:
                enriched.append(item)

    write_jsonl(args.output, enriched)
    report = {
        "input_rows": len(rows),
        "feature_rows": len(enriched),
        "missing_rows": len(rows) - len(enriched),
        "groups": len({row.get("group_key") for row in enriched}),
        "label_distribution": dict(Counter(row.get("label_decision") for row in enriched)),
        "error_counts": dict(errors),
        "cache_validation_ready": bool(cache_validation.get("ready")),
        "cache_validation_valid_rows": cache_validation.get("valid_rows"),
        "output": str(args.output),
        "safe_for_model_claim": False,
        "policy": "MSA features are joined only to strict verified rows; this does not create new labels or relax row-count gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "feature_rows": report["feature_rows"],
        "missing_rows": report["missing_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
