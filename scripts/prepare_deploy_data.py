#!/usr/bin/env python3
"""Scaffold the standard deploy_data layout for local/demo/live datasets."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data"
DEMO_SIFTS = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "structure_smoke" / "1abc.json"
DEMO_ANNOTATIONS = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "local_annotations"

MINI_PDB = """\
HEADER    DEPLOY DATA SMOKE QUERY
ATOM      1  N   MET A   1      11.104  13.207  12.411  1.00 20.00           N
ATOM      2  CA  MET A   1      12.560  13.241  12.519  1.00 20.00           C
ATOM      3  C   ALA A   2      13.101  14.650  12.778  1.00 20.00           C
ATOM      4  O   ALA A   2      12.452  15.653  12.515  1.00 20.00           O
END
"""


def _default_manifest() -> dict[str, object]:
    return {
        "schema_version": 2,
        "name": "deploy_data_live_seed",
        "updated_at": date.today().isoformat(),
        "data_version": date.today().isoformat(),
        "mode": "plan_only_seed",
        "source_policy": "This manifest records expected live datasets and commands only; it does not embed large external data.",
        "pdb_ids": [],
        "uniprot_ids": [],
        "alphafold_structure_format": "cif",
        "download_pae_json": True,
        "required_live_components": [
            "annotations",
            "sifts",
            "pdb",
            "alphafold",
            "foldseek",
            "smoke_query",
        ],
        "expected_datasets": {
            "pdb": {
                "source": "RCSB PDB",
                "expected_from": "pdb_ids",
                "file_patterns": ["<PDB_ID>.cif", "<PDB_ID>.pdb"],
                "plan_only_commands": [
                    "python3 scripts/download_rcsb_structures.py --ids <comma-separated-pdb_ids> --format cif --output deploy_data/pdb"
                ],
            },
            "sifts": {
                "source": "PDBe UniProt mappings / SIFTS-compatible residue mappings",
                "expected_from": "pdb_ids",
                "file_patterns": ["<pdb_id>.json", "<pdb_id>.csv", "<pdb_id>.tsv"],
                "plan_only_commands": [
                    "python3 scripts/download_sifts_mappings.py --ids <comma-separated-pdb_ids> --output deploy_data/sifts"
                ],
            },
            "alphafold": {
                "source": "AlphaFold DB",
                "expected_from": "uniprot_ids",
                "file_patterns": ["AF-<UniProt>-F1-model_v*.cif", "AF-<UniProt>-F1-predicted_aligned_error_v*.json"],
                "plan_only_commands": [
                    "python3 scripts/download_alphafold_models.py --ids <comma-separated-uniprot_ids> --structure-format cif --with-pae-json --output deploy_data/alphafold"
                ],
            },
            "annotations": {
                "source": "UniProt/InterPro plus curated M-CSA/SignalP-compatible exports",
                "expected_from": "uniprot_ids",
                "file_patterns": ["metadata.json", "base.json", "interpro.json", "mcsa.json", "signalp.json"],
                "plan_only_commands": [
                    "python3 scripts/download_real_annotations.py --ids <comma-separated-uniprot_ids> --output deploy_data/annotations"
                ],
            },
            "foldseek": {
                "source": "Local Foldseek indexes built from staged PDB and AlphaFold structures",
                "depends_on": ["pdb", "alphafold"],
                "file_patterns": ["foldseek/pdb/protein_ai_pdb*", "foldseek/alphafold/protein_ai_alphafold*"],
                "plan_only_commands": [
                    "python3 scripts/build_foldseek_db.py --kind pdb --deploy-root deploy_data",
                    "python3 scripts/build_foldseek_db.py --kind alphafold --deploy-root deploy_data",
                    "python3 scripts/materialize_foldseek_links.py --root deploy_data/foldseek --dry-run",
                ],
            },
            "smoke_query": {
                "source": "Representative local query structure selected by the operator",
                "file_patterns": ["smoke/query.pdb"],
                "plan_only_commands": [
                    "cp <representative-query.pdb> deploy_data/smoke/query.pdb"
                ],
            },
        },
        "next_actions": [
            "Fill pdb_ids and uniprot_ids with the live seed set.",
            "Run python3 scripts/run_deploy_data_update.py --plan-only --json to review commands without downloading.",
            "Stage/download data on a network-enabled host, then run python3 scripts/check_deploy_data.py --require-live.",
        ],
    }


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copytree(src: Path, dst: Path, *, overwrite: bool = False) -> None:
    if dst.exists():
        has_existing_content = any(dst.iterdir()) if dst.is_dir() else True
        if has_existing_content and not overwrite:
            raise SystemExit(f"Refusing to overwrite existing directory without --overwrite-demo: {dst}")
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _write_default_manifest(output: Path, overwrite: bool = False) -> Path:
    target = output / "live_manifest.json"
    if target.exists() and not overwrite:
        return target
    target.write_text(json.dumps(_default_manifest(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Target deploy_data root")
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="Copy demo SIFTS fixture, demo local annotations, and a minimal smoke query PDB",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Create deploy_data/live_manifest.json when it is missing.",
    )
    parser.add_argument(
        "--overwrite-manifest",
        action="store_true",
        help="Rewrite deploy_data/live_manifest.json with the default plan-only template.",
    )
    parser.add_argument(
        "--overwrite-demo",
        action="store_true",
        help="Allow --with-demo to replace existing demo target files/directories.",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    annotations = output / "annotations"
    sifts = output / "sifts"
    pdb = output / "pdb"
    alphafold = output / "alphafold"
    foldseek = output / "foldseek"
    smoke = output / "smoke"
    lipase = output / "lipase"

    for path in (
        annotations,
        sifts,
        pdb,
        alphafold,
        lipase,
        foldseek / "pdb",
        foldseek / "alphafold",
        foldseek / "custom",
        smoke,
    ):
        _mkdir(path)

    if args.with_demo:
        sifts_target = sifts / "1abc.json"
        if sifts_target.exists() and not args.overwrite_demo:
            raise SystemExit(f"Refusing to overwrite existing file without --overwrite-demo: {sifts_target}")
        shutil.copy2(DEMO_SIFTS, sifts_target)
        _copytree(DEMO_ANNOTATIONS, annotations, overwrite=args.overwrite_demo)
        (smoke / "query.pdb").write_text(MINI_PDB, encoding="utf-8")

    manifest_path: Path | None = None
    if args.write_manifest or args.overwrite_manifest:
        manifest_path = _write_default_manifest(output, overwrite=args.overwrite_manifest)

    print(f"Prepared deploy data root: {output}")
    print("Subdirectories:")
    print(f"  - {annotations}")
    print(f"  - {sifts}")
    print(f"  - {pdb}")
    print(f"  - {alphafold}")
    print(f"  - {foldseek / 'pdb'}")
    print(f"  - {foldseek / 'alphafold'}")
    print(f"  - {foldseek / 'custom'}")
    print(f"  - {lipase}")
    print(f"  - {smoke}")
    if args.with_demo:
        print("Demo assets copied: annotations/, sifts/1abc.json, smoke/query.pdb")
    else:
        print("No demo assets copied. Drop real exports/databases into the directories above.")
    if manifest_path is not None:
        print(f"Live manifest template: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
