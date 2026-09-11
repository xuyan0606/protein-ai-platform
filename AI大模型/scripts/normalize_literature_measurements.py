#!/usr/bin/env python3
"""Normalize manually extracted enzyme measurements without filling unknowns."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")
UNIT_CONVERSIONS = {
    ("km", "m"): 1.0,
    ("km", "mm"): 0.001,
    ("kcat", "s-1"): 1.0,
    ("tm", "c"): 1.0,
    ("ph", "ph"): 1.0,
    ("mutation_effect", "relative"): 1.0,
    ("stability", "kcal/mol"): 1.0,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _record_id(row: Dict[str, Any]) -> str:
    identity = {
        key: row.get(key)
        for key in ("source_id", "protein_sequence", "mutation", "metric", "value", "unit", "pH", "temperature", "source_row_or_table")
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()[:24]


def _parse_mutation(value: Any) -> Dict[str, Any]:
    mutation = str(value or "").strip().upper()
    if not mutation:
        return {"mutation": None, "wt_aa": None, "mutant_aa": None, "canonical_position": None}
    match = MUTATION_RE.fullmatch(mutation)
    if not match:
        return {"mutation": mutation, "wt_aa": None, "mutant_aa": None, "canonical_position": None}
    return {
        "mutation": mutation,
        "wt_aa": match.group(1),
        "mutant_aa": match.group(3),
        "canonical_position": int(match.group(2)),
    }


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    sequence = str(row.get("protein_sequence") or "").strip().upper()
    metric = str(row.get("metric") or "").strip().lower()
    original_unit = str(row.get("unit") or "").strip()
    unit = original_unit.lower()
    flags: List[str] = []
    if not sequence or not SEQUENCE_RE.fullmatch(sequence):
        flags.append("invalid_protein_sequence")
    if not metric:
        flags.append("missing_metric")
    if row.get("value") in (None, ""):
        flags.append("missing_value")
    if not unit:
        flags.append("missing_unit")
    if not row.get("source_id"):
        flags.append("missing_source_id")
    if not row.get("source_row_or_table"):
        flags.append("missing_source_row_or_table")
    if not row.get("license"):
        flags.append("missing_license")
    mutation = _parse_mutation(row.get("mutation"))
    if mutation["canonical_position"] is not None:
        position = mutation["canonical_position"]
        if position > len(sequence) or sequence[position - 1] != mutation["wt_aa"]:
            flags.append("mutation_wild_type_mismatch")
    try:
        original_value = float(row.get("value"))
    except (TypeError, ValueError):
        original_value = None
        flags.append("invalid_numeric_value")
    factor = UNIT_CONVERSIONS.get((metric, unit))
    if factor is None:
        value_si = None
        if unit:
            flags.append("unsupported_unit")
    else:
        value_si = original_value * factor if original_value is not None else None
    if row.get("pH") in (None, "") and metric in {"km", "kcat", "kcat/km", "tm", "activity", "stability"}:
        flags.append("missing_assay_ph")
    if row.get("temperature") in (None, "") and metric in {"km", "kcat", "kcat/km", "activity"}:
        flags.append("missing_assay_temperature")
    normalized: Dict[str, Any] = dict(row)
    normalized.update(mutation)
    normalized.update(
        {
            "record_id": _record_id(row),
            "protein_sequence": sequence,
            "sequence_hash": hashlib.sha256(sequence.encode("ascii")).hexdigest() if sequence else None,
            "metric": metric,
            "original_value": original_value,
            "original_unit": original_unit or None,
            "value_si": value_si,
            "quality_flags": sorted(set(flags)),
            "provenance_status": "source_attached" if not flags else "incomplete",
            "training_import_status": "training_candidate" if not flags else "needs_review",
        }
    )
    return normalized


def normalize_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_row(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = normalize_rows(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in normalized), encoding="utf-8")
    print(json.dumps({"input_rows": len(rows), "output_rows": len(normalized), "training_candidate_rows": sum(row["training_import_status"] == "training_candidate" for row in normalized)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
