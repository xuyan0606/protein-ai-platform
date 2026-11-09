"""Coordinate-only ligand contact analysis for uploaded PDB structures."""

from __future__ import annotations

from collections import defaultdict
from math import sqrt
from time import perf_counter
from typing import Any

from app.services import storage
from app.services.pdb_parser import _AA3TO1, parse_pdb
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
    from app.services.structure_records import pdb_records, cif_records, is_protein_atom
    if pdb_data.lstrip().startswith('data_'):
        import io
        from Bio.PDB.MMCIF2Dict import MMCIF2Dict
        cif = MMCIF2Dict(io.StringIO(pdb_data))
        rows, models, _ = cif_records(cif)
        raw_models = cif.get('_atom_site.pdbx_PDB_model_num', ['1'] * len(cif.get('_atom_site.id', [])))
        expected = sum(str(m) == str(models[0]) for m in raw_models)
    else:
        rows, models, _ = pdb_records(pdb_data)
        expected = sum(line[:6].strip() in {'ATOM', 'HETATM'} for line in _first_model_lines(pdb_data))
    first = [row for row in rows if row['model_id'] == models[0]]
    selected = [row for row in first if row['altloc'] in {'', 'A'} and row['occupancy'] > 0]
    skipped = len(first) - len(selected)
    atoms = [{
        'record': 'ATOM' if is_protein_atom(row, _AA3TO1) else (
            'POLYMER_OTHER' if row['record'] == 'ATOM' or row.get('label_seq_id') else 'HETATM'),
        'atom_name': row['atom_name'], 'residue_name': row['component_id'],
        'chain_id': row['chain_id'], 'residue_number': row['residue_number'],
        'insertion_code': row['insertion_code'], 'element': row.get('element') or row['atom_name'][:1],
        'coord': row['coordinates'],
    } for row in selected]
    return atoms, {
        'coordinate_records': max(0, expected - skipped), 'parsed_records': len(selected),
        'invalid_records': max(0, expected - len(first)), 'excluded_conformer_or_occupancy_records': skipped,
    }, expected


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
    profile = parse_pdb(pdb_data)
    atoms, coverage, _ = _parse_atoms(pdb_data)
    chains = sorted({a["chain_id"] for a in atoms if a["record"] == "ATOM"})
    result = _base_result(start, coverage, chains)
    result['content_sha256'] = profile['content_sha256']
    result['model_scope'] = profile['model_scope']
    result['declared_connections'] = [row for row in profile['connections'] if not chain_id or any(
        row.get(partner, {}).get('chain_id') == chain_id for partner in ('partner_1', 'partner_2'))]
    result["thresholds"]["contact_distance_angstrom"] = float(contact_distance_angstrom)
    if coverage["invalid_records"] or coverage["coverage"] < 1.0:
        result.update({"status": "not_available", "error_code": "INCOMPLETE_COORDINATES"})
        return result

    proteins = [a for a in atoms if a["record"] == "ATOM" and (not chain_id or a["chain_id"] == chain_id)]
    ligands = [a for a in atoms if a["record"] == "HETATM" and a["residue_name"] not in _WATER]
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
                for connection in result['declared_connections']:
                    if any(connection.get(k) not in {None, '', '1_555', '1555'} for k in ('symmetry_1', 'symmetry_2')):
                        continue
                    endpoints = (connection['partner_1'], connection['partner_2'])
                    def matches(endpoint, atom):
                        return (endpoint.get('chain_id'), endpoint.get('residue_number'),
                                endpoint.get('insertion_code'), endpoint.get('atom_name')) == (
                            atom['chain_id'], atom['residue_number'], atom['insertion_code'], atom['atom_name'])
                    if ((matches(endpoints[0], protein_atom) and matches(endpoints[1], ligand_atom)) or
                            (matches(endpoints[1], protein_atom) and matches(endpoints[0], ligand_atom))):
                        row['declared_connection_type'] = connection['connection_type']
                        row['declared_connection_source'] = connection['source_record']
                        if connection['connection_type'] in {'covale', 'disulf', 'metalc'}:
                            row['contact_type'] = connection['connection_type']
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
