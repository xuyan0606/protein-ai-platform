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
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def text_content(element):
    return " ".join("".join(element.itertext()).replace("\u00a0", " ").split())


def table(root, table_id):
    node = root.find(f".//table-wrap[@id='{table_id}']")
    if node is None:
        raise ValueError(f"missing table {table_id}")
    return node


def table_rows(root, table_id):
    return [[text_content(cell) for cell in row if cell.tag in {"td", "th"}] for row in table(root, table_id).findall(".//tbody/tr")]


def require_headers(root, table_id, expected):
    actual = [[text_content(cell) for cell in row if cell.tag in {"td", "th"}] for row in table(root, table_id).findall(".//thead/tr")]
    if actual != expected:
        raise ValueError(f"{table_id}: unexpected headers; expected={expected!r}, actual={actual!r}")


def unique_index(rows, width, name, skip_empty_key=False):
    result = {}
    for cells in rows:
        if len(cells) != width:
            raise ValueError(f"{name}: expected {width} cells, got {len(cells)}")
        if skip_empty_key and not cells[0]:
            if any(cells[1:]):
                raise ValueError(f"{name}: empty key with non-empty data: {cells}")
            continue
        if cells[0] in result:
            raise ValueError(f"{name}: duplicate key {cells[0]!r}")
        result[cells[0]] = cells[1:]
    return result


def require_keys(indexed, expected, name):
    if set(indexed) != set(expected):
        raise ValueError(f"{name}: unexpected keys; missing={set(expected)-set(indexed)}, extra={set(indexed)-set(expected)}")


def split_value(raw, allow_group_letter=False):
    value = raw.strip()
    if allow_group_letter:
        value = re.sub(r"\s+[a-z]$", "", value)
    parts = re.split(r"\s*\u00b1\s*", value)
    if not 1 <= len(parts) <= 2 or any(NUMBER.fullmatch(part) is None for part in parts):
        raise ValueError(f"malformed numeric value: {raw!r}")
    return parts[0], parts[1] if len(parts) == 2 else ""


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def source_metadata(data_root, relative):
    path = data_root / relative
    root = ET.parse(path).getroot()
    ids = {node.attrib.get("pub-id-type"): (node.text or "").strip() for node in root.findall(".//article-id")}
    return {"root": root, "pmid": ids["pmid"], "doi": ids["doi"], "pmcid": ids["pmcid"], "source_path": str(relative), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def measurement_row(meta, **values):
    row = {field: "" for field in FIELDNAMES}
    row.update({"pmid": meta["pmid"], "doi": meta["doi"], "pmcid": meta["pmcid"], "source_path": meta["source_path"], "source_sha256": meta["source_sha256"], "training_eligible": "false", "formal_decision_written": "false", "safe_for_model_claim": "false"})
    row.update(values)
    return row


def build_mfaps_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/amylase/PMC9105970.xml"))
    root = meta["root"]
    require_headers(root, "foods-11-01207-t002", [["Enzyme", "Relative Activity A,B (%)", "Specific Activity B (U/mg)", "KmB(mg/mL)", "VmaxB(μmol·min−1·mL−1)", "kcatB(×103 sec−1)", "kcat/KmB(×103 mL·mg−1·sec−1)"]])
    require_headers(root, "foods-11-01207-t003", [["Enzyme", "Half-live at 60 °C (min) A", "Tm (°C) A"]])
    expected = {"Wild-type", "A211C-S214C", "S409C-Q412C"}
    activity = unique_index(table_rows(root, "foods-11-01207-t002"), 7, "MFAps Table 2")
    stability = unique_index(table_rows(root, "foods-11-01207-t003"), 3, "MFAps Table 3")
    require_keys(activity, expected, "MFAps Table 2"); require_keys(stability, expected, "MFAps Table 3")
    compositions = {"A211C-S214C": "A211C/S214C", "S409C-Q412C": "S409C/Q412C"}
    specs = (("relative_activity", "percent"), ("specific_activity", "U/mg"), ("Km", "mg/mL"), ("Vmax", "umol/min/mL"), ("kcat", "10^3/s"), ("kcat_per_Km", "10^3*mL/mg/s"))
    rows = []
    for variant, composition in compositions.items():
        for (metric, unit), raw, wt_raw in zip(specs, activity[variant], activity["Wild-type"]):
            value, error = split_value(raw, allow_group_letter=True); wt_value, wt_error = split_value(wt_raw, allow_group_letter=True)
            substrate = "maltodextrin DE=4" if metric in {"Km", "Vmax", "kcat", "kcat_per_Km"} else ""
            note = "Mean of three independent measurements; +/- is SD where reported; significance-group letters removed"
            if metric in {"relative_activity", "specific_activity"}:
                note += "; substrate reporting conflict: table says maltodextrin DE=4, methods/results distinguish soluble starch activity from maltodextrin kinetics"
            rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}", family="amylase", enzyme_name="MFAps", parent_variant="MFAps-WT", variant=variant, mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph="7.5" if metric in {"Km", "Vmax", "kcat", "kcat_per_Km"} else "", assay_temperature_c="50", assay_substrate=substrate, assay_note=note, source_locator="Table 2", numbering_status="article_accession_not_construct_sequence_verified", human_review_status="pending_construct_sequence_and_activity_substrate_review"))
        for (metric, unit), raw, wt_raw in zip((("half_life", "min"), ("Tm", "C")), stability[variant], stability["Wild-type"]):
            value, error = split_value(raw, allow_group_letter=True); wt_value, wt_error = split_value(wt_raw, allow_group_letter=True)
            note = "Mean of three independent measurements; +/- is SD; significance-group letters removed"
            assay_temperature = "60" if metric == "half_life" else ""
            assay_ph = "7.5" if metric == "Tm" else ""
            if metric == "half_life":
                note += "; pH conflict: dialysis buffer pH 7.5 versus thermal-inactivation figure pH 7.0"
            rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}", family="amylase", enzyme_name="MFAps", parent_variant="MFAps-WT", variant=variant, mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph=assay_ph, assay_temperature_c=assay_temperature, assay_note=note, source_locator="Table 3", numbering_status="article_accession_not_construct_sequence_verified", human_review_status="pending_construct_sequence_and_thermal_assay_review"))
    return rows


XYL_VARIANTS = {"M53S/F54L": "M53S/F54L", "N207G": "N207G", "M53S/F54L/N207G": "M53S/F54L/N207G"}


def build_xyl10c_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/xylanase/PMC8487158.xml"))
    root = meta["root"]
    require_headers(root, "Tab1", [["", "Km (mg/mL)", "kcat (s−1)", "Vmax (μmol/min·mg)", "kcat/Km (mL/s·mg)", "Specific activity (U/mg)"]])
    require_headers(root, "Tab2", [["Substrate", "Sugarcane xylan", "Corncob xylan"], ["Enzymes", "Km (mg/mL)", "Vmax (μmol/min·mg)", "kcat/Km (mL/s·mg)", "Specific activity (U/mg)", "Km (mg/mL)", "Vmax (μmol/min·mg)", "kcat/Km (mL/s·mg)", "Specific activity (U/mg)"]])
    expected = {"XYL10C_∆N", *XYL_VARIANTS}
    beechwood = unique_index(table_rows(root, "Tab1"), 6, "XYL10C Table 1")
    other = unique_index(table_rows(root, "Tab2"), 9, "XYL10C Table 2")
    require_keys(beechwood, expected, "XYL10C Table 1"); require_keys(other, expected, "XYL10C Table 2")
    rows = []
    base_note = "Mean +/- SD, n=3; N-terminal-truncated engineered parent; construct-specific optimum pH is 4.0 or 4.5 but row-level mapping is unresolved"
    for variant, composition in XYL_VARIANTS.items():
        specs = (("Km", "mg/mL"), ("kcat", "1/s"), ("Vmax", "umol/min/mg"), ("kcat_per_Km", "mL/mg/s"), ("specific_activity", "U/mg"))
        for (metric, unit), raw, wt_raw in zip(specs, beechwood[variant], beechwood["XYL10C_∆N"]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            note = base_note
            if metric == "specific_activity" and variant in {"M53S/F54L", "N207G"}:
                note += "; formal table value differs from earlier screening value in main text"
            rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}-beechwood", family="xylanase", enzyme_name="XYL10C", parent_variant="XYL10C_∆N", variant=variant, mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_temperature_c="40", assay_substrate="beechwood xylan", assay_note=note, source_locator="Table 1", numbering_status="article_construct_numbering_delta_n_boundary_unverified", human_review_status="pending_delta_n_boundary_pdb_and_assay_ph_review"))
        specs2 = (("Km", "mg/mL"), ("Vmax", "umol/min/mg"), ("kcat_per_Km", "mL/mg/s"), ("specific_activity", "U/mg"))
        for substrate, offset in (("sugarcane xylan", 0), ("corncob xylan", 4)):
            for (metric, unit), raw, wt_raw in zip(specs2, other[variant][offset:offset+4], other["XYL10C_∆N"][offset:offset+4]):
                value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
                note = base_note + "; kinetic substrate concentration series and xylan source/preparation not reported"
                if metric == "kcat_per_Km":
                    note += "; main-text unit conflicts with table header; table unit retained"
                rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}-{slug(substrate)}", family="xylanase", enzyme_name="XYL10C", parent_variant="XYL10C_∆N", variant=variant, mutation_composition=composition, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_temperature_c="40", assay_substrate=substrate, assay_note=note, source_locator="Table 2", numbering_status="article_construct_numbering_delta_n_boundary_unverified", human_review_status="pending_delta_n_boundary_pdb_and_assay_ph_review"))
    return rows


MAN_VARIANTS = ("P191 M", "P194E", "S199G", "S268Q")


def build_manak_rows(data_root):
    meta = source_metadata(data_root, Path("literature/raw_fulltext_xml/mannanase/PMC8313266.xml"))
    root = meta["root"]
    require_headers(root, "mbt213812-tbl-0001", [["Name", "T opt (oC)", "t 1/2 (75°C) a (min)", "pHopt", "Specific activity (U mg‐1)"]])
    require_headers(root, "mbt213812-tbl-0002", [["Name", "K m (mg ml‐1)", "V max (U mg‐1)", "k cat (1 s‐1)", "k cat/K m (ml s mg‐1)"]])
    expected = {"ManAKH", *MAN_VARIANTS}
    properties = unique_index(table_rows(root, "mbt213812-tbl-0001"), 5, "ManAK Table 1", skip_empty_key=True)
    kinetics = unique_index(table_rows(root, "mbt213812-tbl-0002"), 5, "ManAK Table 2")
    require_keys(properties, expected, "ManAK Table 1"); require_keys(kinetics, expected, "ManAK Table 2")
    rows = []
    for source_variant in MAN_VARIANTS:
        variant = source_variant.replace(" ", "")
        conflict = "Table variant retained; source conflicts include S268Q/S286Q, S199G/P199G, and S268Q/S268G"
        prop_specs = (("temperature_optimum", "C"), ("half_life", "min"), ("pH_optimum", "pH"), ("specific_activity", "U/mg"))
        for (metric, unit), raw, wt_raw in zip(prop_specs, properties[source_variant], properties["ManAKH"]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            note = conflict + "; error type and replicate count not reported; CC BY-NC-ND 4.0 license scope review pending"
            assay_ph = "5.5" if metric == "specific_activity" else ""
            assay_temp = "37" if metric == "specific_activity" else ("75" if metric == "half_life" else "")
            substrate = "locust bean gum" if metric == "specific_activity" else ""
            rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}", family="mannanase", enzyme_name="ManAK", parent_variant="ManAKH", variant=variant, mutation_composition=variant, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph=assay_ph, assay_temperature_c=assay_temp, assay_substrate=substrate, assay_note=note, source_locator="Table 1", numbering_precheck_id="", numbering_status="direct_partial_cds_translation_match", human_review_status="pending_partial_cds_parent_boundary_source_conflict_and_license_scope_review"))
        kinetic_specs = (("Km", "mg/mL"), ("Vmax", "U/mg"), ("kcat", "1/s"), ("kcat_per_Km", "mL/mg/s"))
        for (metric, unit), raw, wt_raw in zip(kinetic_specs, kinetics[source_variant], kinetics["ManAKH"]):
            value, error = split_value(raw); wt_value, wt_error = split_value(wt_raw)
            note = conflict + "; table assigns Km=2.1 and kcat/Km=120.4 to S199G despite main-text misassignment to P194E; error type and replicate count not reported; CC BY-NC-ND 4.0 license scope review pending"
            rows.append(measurement_row(meta, measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}", family="mannanase", enzyme_name="ManAK", parent_variant="ManAKH", variant=variant, mutation_composition=variant, metric=metric, mutant_value=value, mutant_error=error, wt_value=wt_value, wt_error=wt_error, unit=unit, assay_ph="5.5", assay_temperature_c="37", assay_substrate="locust bean gum", assay_note=note, source_locator="Table 2", numbering_status="direct_partial_cds_translation_match", human_review_status="pending_partial_cds_parent_boundary_source_conflict_and_license_scope_review"))
    return rows


def build_rows(data_root):
    rows = build_mfaps_rows(data_root) + build_xyl10c_rows(data_root) + build_manak_rows(data_root)
    ids = [row["measurement_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate measurement_id")
    return rows


def write_csv(rows, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES); writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("measurement_candidates_batch005.csv"))
    args = parser.parse_args(); rows = build_rows(args.data_root); write_csv(rows, args.output)
    print({"rows": len(rows), "output": str(args.output)})


if __name__ == "__main__":
    main()
