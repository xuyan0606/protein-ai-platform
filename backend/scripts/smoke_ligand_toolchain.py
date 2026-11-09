#!/usr/bin/env python
"""Smoke test ligand preprocessing, docking, and MD topology prerequisites.

This script is intentionally read-only. It inspects an SDF ligand and checks
whether the host has the command-line tools needed before real docking/MD work:
OpenBabel/RDKit 2D/3D preparation, AutoDock Vina PDBQT docking,
ACPYPE/Antechamber ligand topology generation, and GROMACS.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SDF = PROJECT_ROOT / "Structure2D_COMPOUND_CID_5478883.sdf"


def _command_status(*names: str) -> dict[str, Any]:
    resolved = {name: shutil.which(name) for name in names}
    return {
        "available": any(bool(path) for path in resolved.values()),
        "commands": resolved,
    }


def _module_status(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    return {
        "available": spec is not None,
        "module": module_name,
    }


def _parse_v2000_sdf(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    counts_index = None
    for index, line in enumerate(lines[:80]):
        if "V2000" in line:
            counts_index = index
            break
    if counts_index is None:
        return {
            "format": "unknown",
            "parse_status": "unsupported",
            "error": "V2000 counts line not found",
        }

    counts_line = lines[counts_index]
    try:
        atom_count = int(counts_line[0:3])
        bond_count = int(counts_line[3:6])
    except ValueError:
        parts = counts_line.split()
        atom_count = int(parts[0])
        bond_count = int(parts[1])

    atom_lines = lines[counts_index + 1 : counts_index + 1 + atom_count]
    atoms: list[dict[str, Any]] = []
    z_values: list[float] = []
    element_counts: dict[str, int] = {}
    parse_errors: list[str] = []
    for line in atom_lines:
        try:
            x_value = float(line[0:10])
            y_value = float(line[10:20])
            z_value = float(line[20:30])
            element = line[31:34].strip() or "?"
        except ValueError:
            parts = line.split()
            try:
                x_value = float(parts[0])
                y_value = float(parts[1])
                z_value = float(parts[2])
                element = parts[3]
            except (IndexError, ValueError):
                parse_errors.append(line[:80])
                continue
        z_values.append(z_value)
        element_counts[element] = element_counts.get(element, 0) + 1
        atoms.append({"element": element, "x": x_value, "y": y_value, "z": z_value})

    nonzero_z = [value for value in z_values if abs(value) > 1e-4]
    header_dimension = "2d" if any("2D" in line.upper() for line in lines[:6]) else (
        "3d" if any("3D" in line.upper() for line in lines[:6]) else "unknown"
    )
    inferred_dimension = "3d" if nonzero_z else "2d"
    return {
        "format": "V2000",
        "parse_status": "parsed" if not parse_errors else "parsed_with_errors",
        "atom_count": atom_count,
        "bond_count": bond_count,
        "parsed_atom_count": len(atoms),
        "element_counts": element_counts,
        "header_dimension": header_dimension,
        "inferred_dimension": inferred_dimension,
        "is_2d_sdf": inferred_dimension == "2d",
        "all_z_zero": len(z_values) > 0 and not nonzero_z,
        "z_min": min(z_values) if z_values else None,
        "z_max": max(z_values) if z_values else None,
        "parse_error_count": len(parse_errors),
        "parse_errors_preview": parse_errors[:3],
    }


def _inspect_sdf(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "parse_status": "missing",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = _parse_v2000_sdf(text)
    parsed.update(
        {
            "path": str(path),
            "exists": True,
            "size_bytes": path.stat().st_size,
            "record_count": text.count("$$$$") or 1,
        }
    )
    return parsed


def _evaluate(sdf: dict[str, Any], tools: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    missing: list[str] = []
    warnings: list[str] = []
    if not sdf.get("exists"):
        return "input_missing", ["sdf_file"], warnings
    if sdf.get("parse_status") not in {"parsed", "parsed_with_errors"}:
        return "invalid_sdf", ["valid_v2000_sdf"], warnings
    if not sdf.get("is_2d_sdf"):
        warnings.append("Input SDF appears to already contain non-zero Z coordinates; verify it is the intended ligand state.")

    conformer_ready = bool(tools["openbabel"]["available"] or tools["rdkit"]["available"])
    topology_ready = bool(tools["acpype"]["available"])
    gromacs_ready = bool(tools["gromacs"]["available"])
    requirements = {
        "conformer_generation": conformer_ready,
        "pdbqt_preparation": bool(tools["openbabel"]["available"]),
        "vina_docking": bool(tools["vina"]["available"]),
        "ligand_topology": topology_ready,
        "gromacs_md": gromacs_ready,
    }
    for name, available in requirements.items():
        if not available:
            missing.append(name)
    if missing:
        return "blocked_toolchain_missing", missing, warnings
    return "ready", missing, warnings


def build_payload(sdf_file: str | None = None) -> dict[str, Any]:
    path = Path(sdf_file or os.getenv("LIGAND_SMOKE_SDF_FILE") or DEFAULT_SDF).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    sdf = _inspect_sdf(path)
    tools = {
        "openbabel": _command_status("obabel"),
        "rdkit": _module_status("rdkit"),
        "vina": _command_status("vina"),
        "acpype": _command_status("acpype"),
        "antechamber": _command_status("antechamber"),
        "gromacs": _command_status("gmx", "gmx_mpi"),
    }
    status, missing, warnings = _evaluate(sdf, tools)
    return {
        "name": "ligand_toolchain_smoke",
        "summary": {
            "status": status,
            "input_sdf_exists": bool(sdf.get("exists")),
            "is_2d_sdf": bool(sdf.get("is_2d_sdf")),
            "atom_count": sdf.get("atom_count"),
            "bond_count": sdf.get("bond_count"),
            "missing_requirements": missing,
            "warnings": warnings,
        },
        "sdf": sdf,
        "tools": tools,
        "required_pipeline": [
            "2D SDF -> 3D conformer + hydrogens + geometry optimization",
            "protonation/charge assignment -> PDBQT",
            "AutoDock Vina docking with pocket box parameters",
            "enzyme-ligand 3D complex export",
            "ACPYPE/Antechamber GAFF2 ligand topology -> GROMACS ITP",
            "GROMACS system assembly, solvation, equilibration, and MD",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdf-file", default=None, help="SDF ligand to inspect. Defaults to Structure2D_COMPOUND_CID_5478883.sdf.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--require-live", action="store_true", help="Exit non-zero unless the full ligand docking/MD toolchain is ready.")
    args = parser.parse_args()

    payload = build_payload(args.sdf_file)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            "ligand_toolchain_smoke\t"
            f"status={summary['status']}\t"
            f"input_sdf_exists={summary['input_sdf_exists']}\t"
            f"is_2d_sdf={summary['is_2d_sdf']}\t"
            f"atom_count={summary.get('atom_count') or ''}\t"
            f"bond_count={summary.get('bond_count') or ''}\t"
            f"missing={','.join(summary['missing_requirements'])}"
        )

    if args.require_live and payload["summary"]["status"] != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
