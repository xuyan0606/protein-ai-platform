"""Report auditable side-chain contacts in the first PDB coordinate model."""

from __future__ import annotations

from math import dist
from typing import Any

from app.services import storage
from app.tools.registry import ToolRegistry
from app.tools.site_structure_function_features import _parse_pdb_residue_atoms

_POSITIVE = {"ARG": {"NE", "NH1", "NH2"}, "LYS": {"NZ"}}
_ACIDIC = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}
_HISTIDINE = {"ND1", "NE2"}


def _site(residue: dict[str, Any]) -> str:
    return f"{residue['chain_id']}:{residue['pdb_residue_no']}{residue.get('insertion_code') or ''}"


def _atoms(residue: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    return [atom for atom in residue["atoms"] if atom["atom_name"] in names]


def _nearest(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> tuple[float, str, str] | None:
    pairs = [(dist(left["coord"], right["coord"]), left["atom_name"], right["atom_name"])
             for left in a for right in b]
    return min(pairs) if pairs else None


async def disulfide_saltbridge_scan(
    pdb_data: str = "", pdb_object_name: str = "", chain_id: str = "",
    disulfide_max_angstrom: float = 2.3, ion_contact_max_angstrom: float = 4.0,
) -> dict[str, Any]:
    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
    if not pdb_data.strip():
        return {"status": "failed", "error_code": "MISSING_PDB", "error": "Provide PDB coordinates."}
    residues = _parse_pdb_residue_atoms(pdb_data, chain_id=chain_id)
    if not residues:
        return {"status": "failed", "error_code": "NO_PROTEIN_RESIDUES", "error": "No protein residues for this chain."}

    disulfides: list[dict[str, Any]] = []
    cysteines = [row for row in residues if row["residue_name"] == "CYS"]
    for i, left in enumerate(cysteines):
        for right in cysteines[i + 1:]:
            near = _nearest(_atoms(left, {"SG"}), _atoms(right, {"SG"}))
            if near and 1.7 <= near[0] <= disulfide_max_angstrom:
                disulfides.append({
                    "residue_1": _site(left), "residue_2": _site(right),
                    "sg_distance_angstrom": round(near[0], 3),
                })

    acidic = [row for row in residues if row["residue_name"] in _ACIDIC]
    ionic: list[dict[str, Any]] = []
    histidine: list[dict[str, Any]] = []
    for left in residues:
        positive_names = _POSITIVE.get(left["residue_name"])
        is_histidine = left["residue_name"] == "HIS"
        if not positive_names and not is_histidine:
            continue
        for right in acidic:
            if left is right:
                continue
            near = _nearest(
                _atoms(left, positive_names or _HISTIDINE),
                _atoms(right, _ACIDIC[right["residue_name"]]),
            )
            if near and near[0] <= ion_contact_max_angstrom:
                row = {
                    "residue_1": _site(left), "residue_1_name": left["residue_name"],
                    "residue_2": _site(right), "residue_2_name": right["residue_name"],
                    "atom_1": near[1], "atom_2": near[2],
                    "distance_angstrom": round(near[0], 3),
                }
                (histidine if is_histidine else ionic).append(row)
    ionic.sort(key=lambda row: row["distance_angstrom"])
    histidine.sort(key=lambda row: row["distance_angstrom"])
    return {
        "status": "completed", "found": True, "residue_count": len(residues),
        "chain_id": chain_id or "all", "disulfide_bonds": disulfides,
        "salt_bridges": ionic, "histidine_acidic_contacts": histidine,
        "thresholds_angstrom": {"disulfide_sg": disulfide_max_angstrom, "ionic_heavy_atom": ion_contact_max_angstrom},
        "report_boundary": "仅为首个坐标模型的侧链原子几何接触；His 质子化、离子配对能量及耐热性均未由此确认。",
    }


ToolRegistry.register(
    name="disulfide_saltbridge_scan",
    description="Scan first-model protein side-chain coordinates for cysteine SG contacts and charged side-chain contacts; geometry only.",
    parameters={"type": "object", "properties": {
        "pdb_data": {"type": "string"}, "pdb_object_name": {"type": "string"},
        "chain_id": {"type": "string"},
        "disulfide_max_angstrom": {"type": "number", "default": 2.3},
        "ion_contact_max_angstrom": {"type": "number", "default": 4.0},
    }},
    handler=disulfide_saltbridge_scan, is_async=True, category="structure", timeout_seconds=30,
)
