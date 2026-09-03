#!/usr/bin/env python3
"""Extract local training features from KWB-EnzymeCase JSON files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "datasets" / "sample_case.json"
DEFAULT_JSONL = ROOT / "datasets" / "features" / "sample_features.jsonl"
DEFAULT_CSV = ROOT / "datasets" / "features" / "sample_features.csv"


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def mutation_position(code: str) -> int | None:
    match = re.match(r"^[A-Z]([0-9]{1,5})[A-Z]$", str(code).upper())
    return int(match.group(1)) if match else None


def evidence_counts(case: dict[str, Any]) -> tuple[int, int]:
    private_count = 0
    public_count = 0
    for item in case.get("evidence") or []:
        source = str(item.get("source") or "")
        if source == "kwb_private":
            private_count += 1
        elif source:
            public_count += 1
    return private_count, public_count


def assay_completeness(case: dict[str, Any]) -> tuple[int, dict[str, int]]:
    assay = case.get("assay_condition") or {}
    flags = {
        "assay_has_ph": bool_int(assay.get("ph") not in {None, ""}),
        "assay_has_temperature": bool_int(assay.get("temperature_c") not in {None, ""}),
        "assay_has_expression_system": bool_int(bool(assay.get("expression_system"))),
    }
    completeness = sum(flags.values())
    if assay.get("buffer"):
        completeness += 1
    if assay.get("assay_method"):
        completeness += 1
    return completeness, flags


def extract_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    enzyme = case.get("enzyme") or {}
    structure = case.get("structure") or {}
    substrate = case.get("substrate") or {}
    labels = case.get("labels") or {}
    private_count, public_count = evidence_counts(case)
    completeness, assay_flags = assay_completeness(case)
    tool_names = {str(item.get("tool_name") or "") for item in case.get("tool_results") or []}
    sequence = str(enzyme.get("sequence") or "")
    structure_source = str(structure.get("source_type") or "none")

    base = {
        "case_id": case.get("case_id"),
        "case_type": case.get("case_type"),
        "enzyme_name": enzyme.get("name"),
        "enzyme_family": enzyme.get("family"),
        "has_sequence": bool_int(bool(sequence)),
        "sequence_length": len(sequence),
        "has_structure": bool_int(structure_source not in {"none", "", "None"}),
        "structure_source_uploaded_pdb": bool_int(structure_source == "uploaded_pdb"),
        "structure_source_predicted": bool_int(structure_source in {"alphafold", "esmfold"}),
        "numbering_verified": bool_int(structure.get("numbering_verified")),
        "has_substrate": bool_int(any(substrate.get(key) for key in ("name", "smiles", "sdf_object"))),
        "kwb_private_records": private_count,
        "public_database_records": public_count,
        "tool_result_count": len(tool_names),
        "has_ligand_tool_result": bool_int("ligand_preprocess" in tool_names),
        "has_md_tool_result": bool_int("gromacs_md" in tool_names),
        "has_annotation_result": bool_int(bool(tool_names & {"annotation_bundle", "interpro_annotation", "catalytic_site_lookup"})),
        "assay_completeness": completeness,
        **assay_flags,
        "label_activity_relative_to_wt": labels.get("activity_relative_to_wt"),
        "label_stability_delta_tm_c": labels.get("stability_delta_tm_c"),
        "label_assay_success": labels.get("assay_success"),
        "label_substrate_fit": labels.get("substrate_fit_label"),
        "label_decision": labels.get("decision"),
    }

    rows: list[dict[str, Any]] = []
    for mutation in case.get("mutations") or []:
        code = str(mutation.get("code") or "").upper()
        risk_flags = {str(flag) for flag in mutation.get("risk_flags") or []}
        wild_type = str(mutation.get("wild_type") or (code[:1] if code else "")).upper()
        mutant = str(mutation.get("mutant") or (code[-1:] if code else "")).upper()
        row = dict(base)
        row.update({
            "mutation": code,
            "mutation_position": mutation.get("position") or mutation_position(code),
            "wild_type": wild_type,
            "mutant": mutant,
            "is_proline_mutation": bool_int(mutant == "P"),
            "is_charge_mutation": bool_int(bool({wild_type, mutant} & {"D", "E", "K", "R"})),
            "is_glycine_or_proline_origin": bool_int(wild_type in {"G", "P"}),
            "has_prior_go": bool_int(str(mutation.get("status") or "").lower() == "go"),
            "has_prior_no_go": bool_int(str(mutation.get("status") or "").lower() in {"no_go", "failed"}),
            "risk_protected_catalytic": bool_int(bool(risk_flags & {"protected_catalytic", "catalytic", "active_site_core"})),
            "risk_near_active_site": bool_int("near_active_site" in risk_flags),
            "risk_near_pocket": bool_int("near_pocket" in risk_flags),
            "risk_numbering_uncertain": bool_int("numbering_uncertain" in risk_flags),
            "risk_low_structure_confidence": bool_int("low_structure_confidence" in risk_flags),
        })
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, Any]], jsonl_path: Path, csv_path: Path) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract KWB-EnzymeDesigner local features")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    case = json.loads(args.input.read_text(encoding="utf-8"))
    rows = extract_rows(case)
    write_outputs(rows, args.jsonl, args.csv)
    print(json.dumps({"rows": len(rows), "jsonl": str(args.jsonl), "csv": str(args.csv)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

