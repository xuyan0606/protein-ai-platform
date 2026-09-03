#!/usr/bin/env python3
"""Build a supervised mutation table from enzyme DB labels.

The table intentionally excludes direct measurement values such as dTm and ddG
from model features because current labels are derived from those measurements.
Those fields are preserved as label metadata only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "features" / "enzyme_mutation_labels.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "enzyme_mutation_training_table_report.json"

AA_CHARGE = {
    "D": -1,
    "E": -1,
    "K": 1,
    "R": 1,
    "H": 0.5,
}
AA_HYDROPATHY = {
    "A": 1.8,
    "R": -4.5,
    "N": -3.5,
    "D": -3.5,
    "C": 2.5,
    "Q": -3.5,
    "E": -3.5,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "L": 3.8,
    "K": -3.9,
    "M": 1.9,
    "F": 2.8,
    "P": -1.6,
    "S": -0.8,
    "T": -0.7,
    "W": -0.9,
    "Y": -1.3,
    "V": 4.2,
}
AA_VOLUME = {
    "A": 88.6,
    "R": 173.4,
    "N": 114.1,
    "D": 111.1,
    "C": 108.5,
    "Q": 143.8,
    "E": 138.4,
    "G": 60.1,
    "H": 153.2,
    "I": 166.7,
    "L": 166.7,
    "K": 168.6,
    "M": 162.9,
    "F": 189.9,
    "P": 112.7,
    "S": 89.0,
    "T": 116.1,
    "W": 227.8,
    "Y": 193.6,
    "V": 140.0,
}
AA_AROMATIC = set("FYW")
AA_POLAR = set("STNQYC")
AA_SMALL = set("AGSTC")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_truthy_marker(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return False


def aa_charge(aa: str | None) -> float:
    return float(AA_CHARGE.get((aa or "").upper(), 0.0))


def aa_value(table: dict[str, float], aa: str | None) -> float:
    return float(table.get((aa or "").upper(), 0.0))


def band_ph(value: Any) -> tuple[bool, bool, bool]:
    if value is None:
        return False, False, False
    ph = float(value)
    return ph < 6.0, 6.0 <= ph <= 8.0, ph > 8.0


def band_temperature(value: Any) -> tuple[bool, bool, bool]:
    if value is None:
        return False, False, False
    temp = float(value)
    return temp < 30.0, 30.0 <= temp <= 45.0, temp > 45.0


def method_flags(value: Any) -> dict[str, bool]:
    text = str(value or "").lower()
    return {
        "method_cd": "cd" in text or "circular" in text,
        "method_calorimetry": "dsc" in text or "calorim" in text,
        "method_fluorescence": "fluor" in text,
        "method_denaturation": "denaturation" in text or "urea" in text or "gdn" in text,
        "method_thermal_shift": "thermal" in text or "tm" in text,
    }


def convert_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if (
        row.get("usable_as_training_label") is not True
        or row.get("usable_as_supervised_label") is not True
        or row.get("training_pipeline_unlocked") is not True
        or row.get("numbering_verified_by_sequence") is not True
        or is_truthy_marker(row.get("usable_as_weak_evidence"))
        or row.get("integrity_flags")
        or row.get("label_decision") not in {"go", "watch", "no_go"}
    ):
        return None

    wt = (row.get("wild_type") or "").upper()
    mut = (row.get("mutant") or "").upper()
    seq_length = int(row.get("seq_length") or 0)
    mutation_position = int(row.get("mutation_position") or 0)
    position_fraction = round(mutation_position / seq_length, 6) if seq_length > 0 and mutation_position > 0 else 0.0
    ph_acidic, ph_neutral, ph_basic = band_ph(row.get("assay_ph"))
    temp_low, temp_mesophilic, temp_high = band_temperature(row.get("assay_temperature_c"))
    wt_charge = aa_charge(wt)
    mut_charge = aa_charge(mut)
    method_features = method_flags(row.get("method"))

    output = {
        "record_id": row.get("label_id"),
        "source": row.get("source"),
        "record_type": row.get("record_type"),
        "uniprot_id": row.get("uniprot_id"),
        "group_key": f"uniprot:{row.get('uniprot_id') or 'unknown'}",
        "seq_length": seq_length,
        "mutation": row.get("mutation"),
        "mutation_position": mutation_position,
        "position_fraction": position_fraction,
        "wild_type": wt,
        "mutant": mut,
        "is_to_proline": mut == "P",
        "is_from_proline": wt == "P",
        "is_to_glycine": mut == "G",
        "is_from_glycine": wt == "G",
        "is_aromatic_to_nonaromatic": wt in AA_AROMATIC and mut not in AA_AROMATIC,
        "is_nonaromatic_to_aromatic": wt not in AA_AROMATIC and mut in AA_AROMATIC,
        "is_polar_change": (wt in AA_POLAR) != (mut in AA_POLAR),
        "is_small_change": (wt in AA_SMALL) != (mut in AA_SMALL),
        "wt_charge": wt_charge,
        "mutant_charge": mut_charge,
        "charge_delta": mut_charge - wt_charge,
        "charge_abs_delta": abs(mut_charge - wt_charge),
        "hydropathy_delta": round(aa_value(AA_HYDROPATHY, mut) - aa_value(AA_HYDROPATHY, wt), 3),
        "volume_delta": round(aa_value(AA_VOLUME, mut) - aa_value(AA_VOLUME, wt), 3),
        "volume_abs_delta": round(abs(aa_value(AA_VOLUME, mut) - aa_value(AA_VOLUME, wt)), 3),
        "assay_has_ph": row.get("assay_ph") is not None,
        "assay_ph_acidic": ph_acidic,
        "assay_ph_neutral": ph_neutral,
        "assay_ph_basic": ph_basic,
        "assay_has_temperature": row.get("assay_temperature_c") is not None,
        "assay_temp_low": temp_low,
        "assay_temp_mesophilic": temp_mesophilic,
        "assay_temp_high": temp_high,
        "method_present": bool(row.get("method")),
        "label_decision": row.get("label_decision"),
        "label_stability_delta_tm_c": row.get("label_stability_delta_tm_c"),
        "label_ddg": row.get("label_ddg"),
        "label_source_db": row.get("source_db"),
    }
    output.update(method_features)
    return output


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build supervised mutation training table")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = [converted for row in load_jsonl(args.input) if (converted := convert_row(row)) is not None]
    decisions: dict[str, int] = {}
    groups: dict[str, int] = {}
    for row in rows:
        decisions[row["label_decision"]] = decisions.get(row["label_decision"], 0) + 1
        groups[row["group_key"]] = groups.get(row["group_key"], 0) + 1

    write_jsonl(args.output, rows)
    report = {
        "rows": len(rows),
        "groups": len(groups),
        "label_distribution": dict(sorted(decisions.items())),
        "output": str(args.output),
        "training_pipeline_unlocked": bool(rows),
        "safe_for_training_pipeline": bool(rows),
        "safe_for_model_claim": False,
        "leakage_guard": "label_stability_delta_tm_c and label_ddg are retained as metadata and must not be used as training features",
        "policy": "Rows must explicitly carry usable_as_training_label, usable_as_supervised_label, training_pipeline_unlocked, numbering_verified_by_sequence, no truthy weak-evidence marker, no integrity_flags, and an allowed label_decision before this legacy builder emits training rows.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "groups": len(groups), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
