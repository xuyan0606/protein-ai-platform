#!/usr/bin/env python3
"""Extract evidence-only kinetics from PMC12695923 Table 1."""
import argparse
import csv
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

FIELDNAMES = [
    "measurement_id", "pmid", "doi", "pmcid", "family", "enzyme_name",
    "parent_variant", "variant", "mutation_composition", "metric",
    "mutant_value", "mutant_error", "wt_value", "wt_error", "unit",
    "assay_ph", "assay_temperature_c", "assay_substrate", "assay_note",
    "source_path", "source_sha256", "source_locator", "numbering_precheck_id",
    "numbering_status", "human_review_status", "training_eligible",
    "formal_decision_written", "safe_for_model_claim",
]


def txt(element):
    return " ".join("".join(element.itertext()).replace("\u00a0", " ").split())


def value(raw):
    parts = re.split(r"\s*±\s*", raw.strip())
    if len(parts) != 2:
        raise ValueError(f"expected mean ± error value, got {raw!r}")
    return parts[0].replace(",", ""), parts[1].replace(",", "")


def build_rows(rootdir):
    rel = Path("literature/raw_fulltext_xml/amylase/PMC12695923.xml")
    path = rootdir / rel
    root = ET.parse(path).getroot()
    ids = {node.attrib.get("pub-id-type"): (node.text or "").strip()
           for node in root.findall(".//article-id")}
    required = {"pmid", "doi", "pmcid"}
    if not required <= ids.keys():
        raise ValueError("missing article identifiers")
    source = {
        "pmid": ids["pmid"], "doi": ids["doi"], "pmcid": ids["pmcid"],
        "source_path": str(rel),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    table = root.find(".//table-wrap[@id='Tab1']")
    if table is None:
        raise ValueError("missing Table 1")
    rows = table.findall(".//tr")
    if not rows:
        raise ValueError("empty Table 1")
    header = [txt(cell) for cell in rows[0] if cell.tag in {"th", "td"}]
    expected_header = ["", "BaqA∆C", "BaqA∆C N185D"]
    if header != expected_header:
        raise ValueError(f"header drift: {header!r}")
    table_rows = {}
    for row in rows[1:]:
        cells = [txt(cell) for cell in row if cell.tag in {"th", "td"}]
        if len(cells) != 3:
            raise ValueError(f"malformed Table 1 row: {cells!r}")
        table_rows[cells[0]] = cells[1:]
    expected_metrics = {
        "Km (mg.mL− 1)": ("Km", "mg/mL"),
        "kcat (s− 1)": ("kcat", "s−1"),
        "kcat/Km (mL.mg− 1.s− 1)": ("kcat_per_Km", "mL mg−1 s−1"),
    }
    if set(table_rows) != set(expected_metrics):
        raise ValueError(f"metric keys drift: {set(table_rows)!r}")
    output = []
    for label, (metric, unit) in expected_metrics.items():
        wt, wt_error = value(table_rows[label][0])
        mutant, mutant_error = value(table_rows[label][1])
        output.append({
            **{field: "" for field in FIELDNAMES}, **source,
            "measurement_id": f"litm-{source['pmid']}-baqa-n185d-{metric.lower()}",
            "family": "amylase", "enzyme_name": "BaqA",
            "parent_variant": "BaqA∆C", "variant": "BaqA∆C N185D",
            "mutation_composition": "N185D (BaqA∆C numbering)",
            "metric": metric, "mutant_value": mutant,
            "mutant_error": mutant_error, "wt_value": wt, "wt_error": wt_error,
            "unit": unit, "assay_ph": "6.5", "assay_temperature_c": "50",
            "assay_substrate": "soluble starch",
            "assay_note": "Table 1; soluble starch kinetics; BaqA∆C comparator",
            "source_locator": "Table 1", "numbering_status": "sequence_accession_only",
            "human_review_status": "pending_construct_sequence_review",
            "training_eligible": "false", "formal_decision_written": "false",
            "safe_for_model_claim": "false",
        })
    return output


def write_csv(rows, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    extracted = build_rows(args.data_root)
    write_csv(extracted, args.output)
    print({"rows": len(extracted), "output": str(args.output)})
