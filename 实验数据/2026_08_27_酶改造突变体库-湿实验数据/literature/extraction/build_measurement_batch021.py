#!/usr/bin/env python3
"""Extract GOx mutant thermal-stability measurements from PMC5855647 Table 1."""
import argparse
import csv
import hashlib
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


def build_rows(rootdir):
    rel = Path("literature/raw_fulltext_xml/glucose_oxidase/PMC5855647.xml")
    path = rootdir / rel
    root = ET.parse(path).getroot()
    ids = {node.attrib.get("pub-id-type"): (node.text or "").strip()
           for node in root.findall(".//article-id")}
    if not {"pmid", "doi", "pmcid"} <= ids.keys():
        raise ValueError("missing article identifiers")
    source = {"pmid": ids["pmid"], "doi": ids["doi"], "pmcid": ids["pmcid"],
              "source_path": str(rel),
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    table = root.find(".//table-wrap[@id='ijms-19-00425-t001']")
    if table is None:
        raise ValueError("missing Table 1")
    trs = table.findall(".//tr")
    header = [txt(cell) for cell in trs[0] if cell.tag in {"th", "td"}]
    if header != ["Mutant", "t1/2 (min) at 55 °C", "Tm (°C)"]:
        raise ValueError(f"header drift: {header!r}")
    parsed = []
    for tr in trs[1:]:
        cells = [txt(cell) for cell in tr if cell.tag in {"th", "td"}]
        if len(cells) != 3:
            raise ValueError(f"malformed Table 1 row: {cells!r}")
        parsed.append(cells)
    if not parsed or parsed[0][0] != "WT":
        raise ValueError("WT comparator must be first")
    wt = parsed[0]
    mutants = parsed[1:]
    if len(mutants) != 7 or any(not row[0] or row[0] == "WT" for row in mutants):
        raise ValueError("unexpected mutant set")
    output = []
    for variant, half_life, tm in mutants:
        for metric, value, unit in (("half_life", half_life, "min"), ("Tm", tm, "°C")):
            output.append({
                **{field: "" for field in FIELDNAMES}, **source,
                "measurement_id": f"litm-{source['pmid']}-gox-{variant.lower()}-{metric.lower()}",
                "family": "glucose_oxidase", "enzyme_name": "glucose oxidase",
                "parent_variant": "WT", "variant": variant,
                "mutation_composition": variant,
                "metric": metric, "mutant_value": value,
                "wt_value": wt[1] if metric == "half_life" else wt[2],
                "unit": unit, "assay_temperature_c": "55",
                "assay_substrate": "thermal inactivation",
                "assay_note": "Table 1; mutant versus WT thermal stability comparator",
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
    rows = build_rows(args.data_root)
    write_csv(rows, args.output)
    print({"rows": len(rows), "output": str(args.output)})
