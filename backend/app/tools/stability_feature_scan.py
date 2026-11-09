"""Structure-coordinate scans for disulfides and salt bridges."""

from __future__ import annotations

import math
from collections import defaultdict

from app.tools.registry import ToolRegistry


POSITIVE_ATOMS = {"LYS": {"NZ"}, "ARG": {"NE", "NH1", "NH2"}, "HIS": {"ND1", "NE2"}}
PROTEIN_RESIDUES = set("ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL MSE SEC PYL".split())
NEGATIVE_ATOMS = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}


def _distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))


def _parse_pdb(protein_pdb: str) -> dict[tuple[str, int, str], dict]:
    residues: dict[tuple[str, int, str], dict] = {}
    for line in protein_pdb.splitlines():
        if line.startswith("ENDMDL"):
            break  # Contacts belong to one coordinate model.
        if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 54:
            continue
        altloc = line[16].strip()
        if altloc not in {"", "A"}:
            continue
        try:
            atom = line[12:16].strip()
            residue_name = line[17:20].strip().upper()
            if residue_name not in PROTEIN_RESIDUES:
                continue
            chain = line[21].strip() or "_"
            residue_number = int(line[22:26])
            insertion_code = line[26].strip()
            coordinate = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError:
            continue
        key = (chain, residue_number, insertion_code)
        entry = residues.setdefault(
            key,
            {"chain": chain, "residue_number": residue_number, "insertion_code": insertion_code,
             "residue_name": residue_name, "atoms": {}},
        )
        entry["atoms"][atom] = coordinate
    if not residues:
        raise ValueError("INVALID_PDB: no parseable protein coordinates found")
    return residues


def _label(residue: dict) -> str:
    suffix = residue["insertion_code"]
    return f'{residue["chain"]}:{residue["residue_name"]}{residue["residue_number"]}{suffix}'


def disulfide_saltbridge_scan(
    protein_pdb: str,
    disulfide_sg_cutoff_angstrom: float = 2.5,
    salt_bridge_cutoff_angstrom: float = 4.0,
    max_candidates: int = 100,
) -> dict:
    """Scan existing ionic contacts and geometry-only disulfide opportunities."""
    if not 1.8 <= disulfide_sg_cutoff_angstrom <= 3.5:
        raise ValueError("INVALID_DISULFIDE_CUTOFF: expected 1.8-3.5 angstrom")
    if not 2.5 <= salt_bridge_cutoff_angstrom <= 6.0:
        raise ValueError("INVALID_SALT_BRIDGE_CUTOFF: expected 2.5-6.0 angstrom")
    if not 1 <= max_candidates <= 1000:
        raise ValueError("INVALID_MAX_CANDIDATES: expected 1-1000")

    residues = list(_parse_pdb(protein_pdb).values())
    cysteines = [residue for residue in residues if residue["residue_name"] == "CYS" and "SG" in residue["atoms"]]
    existing_disulfides = []
    for index, first in enumerate(cysteines):
        for second in cysteines[index + 1:]:
            distance = _distance(first["atoms"]["SG"], second["atoms"]["SG"])
            if distance <= disulfide_sg_cutoff_angstrom:
                existing_disulfides.append({
                    "residue_1": _label(first), "residue_2": _label(second),
                    "sg_distance_angstrom": round(distance, 3),
                })

    geometric_candidates = []
    candidates = [residue for residue in residues if "CA" in residue["atoms"] and "CB" in residue["atoms"]]
    for index, first in enumerate(candidates):
        for second in candidates[index + 1:]:
            if first["chain"] == second["chain"] and abs(first["residue_number"] - second["residue_number"]) < 3:
                continue
            ca_distance = _distance(first["atoms"]["CA"], second["atoms"]["CA"])
            cb_distance = _distance(first["atoms"]["CB"], second["atoms"]["CB"])
            if 4.0 <= ca_distance <= 7.5 and 3.0 <= cb_distance <= 5.5:
                geometric_candidates.append({
                    "residue_1": _label(first), "residue_2": _label(second),
                    "ca_distance_angstrom": round(ca_distance, 3),
                    "cb_distance_angstrom": round(cb_distance, 3),
                    "geometry_deviation": round(abs(cb_distance - 4.5), 3),
                })
    geometric_candidates.sort(key=lambda item: item["geometry_deviation"])

    charged_atoms: dict[str, list[tuple[dict, str, tuple[float, float, float]]]] = defaultdict(list)
    for residue in residues:
        residue_name = residue["residue_name"]
        for atom_name in POSITIVE_ATOMS.get(residue_name, set()):
            if atom_name in residue["atoms"]:
                charged_atoms["positive"].append((residue, atom_name, residue["atoms"][atom_name]))
        for atom_name in NEGATIVE_ATOMS.get(residue_name, set()):
            if atom_name in residue["atoms"]:
                charged_atoms["negative"].append((residue, atom_name, residue["atoms"][atom_name]))

    closest_contacts: dict[tuple[str, str], dict] = {}
    for positive, positive_atom, positive_xyz in charged_atoms["positive"]:
        for negative, negative_atom, negative_xyz in charged_atoms["negative"]:
            distance = _distance(positive_xyz, negative_xyz)
            if distance > salt_bridge_cutoff_angstrom:
                continue
            pair = (_label(positive), _label(negative))
            previous = closest_contacts.get(pair)
            if previous is None or distance < previous["distance_angstrom"]:
                closest_contacts[pair] = {
                    "positive_residue": pair[0], "positive_atom": positive_atom,
                    "negative_residue": pair[1], "negative_atom": negative_atom,
                    "distance_angstrom": round(distance, 3),
                }

    return {
        "status": "completed_geometry_scan",
        "residue_count": len(residues),
        "existing_disulfides": existing_disulfides,
        "disulfide_geometry_candidates": geometric_candidates[:max_candidates],
        "existing_salt_bridges": sorted(
            (item for item in closest_contacts.values() if not item["positive_residue"].split(":", 1)[-1].startswith("HIS")),
            key=lambda item: item["distance_angstrom"],
        ),
        "histidine_acid_contacts": sorted(
            (item for item in closest_contacts.values() if item["positive_residue"].split(":", 1)[-1].startswith("HIS")),
            key=lambda item: item["distance_angstrom"],
        ),
        "limitations": [
            "Disulfide candidates pass distance filters only; side-chain rotamers, solvent exposure, strain, and redox environment require validation.",
            "Salt bridges are coordinate contacts, not calculated energetic contributions.",
            "Histidine-acid contacts are separate because histidine protonation depends on pH and local environment.",
        ],
    }


# Legacy direct-call API only. The uploaded-coordinate tool owns registration.
