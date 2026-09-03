#!/usr/bin/env python3
"""Download PDBe UniProt mappings and expand them into local SIFTS-style rows.

Examples:
  python scripts/download_sifts_mappings.py --ids 1QHP,1QHO,1BLI
  python scripts/download_sifts_mappings.py --id-file ./pdb_ids.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data" / "sifts"
PDBe_MAPPING_API = "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot"


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
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def _safe_int(value: object) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _expand_region(pdb_id: str, uniprot_id: str, mapping: dict[str, object]) -> tuple[list[dict[str, object]], str | None]:
    start = mapping.get("start") if isinstance(mapping.get("start"), dict) else {}
    end = mapping.get("end") if isinstance(mapping.get("end"), dict) else {}

    pdb_start = _safe_int((start or {}).get("author_residue_number"))
    pdb_end = _safe_int((end or {}).get("author_residue_number"))
    unp_start = _safe_int(mapping.get("unp_start"))
    unp_end = _safe_int(mapping.get("unp_end"))
    start_icode = str((start or {}).get("author_insertion_code") or "").strip()
    end_icode = str((end or {}).get("author_insertion_code") or "").strip()

    if None in (pdb_start, pdb_end, unp_start, unp_end):
        return [], "missing residue boundaries"
    if start_icode or end_icode:
        return [], "insertion codes present; region not expanded"

    pdb_len = pdb_end - pdb_start + 1
    unp_len = unp_end - unp_start + 1
    if pdb_len != unp_len or pdb_len <= 0:
        return [], f"length mismatch pdb={pdb_len} uniprot={unp_len}"

    chain_id = str(mapping.get("chain_id") or mapping.get("struct_asym_id") or "_").strip() or "_"
    rows: list[dict[str, object]] = []
    for offset in range(pdb_len):
        rows.append(
            {
                "pdb_id": pdb_id.lower(),
                "chain_id": chain_id,
                "pdb_residue_no": pdb_start + offset,
                "uniprot_id": uniprot_id,
                "uniprot_position": unp_start + offset,
                "mapping_confidence": "curated_sifts_region_expand",
                "identity": mapping.get("identity"),
                "coverage": mapping.get("coverage"),
                "entity_id": mapping.get("entity_id"),
                "struct_asym_id": mapping.get("struct_asym_id"),
            }
        )
    return rows, None


def _convert_payload(pdb_id: str, payload: object) -> dict[str, object]:
    root = payload.get(pdb_id.lower()) if isinstance(payload, dict) else None
    uniprot_block = (root or {}).get("UniProt") if isinstance(root, dict) else None
    rows: list[dict[str, object]] = []
    warnings: list[str] = []

    if isinstance(uniprot_block, dict):
        for uniprot_id, info in uniprot_block.items():
            mappings = info.get("mappings") if isinstance(info, dict) else None
            if not isinstance(mappings, list):
                continue
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    continue
                expanded, warning = _expand_region(pdb_id, uniprot_id, mapping)
                if warning:
                    warnings.append(f"{uniprot_id}:{mapping.get('chain_id') or mapping.get('struct_asym_id') or '_'} {warning}")
                rows.extend(expanded)

    rows.sort(key=lambda item: (str(item["chain_id"]), int(item["pdb_residue_no"])))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "pdbe_api_uniprot_mappings",
        "pdb_id": pdb_id.lower(),
        "mapping_count": len(rows),
        "warnings": warnings,
        "mappings": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated PDB IDs, e.g. 1QHP,1QHO,1BLI")
    parser.add_argument("--id-file", help="Text file with PDB IDs separated by commas or newlines")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Download directory")
    args = parser.parse_args()

    ids = _parse_ids(args.ids, args.id_file)
    if not ids:
        print("No PDB IDs provided. Use --ids or --id-file.", file=sys.stderr)
        return 1

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for pdb_id in ids:
        try:
            payload = _read_json(f"{PDBe_MAPPING_API}/{pdb_id.lower()}")
            converted = _convert_payload(pdb_id, payload)
            target = output / f"{pdb_id.lower()}.json"
            target.write_text(json.dumps(converted, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"OK {pdb_id} -> {target} ({converted['mapping_count']} rows)")
        except urllib.error.HTTPError as exc:
            failures.append(f"{pdb_id}: HTTP {exc.code}")
        except Exception as exc:
            failures.append(f"{pdb_id}: {exc}")

    if failures:
        print("Failed downloads:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
