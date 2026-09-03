#!/usr/bin/env python3
import argparse
import csv
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path


FIELDNAMES = [
    "measurement_id",
    "pmid",
    "doi",
    "pmcid",
    "family",
    "enzyme_name",
    "parent_variant",
    "variant",
    "mutation_composition",
    "metric",
    "mutant_value",
    "mutant_error",
    "wt_value",
    "wt_error",
    "unit",
    "assay_ph",
    "assay_temperature_c",
    "assay_substrate",
    "assay_note",
    "source_path",
    "source_sha256",
    "source_locator",
    "numbering_precheck_id",
    "numbering_status",
    "human_review_status",
    "training_eligible",
    "formal_decision_written",
    "safe_for_model_claim",
]


EFAMY_COMPOSITIONS = {
    "E166P": "E166P",
    "S185P": "S185P",
    "T350P": "T350P",
    "V212T": "V212T",
    "V232T": "V232T",
    "V212T/V232T": "V212T/V232T",
    "E166P/S185P/T350P": "E166P/S185P/T350P",
    "E166P/S185P/T350P/V212T/V232T": "E166P/S185P/T350P/V212T/V232T",
}

TMPHY_M = "M33T/E44D/E48P/K49P/G58Y/G62A/T63Q"
TMPHY_MD1 = TMPHY_M + "/E11C/V309C/E85C/P263C"
TMPHY_COMPOSITIONS = {
    "TmPhyM": TMPHY_M,
    "TmPhyMD1": TMPHY_MD1,
    "TmPhyMD2": TMPHY_MD1 + "/NtermDeletionLength=10/deleted_sequence=unverified",
    "TmPhyMD3": TMPHY_MD1 + "/NtermReplacement=LNSSVPGA/replaced_span=unresolved",
}
TMPHY_PARENTS = {
    "TmPhyM": "TmPhy",
    "TmPhyMD1": "TmPhyM",
    "TmPhyMD2": "TmPhyMD1",
    "TmPhyMD3": "TmPhyMD1",
}


def text_content(element):
    return " ".join("".join(element.itertext()).replace("\u00a0", " ").split())


def table_rows(root, table_id):
    table = root.find(f".//table-wrap[@id='{table_id}']")
    if table is None:
        raise ValueError(f"missing table {table_id}")
    return [
        [text_content(cell) for cell in row if cell.tag in {"td", "th"}]
        for row in table.findall(".//tbody/tr")
    ]


def require_headers(root, table_id, expected):
    table = root.find(f".//table-wrap[@id='{table_id}']")
    if table is None:
        raise ValueError(f"missing table {table_id}")
    actual = [
        [text_content(cell) for cell in row if cell.tag in {"td", "th"}]
        for row in table.findall(".//thead/tr")
    ]
    if actual != expected:
        raise ValueError(f"{table_id}: unexpected headers; expected={expected!r}, actual={actual!r}")


NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def split_value(raw, allow_decimal_comma=False):
    parts = re.split(r"\s*\u00b1\s*", raw.strip())
    if not 1 <= len(parts) <= 2 or not parts[0]:
        raise ValueError(f"malformed numeric value: {raw!r}")
    normalized = []
    for part in parts:
        if "," in part:
            if not allow_decimal_comma or not re.fullmatch(r"[+-]?\d+,\d+", part):
                raise ValueError(f"unsupported comma in numeric value: {raw!r}")
            part = part.replace(",", ".")
        if NUMBER_PATTERN.fullmatch(part) is None:
            raise ValueError(f"non-numeric value: {raw!r}")
        normalized.append(part)
    return normalized[0], normalized[1] if len(normalized) == 2 else ""


def unique_index(rows, expected_width, table_name):
    indexed = {}
    for cells in rows:
        if len(cells) != expected_width:
            raise ValueError(f"{table_name}: expected {expected_width} cells, got {len(cells)}: {cells}")
        key = cells[0]
        if key in indexed:
            raise ValueError(f"{table_name}: duplicate key {key!r}")
        indexed[key] = cells[1:]
    return indexed


def require_keys(indexed, expected, table_name):
    actual = set(indexed)
    if actual != set(expected):
        raise ValueError(f"{table_name}: unexpected keys; missing={set(expected) - actual}, extra={actual - set(expected)}")


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def source_metadata(data_root, relative_path):
    path = data_root / relative_path
    root = ET.parse(path).getroot()
    ids = {
        node.attrib.get("pub-id-type"): (node.text or "").strip()
        for node in root.findall(".//article-id")
    }
    return {
        "path": path,
        "root": root,
        "pmid": ids["pmid"],
        "doi": ids["doi"],
        "pmcid": ids["pmcid"],
        "source_path": str(relative_path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def measurement_row(meta, **values):
    row = {field: "" for field in FIELDNAMES}
    row.update(
        {
            "pmid": meta["pmid"],
            "doi": meta["doi"],
            "pmcid": meta["pmcid"],
            "source_path": meta["source_path"],
            "source_sha256": meta["source_sha256"],
            "training_eligible": "false",
            "formal_decision_written": "false",
            "safe_for_model_claim": "false",
        }
    )
    row.update(values)
    return row


def build_efamy_rows(data_root):
    relative = Path("literature/raw_fulltext_xml/amylase/PMC5478988.xml")
    meta = source_metadata(data_root, relative)
    root = meta["root"]
    rows = []

    require_headers(root, "T1", [["Enzyme or mutation(s)", "t1/2 (min) at:"], ["40°C", "50°C"]])
    require_headers(
        root,
        "T2",
        [["Enzyme or mutation(s)", "Temp (°C)", "kcat (s−1)", "Km (g · liter−1)", "kcat/Km (s−1 · g−1 · liter)"]],
    )

    stability_rows = [
        [cells[0].replace(" (wild type)", ""), *cells[1:]]
        for cells in table_rows(root, "T1")
    ]
    stability = unique_index(stability_rows, 3, "EfAmy Table 1")
    require_keys(stability, {"EfAmy", "EcAmy", *EFAMY_COMPOSITIONS}, "EfAmy Table 1")
    wt_half_life = stability["EfAmy"]
    for variant, composition in EFAMY_COMPOSITIONS.items():
        for temperature, mutant_raw, wt_raw in zip(("40", "50"), stability[variant], wt_half_life):
            rows.append(
                measurement_row(
                    meta,
                    measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-half-life-{temperature}c",
                    family="amylase",
                    enzyme_name="EfAmy",
                    parent_variant="EfAmy",
                    variant=variant,
                    mutation_composition=composition,
                    metric="half_life",
                    mutant_value=split_value(mutant_raw)[0],
                    wt_value=split_value(wt_raw)[0],
                    unit="min",
                    assay_ph="9.0",
                    assay_temperature_c=temperature,
                    assay_substrate="soluble starch",
                    assay_note="Thermal preincubation in 0.1 M Tris-HCl; replicate count and dispersion not reported",
                    source_locator="Table 1",
                    numbering_status="not_prechecked",
                    human_review_status="pending_parent_construct_sequence_review",
                )
            )

    kinetics = {}
    current_variant = None
    for cells in table_rows(root, "T2"):
        if len(cells) == 5:
            current_variant = cells[0]
            values = cells[1:]
        elif len(cells) == 4 and current_variant:
            values = cells
        else:
            raise ValueError(f"unexpected EfAmy Table 2 row: {cells}")
        if values[0] in kinetics.setdefault(current_variant, {}):
            raise ValueError(f"EfAmy Table 2: duplicate temperature for {current_variant}: {values[0]}")
        kinetics[current_variant][values[0]] = values[1:]
    require_keys(kinetics, {"EfAmy", "EcAmy", *EFAMY_COMPOSITIONS}, "EfAmy Table 2 variants")
    for variant, temperatures in kinetics.items():
        require_keys(temperatures, {"5", "25", "35"}, f"EfAmy Table 2 {variant} temperatures")
        if any(len(values) != 3 for values in temperatures.values()):
            raise ValueError(f"EfAmy Table 2 {variant}: expected three metrics per temperature")

    metric_specs = (
        ("kcat", "1/s"),
        ("Km", "g/L"),
        ("kcat_per_Km", "L/g/s"),
    )
    for variant, composition in EFAMY_COMPOSITIONS.items():
        for temperature in ("5", "25", "35"):
            mutant_values = kinetics[variant][temperature]
            wt_values = kinetics["EfAmy"][temperature]
            for (metric, unit), mutant_raw, wt_raw in zip(metric_specs, mutant_values, wt_values):
                decimal_comma = variant == "E166P" and temperature == "35" and metric == "kcat"
                mutant_value, mutant_error = split_value(mutant_raw, allow_decimal_comma=decimal_comma)
                wt_value, wt_error = split_value(wt_raw)
                note = "Duplicate independent experiments; +/- is SE from nonlinear curve fit; pH inherited from standard assay"
                if variant == "E166P" and temperature == "35" and metric == "kcat":
                    note += "; decimal separator normalized from 1033,78"
                rows.append(
                    measurement_row(
                        meta,
                        measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}-{temperature}c",
                        family="amylase",
                        enzyme_name="EfAmy",
                        parent_variant="EfAmy",
                        variant=variant,
                        mutation_composition=composition,
                        metric=metric,
                        mutant_value=mutant_value,
                        mutant_error=mutant_error,
                        wt_value=wt_value,
                        wt_error=wt_error,
                        unit=unit,
                        assay_ph="9.0",
                        assay_temperature_c=temperature,
                        assay_substrate="soluble starch",
                        assay_note=note,
                        source_locator="Table 2",
                        numbering_status="not_prechecked",
                        human_review_status="pending_parent_construct_sequence_review",
                    )
                )
    return rows


def build_tmphy_rows(data_root):
    relative = Path("literature/raw_fulltext_xml/phytase/PMC11180912.xml")
    meta = source_metadata(data_root, relative)
    root = meta["root"]
    rows = []
    require_headers(root, "T1", [["Enzyme", "Specific activity (U/mg)"]])
    require_headers(root, "T2", [["", "Km (mM)", "kcat (s-1)", "kcat/Km (s-1mM-1)"]])
    activity = unique_index(table_rows(root, "T1"), 2, "TmPhy Table 1")
    require_keys(activity, {"TmPhy", *TMPHY_COMPOSITIONS}, "TmPhy Table 1")
    wt_activity, wt_activity_error = split_value(activity["TmPhy"][0])

    for variant, composition in TMPHY_COMPOSITIONS.items():
        value, error = split_value(activity[variant][0])
        rows.append(
            measurement_row(
                meta,
                measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-specific-activity",
                family="phytase",
                enzyme_name="TmPhy",
                parent_variant=TMPHY_PARENTS[variant],
                variant=variant,
                mutation_composition=composition,
                metric="specific_activity",
                mutant_value=value,
                mutant_error=error,
                wt_value=wt_activity,
                wt_error=wt_activity_error,
                unit="U/mg",
                assay_ph="3.0",
                assay_temperature_c="37",
                assay_substrate="sodium phytate",
                assay_note="Source table dispersion retained; construct includes substitutions and may include N-terminal deletion or replacement",
                source_locator="Table 1",
                numbering_precheck_id="seqcheck-tmphy-wp277039767",
                numbering_status="candidate_mature_chain_offset_match",
                human_review_status="pending_signal_peptide_and_construct_boundary_review",
            )
        )

    kinetics = unique_index(table_rows(root, "T2"), 4, "TmPhy Table 2")
    require_keys(kinetics, {"TmPhy", *TMPHY_COMPOSITIONS}, "TmPhy Table 2")
    metric_specs = (("Km", "mM"), ("kcat", "1/s"), ("kcat_per_Km", "1/mM/s"))
    for variant, composition in TMPHY_COMPOSITIONS.items():
        for (metric, unit), mutant_raw, wt_raw in zip(metric_specs, kinetics[variant], kinetics["TmPhy"]):
            mutant_value, mutant_error = split_value(mutant_raw)
            wt_value, wt_error = split_value(wt_raw)
            rows.append(
                measurement_row(
                    meta,
                    measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                    family="phytase",
                    enzyme_name="TmPhy",
                    parent_variant=TMPHY_PARENTS[variant],
                    variant=variant,
                    mutation_composition=composition,
                    metric=metric,
                    mutant_value=mutant_value,
                    mutant_error=mutant_error,
                    wt_value=wt_value,
                    wt_error=wt_error,
                    unit=unit,
                    assay_ph="5.5",
                    assay_temperature_c="37",
                    assay_substrate="sodium phytate",
                    assay_note="Source table dispersion retained; multi-step construct kept intact",
                    source_locator="Table 2",
                    numbering_precheck_id="seqcheck-tmphy-wp277039767",
                    numbering_status="candidate_mature_chain_offset_match",
                    human_review_status="pending_signal_peptide_and_construct_boundary_review",
                )
            )
    return rows


def build_gox_rows(data_root):
    relative = Path("literature/raw_fulltext_xml/glucose_oxidase/PMC7287683.xml")
    meta = source_metadata(data_root, relative)
    root = meta["root"]
    require_headers(
        root,
        "molecules-25-02418-t001",
        [["Enzyme Variant", "Km(mM)", "kcat(s−1)", "kcat/Km(mM−1·s−1)", "Sp (U/mg)", "Mutations"]],
    )
    table = table_rows(root, "molecules-25-02418-t001")
    parsed = unique_index(table, 6, "GOx Table 1")
    require_keys(parsed, {"Wild Type", "Parent", "A2", "A21", "M6", "F9", "F91", "M15"}, "GOx Table 1")
    wt_values = parsed["Wild Type"][:4]
    metric_specs = (
        ("Km", "mM"),
        ("kcat", "1/s"),
        ("kcat_per_Km", "1/mM/s"),
        ("specific_activity", "U/mg"),
    )
    rows = []
    for variant in ("Parent", "A2", "A21", "M6", "F9", "F91", "M15"):
        values = parsed[variant]
        composition = "/".join(part.strip() for part in values[4].split(","))
        parent_variant = "GOx-WT" if variant == "Parent" else "GOx-Parent"
        for (metric, unit), mutant_raw, wt_raw in zip(metric_specs, values[:4], wt_values):
            rows.append(
                measurement_row(
                    meta,
                    measurement_id=f"litm-{meta['pmid']}-{slug(variant)}-{slug(metric)}",
                    family="glucose_oxidase",
                    enzyme_name="GOx",
                    parent_variant=parent_variant,
                    variant=variant,
                    mutation_composition=composition,
                    metric=metric,
                    mutant_value=split_value(mutant_raw)[0],
                    wt_value=split_value(wt_raw)[0],
                    unit=unit,
                    assay_substrate="D-glucose",
                    assay_note="Purified enzyme values compared with table WT; triplicate ABTS assays; pH 5.5 and 7.4 unresolved at table-row level; no dispersion reported; full construct retained",
                    source_locator="Table 1",
                    numbering_status="not_prechecked",
                    human_review_status="pending_parent_construct_sequence_and_assay_review",
                )
            )
    return rows


def build_rows(data_root):
    rows = build_efamy_rows(data_root) + build_tmphy_rows(data_root) + build_gox_rows(data_root)
    ids = [row["measurement_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate measurement_id")
    return rows


def write_csv(rows, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("measurement_candidates_batch003.csv"))
    args = parser.parse_args()
    rows = build_rows(args.data_root)
    write_csv(rows, args.output)
    print({"rows": len(rows), "output": str(args.output)})


if __name__ == "__main__":
    main()
