"""Coordinate-only ligand contact analysis for uploaded PDB structures."""

from __future__ import annotations

from collections import defaultdict
from math import sqrt
from time import perf_counter
from typing import Any

from app.services import storage
from app.services.pdb_parser import _AA3TO1
from app.tools.registry import ToolRegistry

_WATER = {"HOH", "WAT", "DOD"}
CONTACT_DISTANCE = 4.5


def _first_model_lines(pdb_data: str) -> list[str]:
    lines: list[str] = []
    model_seen = False
    for line in pdb_data.splitlines():
        record = line[:6].strip().upper()
        if record == "MODEL":
            if model_seen:
                break
            model_seen = True
            continue
        if record == "ENDMDL" and model_seen:
            break
        lines.append(line)
    return lines


def _parse_atoms(pdb_data: str) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    atoms: list[dict[str, Any]] = []
    coordinate_records = 0
    parsed_records = 0
    invalid_records = 0
    for line in _first_model_lines(pdb_data):
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        coordinate_records += 1
        try:
            if len(line) < 54:
                raise ValueError("short coordinate record")
            atom_name = line[12:16].strip().upper()
            alt_loc = line[16].strip()
            res_name = line[17:20].strip().upper()
            chain_id = line[21].strip() or "_"
            residue_number = int(line[22:26].strip())
            insertion_code = line[26].strip() or None
            x, y, z = (float(line[a:b].strip()) for a, b in ((30, 38), (38, 46), (46, 54)))
            element = (line[76:78].strip().upper() if len(line) >= 78 else "") or atom_name[:1]
        except (TypeError, ValueError, IndexError):
            invalid_records += 1
            continue
        if alt_loc not in {"", "A"}:
            continue
        parsed_records += 1
        atoms.append({
            "record": record,
            "atom_name": atom_name,
            "residue_name": res_name,
            "chain_id": chain_id,
            "residue_number": residue_number,
            "insertion_code": insertion_code,
            "element": element,
            "coord": (x, y, z),
        })
    return atoms, {
        "coordinate_records": coordinate_records,
        "parsed_records": parsed_records,
        "invalid_records": invalid_records,
    }, coordinate_records


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _base_result(start: float, coverage: dict[str, Any], chain_scope: list[str]) -> dict[str, Any]:
    denominator = coverage["coordinate_records"]
    coverage["coverage"] = round(
        coverage["parsed_records"] / denominator, 4
    ) if denominator else 0.0
    return {
        "schema_version": "ligand_contact_analysis_v1",
        "status": "completed",
        "geometry_only": True,
        "evidence_level": "GEOMETRY_ONLY",
        "capability_status": "coordinate_geometry",
        "ligand_instances": [],
        "contacts": [],
        "contact_residues": [],
        "thresholds": {"contact_distance_angstrom": CONTACT_DISTANCE},
        "coordinate_coverage": coverage,
        "chain_scope": chain_scope,
        "calculation_time_ms": round((perf_counter() - start) * 1000, 3),
        "interpretation_boundary": (
            "Geometry-only coordinate proximity; cannot establish binding energy, affinity, catalytic activity, mechanism, or experimental benefit."
        ),
    }


async def ligand_contact_analysis(
    pdb_data: str | None = None,
    pdb_object_name: str = "",
    chain_id: str = "",
    contact_distance_angstrom: float = CONTACT_DISTANCE,
) -> dict[str, Any]:
    start = perf_counter()
    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
    if not pdb_data:
        return {
            "schema_version": "ligand_contact_analysis_v1", "status": "not_available",
            "error_code": "MISSING_PDB", "geometry_only": True, "ligand_instances": [],
            "contacts": [], "contact_residues": [], "chain_scope": [],
            "coordinate_coverage": {"coordinate_records": 0, "parsed_records": 0, "invalid_records": 0, "coverage": 0.0},
            "evidence_level": "GEOMETRY_ONLY", "capability_status": "coordinate_geometry",
            "interpretation_boundary": "No structure coordinates were supplied; binding energy and catalytic claims are unavailable.",
            "calculation_time_ms": round((perf_counter() - start) * 1000, 3),
        }
    atoms, coverage, _ = _parse_atoms(pdb_data)
    chains = sorted({a["chain_id"] for a in atoms if a["record"] == "ATOM"})
    result = _base_result(start, coverage, chains)
    result["thresholds"]["contact_distance_angstrom"] = float(contact_distance_angstrom)
    if coverage["invalid_records"] or coverage["coverage"] < 1.0:
        result.update({"status": "not_available", "error_code": "INCOMPLETE_COORDINATES"})
        return result

    proteins = [a for a in atoms if a["record"] == "ATOM" and (not chain_id or a["chain_id"] == chain_id)]
    ligands = [a for a in atoms if a["record"] == "HETATM" and a["residue_name"] not in _WATER and a["residue_name"] not in _AA3TO1]
    if not ligands:
        result.update({"status": "not_available", "error_code": "NO_LIGAND"})
        return result

    grouped: dict[tuple[str, str, int, str | None], list[dict[str, Any]]] = defaultdict(list)
    for atom in ligands:
        grouped[(atom["residue_name"], atom["chain_id"], atom["residue_number"], atom["insertion_code"])].append(atom)
    for (component, chain, number, insertion), instance_atoms in sorted(grouped.items()):
        instance_id = f"{component}:{chain}:{number}{insertion or ''}"
        result["ligand_instances"].append({
            "instance_id": instance_id, "component_id": component, "chain_id": chain,
            "residue_number": number, "insertion_code": insertion,
            "atom_count": len(instance_atoms), "heavy_atom_count": sum(a["element"] not in {"H", "D"} for a in instance_atoms),
        })
        seen: dict[tuple[str, int, str | None], dict[str, Any]] = {}
        for ligand_atom in instance_atoms:
            if ligand_atom["element"] in {"H", "D"}:
                continue
            for protein_atom in proteins:
                distance = _distance(ligand_atom["coord"], protein_atom["coord"])
                if distance > contact_distance_angstrom:
                    continue
                key = (protein_atom["chain_id"], protein_atom["residue_number"], protein_atom["insertion_code"])
                contact_type = "close_contact" if distance <= 3.5 else "van_der_waals_contact"
                row = {
                    "instance_id": instance_id, "component_id": component,
                    "ligand_chain_id": chain, "ligand_residue_number": number,
                    "chain_id": protein_atom["chain_id"], "residue_number": protein_atom["residue_number"],
                    "insertion_code": protein_atom["insertion_code"], "residue_name": protein_atom["residue_name"],
                    "distance_angstrom": round(distance, 3), "contact_type": contact_type,
                    "ligand_atom": ligand_atom["atom_name"], "protein_atom": protein_atom["atom_name"],
                }
                if key not in seen or distance < seen[key]["distance_angstrom"]:
                    seen[key] = row
        result["contacts"].extend(sorted(seen.values(), key=lambda row: (row["chain_id"], row["residue_number"], row["distance_angstrom"])))
    result["contact_residues"] = result["contacts"]
    result["calculation_time_ms"] = round((perf_counter() - start) * 1000, 3)
    return result


ToolRegistry.register(
    name="ligand_contact_analysis",
    description="Compute coordinate-only ligand instance and protein residue contacts from a PDB.",
    parameters={"type": "object", "properties": {
        "pdb_data": {"type": "string"}, "pdb_object_name": {"type": "string"},
        "chain_id": {"type": "string"},
        "contact_distance_angstrom": {"type": "number", "minimum": 1.0, "default": CONTACT_DISTANCE},
    }},
    handler=ligand_contact_analysis, is_async=True, category="structure", timeout_seconds=30,
)
