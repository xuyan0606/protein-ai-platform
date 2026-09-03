#!/usr/bin/env python3
"""Clean-room KWB kinetics normalizer inspired by observed OED data contracts.

This module is independently implemented. It does not copy OED source code.
It preserves raw values and emits provenance/quality flags instead of silently
promoting records to training labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MUTATION_RE = re.compile(r"\b[A-Z][0-9]+[A-Z]\b")
PH_RE = re.compile(r"\bpH\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
TEMP_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:°\s*C|℃|C)\b", re.I)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() not in {"", "-", "nan", "None"}:
            return str(value).strip()
    return None


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", value)
    return float(match.group(0)) if match else None


def parse_condition(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    ph_match = PH_RE.search(text)
    temp_match = TEMP_RE.search(text)
    return (
        float(ph_match.group(1)) if ph_match else None,
        float(temp_match.group(1)) if temp_match else None,
    )


def mutation_info(text: str | None) -> tuple[str, list[str], str]:
    if not text:
        return "wildtype", [], "no_mutation_text"
    mutations = sorted(set(MUTATION_RE.findall(text)))
    lowered = text.lower()
    if "mutant" in lowered or "mutated" in lowered or mutations:
        return (
            "mutant" if mutations else "mutant_unparsed",
            mutations,
            "mutation_tokens_found" if mutations else "mutant_text_without_parseable_token",
        )
    return "wildtype", [], "wildtype_text"


def normalize_unit(parameter: str, unit: str | None, value: float | None) -> tuple[str | None, float | None, str]:
    raw_unit = (unit or "").strip()
    unit_key = raw_unit.lower().replace(" ", "")
    if value is None:
        return None, None, "missing_numeric_value"
    if parameter == "kcat":
        if unit_key in {"s^(-1)", "s-1", "1/s", "s^-1"}:
            return "1/s", value, "unit_normalized"
    if parameter == "km":
        if unit_key in {"m", "mol"}:
            return "mM", value * 1000.0, "unit_converted_m_to_mm"
        if unit_key in {"mm", "mmol"}:
            return "mM", value, "unit_normalized"
    if parameter == "kcat_km":
        if unit_key in {"m^(-1)*s^(-1)", "mol^(-1)*s^(-1)", "1/m*s", "1/(m*s)"}:
            return "1/mM*1/s", value / 1000.0, "unit_converted_m_to_mm"
        if unit_key in {"1/mm*1/s", "mm^-1*s^-1"}:
            return "1/mM*1/s", value, "unit_normalized"
    return raw_unit or None, value, "unit_unrecognized"


def normalize_row(
    row: dict[str, str],
    source_file: Path,
    source_file_sha256: str,
    source_row_index: int,
) -> dict[str, Any]:
    parameter_raw = first(row, "parameter", "Parameter", "parameter.type", "TYPE", "type") or ""
    parameter_key = parameter_raw.lower().replace("/", "_").replace(" ", "")
    if parameter_key in {"kcat/km", "kcat_km", "kcatkm"}:
        parameter = "kcat_km"
    elif parameter_key == "kcat":
        parameter = "kcat"
    elif parameter_key == "km":
        parameter = "km"
    else:
        parameter = parameter_key or "unknown"

    commentary = first(row, "COMMENTARY", "commentary", "EnzymeType", "enzyme_type")
    mutation_class, mutations, mutation_basis = mutation_info(commentary)
    condition_text = first(row, "COMMENTARY", "commentary")
    ph, temperature_c = parse_condition(condition_text)
    ph = parse_number(first(row, "PH", "pH")) if first(row, "PH", "pH") else ph
    temperature_c = (
        parse_number(first(row, "Temperature", "temperature_c", "temperature"))
        if first(row, "Temperature", "temperature_c", "temperature")
        else temperature_c
    )

    value_raw = first(row, "value", "VALUE", "parameter.startValue", "KCAT VALUE", "KM VALUE", "KCAT/KM VALUE")
    unit_raw = first(row, "unit", "UNIT", "parameter.unit")
    normalized_unit, normalized_value, unit_status = normalize_unit(
        parameter,
        unit_raw,
        parse_number(value_raw),
    )

    record: dict[str, Any] = {
        "source": first(row, "source", "SOURCE") or "unknown",
        "source_file": str(source_file),
        "source_file_sha256": source_file_sha256,
        "source_row_index": source_row_index,
        "ec": first(row, "EC", "ECNumber", "ec"),
        "substrate": first(row, "SUBSTRATE", "Substrate", "associatedSpecies"),
        "organism": first(row, "ORGANISM", "Organism", "organism"),
        "uniprot_ids": [x for x in re.split(r"[,;\s]+", first(row, "UNIPROT", "UniprotID", "uniprot") or "") if x],
        "pubmed_id": first(row, "PubMedID", "pubmed_id"),
        "enzyme_class": mutation_class,
        "mutation_tokens": mutations,
        "mutation_basis": mutation_basis,
        "parameter": parameter,
        "value_raw": value_raw,
        "unit_raw": unit_raw,
        "value": normalized_value,
        "unit": normalized_unit,
        "unit_status": unit_status,
        "ph": ph,
        "temperature_c": temperature_c,
        "raw_record": row,
        "quality_flags": [],
        "training_eligible": False,
    }

    if not record["ec"]:
        record["quality_flags"].append("missing_ec")
    if not record["substrate"]:
        record["quality_flags"].append("missing_substrate")
    if not record["uniprot_ids"]:
        record["quality_flags"].append("missing_uniprot")
    if record["enzyme_class"] == "mutant_unparsed":
        record["quality_flags"].append("mutant_without_parseable_site")
    if record["value"] is None or record["value"] <= 0:
        record["quality_flags"].append("non_positive_or_missing_value")
    if record["unit_status"] == "unit_unrecognized":
        record["quality_flags"].append("unit_not_admitted")
    return record


def normalize_csv(input_path: Path, output_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_file_sha256 = sha256_file(input_path)
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=2):
            rows.append(normalize_row(row, input_path, source_file_sha256, index))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "input_file": str(input_path),
        "input_sha256": source_file_sha256,
        "output_file": str(output_path),
        "rows": len(rows),
        "rows_with_quality_flags": sum(bool(row["quality_flags"]) for row in rows),
        "rows_training_eligible": 0,
        "policy": "clean-room ETL reference only; provenance and quality flags are retained; no automatic training promotion",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize kinetics CSV into auditable KWB JSONL.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(normalize_csv(args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
