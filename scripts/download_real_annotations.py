#!/usr/bin/env python3
"""Build real local annotation bundles from official UniProt and InterPro APIs.

Examples:
  python scripts/download_real_annotations.py --ids P00692,P19531,P00691
  python scripts/download_real_annotations.py --id-file ./uniprot_ids.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data" / "annotations"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot"


def _parse_ids(raw_ids: str | None, id_file: str | None) -> list[str]:
    values: list[str] = []
    if raw_ids:
        values.extend(part.strip() for part in raw_ids.replace("\n", ",").split(","))
    if id_file:
        text = Path(id_file).expanduser().read_text(encoding="utf-8")
        values.extend(part.strip() for part in text.replace("\n", ",").split(","))
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        normalized = value.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _read_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _first_comment_text(entry: dict, comment_type: str) -> str | None:
    for comment in entry.get("comments") or []:
        if comment.get("commentType") != comment_type:
            continue
        texts = comment.get("texts") or []
        for item in texts:
            value = item.get("value")
            if value:
                return str(value)
        reaction = comment.get("reaction") or {}
        if reaction.get("name"):
            return str(reaction["name"])
    return None


def _extract_ec_numbers(entry: dict) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    def _append(value: str, is_primary: bool) -> None:
        if not value or value in seen:
            return
        seen.add(value)
        parts = value.split(".")
        results.append(
            {
                "ec_number": value,
                "name": "",
                "category": "",
                "level1": parts[0] if len(parts) > 0 else "",
                "level2": ".".join(parts[:2]) if len(parts) > 1 else "",
                "level3": ".".join(parts[:3]) if len(parts) > 2 else "",
                "is_primary": is_primary,
            }
        )

    recommended = (((entry.get("proteinDescription") or {}).get("recommendedName")) or {})
    for ec in recommended.get("ecNumbers") or []:
        value = ec.get("value")
        if value:
            _append(str(value), True)

    for comment in entry.get("comments") or []:
        if comment.get("commentType") != "CATALYTIC ACTIVITY":
            continue
        reaction = comment.get("reaction") or {}
        value = reaction.get("ecNumber")
        if value:
            _append(str(value), False)

    return results


def _lineage_taxonomy(entry: dict) -> dict:
    organism = entry.get("organism") or {}
    lineage = organism.get("lineage") or []
    scientific_name = str(organism.get("scientificName") or "")
    parts = scientific_name.split()
    return {
        "ncbi_taxid": organism.get("taxonId"),
        "scientific_name": scientific_name,
        "common_name": organism.get("commonName"),
        "kingdom": lineage[0] if len(lineage) > 0 else None,
        "phylum": lineage[2] if len(lineage) > 2 else (lineage[1] if len(lineage) > 1 else None),
        "class_name": lineage[3] if len(lineage) > 3 else None,
        "order_name": lineage[4] if len(lineage) > 4 else None,
        "family": lineage[5] if len(lineage) > 5 else None,
        "genus": lineage[6] if len(lineage) > 6 else (parts[0] if parts else None),
        "species": scientific_name if len(parts) >= 2 else None,
    }


def _recommended_name(entry: dict) -> str:
    desc = entry.get("proteinDescription") or {}
    rec = desc.get("recommendedName") or {}
    full = rec.get("fullName") or {}
    if full.get("value"):
        return str(full["value"])
    submitted = desc.get("submissionNames") or []
    if submitted:
        full = (submitted[0] or {}).get("fullName") or {}
        if full.get("value"):
            return str(full["value"])
    return ""


def _gene_name(entry: dict) -> str | None:
    genes = entry.get("genes") or []
    for gene in genes:
        gene_name = gene.get("geneName") or {}
        if gene_name.get("value"):
            return str(gene_name["value"])
    return None


def _extract_signal_prediction(entry: dict) -> dict:
    sequence = ((entry.get("sequence") or {}).get("value") or "").strip().upper()
    signal_feature = None
    for feature in entry.get("features") or []:
        if feature.get("type") == "Signal":
            signal_feature = feature
            break

    if signal_feature is None:
        return {
            "has_signal_peptide": False,
            "confidence": None,
            "predicted_type": "none",
            "cleavage_site": None,
            "model": "uniprot_feature_import",
            "note": "No curated UniProt signal peptide feature found.",
        }

    start = ((signal_feature.get("location") or {}).get("start") or {}).get("value")
    end = ((signal_feature.get("location") or {}).get("end") or {}).get("value")
    cleavage_site = None
    if isinstance(end, int) and end >= 1 and len(sequence) > end:
        cleavage_site = f"{sequence[end - 1]}{end}|{sequence[end]}"
    return {
        "has_signal_peptide": True,
        "confidence": None,
        "predicted_type": "curated_uniprot_signal_feature",
        "cleavage_site": cleavage_site,
        "model": "uniprot_feature_import",
        "note": "Derived from UniProt curated signal peptide feature.",
        "regions": {
            "signal_region": {
                "start": start,
                "end": end,
            }
        },
    }


def _extract_catalytic_sites(entry: dict) -> list[dict]:
    residues: list[dict] = []
    for feature in entry.get("features") or []:
        if feature.get("type") != "Active site":
            continue
        start = ((feature.get("location") or {}).get("start") or {}).get("value")
        if not isinstance(start, int):
            continue
        residues.append(
            {
                "residue_pos": start,
                "residue_aa": None,
                "role": feature.get("description") or "active_site",
                "confidence": 0.9,
            }
        )
    if not residues:
        return []
    return [
        {
            "source": "uniprot_active_site_feature",
            "mechanism_name": "Catalytic residues from UniProt curated active-site features",
            "reaction_text": _first_comment_text(entry, "CATALYTIC ACTIVITY") or _first_comment_text(entry, "FUNCTION"),
            "evidence_json": {"source": "UniProtKB", "feature_type": "Active site"},
            "residues": residues,
        }
    ]


def _interpro_rows(uniprot_id: str) -> tuple[list[dict], list[dict]]:
    interpro_rows: list[dict] = []
    pfam_rows: list[dict] = []
    seen_pfam: set[tuple[str, int, int]] = set()

    next_url = (
        f"{INTERPRO_BASE}/{urllib.parse.quote(uniprot_id)}"
        "?extra_fields=short_name&page_size=200"
    )
    while next_url:
        payload = _read_json(next_url)
        if not isinstance(payload, dict):
            break
        for result in payload.get("results") or []:
            if not isinstance(result, dict):
                continue
            metadata = result.get("metadata") or {}
            accession = metadata.get("accession")
            go_terms = []
            for term in metadata.get("go_terms") or []:
                if term.get("identifier") and term.get("name"):
                    go_terms.append(f"{term['identifier']} {term['name']}")

            proteins = result.get("proteins") or []
            for protein in proteins:
                if str(protein.get("accession") or "").upper() != uniprot_id.upper():
                    continue
                for location in protein.get("entry_protein_locations") or []:
                    for fragment in location.get("fragments") or []:
                        start = fragment.get("start")
                        end = fragment.get("end")
                        if not isinstance(start, int) or not isinstance(end, int):
                            continue
                        interpro_rows.append(
                            {
                                "uniprot_id": uniprot_id,
                                "interpro_id": accession,
                                "entry_type": metadata.get("type"),
                                "name": metadata.get("name"),
                                "description": (result.get("extra_fields") or {}).get("short_name"),
                                "source_db": metadata.get("source_database") or "interpro",
                                "go_terms": go_terms,
                                "start_pos": start,
                                "end_pos": end,
                                "score": None,
                                "evidence": "interpro_api",
                            }
                        )

                        pfam_block = metadata.get("member_databases") or {}
                        for pfam_id, pfam_name in (pfam_block.get("pfam") or {}).items():
                            key = (pfam_id, start, end)
                            if key in seen_pfam:
                                continue
                            seen_pfam.add(key)
                            pfam_rows.append(
                                {
                                    "pfam_id": pfam_id,
                                    "name": pfam_name,
                                    "description": metadata.get("name"),
                                    "start_pos": start,
                                    "end_pos": end,
                                    "evalue": None,
                                }
                            )
        next_value = payload.get("next")
        next_url = str(next_value) if next_value else ""
    return interpro_rows, pfam_rows


def _base_bundle(entry: dict, interpro_pfam: list[dict]) -> dict:
    accession = str(entry.get("primaryAccession") or "")
    sequence = str(((entry.get("sequence") or {}).get("value")) or "").strip().upper()
    return {
        "taxonomy": _lineage_taxonomy(entry),
        "enzyme": {
            "uniprot_id": accession,
            "entry_name": entry.get("uniProtkbId"),
            "sequence": sequence,
            "protein_name": _recommended_name(entry),
            "gene_name": _gene_name(entry),
            "description": _recommended_name(entry),
            "function_annotation": _first_comment_text(entry, "FUNCTION"),
            "catalytic_activity": _first_comment_text(entry, "CATALYTIC ACTIVITY"),
            "source_db": "uniprot",
            "source_version": str(date.today()),
            "is_reviewed": str(entry.get("entryType") or "").lower().startswith("reviewed"),
        },
        "ec_numbers": _extract_ec_numbers(entry),
        "pfam_domains": interpro_pfam,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated UniProt accessions")
    parser.add_argument("--id-file", help="Text file with UniProt accessions separated by commas or newlines")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="annotations directory")
    args = parser.parse_args()

    ids = _parse_ids(args.ids, args.id_file)
    if not ids:
        print("No UniProt accessions provided. Use --ids or --id-file.", file=sys.stderr)
        return 1

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    base_rows: list[dict] = []
    interpro_rows: list[dict] = []
    mcsa_rows: list[dict] = []
    signalp_rows: list[dict] = []

    for uniprot_id in ids:
        entry = _read_json(f"{UNIPROT_BASE}/{urllib.parse.quote(uniprot_id)}.json")
        if not isinstance(entry, dict):
            raise SystemExit(f"Unexpected UniProt payload for {uniprot_id}")
        protein_interpro, pfam_rows = _interpro_rows(uniprot_id)
        base_rows.append(_base_bundle(entry, pfam_rows))
        interpro_rows.extend(protein_interpro)
        mcsa_rows.extend(
            {
                "uniprot_id": uniprot_id,
                **site,
            }
            for site in _extract_catalytic_sites(entry)
        )
        signalp_rows.append(
            {
                "uniprot_id": uniprot_id,
                **_extract_signal_prediction(entry),
            }
        )
        print(
            f"OK {uniprot_id}: base=1 interpro={len(protein_interpro)} "
            f"catalytic_sites={sum(1 for row in mcsa_rows if row['uniprot_id'] == uniprot_id)}"
        )

    metadata = {
        "dataset_name": "real_annotations_uniprot_interpro",
        "dataset_version": str(date.today()),
        "default_source_db": "uniprot",
        "sources": ["UniProtKB", "InterPro"],
        "record_count": len(base_rows),
    }

    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
    (output / "base.json").write_text(json.dumps(base_rows, ensure_ascii=True, indent=2), encoding="utf-8")
    (output / "interpro.json").write_text(json.dumps(interpro_rows, ensure_ascii=True, indent=2), encoding="utf-8")
    (output / "mcsa.json").write_text(json.dumps(mcsa_rows, ensure_ascii=True, indent=2), encoding="utf-8")
    (output / "signalp.json").write_text(json.dumps(signalp_rows, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Wrote annotations bundle to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
