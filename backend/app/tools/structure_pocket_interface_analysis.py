"""Geometry-only pocket, channel, and chain-interface clues."""

from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any

from app.services import storage
from app.tools.ligand_contact_analysis import _distance, _parse_atoms
from app.tools.registry import ToolRegistry

POCKET_DISTANCE = 6.0
INTERFACE_DISTANCE = 5.0


async def structure_pocket_interface_analysis(
    pdb_data: str | None = None,
    pdb_object_name: str = "",
    chain_scope: list[str] | None = None,
    pocket_distance_angstrom: float = POCKET_DISTANCE,
    interface_distance_angstrom: float = INTERFACE_DISTANCE,
) -> dict[str, Any]:
    start = perf_counter()
    base = {
        "schema_version": "structure_pocket_interface_analysis_v1", "status": "completed",
        "geometry_only": True, "evidence_level": "GEOMETRY_ONLY", "capability_status": "coordinate_geometry",
        "thresholds": {
            "pocket_distance_angstrom": pocket_distance_angstrom,
            "interface_distance_angstrom": interface_distance_angstrom,
        }, "pocket": {"residues": [], "status": "not_available"},
        "channels": {"status": "geometric_clues_only", "clues": []}, "chain_interfaces": [],
        "interpretation_boundary": "Geometry-only clues cannot establish binding energy, catalytic mechanism, or catalytic proof.",
        "calculation_time_ms": 0.0,
    }
    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
    if not pdb_data:
        base.update({"status": "not_available", "error_code": "MISSING_PDB"})
        return base
    atoms, coverage, _ = _parse_atoms(pdb_data)
    coverage["coverage"] = round(coverage["parsed_records"] / coverage["coordinate_records"], 4) if coverage["coordinate_records"] else 0.0
    base["coordinate_coverage"] = coverage
    if coverage["invalid_records"] or coverage["coverage"] < 1.0:
        base.update({"status": "not_available", "error_code": "INCOMPLETE_COORDINATES"})
        return base
    selected = set(chain_scope or [])
    protein = [a for a in atoms if a["record"] == "ATOM" and (not selected or a["chain_id"] in selected)]
    ligands = [a for a in atoms if a["record"] == "HETATM" and a["residue_name"] not in {"HOH", "WAT", "DOD"}]
    if not ligands:
        base.update({"status": "not_available", "error_code": "NO_LIGAND"})
        return base
    pocket: dict[tuple[str, int, str | None], dict[str, Any]] = {}
    for residue_atom in protein:
        distances = [_distance(residue_atom["coord"], ligand["coord"]) for ligand in ligands]
        if distances and min(distances) <= pocket_distance_angstrom:
            key = (residue_atom["chain_id"], residue_atom["residue_number"], residue_atom["insertion_code"])
            pocket[key] = {
                "chain_id": residue_atom["chain_id"], "residue_number": residue_atom["residue_number"],
                "insertion_code": residue_atom["insertion_code"], "residue_name": residue_atom["residue_name"],
                "min_ligand_distance_angstrom": round(min(distances), 3),
            }
    pocket_rows = sorted(pocket.values(), key=lambda row: (row["chain_id"], row["residue_number"]))
    base["pocket"] = {"status": "computed", "residues": pocket_rows, "residue_count": len(pocket_rows)}
    # A channel can only be responsibly represented here as a proximity-clue list;
    # no solvent or tunnel algorithm is claimed.
    if len(pocket) >= 2:
        base["channels"]["clues"] = [{"type": "ligand_surrounding_residue_cluster", "residue_count": len(pocket)}]
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in protein:
        by_chain[atom["chain_id"]].append(atom)
    chain_ids = sorted(by_chain)
    for index, chain_a in enumerate(chain_ids):
        for chain_b in chain_ids[index + 1:]:
            distances = [_distance(a["coord"], b["coord"]) for a in by_chain[chain_a] for b in by_chain[chain_b]]
            close = [value for value in distances if value <= interface_distance_angstrom]
            if close:
                base["chain_interfaces"].append({
                    "chain_ids": [chain_a, chain_b], "contact_count": len(close),
                    "min_distance_angstrom": round(min(close), 3),
                    "interface_distance_angstrom": interface_distance_angstrom,
                    "geometry_only": True,
                })
    base["chain_scope"] = chain_ids
    base["calculation_time_ms"] = round((perf_counter() - start) * 1000, 3)
    return base


ToolRegistry.register(
    name="structure_pocket_interface_analysis",
    description="Report coordinate-only ligand pocket, channel, and chain-interface geometry clues.",
    parameters={"type": "object", "properties": {
        "pdb_data": {"type": "string"}, "pdb_object_name": {"type": "string"},
        "chain_scope": {"type": "array", "items": {"type": "string"}},
        "pocket_distance_angstrom": {"type": "number", "default": POCKET_DISTANCE},
        "interface_distance_angstrom": {"type": "number", "default": INTERFACE_DISTANCE},
    }},
    handler=structure_pocket_interface_analysis, is_async=True, category="structure", timeout_seconds=30,
)
