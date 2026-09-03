"""Residue-level structure/function feature table.

This tool is intentionally deterministic and evidence-bounded. It extracts
auditable CA-coordinate features from a PDB file and projects optional
PDB/UniProt mappings without inferring enzyme identity or wet-lab effects.
"""

from __future__ import annotations

from io import StringIO
from math import atan2, degrees, sqrt
from typing import Any

from Bio.PDB import PDBParser
from Bio.PDB.SASA import ShrakeRupley

from app.services import storage
from app.services.pdb_parser import _AA3TO1
from app.tools.registry import ToolRegistry


# Tien et al. maximal solvent-accessible areas (A^2), used only to normalize
# the input-PDB residue SASA into a comparable relative exposure value.
_MAX_RESIDUE_ASA: dict[str, float] = {
    "A": 121.0, "R": 265.0, "N": 187.0, "D": 187.0, "C": 148.0,
    "Q": 214.0, "E": 214.0, "G": 97.0, "H": 216.0, "I": 195.0,
    "L": 191.0, "K": 230.0, "M": 203.0, "F": 228.0, "P": 154.0,
    "S": 143.0, "T": 163.0, "W": 264.0, "Y": 255.0, "V": 165.0,
}
_WATER_RESIDUE_NAMES = {"HOH", "WAT", "DOD"}


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _vector_sub(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vector_dot(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vector_cross(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vector_norm(a: tuple[float, float, float]) -> float:
    return sqrt(_vector_dot(a, a))


def _dihedral_degrees(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
    d: tuple[float, float, float],
) -> float | None:
    """Return a four-point torsion angle in degrees, or None for degenerate geometry."""
    b1 = _vector_sub(b, a)
    b2 = _vector_sub(c, b)
    b3 = _vector_sub(d, c)
    b2_norm = _vector_norm(b2)
    if not b2_norm:
        return None
    b2_unit = (b2[0] / b2_norm, b2[1] / b2_norm, b2[2] / b2_norm)
    v = _vector_sub(b1, tuple(_vector_dot(b1, b2_unit) * x for x in b2_unit))
    w = _vector_sub(b3, tuple(_vector_dot(b3, b2_unit) * x for x in b2_unit))
    v_norm = _vector_norm(v)
    w_norm = _vector_norm(w)
    if not v_norm or not w_norm:
        return None
    x_value = _vector_dot(v, w)
    y_value = _vector_dot(_vector_cross(b2_unit, v), w)
    return round(degrees(atan2(y_value, x_value)), 2)


def _first_model_lines(pdb_data: str) -> list[str]:
    """Return the header plus only the first coordinate model when MODEL records exist."""
    lines: list[str] = []
    first_model_started = False
    for line in pdb_data.splitlines():
        record = line[:6].strip().upper()
        if record == "MODEL":
            if first_model_started:
                break
            first_model_started = True
            continue
        if record == "ENDMDL" and first_model_started:
            break
        lines.append(line)
    return lines


def _parse_pdb_residue_atoms(pdb_data: str, chain_id: str = "") -> list[dict[str, Any]]:
    residues: dict[tuple[str, int, str], dict[str, Any]] = {}
    chain_filter = chain_id.strip() or None

    for line in _first_model_lines(pdb_data):
        record = line[:6].strip()
        if record != "ATOM":
            continue
        if len(line) < 54:
            continue
        alt_loc = line[16].strip()
        if alt_loc not in {"", "A"}:
            continue
        res_name = line[17:20].strip().upper()
        residue_aa = _AA3TO1.get(res_name)
        if not residue_aa:
            continue
        chain = line[21].strip() or "_"
        if chain_filter and chain != chain_filter:
            continue
        pdb_residue_no = _safe_int(line[22:26].strip())
        if pdb_residue_no is None:
            continue
        insertion_code = line[26].strip()
        atom_name = line[12:16].strip().upper()
        element = (line[76:78].strip().upper() if len(line) >= 78 else "") or atom_name[:1]
        x = _safe_float(line[30:38].strip())
        y = _safe_float(line[38:46].strip())
        z = _safe_float(line[46:54].strip())
        if x is None or y is None or z is None:
            continue
        b_factor = _safe_float(line[60:66].strip()) if len(line) >= 66 else None

        key = (chain, pdb_residue_no, insertion_code)
        residue = residues.setdefault(
            key,
            {
                "chain_id": chain,
                "pdb_residue_no": pdb_residue_no,
                "insertion_code": insertion_code or None,
                "residue_name": res_name,
                "wild_type": residue_aa,
                "atoms": [],
                "ca_coord": None,
                "ca_b_factor": None,
            },
        )
        residue["atoms"].append({
            "atom_name": atom_name,
            "element": element,
            "coord": (x, y, z),
            "b_factor": b_factor,
        })
        if atom_name == "CA":
            residue["ca_coord"] = (x, y, z)
            residue["ca_b_factor"] = b_factor

    return [
        residues[key]
        for key in sorted(residues, key=lambda item: (item[0], item[1], item[2]))
    ]


def _parse_nonpolymer_heteroatoms(pdb_data: str) -> list[dict[str, Any]]:
    """Return non-water, non-polymer HETATM heavy atoms from the input PDB."""
    atoms: list[dict[str, Any]] = []
    for line in _first_model_lines(pdb_data):
        if line[:6].strip().upper() != "HETATM" or len(line) < 54:
            continue
        alt_loc = line[16].strip()
        if alt_loc not in {"", "A"}:
            continue
        component_id = line[17:20].strip().upper()
        if not component_id or component_id in _WATER_RESIDUE_NAMES or component_id in _AA3TO1:
            continue
        x = _safe_float(line[30:38].strip())
        y = _safe_float(line[38:46].strip())
        z = _safe_float(line[46:54].strip())
        if x is None or y is None or z is None:
            continue
        atom_name = line[12:16].strip().upper()
        element = (line[76:78].strip().upper() if len(line) >= 78 else "") or atom_name[:1]
        if element in {"H", "D"}:
            continue
        chain_id = line[21].strip() or "_"
        residue_no = _safe_int(line[22:26].strip())
        insertion_code = line[26].strip()
        position = (
            f"{chain_id}:{residue_no}{insertion_code}"
            if residue_no is not None
            else chain_id
        )
        atoms.append({
            "component_id": component_id,
            "component_position": position,
            "atom_name": atom_name,
            "element": element,
            "coord": (x, y, z),
        })
    return atoms


def _parse_pdb_secondary_ranges(pdb_data: str) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for line in _first_model_lines(pdb_data):
        record = line[:6].strip()
        if record == "HELIX":
            start_chain = line[19].strip() or "_"
            start = _safe_int(line[21:25].strip())
            end_chain = line[31].strip() or "_"
            end = _safe_int(line[33:37].strip())
            kind = "helix"
        elif record == "SHEET":
            start_chain = line[21].strip() or "_"
            start = _safe_int(line[22:26].strip())
            end_chain = line[32].strip() or "_"
            end = _safe_int(line[33:37].strip())
            kind = "sheet"
        else:
            continue
        if start is None or end is None or start_chain != end_chain:
            continue
        if end < start:
            start, end = end, start
        ranges.append({
            "chain_id": start_chain,
            "start": start,
            "end": end,
            "secondary_structure": kind,
            "source": "pdb_helix_sheet_records",
        })
    return ranges


def _compute_rel_sasa(
    pdb_data: str,
    chain_id: str = "",
) -> tuple[dict[tuple[str, int, str], dict[str, Any]], str, str | None]:
    """Compute residue SASA from the supplied PDB, with explicit provenance."""
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("site_features", StringIO(pdb_data))
        ShrakeRupley().compute(structure, level="R")
    except Exception as exc:
        return {}, "failed", f"{type(exc).__name__}: {exc}"

    chain_filter = chain_id.strip() or None
    values: dict[tuple[str, int, str], dict[str, Any]] = {}
    first_model = next(structure.get_models(), None)
    if first_model is None:
        return {}, "failed", "PDB contains no model"

    for chain in first_model:
        if chain_filter and chain.id.strip() != chain_filter:
            continue
        for residue in chain:
            hetfield, residue_no, insertion_code = residue.id
            residue_aa = _AA3TO1.get(str(residue.resname).strip().upper())
            if not residue_aa or hetfield not in {" ", "H_MSE"}:
                continue
            max_asa = _MAX_RESIDUE_ASA.get(residue_aa)
            residue_sasa = getattr(residue, "sasa", None)
            if max_asa is None or not isinstance(residue_sasa, (int, float)):
                continue
            key = (chain.id.strip() or "_", int(residue_no), str(insertion_code or "").strip())
            values[key] = {
                "residue_sasa_angstrom2": round(float(residue_sasa), 2),
                "rel_sasa": round(min(1.5, max(0.0, float(residue_sasa) / max_asa)), 4),
                "rel_sasa_status": "computed_from_input_pdb",
                "rel_sasa_source": "biopython_shrake_rupley_tien_max_asa",
            }

    return (
        values,
        "computed" if values else "failed",
        None if values else "no standard protein residues with SASA",
    )


def _secondary_structure_for_residue(
    chain_id: str,
    pdb_residue_no: int,
    ranges: list[dict[str, Any]],
) -> tuple[str, str]:
    for item in ranges:
        if (
            item.get("chain_id") == chain_id
            and int(item.get("start", -1)) <= pdb_residue_no <= int(item.get("end", -1))
        ):
            return str(item["secondary_structure"]), str(item["source"])
    return (
        "unannotated_or_loop"
        if ranges
        else "unknown",
        "pdb_helix_sheet_records"
        if ranges
        else "not_available",
    )


def _mapping_index(
    residue_mappings: list[dict[str, Any]] | None,
) -> dict[tuple[str, int, str], list[dict[str, Any]]]:
    index: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in residue_mappings or []:
        if not isinstance(row, dict):
            continue
        pdb_residue_no = _safe_int(
            row.get("pdb_residue_no")
            or row.get("pdb_residue_number")
            or row.get("target_position")
        )
        if pdb_residue_no is None:
            continue
        chain = str(
            row.get("chain_id")
            or row.get("chain")
            or row.get("target_chain_id")
            or "_"
        ).strip() or "_"
        insertion_code = str(
            row.get("insertion_code")
            or row.get("icode")
            or row.get("target_insertion_code")
            or ""
        ).strip()
        source_scheme = str(row.get("source_scheme") or "").strip().lower()
        source_position = _safe_int(row.get("source_position"))
        user_position = _safe_int(
            row.get("user_position")
            or row.get("user_sequence_position")
            or row.get("user_sequence_residue_no")
        )
        uniprot_position = _safe_int(
            row.get("uniprot_position")
            or row.get("uniprot_residue_no")
            or row.get("uniprot_residue_number")
        )
        if source_scheme == "user_sequence" and source_position is not None:
            user_position = source_position
        elif source_scheme == "uniprot" and source_position is not None:
            uniprot_position = source_position
        elif user_position is None and uniprot_position is not None:
            # Legacy rows historically treated the UniProt coordinate as the
            # user coordinate. Keep that compatibility only in the normalized
            # record; projection still depends on verified one-to-one status.
            user_position = uniprot_position

        confidence = str(
            row.get("mapping_confidence")
            or row.get("confidence")
            or "unknown"
        ).strip().lower()
        if confidence in {"curated_sifts", "local_sifts", "sifts", "curated", "exact", "high"}:
            mapping_status = "verified"
        elif confidence in {
            "inferred_from_coordinate_order",
            "coordinate_order_inference",
            "inferred",
        }:
            mapping_status = "inferred_requires_confirmation"
        else:
            mapping_status = "unmapped"

        normalized = {
            "chain_id": chain,
            "pdb_residue_no": pdb_residue_no,
            "insertion_code": insertion_code or None,
            "user_position": user_position,
            "uniprot_position": uniprot_position,
            "uniprot_id": str(
                row.get("uniprot_id")
                or row.get("uniprot")
                or row.get("accession")
                or ""
            ).strip() or None,
            "mapping_confidence": confidence,
            "mapping_status": mapping_status,
            "raw": row,
        }
        index.setdefault((chain, pdb_residue_no, insertion_code), []).append(normalized)
    return index


def _mapping_contract_index(
    residue_mappings: list[dict[str, Any]] | None,
) -> dict[tuple[str, int, str], dict[str, Any]]:
    """Build namespace-aware mapping status without projecting inferred rows."""
    by_target = _mapping_index(residue_mappings)
    user_targets: dict[int, set[tuple[str, int, str]]] = {}
    uniprot_targets: dict[int, set[tuple[str, int, str]]] = {}
    for target, rows in by_target.items():
        for row in rows:
            if row["mapping_status"] != "verified":
                continue
            if row["user_position"] is not None:
                user_targets.setdefault(row["user_position"], set()).add(target)
            if row["uniprot_position"] is not None:
                uniprot_targets.setdefault(row["uniprot_position"], set()).add(target)

    output: dict[tuple[str, int, str], dict[str, Any]] = {}
    for target, rows in by_target.items():
        def _coordinate_contract(namespace: str) -> dict[str, Any]:
            position_key = f"{namespace}_position"
            positions = {
                row[position_key]
                for row in rows
                if row[position_key] is not None
            }
            verified_positions = {
                row[position_key]
                for row in rows
                if row["mapping_status"] == "verified" and row[position_key] is not None
            }
            inferred_positions = {
                row[position_key]
                for row in rows
                if row["mapping_status"] == "inferred_requires_confirmation"
                and row[position_key] is not None
            }
            target_index = user_targets if namespace == "user" else uniprot_targets
            source_is_non_unique = any(
                len(target_index.get(position, set())) != 1
                for position in verified_positions
            )
            if len(verified_positions) == 1 and not source_is_non_unique:
                status = "verified"
                position = next(iter(verified_positions))
            elif len(verified_positions) > 1 or source_is_non_unique:
                status = "conflicted"
                position = None
            elif inferred_positions:
                status = "inferred_requires_confirmation"
                position = next(iter(inferred_positions)) if len(inferred_positions) == 1 else None
            else:
                status = "unmapped"
                position = next(iter(positions)) if len(positions) == 1 else None
            return {
                "position": position,
                "status": status,
            }

        user = _coordinate_contract("user")
        uniprot = _coordinate_contract("uniprot")
        accessions = {
            row["uniprot_id"]
            for row in rows
            if row.get("uniprot_id")
        }
        has_inferred = any(
            row["mapping_status"] == "inferred_requires_confirmation"
            for row in rows
        )
        if user["status"] == "verified" and uniprot["status"] == "verified":
            projection_reason = "verified_one_to_one_mapping"
        elif user["status"] == "verified":
            projection_reason = "user_sequence_verified_uniprot_unavailable"
        elif uniprot["status"] == "verified":
            projection_reason = "uniprot_verified_user_sequence_unavailable"
        elif user["status"] == "conflicted" or uniprot["status"] == "conflicted":
            projection_reason = "mapping_conflict_blocks_projection"
        elif has_inferred:
            projection_reason = "inferred_mapping_requires_confirmation"
        else:
            projection_reason = "no_verified_mapping"
        output[target] = {
            "rows": rows,
            "user_sequence": user,
            "uniprot": {
                **uniprot,
                "accession": next(iter(accessions)) if len(accessions) == 1 else None,
            },
            "projection_eligibility": {
                "user_sequence": user["status"] == "verified",
                "uniprot": uniprot["status"] == "verified",
                "reason": projection_reason,
            },
        }
    return output


def _position_tokens(feature: dict[str, Any]) -> set[int]:
    # PDB author coordinates are always local geometry coordinates. User and
    # UniProt coordinates enter this set only after a verified projection.
    tokens = {_safe_int(feature.get("pdb_residue_no"))}
    for key in ("user_sequence_coordinate", "uniprot_coordinate"):
        coordinate = feature.get(key)
        if isinstance(coordinate, dict) and coordinate.get("status") == "verified":
            tokens.add(_safe_int(coordinate.get("position")))
    return {item for item in tokens if item is not None}


def _round_coord(coord: tuple[float, float, float] | None) -> dict[str, float] | None:
    if coord is None:
        return None
    return {"x": round(coord[0], 3), "y": round(coord[1], 3), "z": round(coord[2], 3)}


def _ca_contact_environment(contact_count: int) -> str:
    if contact_count >= 8:
        return "packed_ca_neighborhood"
    if contact_count >= 4:
        return "moderate_ca_neighborhood"
    return "sparse_ca_neighborhood"


def _build_ca_distance_graph(
    features: list[dict[str, Any]],
    radius: float,
) -> dict[str, Any]:
    """Build a bounded CA-CA edge list for returned residue rows."""
    ca_nodes = [
        (
            feature,
            (feature["ca_coord"]["x"], feature["ca_coord"]["y"], feature["ca_coord"]["z"]),
        )
        for feature in features
        if isinstance(feature.get("ca_coord"), dict)
    ]
    edges: list[dict[str, Any]] = []
    nearest_by_feature: dict[int, tuple[float, dict[str, Any]]] = {}
    for index, (source, source_coord) in enumerate(ca_nodes):
        for target, target_coord in ca_nodes[index + 1:]:
            distance = _distance(source_coord, target_coord)
            source_key = id(source)
            target_key = id(target)
            if source_key not in nearest_by_feature or distance < nearest_by_feature[source_key][0]:
                nearest_by_feature[source_key] = (distance, target)
            if target_key not in nearest_by_feature or distance < nearest_by_feature[target_key][0]:
                nearest_by_feature[target_key] = (distance, source)
            if distance <= radius:
                edges.append({
                    "source_position": source.get("position"),
                    "target_position": target.get("position"),
                    "source_pdb_position": source.get("pdb_position"),
                    "target_pdb_position": target.get("pdb_position"),
                    "distance_ca_angstrom": round(distance, 2),
                    "coordinate_basis": "ca_atom",
                    "edge_type": "ca_distance_within_radius",
                })

    for feature in features:
        nearest = nearest_by_feature.get(id(feature))
        if nearest:
            distance, neighbor = nearest
            feature["nearest_ca_neighbor_distance_angstrom"] = round(distance, 2)
            feature["nearest_ca_neighbor_position"] = neighbor.get("position")
            feature["nearest_ca_neighbor_pdb_position"] = neighbor.get("pdb_position")
        else:
            feature["nearest_ca_neighbor_distance_angstrom"] = None
            feature["nearest_ca_neighbor_position"] = None
            feature["nearest_ca_neighbor_pdb_position"] = None

    return {
        "schema_version": "residue_distance_graph_v1",
        "status": "ready" if len(ca_nodes) >= 2 else "blocked_insufficient_ca_nodes",
        "scope": "returned_feature_rows",
        "coordinate_basis": "ca_atom",
        "radius_angstrom": round(radius, 2),
        "node_count": len(ca_nodes),
        "edge_count": len(edges),
        "edges": edges,
        "boundary": (
            "CA distance edges are geometric adjacency evidence only. They are not a "
            "pocket, channel, interface, binding, or functional mechanism assignment."
        ),
    }


def _atom_coord_by_name(residue: dict[str, Any], atom_name: str) -> tuple[float, float, float] | None:
    for atom in residue.get("atoms", []):
        if atom.get("atom_name") == atom_name and isinstance(atom.get("coord"), tuple):
            return atom["coord"]
    return None


def _backbone_torsions(
    residues: list[dict[str, Any]],
) -> dict[tuple[str, int, str], dict[str, Any]]:
    """Compute conservative phi/psi values only across continuous peptide bonds."""
    by_chain: dict[str, list[dict[str, Any]]] = {}
    for residue in residues:
        by_chain.setdefault(str(residue["chain_id"]), []).append(residue)
    output: dict[tuple[str, int, str], dict[str, Any]] = {}
    peptide_bond_max = 2.0

    for chain_id, chain_residues in by_chain.items():
        for index, residue in enumerate(chain_residues):
            key = (chain_id, residue["pdb_residue_no"], residue.get("insertion_code") or "")
            reasons: list[str] = []
            phi: float | None = None
            psi: float | None = None

            previous = chain_residues[index - 1] if index > 0 else None
            next_residue = chain_residues[index + 1] if index + 1 < len(chain_residues) else None
            n_coord = _atom_coord_by_name(residue, "N")
            ca_coord = _atom_coord_by_name(residue, "CA")
            c_coord = _atom_coord_by_name(residue, "C")

            if previous is None:
                reasons.append("terminal_or_missing_previous_residue")
            else:
                previous_c = _atom_coord_by_name(previous, "C")
                if previous_c is None or n_coord is None or ca_coord is None:
                    reasons.append("missing_backbone_atom_for_phi")
                elif _distance(previous_c, n_coord) > peptide_bond_max:
                    reasons.append("peptide_chain_break_before_residue")
                else:
                    phi = _dihedral_degrees(previous_c, n_coord, ca_coord, c_coord) if c_coord else None
                    if phi is None:
                        reasons.append("degenerate_backbone_geometry_for_phi")

            if next_residue is None:
                reasons.append("terminal_or_missing_next_residue")
            else:
                next_n = _atom_coord_by_name(next_residue, "N")
                if c_coord is None or next_n is None or ca_coord is None or n_coord is None:
                    reasons.append("missing_backbone_atom_for_psi")
                elif _distance(c_coord, next_n) > peptide_bond_max:
                    reasons.append("peptide_chain_break_after_residue")
                else:
                    psi = _dihedral_degrees(n_coord, ca_coord, c_coord, next_n)
                    if psi is None:
                        reasons.append("degenerate_backbone_geometry_for_psi")

            if phi is not None and psi is not None:
                status = "computed"
            elif phi is not None or psi is not None:
                status = "partial"
            else:
                status = "not_computed"
            output[key] = {
                "phi_deg": phi,
                "psi_deg": psi,
                "backbone_torsion_status": status,
                "backbone_torsion_reason": ";".join(dict.fromkeys(reasons)) or None,
                "backbone_torsion_source": "input_pdb_backbone_atoms_first_model",
            }
    return output


def _heavy_atom_coords(residue: dict[str, Any]) -> list[tuple[float, float, float]]:
    return [
        atom["coord"]
        for atom in residue.get("atoms", [])
        if atom.get("element") not in {"H", "D"} and isinstance(atom.get("coord"), tuple)
    ]


def _with_report_contract(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("schema_version", "site_structure_function_features_v1")
    payload.setdefault("capability_status", "structure_feature_table")
    payload.setdefault("evidence_level", "STRUCTURE_GEOMETRY_FEATURES")
    payload.setdefault(
        "report_boundary",
        (
            "位点特征表只来自 PDB 坐标、PDB HELIX/SHEET 记录、输入结构 SASA 和可选编号映射；"
            "CA 距离、B-factor、接触数、relSASA、文件内二级结构注释和非聚合 HETATM 原子近邻"
            "可用于人工复核；HETATM 近邻不等于已确认底物、辅因子、金属功能位点或口袋。"
            "pocket/channel/interface 当前仍为 not_computed，不能写成已确认通路或结合界面。"
            "这些字段不能单独证明酶身份、突变收益或湿实验结论。"
        ),
    )
    payload.setdefault("feature_table_contract", _build_feature_table_contract(payload))
    return payload


def _build_feature_table_contract(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    feature_count = _safe_int(payload.get("feature_count"))
    status = str(payload.get("status") or "blocked").strip().lower()
    computed = status == "completed" and (feature_count or 0) > 0
    rel_sasa_status = str(summary.get("rel_sasa_status") or "not_computed").strip().lower()
    backbone_status = str(summary.get("backbone_torsion_status") or "not_computed").strip().lower()
    secondary_source = str(summary.get("secondary_structure_source") or "not_available").strip().lower()
    return {
        "schema_version": "site_structure_function_features_contract_v1",
        "status": "ready" if computed else "blocked",
        "feature_table_status": status,
        "feature_count": feature_count or 0,
        "capability_status": payload.get("capability_status") or "structure_feature_table",
        "field_state": {
            "ca_geometry": "ready" if computed else "blocked",
            "mapping_projection": (
                "ready"
                if (summary.get("verified_projection_count") or 0) > 0
                else "partial"
                if computed
                else "blocked"
            ),
            "secondary_structure": "ready" if secondary_source == "pdb_helix_sheet_records" else "partial" if computed else "blocked",
            "rel_sasa": (
                "ready"
                if rel_sasa_status == "computed"
                else "partial"
                if rel_sasa_status == "failed"
                else "not_computed"
            ),
            "nonpolymer_proximity": (
                "ready"
                if str(summary.get("nonpolymer_proximity_status") or "").strip().lower() == "computed_from_input_pdb"
                else "not_available"
            ),
            "backbone_torsion": backbone_status,
            "residue_distance_graph": (
                "ready"
                if str(summary.get("distance_graph_status") or "").strip().lower() == "ready"
                else "blocked"
                if computed
                else "not_computed"
            ),
            "pocket_channel_interface": "not_computed",
        },
        "unknown_fields": [
            "pocket_channel_interface_status",
            "ligand_role",
            "substrate_channel",
        ],
        "must_not_claim": [
            "pocket_channel_interface_assignment",
            "ligand_identity_or_function",
            "enzyme_identity_or_ec_assignment",
            "wet_lab_validation",
        ],
        "blocked_reasons": (
            ["no_structure_features_computed"]
            if not computed
            else ["pocket_channel_interface_not_computed"]
        ),
        "required_inputs": [
            "input_pdb_coordinates",
            "optional residue mappings",
        ],
        "report_boundary": (
            "This contract only covers residue-level geometry, mapping, and local structural evidence. "
            "Pocket/channel/interface remain not computed and must not be promoted into functional claims."
        ),
    }


async def build_site_structure_function_features(
    pdb_data: str = "",
    pdb_object_name: str = "",
    chain_id: str = "",
    residue_mappings: list[dict[str, Any]] | None = None,
    catalytic_positions: list[int] | None = None,
    protected_positions: list[int] | None = None,
    target_positions: list[int] | None = None,
    contact_radius_angstrom: float = 8.0,
) -> dict[str, Any]:
    """Build residue-level CA geometry and mapping features for review tables."""

    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")

    if not pdb_data.strip():
        return _with_report_contract({
            "found": False,
            "status": "failed",
            "error_code": "MISSING_PDB",
            "error": "Provide pdb_data or pdb_object_name.",
            "features": [],
        })

    residues = _parse_pdb_residue_atoms(pdb_data, chain_id=chain_id)
    if not residues:
        return _with_report_contract({
            "found": False,
            "status": "failed",
            "error_code": "NO_PROTEIN_RESIDUES",
            "error": "No protein ATOM residues were found for the requested chain.",
            "features": [],
        })

    mapping_by_pdb = _mapping_contract_index(residue_mappings)
    secondary_ranges = _parse_pdb_secondary_ranges(pdb_data)
    sasa_by_pdb, sasa_status, sasa_error = _compute_rel_sasa(pdb_data, chain_id=chain_id)
    nonpolymer_heteroatoms = _parse_nonpolymer_heteroatoms(pdb_data)
    catalytic_set = {int(pos) for pos in catalytic_positions or [] if _safe_int(pos) is not None}
    protected_set = {int(pos) for pos in protected_positions or [] if _safe_int(pos) is not None} | catalytic_set
    target_set = {int(pos) for pos in target_positions or [] if _safe_int(pos) is not None}
    radius = max(1.0, float(contact_radius_angstrom or 8.0))

    features: list[dict[str, Any]] = []
    for residue in residues:
        mapping_contract = mapping_by_pdb.get((
            residue["chain_id"],
            residue["pdb_residue_no"],
            residue.get("insertion_code") or "",
        ))
        user_coordinate = (
            mapping_contract["user_sequence"]
            if isinstance(mapping_contract, dict)
            else {"position": None, "status": "unmapped"}
        )
        uniprot_coordinate = (
            mapping_contract["uniprot"]
            if isinstance(mapping_contract, dict)
            else {"position": None, "status": "unmapped", "accession": None}
        )
        projection_eligibility = (
            mapping_contract["projection_eligibility"]
            if isinstance(mapping_contract, dict)
            else {
                "user_sequence": False,
                "uniprot": False,
                "reason": "no_verified_mapping",
            }
        )
        rows = mapping_contract.get("rows", []) if isinstance(mapping_contract, dict) else []
        first_mapping = rows[0] if rows else None
        uniprot_position = _safe_int(uniprot_coordinate.get("position"))
        user_position = _safe_int(user_coordinate.get("position"))
        if uniprot_position is not None:
            position = uniprot_position
            position_source = (
                "uniprot_mapping"
                if uniprot_coordinate.get("status") == "verified"
                else "inferred_uniprot_mapping"
            )
        elif user_position is not None:
            position = user_position
            position_source = (
                "user_sequence_mapping"
                if user_coordinate.get("status") == "verified"
                else "inferred_user_sequence_mapping"
            )
        else:
            position = residue["pdb_residue_no"]
            position_source = "pdb_residue_number"
        mapping_confidence = (
            str(first_mapping.get("mapping_confidence") or "provided_mapping")
            if isinstance(first_mapping, dict)
            else "unmapped_pdb_coordinate"
        )
        secondary_structure, secondary_structure_source = _secondary_structure_for_residue(
            residue["chain_id"],
            residue["pdb_residue_no"],
            secondary_ranges,
        )
        feature = {
            "position": position,
            "position_source": position_source,
            "wild_type": residue["wild_type"],
            "chain_id": residue["chain_id"],
            "pdb_position": f"{residue['chain_id']}:{residue['pdb_residue_no']}{residue.get('insertion_code') or ''}",
            "pdb_residue_no": residue["pdb_residue_no"],
            "insertion_code": residue.get("insertion_code"),
            "uniprot_position": uniprot_position,
            "pdb_author_coordinate": {
                "chain_id": residue["chain_id"],
                "residue_no": residue["pdb_residue_no"],
                "insertion_code": residue.get("insertion_code"),
            },
            "user_sequence_coordinate": {
                "position": user_coordinate.get("position"),
                "status": user_coordinate.get("status", "unmapped"),
            },
            "uniprot_coordinate": {
                "accession": uniprot_coordinate.get("accession"),
                "position": uniprot_coordinate.get("position"),
                "status": uniprot_coordinate.get("status", "unmapped"),
            },
            "projection_eligibility": projection_eligibility,
            "has_ca": residue.get("ca_coord") is not None,
            "ca_coord": _round_coord(residue.get("ca_coord")),
            "b_factor": round(residue["ca_b_factor"], 2) if residue.get("ca_b_factor") is not None else None,
            "atom_count": len(residue.get("atoms") or []),
            "secondary_structure": secondary_structure,
            "secondary_structure_source": secondary_structure_source,
            "rel_sasa": None,
            "rel_sasa_status": "not_computed",
            "rel_sasa_source": "not_available",
            "residue_sasa_angstrom2": None,
            "pocket_channel_interface_status": "not_computed",
            "phi_deg": None,
            "psi_deg": None,
            "backbone_torsion_status": "not_computed",
            "backbone_torsion_reason": "not_computed_until_backbone_features_are_built",
            "backbone_torsion_source": "not_available",
            "nonpolymer_proximity_status": (
                "computed_from_input_pdb"
                if nonpolymer_heteroatoms
                else "not_available_no_nonpolymer_heteroatoms"
            ),
            "nearest_nonpolymer_heteroatom_distance_angstrom": None,
            "nearest_nonpolymer_component_id": None,
            "nearest_nonpolymer_component_position": None,
            "nonpolymer_component_ids_within_4a": [],
            "mapping_evidence": {
                "status": "mapped" if isinstance(mapping_contract, dict) else "unmapped",
                "confidence": mapping_confidence,
                "source": "residue_mappings" if isinstance(mapping_contract, dict) else "pdb_coordinate_only",
                "mapping_status": (
                    projection_eligibility.get("reason")
                    if isinstance(projection_eligibility, dict)
                    else "no_verified_mapping"
                ),
            },
        }
        sasa = sasa_by_pdb.get((
            residue["chain_id"],
            residue["pdb_residue_no"],
            residue.get("insertion_code") or "",
        ))
        if isinstance(sasa, dict):
            feature.update(sasa)
        elif sasa_status == "failed":
            feature["rel_sasa_status"] = "failed"
            feature["rel_sasa_source"] = "biopython_shrake_rupley"
        tokens = _position_tokens(feature)
        feature["is_catalytic"] = bool(tokens & catalytic_set)
        feature["is_protected"] = bool(tokens & protected_set)
        nearest_nonpolymer: dict[str, Any] | None = None
        nearest_nonpolymer_distance: float | None = None
        nearby_components: set[str] = set()
        for residue_coord in _heavy_atom_coords(residue):
            for heteroatom in nonpolymer_heteroatoms:
                distance = _distance(residue_coord, heteroatom["coord"])
                if nearest_nonpolymer_distance is None or distance < nearest_nonpolymer_distance:
                    nearest_nonpolymer_distance = distance
                    nearest_nonpolymer = heteroatom
                if distance <= 4.0:
                    nearby_components.add(str(heteroatom["component_id"]))
        if nearest_nonpolymer is not None and nearest_nonpolymer_distance is not None:
            feature["nearest_nonpolymer_heteroatom_distance_angstrom"] = round(nearest_nonpolymer_distance, 2)
            feature["nearest_nonpolymer_component_id"] = nearest_nonpolymer["component_id"]
            feature["nearest_nonpolymer_component_position"] = nearest_nonpolymer["component_position"]
            feature["nonpolymer_component_ids_within_4a"] = sorted(nearby_components)[:8]
        features.append(feature)

    catalytic_features = [
        feature for feature in features
        if feature.get("is_catalytic") and feature.get("ca_coord")
    ]
    ca_by_feature = [
        (feature, (feature["ca_coord"]["x"], feature["ca_coord"]["y"], feature["ca_coord"]["z"]))
        for feature in features
        if feature.get("ca_coord")
    ]
    torsions_by_pdb = _backbone_torsions(residues)
    for feature in features:
        torsion = torsions_by_pdb.get((
            feature["chain_id"],
            feature["pdb_residue_no"],
            feature.get("insertion_code") or "",
        ))
        if torsion:
            feature.update(torsion)

    for feature, coord in ca_by_feature:
        nearest_distance = None
        nearest_position = None
        for catalytic in catalytic_features:
            if catalytic is feature:
                continue
            catalytic_coord = (
                catalytic["ca_coord"]["x"],
                catalytic["ca_coord"]["y"],
                catalytic["ca_coord"]["z"],
            )
            distance = _distance(coord, catalytic_coord)
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_position = catalytic.get("position")
        feature["nearest_catalytic_distance_ca_angstrom"] = (
            round(nearest_distance, 2) if nearest_distance is not None else None
        )
        feature["nearest_catalytic_position"] = nearest_position
        feature["contact_count_ca_8a"] = sum(
            1
            for other, other_coord in ca_by_feature
            if other is not feature and _distance(coord, other_coord) <= radius
        )
        feature["ca_contact_environment"] = _ca_contact_environment(feature["contact_count_ca_8a"])

    for feature in features:
        feature.setdefault("nearest_catalytic_distance_ca_angstrom", None)
        feature.setdefault("nearest_catalytic_position", None)
        feature.setdefault("contact_count_ca_8a", 0)
        feature.setdefault("ca_contact_environment", "missing_ca_coordinate")
        risk_flags: list[str] = []
        if not feature["has_ca"]:
            risk_flags.append("missing_ca_coordinate")
        if feature["is_protected"]:
            risk_flags.append("protected_or_catalytic_position")
        distance_to_cat = feature.get("nearest_catalytic_distance_ca_angstrom")
        if isinstance(distance_to_cat, (int, float)) and distance_to_cat <= 6.0:
            risk_flags.append("within_6A_of_catalytic_ca")
        if feature.get("uniprot_position") is None:
            risk_flags.append("missing_uniprot_mapping")
        if str(feature["mapping_evidence"].get("confidence")) == "inferred_from_coordinate_order":
            risk_flags.append("coordinate_order_inference_not_uniprot_evidence")
        b_factor = feature.get("b_factor")
        if isinstance(b_factor, (int, float)) and b_factor >= 60.0:
            risk_flags.append("high_ca_b_factor_review_structure_quality")
        nonpolymer_distance = feature.get("nearest_nonpolymer_heteroatom_distance_angstrom")
        if isinstance(nonpolymer_distance, (int, float)) and nonpolymer_distance <= 4.0:
            risk_flags.append("within_4A_of_nonpolymer_heteroatom_review_component_role")
        feature["risk_flags"] = risk_flags

    if target_set:
        features = [
            feature for feature in features
            if _position_tokens(feature) & target_set
        ]
    distance_graph = _build_ca_distance_graph(features, radius)

    return _with_report_contract({
        "found": True,
        "status": "completed",
        "source": "pdb_ca_geometry",
        "chain_id": chain_id.strip() or None,
        "contact_radius_angstrom": radius,
        "catalytic_positions": sorted(catalytic_set),
        "protected_positions": sorted(protected_set),
        "target_positions": sorted(target_set),
        "feature_count": len(features),
        "summary": {
            "residue_count": len(residues),
            "feature_count": len(features),
            "mapped_count": sum(1 for item in features if item["mapping_evidence"]["status"] == "mapped"),
            "verified_projection_count": sum(
                1
                for item in features
                if item["projection_eligibility"]["user_sequence"]
                or item["projection_eligibility"]["uniprot"]
            ),
            "inferred_mapping_count": sum(
                1
                for item in features
                if item["user_sequence_coordinate"]["status"] == "inferred_requires_confirmation"
                or item["uniprot_coordinate"]["status"] == "inferred_requires_confirmation"
            ),
            "ca_available_count": sum(1 for item in features if item["has_ca"]),
            "protected_count": sum(1 for item in features if item["is_protected"]),
            "secondary_structure_source": "pdb_helix_sheet_records" if secondary_ranges else "not_available",
            "rel_sasa_status": sasa_status,
            "rel_sasa_method": "ShrakeRupley residue SASA normalized by Tien maximal ASA",
            "rel_sasa_error": sasa_error,
            "pocket_channel_interface_status": "not_computed",
            "backbone_torsion_status": (
                "computed"
                if any(item.get("backbone_torsion_status") == "computed" for item in features)
                else "partial"
                if any(item.get("backbone_torsion_status") == "partial" for item in features)
                else "not_computed"
            ),
            "backbone_torsion_source": "input_pdb_backbone_atoms_first_model",
            "distance_graph_status": distance_graph["status"],
            "distance_graph_node_count": distance_graph["node_count"],
            "distance_graph_edge_count": distance_graph["edge_count"],
            "distance_graph_radius_angstrom": distance_graph["radius_angstrom"],
            "nonpolymer_proximity_status": (
                "computed_from_input_pdb"
                if nonpolymer_heteroatoms
                else "not_available_no_nonpolymer_heteroatoms"
            ),
            "nonpolymer_component_count": len({
                (item["component_id"], item["component_position"])
                for item in nonpolymer_heteroatoms
            }),
            "nonpolymer_heavy_atom_count": len(nonpolymer_heteroatoms),
            "nonpolymer_component_ids": sorted({
                str(item["component_id"])
                for item in nonpolymer_heteroatoms
            })[:20],
        },
        "residue_distance_graph": distance_graph,
        "features": features,
    })


ToolRegistry.register(
    name="build_site_structure_function_features",
    description=(
        "Build a residue-level structure/function feature table from PDB coordinates. "
        "Reports CA coordinates, CA B-factor, nearest catalytic CA distance, CA contact "
        "count within a configurable radius, local CA contact environment, optional "
        "PDB HELIX/SHEET secondary-structure annotation, protected/catalytic flags, "
        "non-water/non-polymer HETATM heavy-atom proximity, and numbering mapping "
        "backbone phi/psi torsions, and numbering mapping evidence for enzyme-engineering "
        "review. HETATM proximity does not assign a component role or identify a binding "
        "pocket; phi/psi fields do not classify Ramachandran outliers or predict function."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {"type": "string", "description": "Raw PDB text."},
            "pdb_object_name": {"type": "string", "description": "Stored PDB object name."},
            "chain_id": {"type": "string", "description": "Optional PDB chain ID filter."},
            "residue_mappings": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional residue_mapping_sifts mappings.",
            },
            "catalytic_positions": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Catalytic positions in UniProt or PDB numbering.",
            },
            "protected_positions": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Additional protected positions in UniProt or PDB numbering.",
            },
            "target_positions": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional positions to return; matches PDB, UniProt, or feature position.",
            },
            "contact_radius_angstrom": {
                "type": "number",
                "minimum": 1.0,
                "default": 8.0,
                "description": "CA contact radius in Angstrom.",
            },
        },
    },
    handler=build_site_structure_function_features,
    is_async=True,
    category="structure",
    timeout_seconds=30,
)
