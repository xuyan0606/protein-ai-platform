#!/usr/bin/env python3
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


def text_content(element):
    return " ".join("".join(element.itertext()).replace("\u00a0", " ").split())


def table(root, table_id):
    node = root.find(f".//table-wrap[@id='{table_id}']")
    if node is None:
        raise ValueError(f"missing table {table_id}")
    return node


def table_rows(root, table_id):
    return [
        [text_content(cell) for cell in row if cell.tag in {"td", "th"}]
        for row in table(root, table_id).findall(".//tbody/tr")
    ]


def require_headers(root, table_id, expected):
    actual = [
        [text_content(cell) for cell in row if cell.tag in {"td", "th"}]
        for row in table(root, table_id).findall(".//thead/tr")
    ]
    if actual != expected:
        raise ValueError(f"{table_id}: unexpected headers; expected={expected!r}, actual={actual!r}")


def unique_index(rows, width, name):
    result = {}
    for cells in rows:
        if len(cells) != width:
            raise ValueError(f"{name}: expected {width} cells, got {len(cells)}")
        if cells[0] in result:
            raise ValueError(f"{name}: duplicate key {cells[0]!r}")
        result[cells[0]] = cells[1:]
    return result


def require_keys(indexed, expected, name):
    if set(indexed) != set(expected):
        raise ValueError(f"{name}: unexpected keys; missing={set(expected)-set(indexed)}, extra={set(indexed)-set(expected)}")


NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def split_value(raw):
    parts = re.split(r"\s*\u00b1\s*", raw.strip())
    if not 1 <= len(parts) <= 2 or any(NUMBER.fullmatch(part) is None for part in parts):
        raise ValueError(f"malformed numeric value: {raw!r}")
    return parts[0], parts[1] if len(parts) == 2 else ""


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def source_metadata(data_root, relative):
    path = data_root / relative
    root = ET.parse(path).getroot()
    ids = {node.attrib.get("pub-id-type"): (node.text or "").strip() for node in root.findall(".//article-id")}
    return {
        "root": root, "pmid": ids["pmid"], "doi": ids["doi"], "pmcid": ids["pmcid"],
        "source_path": str(relative), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def measurement_row(meta, **values):
    row = {field: "" for field in FIELDNAMES}
    row.update({
        "pmid": meta["pmid"], "doi": meta["doi"], "pmcid": meta["pmcid"],
        "source_path": meta["source_path"], "source_sha256": meta["source_sha256"],
        "training_eligible": "false", "formal_decision_written": "false",
        "safe_for_model_claim": "false",
    })
    row.update(values)
    return row


def build_bla_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/amylase/PMC10883975.xml"))
    root = meta["root"]
    require_headers(root, "tbl0005", [["", "KM (g·L−1)", "kcat (s−1)", "kcat/KM (g·L−1·s−1)", "t1/2 (s)", "Tm (°C)"]])
    parsed = unique_index(table_rows(root, "tbl0005"), 6, "BLA Table 1")
    expected = {"WT", "K251E", "E271L", "E271R", "E271M", "E271Q", "E271T", "E271V", "E271I", "T277C", "T277I", "T277V", "N278K", "K319W", "E336S", "E271L/K319W", "E271L/N278K", "E271L/K251E"}
    require_keys(parsed, expected, "BLA Table 1")
    specs = (("Km", "g/L"), ("kcat", "1/s"), ("kcat_per_Km", "g/L/s"), ("half_life", "s"), ("Tm", "C"))
    rows = []
    for variant in sorted(expected - {"WT"}):
        for (metric, unit), raw, wt_raw in zip(specs, parsed[variant], parsed["WT"]):
            value, error = split_value(raw)
            wt_value, wt_error = split_value(wt_raw)
            note = "table/method condition conflict: table pH 6.0 and 95 C; results pH 6.5 and 95 C; kinetics methods pH 6.5 and 70 C; results half-life 95 C versus methods 90 C; +/- type unspecified"
            if metric == "kcat_per_Km":
                note += "; reported unit dimension conflicts with metric definition"
            if "T277" in variant:
                note += "; introduction uses E277 but table and main results use T277"
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                family="amylase", enzyme_name="BLA", parent_variant="BLA-WT", variant=variant,
                mutation_composition=variant, metric=metric, mutant_value=value, mutant_error=error,
                wt_value=wt_value, wt_error=wt_error, unit=unit, assay_substrate="soluble starch" if metric in {"Km", "kcat", "kcat_per_Km"} else "",
                assay_note=note, source_locator="Table 1", numbering_status="not_prechecked",
                human_review_status="pending_construct_sequence_and_assay_condition_conflict_review",
            ))
    return rows


XYL_VARIANTS = {
    "T46P": "T46P", "S136P": "S136P", "T46P/S136P": "T46P/S136P",
    "T53C-T142C": "T53C/T142C", "T53C-T142C/T46P": "T53C/T142C/T46P",
    "T53C-T142C/S136P": "T53C/T142C/S136P",
    "T53C-T142C/T46P/S136P": "T53C/T142C/T46P/S136P",
}


def build_xylanase_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/xylanase/PMC5431495.xml"))
    root = meta["root"]
    require_headers(root, "Tab3", [["Enzyme", "t 1/2 (min)"], ["60 °C", "70 °C", "80 °C"]])
    require_headers(root, "Tab4", [["Relative activity (%)", "control", "NaCla", "KCla", "CaCl2 a", "MgCl2 a", "CuSO4 a", "ZnSO4 a", "MnSO4 a", "EDTAa"]])
    require_headers(root, "Tab5", [["Enzyme", "Sp act (U/mg)a", "K m (mg/mL)a", "V max (μmol/min/mg)a"]])
    expected = {"xynA-wt", *XYL_VARIANTS}
    half = unique_index(table_rows(root, "Tab3"), 4, "xynA Table 3")
    additives = unique_index(table_rows(root, "Tab4"), 10, "xynA Table 4")
    kinetics = unique_index(table_rows(root, "Tab5"), 4, "xynA Table 5")
    for name, index in (("Table 3", half), ("Table 4", additives), ("Table 5", kinetics)):
        require_keys(index, expected, f"xynA {name}")
    rows = []
    for variant, composition in XYL_VARIANTS.items():
        for temperature, raw, wt_raw in zip(("60", "70", "80"), half[variant], half["xynA-wt"]):
            if raw.startswith("ND"):
                continue
            value, error = split_value(raw)
            wt_value, wt_error = ("", "") if wt_raw.startswith("ND") else split_value(wt_raw)
            note = "Half-life is time to 50% activity; no dispersion reported; general activity assay says triplicate"
            if not wt_value:
                note += "; WT reported ND at this temperature, so no numeric WT comparator"
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-half-life-{temperature}c",
                family="xylanase", enzyme_name="xynA", parent_variant="xynA-wt", variant=variant,
                mutation_composition=composition, metric="half_life", mutant_value=value, mutant_error=error,
                wt_value=wt_value, wt_error=wt_error, unit="min", assay_ph="3.0",
                assay_temperature_c=temperature, assay_substrate="beechwood xylan", assay_note=note,
                source_locator="Table 3", numbering_status="not_prechecked",
                human_review_status="pending_construct_sequence_and_numbering_review",
            ))
        for additive, raw, wt_raw in zip(("NaCl", "KCl", "CaCl2", "MgCl2", "CuSO4", "ZnSO4", "MnSO4", "EDTA"), additives[variant][1:], additives["xynA-wt"][1:]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-relative-activity-{slug(additive)}",
                family="xylanase", enzyme_name="xynA", parent_variant="xynA-wt", variant=variant,
                mutation_composition=composition, metric="relative_activity_after_additive", mutant_value=value,
                mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit="percent", assay_ph="3.0",
                assay_substrate="beechwood xylan", assay_note=f"10 mM {additive}; 2 h preincubation; each construct self-normalized to its own no-additive control; construct-specific optimum temperature; WT percentage is response comparator, not absolute activity",
                source_locator="Table 4", numbering_status="not_prechecked",
                human_review_status="pending_construct_sequence_and_condition_comparability_review",
            ))
        for (metric, unit), raw, wt_raw in zip((("specific_activity", "U/mg"), ("Km", "mg/mL"), ("Vmax", "umol/min/mg")), kinetics[variant], kinetics["xynA-wt"]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                family="xylanase", enzyme_name="xynA", parent_variant="xynA-wt", variant=variant,
                mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error,
                wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph="3.0",
                assay_substrate="beechwood xylan", assay_note="Mean +/- SD; general assay triplicate; measured at construct-specific optimum temperature, so WT is not a strict same-temperature comparator",
                source_locator="Table 5", numbering_status="not_prechecked",
                human_review_status="pending_construct_sequence_and_condition_comparability_review",
            ))
    return rows


GOX_VARIANTS = {"T132S": "T132S", "T132S/T56V": "T132S/T56V", "T132S/V42Y": "T132S/V42Y", "V42Y": "V42Y"}
GOX_PARENTS = {"T132S": "GOx-Parent", "T132S/T56V": "T132S", "T132S/V42Y": "T132S", "V42Y": "GOx-Parent"}


def build_gox_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/glucose_oxidase/PMC3374809.xml"))
    root = meta["root"]
    require_headers(root, "pone-0037924-t001", [["", "", "", "", "Improvement over Parent"], ["GOx Strain", "K M (mM)1", "k cat (s−1)1,2", "k cat/K M (s−1 ⋅ mM−1)", "(% K M)3", "(×k cat)"]])
    require_headers(root, "pone-0037924-t002", [["GOx Strain", "T 70% (hrs)1", "T 1/2 (hrs)1", "Corr. Coeff. (R2)2"]])
    kinetic_rows = [cells for cells in table_rows(root, "pone-0037924-t001") if cells and cells[0] in {"P. amag. 4", *GOX_VARIANTS}]
    kinetics = unique_index(kinetic_rows, 6, "GOx Table 1")
    require_keys(kinetics, {"P. amag. 4", *GOX_VARIANTS}, "GOx Table 1")
    stability = unique_index(table_rows(root, "pone-0037924-t002"), 4, "GOx Table 2")
    require_keys(stability, {"Biozyme", "Parent", *GOX_VARIANTS}, "GOx Table 2")
    rows = []
    for variant, composition in GOX_VARIANTS.items():
        for (metric, unit), raw in zip((("Km", "mM"), ("kcat", "1/s"), ("kcat_per_Km", "1/mM/s")), kinetics[variant][:3]):
            value, error = split_value(raw)
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                family="glucose_oxidase", enzyme_name="GOx", parent_variant=GOX_PARENTS[variant], variant=variant,
                mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error,
                unit=unit, assay_ph="6.8", assay_substrate="D-glucose",
                assay_note="Electrochemical initial-rate assay; +/- is 95% CI from nonlinear regression; parent kinetic value absent from source table; assay temperature not reported; triplicate type unresolved",
                source_locator="Table 1", numbering_status="precursor_numbering_reported_not_sequence_verified",
                human_review_status="pending_parent_construct_sequence_and_kinetic_normalization_review",
            ))
        for (metric, unit), raw, wt_raw in zip((("T70_percent_time", "h"), ("half_life", "h")), stability[variant][:2], stability["Parent"][:2]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            rows.append(measurement_row(
                meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                family="glucose_oxidase", enzyme_name="GOx", parent_variant=GOX_PARENTS[variant], variant=variant,
                mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error,
                wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph="7.0", assay_temperature_c="50",
                assay_substrate="D-glucose", assay_note="ABTS-buffer thermal incubation; triplicate mean +/- SD; exponential fit; T70% interpreted as time to 70% residual activity",
                source_locator="Table 2", numbering_status="precursor_numbering_reported_not_sequence_verified",
                human_review_status="pending_parent_construct_sequence_review",
            ))
    return rows


def build_rows(data_root):
    rows = build_bla_rows(data_root) + build_xylanase_rows(data_root) + build_gox_rows(data_root)
    ids = [row["measurement_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate measurement_id")
    return rows


def write_csv(rows, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("measurement_candidates_batch004.csv"))
    args = parser.parse_args(); rows = build_rows(args.data_root); write_csv(rows, args.output)
    print({"rows": len(rows), "output": str(args.output)})


if __name__ == "__main__":
    main()
