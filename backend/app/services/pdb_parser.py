"""PDB file parser — extracts sequence, structure metadata, and quality metrics.

Pure Python, no external dependencies. Parses the standard PDB format (v3.30).
"""

from __future__ import annotations

import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


# Standard 3-letter to 1-letter amino acid mapping
_AA3TO1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    # Non-standard
    "MSE": "M", "SEC": "U", "PYL": "O", "HYP": "P",
    "ASX": "B", "GLX": "Z", "XLE": "J", "UNK": "X",
}

# PDB writes common covalently incorporated amino-acid variants as HETATM.
# Other HETATM records are ligands, ions, glycans, solvents, etc. and must not
# be counted as protein residues or converted to synthetic ``X`` chains.
_POLYMER_HETATM_RESIDUES = {"MSE", "SEC", "PYL", "HYP"}


@dataclass
class ChainInfo:
    chain_id: str
    sequence: str = ""
    residue_count: int = 0
    atom_count: int = 0
    residue_range: tuple[int, int] | None = None
    b_factors: list[float] = field(default_factory=list)


@dataclass
class PDBResult:
    header: dict[str, Any] = field(default_factory=dict)
    chains: list[ChainInfo] = field(default_factory=list)
    resolution: float | None = None
    r_factor: float | None = None
    space_group: str | None = None
    unit_cell: dict[str, float] | None = None
    b_factor_stats: dict[str, float] = field(default_factory=dict)
    total_atoms: int = 0
    total_residues: int = 0
    seqres_sequence: str = ""
    seqres_by_chain: dict[str, str] = field(default_factory=dict)
    method: str | None = None
    deposited_date: str | None = None
    nonpolymer_components: list[dict[str, Any]] = field(default_factory=list)
    compound_annotation: dict[str, str] = field(default_factory=dict)
    engineered_mutations: list[dict[str, Any]] = field(default_factory=list)


def pdb_coordinate_text(content: str) -> str:
    """Give coordinate tools PDB records while preserving author chain numbering."""
    if not content.lstrip().startswith("data_"):
        return content
    from Bio.PDB import MMCIFParser, PDBIO

    structure = MMCIFParser(QUIET=True).get_structure("uploaded", io.StringIO(content))
    writer = PDBIO()
    writer.set_structure(structure)
    pdb_stream = io.StringIO()
    writer.save(pdb_stream)
    return pdb_stream.getvalue()


def _parse_mmcif(content: str) -> dict[str, Any]:
    """Read mmCIF coordinates with Biopython, then reuse the PDB atom analysis."""
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict

    cif = MMCIF2Dict(io.StringIO(content))
    analysis = parse_pdb(pdb_coordinate_text(content))

    def value(key: str) -> str | None:
        raw = cif.get(key)
        item = raw[0] if isinstance(raw, list) and raw else raw
        text = str(item).strip() if item is not None else ""
        return text if text and text not in {"?", "."} else None

    def number(key: str) -> float | None:
        raw = value(key)
        try:
            return float(raw) if raw is not None else None
        except ValueError:
            return None

    analysis["header"]["title"] = value("_struct.title")
    analysis["header"]["classification"] = value("_struct_keywords.pdbx_keywords")
    analysis["method"] = value("_exptl.method")
    analysis["resolution"] = number("_refine.ls_d_res_high")
    analysis["r_factor"] = number("_refine.ls_R_factor_R_work")
    analysis["space_group"] = value("_symmetry.space_group_name_H-M") or value("_space_group.name_H-M_alt")
    analysis["deposited_date"] = value("_pdbx_database_status.recvd_initial_deposition_date")
    cell_keys = {axis: number(f"_cell.length_{axis}") for axis in "abc"}
    angle_keys = {axis: number(f"_cell.angle_{axis}") for axis in ("alpha", "beta", "gamma")}
    if all(item is not None for item in (*cell_keys.values(), *angle_keys.values())):
        analysis["unit_cell"] = {**cell_keys, **angle_keys}
    return analysis


def parse_pdb(content: str) -> dict[str, Any]:
    """Parse PDB file content into structured analysis data.

    Args:
        content: Raw PDB file text.

    Returns:
        Dict with chains, sequences, quality metrics, and structure metadata.
    """
    if content.lstrip().startswith("data_"):
        return _parse_mmcif(content)

    result = PDBResult()
    lines = content.splitlines()

    chains: dict[str, ChainInfo] = {}
    seqres_chains: dict[str, str] = defaultdict(str)
    seen_residues: set[tuple[str, int, str]] = set()  # (chain, resnum, resname)
    nonpolymer_components: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    all_b_factors: list[float] = []
    current_model: int | None = None
    compound_fragments: list[str] = []
    title_fragments: list[str] = []

    for line in lines:
        record = line[:6].strip()

        if record == "HEADER":
            result.header["classification"] = line[10:50].strip() or None
            result.deposited_date = line[50:59].strip() or None

        elif record == "EXPDTA":
            result.method = _parse_method(line[10:].strip())

        elif record == "COMPND":
            compound_fragments.append(line[10:].strip())

        elif record == "SEQADV" and "ENGINEERED MUTATION" in line[49:].upper():
            try:
                result.engineered_mutations.append({
                    "chain_id": line[16].strip() or "_",
                    "pdb_residue_no": int(line[18:22]),
                    "pdb_residue_aa": line[12:15].strip(),
                    "reference_residue_aa": line[39:42].strip(),
                    "reference_position": int(line[43:48]),
                })
            except (IndexError, ValueError):
                pass

        elif record == "TITLE":
            title_fragments.append(line[10:].strip())

        elif record == "REMARK":
            _parse_remark(line, result)

        elif record == "CRYST1":
            result.space_group = line[55:66].strip() or None
            try:
                result.unit_cell = {
                    "a": float(line[6:15]),
                    "b": float(line[15:24]),
                    "c": float(line[24:33]),
                    "alpha": float(line[33:40]),
                    "beta": float(line[40:47]),
                    "gamma": float(line[47:54]),
                }
            except ValueError:
                pass

        elif record == "SEQRES":
            chain_id = line[11]
            if chain_id not in seqres_chains:
                seqres_chains[chain_id] = ""
            res_names = line[19:].split()
            for rn in res_names:
                normalized = rn.upper()
                if normalized in _AA3TO1:
                    seqres_chains[chain_id] += _AA3TO1[normalized]

        elif record == "MODEL":
            try:
                current_model = int(line[10:14])
            except ValueError:
                current_model = None
            # Only parse first model for NMR
            if current_model is not None and current_model > 1:
                continue

        elif record == "ENDMDL":
            current_model = None

        elif record in ("ATOM", "HETATM"):
            if current_model is not None and current_model > 1:
                continue

            try:
                atom_serial = int(line[6:11])
                atom_name = line[12:16].strip()
                alt_loc = line[16]
                res_name = line[17:20].strip()
                chain_id = line[21]
                res_seq = int(line[22:26])
                i_code = line[26]
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                occupancy = float(line[54:60]) if line[54:60].strip() else 1.0
                b_factor = float(line[60:66]) if line[60:66].strip() else 0.0
                element = line[76:78].strip() or atom_name[0]
            except (ValueError, IndexError):
                continue

            # Skip alternate conformations
            if alt_loc not in (" ", "A"):
                continue

            # Skip water
            if res_name == "HOH":
                continue

            result.total_atoms += 1

            is_polymer_residue = record == "ATOM" or res_name.upper() in _POLYMER_HETATM_RESIDUES
            if not is_polymer_residue:
                component_key = (chain_id, res_seq, i_code, res_name.upper())
                component = nonpolymer_components.setdefault(
                    component_key,
                    {
                        "component_id": res_name.upper(),
                        "chain_id": chain_id or "_",
                        "residue_number": res_seq,
                        "insertion_code": i_code.strip() or None,
                        "atom_count": 0,
                    },
                )
                component["atom_count"] += 1
                continue

            if chain_id not in chains:
                chains[chain_id] = ChainInfo(chain_id=chain_id)

            chain = chains[chain_id]
            chain.atom_count += 1
            chain.b_factors.append(b_factor)
            all_b_factors.append(b_factor)
            # Track unique residues
            res_key = (chain_id, res_seq, res_name)
            if res_key not in seen_residues:
                seen_residues.add(res_key)
                chain.residue_count += 1
                result.total_residues += 1
                aa = _AA3TO1.get(res_name.upper(), "X")
                chain.sequence += aa

                if chain.residue_range is None:
                    chain.residue_range = (res_seq, res_seq)
                else:
                    lo, hi = chain.residue_range
                    chain.residue_range = (min(lo, res_seq), max(hi, res_seq))

    # Build chain list sorted by chain ID
    result.chains = sorted(chains.values(), key=lambda c: c.chain_id)
    result.nonpolymer_components = sorted(
        nonpolymer_components.values(),
        key=lambda item: (item["chain_id"], item["residue_number"], item["insertion_code"] or ""),
    )

    # B-factor statistics
    if all_b_factors:
        result.b_factor_stats = {
            "mean": round(sum(all_b_factors) / len(all_b_factors), 2),
            "min": round(min(all_b_factors), 2),
            "max": round(max(all_b_factors), 2),
            "atom_count": len(all_b_factors),
        }

    # SEQRES (full construct sequence)
    if seqres_chains:
        ordered = sorted(seqres_chains.keys())
        result.seqres_by_chain = dict(seqres_chains)
        result.seqres_sequence = "".join(seqres_chains[c] for c in ordered)

    if title_fragments:
        result.header["title"] = " ".join(title_fragments)

    compound_text = " ".join(compound_fragments)
    if len(re.findall(r"\bMOL_ID\s*:", compound_text, flags=re.IGNORECASE)) <= 1:
        for entry in compound_text.split(";"):
            key, separator, value = entry.partition(":")
            if separator and value.strip():
                result.compound_annotation[key.strip().lower()] = value.strip()

    return _to_dict(result)


def _parse_method(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    method_map = {
        "X-RAY": "X-RAY DIFFRACTION",
        "SOLUTION NMR": "SOLUTION NMR",
        "ELECTRON MICROSCOPY": "ELECTRON MICROSCOPY",
        "SOLID-STATE NMR": "SOLID-STATE NMR",
        "ELECTRON CRYSTALLOGRAPHY": "ELECTRON CRYSTALLOGRAPHY",
        "FIBER DIFFRACTION": "FIBER DIFFRACTION",
        "NEUTRON DIFFRACTION": "NEUTRON DIFFRACTION",
        "POWDER DIFFRACTION": "POWDER DIFFRACTION",
    }
    for key, val in method_map.items():
        if key in raw.upper():
            return val
    return raw


def _parse_remark(line: str, result: PDBResult) -> None:
    """Parse REMARK 2 (resolution) and REMARK 3 (R-factor)."""
    remark_num = line[7:10].strip()
    text = line[11:]

    if remark_num == "2":
        m = re.search(r"RESOLUTION\.\s+(\d+\.?\d*)\s+ANGSTROMS", text)
        if m and result.resolution is None:
            result.resolution = float(m.group(1))

    elif remark_num == "3":
        m = re.search(r"R VALUE\s+\(WORKING SET\)\s*:\s*(\d+\.?\d*)", text)
        if m and result.r_factor is None:
            result.r_factor = float(m.group(1))


def _to_dict(result: PDBResult) -> dict[str, Any]:
    return {
        "header": result.header,
        "chains": [
            {
                "chain_id": c.chain_id,
                "sequence": c.sequence,
                "residue_count": c.residue_count,
                "atom_count": c.atom_count,
                "residue_range": list(c.residue_range) if c.residue_range else None,
            }
            for c in result.chains
        ],
        "resolution": result.resolution,
        "r_factor": result.r_factor,
        "space_group": result.space_group,
        "unit_cell": result.unit_cell,
        "b_factor_stats": result.b_factor_stats or None,
        "b_factor_scope": (
            "protein_polymer_atoms_only; raw PDB temperature-factor column; interpretation depends on structure source"
            if result.b_factor_stats else None
        ),
        "total_atoms": result.total_atoms,
        "total_residues": result.total_residues,
        "seqres_sequence": result.seqres_sequence or None,
        "seqres_by_chain": result.seqres_by_chain,
        "nonpolymer_components": result.nonpolymer_components,
        "compound_annotation": result.compound_annotation,
        "engineered_mutations": result.engineered_mutations,
        "method": result.method,
        "deposited_date": result.deposited_date,
    }
