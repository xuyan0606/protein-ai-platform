#!/usr/bin/env python3
"""Refresh deploy_data from an external manifest and optionally verify live gates.

This is the migration-friendly entrypoint for rebuilding a live deploy_data tree
on another machine from official sources plus local Foldseek indices.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEPLOY_ROOT = PROJECT_ROOT / "deploy_data"
DEFAULT_MANIFEST = DEFAULT_DEPLOY_ROOT / "live_manifest.json"


def _read_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Manifest must be a JSON object: {path}")
    return payload


def _string_list(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key) or []
    if not isinstance(value, list):
        raise SystemExit(f"Manifest field '{key}' must be a JSON array")
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> None:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="JSON manifest with pdb_ids and uniprot_ids")
    parser.add_argument("--deploy-root", default=str(DEFAULT_DEPLOY_ROOT), help="deploy_data root")
    parser.add_argument("--skip-downloads", action="store_true", help="Reuse existing downloaded files")
    parser.add_argument("--verify", action="store_true", help="Run live host/backend gates at the end")
    parser.add_argument("--docker-verify", action="store_true", help="Also run Docker live gate and smoke at the end")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    deploy_root = Path(args.deploy_root).expanduser().resolve()
    manifest = _read_manifest(manifest_path)

    pdb_ids = _string_list(manifest, "pdb_ids")
    uniprot_ids = _string_list(manifest, "uniprot_ids")
    alphafold_format = str(manifest.get("alphafold_structure_format") or "cif").strip() or "cif"
    with_pae_json = bool(manifest.get("download_pae_json", True))

    if not args.skip_downloads:
        if pdb_ids:
            _run(
                [
                    sys.executable,
                    "scripts/download_rcsb_structures.py",
                    "--ids",
                    ",".join(pdb_ids),
                    "--format",
                    "cif",
                    "--output",
                    str(deploy_root / "pdb"),
                ]
            )
            _run(
                [
                    sys.executable,
                    "scripts/download_sifts_mappings.py",
                    "--ids",
                    ",".join(pdb_ids),
                    "--output",
                    str(deploy_root / "sifts"),
                ]
            )
        if uniprot_ids:
            af_cmd = [
                sys.executable,
                "scripts/download_alphafold_models.py",
                "--ids",
                ",".join(uniprot_ids),
                "--structure-format",
                alphafold_format,
                "--output",
                str(deploy_root / "alphafold"),
            ]
            if with_pae_json:
                af_cmd.append("--with-pae-json")
            _run(af_cmd)
            _run(
                [
                    sys.executable,
                    "scripts/download_real_annotations.py",
                    "--ids",
                    ",".join(uniprot_ids),
                    "--output",
                    str(deploy_root / "annotations"),
                ]
            )

    _run([sys.executable, "scripts/build_foldseek_db.py", "--kind", "pdb", "--deploy-root", str(deploy_root)])
    _run([sys.executable, "scripts/build_foldseek_db.py", "--kind", "alphafold", "--deploy-root", str(deploy_root)])
    _run([sys.executable, "scripts/materialize_foldseek_links.py", "--root", str(deploy_root / "foldseek")])
    _run([sys.executable, "scripts/write_deploy_env.py", "--deploy-root", str(deploy_root)])
    _run([sys.executable, "scripts/check_deploy_data.py", "--root", str(deploy_root)])

    if args.verify:
        _run(["make", "deploy-live-gate"])
        _run(["make", "backend-smoke-live"])

    if args.docker_verify:
        _run(["make", "docker-backend-live-gate"])
        _run(["make", "docker-backend-smoke-live"])

    print("Refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
