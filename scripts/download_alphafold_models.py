#!/usr/bin/env python3
"""Download AlphaFold DB structures and metadata by UniProt accession.

Examples:
  python scripts/download_alphafold_models.py --ids P19531,P00690
  python scripts/download_alphafold_models.py --id-file ./uniprot_ids.txt --structure-format both --with-pae-json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data" / "alphafold"
AFDB_API = "https://alphafold.ebi.ac.uk/api/prediction"


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


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def _read_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def _save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _pick_structure_urls(entry: dict[str, object], structure_format: str) -> list[str]:
    urls: list[str] = []
    cif_url = str(entry.get("cifUrl") or "").strip()
    pdb_url = str(entry.get("pdbUrl") or "").strip()
    if structure_format in {"cif", "both"} and cif_url:
        urls.append(cif_url)
    if structure_format in {"pdb", "both"} and pdb_url:
        urls.append(pdb_url)
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated UniProt accessions, e.g. P19531,P00690")
    parser.add_argument("--id-file", help="Text file with UniProt accessions separated by commas or newlines")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Download directory")
    parser.add_argument(
        "--structure-format",
        choices=("cif", "pdb", "both"),
        default="cif",
        help="Structure file format to download",
    )
    parser.add_argument("--with-pae-json", action="store_true", help="Also download PAE JSON when available")
    parser.add_argument("--with-confidence-json", action="store_true", help="Also download per-residue confidence JSON when available")
    args = parser.parse_args()

    ids = _parse_ids(args.ids, args.id_file)
    if not ids:
        print("No UniProt accessions provided. Use --ids or --id-file.", file=sys.stderr)
        return 1

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for uniprot_id in ids:
        url = f"{AFDB_API}/{uniprot_id}"
        try:
            payload = _read_json(url)
            entries = payload if isinstance(payload, list) else [payload]
            entries = [entry for entry in entries if isinstance(entry, dict)]
            if not entries:
                failures.append(f"{uniprot_id}: empty AlphaFold response")
                continue

            _save_json(output / f"{uniprot_id}.json", entries)
            downloaded = 0
            for entry in entries:
                for file_url in _pick_structure_urls(entry, args.structure_format):
                    destination = output / Path(file_url).name
                    _download(file_url, destination)
                    downloaded += 1
                if args.with_pae_json:
                    pae_url = str(entry.get("paeDocUrl") or entry.get("paeUrl") or "").strip()
                    if pae_url:
                        _download(pae_url, output / Path(pae_url).name)
                        downloaded += 1
                if args.with_confidence_json:
                    confidence_url = str(entry.get("plddtDocUrl") or "").strip()
                    if confidence_url:
                        _download(confidence_url, output / Path(confidence_url).name)
                        downloaded += 1
            print(f"OK {uniprot_id} -> metadata + {downloaded} file(s)")
        except urllib.error.HTTPError as exc:
            failures.append(f"{uniprot_id}: HTTP {exc.code}")
        except Exception as exc:
            failures.append(f"{uniprot_id}: {exc}")

    if failures:
        print("Failed downloads:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
