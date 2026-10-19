#!/usr/bin/env python
"""Smoke test configured SIFTS/Foldseek data sources.

This script is intentionally env-driven. It does not download public datasets or
pretend a real Foldseek/SIFTS source exists; it validates configured local/remote
sources when they are present and prints SKIP for missing optional inputs.

Usage examples:
    SIFTS_SMOKE_USE_DEMO=1 FOLDSEEK_SMOKE_USE_DEMO=1 \
        .venv/bin/python scripts/smoke_structure_data.py

    SIFTS_MAPPING_PATH=/data/sifts SIFTS_SMOKE_PDB_ID=1abc \
        .venv/bin/python scripts/smoke_structure_data.py

    FOLDSEEK_BINARY=foldseek FOLDSEEK_DATABASE_PDB=/data/foldseek/pdb \
        STRUCTURE_SMOKE_PDB_FILE=/tmp/query.pdb \
        .venv/bin/python scripts/smoke_structure_data.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_SIFTS_DIR = PROJECT_ROOT / "app" / "data" / "fixtures" / "structure_smoke"
DEMO_SIFTS_FILENAMES = {"1abc.json"}

from app.core.config import settings


MINI_PDB = """\
HEADER    STRUCTURE SMOKE FALLBACK
ATOM      1  N   MET A   1      11.104  13.207  12.411  1.00 20.00           N
ATOM      2  CA  MET A   1      12.560  13.241  12.519  1.00 20.00           C
ATOM      3  C   ALA A   2      13.101  14.650  12.778  1.00 20.00           C
ATOM      4  O   ALA A   2      12.452  15.653  12.515  1.00 20.00           O
END
"""


def _load_pdb_text() -> str:
    path = (settings.STRUCTURE_SMOKE_PDB_FILE or "").strip()
    if not path:
        return MINI_PDB
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _use_demo_sifts() -> bool:
    return os.getenv("SIFTS_SMOKE_USE_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


def _use_demo_foldseek() -> bool:
    return os.getenv("FOLDSEEK_SMOKE_USE_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_sifts_config() -> tuple[str, str]:
    if _use_demo_sifts():
        return str(DEMO_SIFTS_DIR), os.getenv("SIFTS_SMOKE_PDB_ID", "").strip() or "1abc"

    mapping_path = (settings.SIFTS_MAPPING_PATH or "").strip()
    pdb_id = os.getenv("SIFTS_SMOKE_PDB_ID", "").strip()

    if mapping_path:
        if not pdb_id:
            path = Path(mapping_path)
            if path.is_file() and path.suffix.lower() in {".json", ".csv", ".tsv"}:
                pdb_id = path.stem
            elif path.is_dir():
                preferred: list[Path] = []
                fallback: list[Path] = []
                for candidate in sorted(path.iterdir()):
                    if candidate.is_file() and candidate.suffix.lower() in {".json", ".csv", ".tsv"}:
                        if candidate.name in DEMO_SIFTS_FILENAMES:
                            fallback.append(candidate)
                        else:
                            preferred.append(candidate)
                ordered = preferred + fallback
                if ordered:
                    pdb_id = ordered[0].stem
        return mapping_path, pdb_id

    return "", pdb_id


async def _smoke_sifts(pdb_text: str) -> bool:
    from app.tools.residue_mapping_sifts import residue_mapping_sifts

    mapping_path, pdb_id = _resolve_sifts_config()
    if not mapping_path:
        print("SKIP sifts: SIFTS_MAPPING_PATH is not configured")
        return True

    if not pdb_id:
        print("SKIP sifts: SIFTS_SMOKE_PDB_ID is required when SIFTS_MAPPING_PATH is set")
        return True

    original_mapping_path = settings.SIFTS_MAPPING_PATH
    settings.SIFTS_MAPPING_PATH = mapping_path
    try:
        result = await residue_mapping_sifts(
            pdb_data=pdb_text,
            pdb_id=pdb_id,
            chain_id=os.getenv("SIFTS_SMOKE_CHAIN", "").strip(),
            uniprot_id=os.getenv("SIFTS_SMOKE_UNIPROT_ID", "").strip(),
            input_sequence="MA" if _use_demo_sifts() else "",
        )
    finally:
        settings.SIFTS_MAPPING_PATH = original_mapping_path
    if result.get("source") != "local_sifts_mapping" or not result.get("mappings"):
        print(f"FAIL sifts: expected local_sifts_mapping with mappings, got {result}")
        return False

    print(
        "PASS sifts: "
        f"{result['mapping_count']} mappings from {result.get('mapping_source')}"
    )
    return True


async def _smoke_foldseek(pdb_text: str) -> bool:
    from app.tools.structure_search_foldseek import structure_search_foldseek

    if _use_demo_foldseek():
        result = await structure_search_foldseek(
            pdb_data=pdb_text,
            database=os.getenv("FOLDSEEK_SMOKE_DATABASE", "pdb").strip() or "pdb",
            max_results=int(os.getenv("FOLDSEEK_SMOKE_MAX_RESULTS", "5")),
        )
        if (
            result.get("status") != "degraded"
            or result.get("error_code") != "FOLDSEEK_NOT_CONFIGURED"
            or result.get("backend") != "summary_only"
        ):
            print(f"FAIL foldseek-demo: expected degraded summary_only, got {result}")
            return False
        print(
            "PASS foldseek-demo: "
            f"backend={result.get('backend')} residues={result.get('query_structure', {}).get('total_residues')}"
        )
        return True

    configured = bool(settings.FOLDSEEK_API_URL.strip()) or (
        bool(settings.FOLDSEEK_BINARY.strip())
        and bool(
            settings.FOLDSEEK_DATABASE_PDB.strip()
            or settings.FOLDSEEK_DATABASE_ALPHAFOLD.strip()
            or settings.FOLDSEEK_DATABASE_CUSTOM.strip()
            or settings.FOLDSEEK_DATABASE_ROOT.strip()
        )
    )
    if not configured:
        print("SKIP foldseek: FOLDSEEK_API_URL or FOLDSEEK_BINARY + database path is not configured")
        return True

    if not (settings.STRUCTURE_SMOKE_PDB_FILE or "").strip():
        print("SKIP foldseek: STRUCTURE_SMOKE_PDB_FILE is required for real Foldseek smoke")
        return True

    database = os.getenv("FOLDSEEK_SMOKE_DATABASE", "pdb").strip() or "pdb"
    result = await structure_search_foldseek(
        pdb_data=pdb_text,
        database=database,
        max_results=int(os.getenv("FOLDSEEK_SMOKE_MAX_RESULTS", "5")),
    )
    if result.get("status") != "completed":
        print(f"FAIL foldseek: expected completed search, got {result}")
        return False

    print(
        "PASS foldseek: "
        f"backend={result.get('backend')} results={result.get('results_count')} database={database}"
    )
    return True


async def main() -> int:
    pdb_text = MINI_PDB if _use_demo_sifts() else _load_pdb_text()
    results = [
        await _smoke_sifts(pdb_text),
        await _smoke_foldseek(pdb_text),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
