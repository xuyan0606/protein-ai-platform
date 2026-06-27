"""PDB file parser — extracts sequence, structure metadata, and quality metrics.

Pure Python, no external dependencies. Parses the standard PDB format (v3.30).
"""

from __future__ import annotations

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
    method: str | None = None
    deposited_date: str | None = None


def parse_pdb(content: str) -> dict[str, Any]:
    """Parse PDB file content into structured analysis data.

    Args:
        content: Raw PDB file text.

    Returns:
        Dict with chains, sequences, quality metrics, and structure metadata.
    """
    result = PDBResult()
    lines = content.splitlines()

    chains: dict[str, ChainInfo] = {}
    seqres_chains: dict[str, str] = defaultdict(str)
    seen_residues: set[tuple[str, int, str]] = set()  # (chain, resnum, resname)
    current_model: int | None = None

    for line in lines:
        record = line[:6].strip()

        if record == "HEADER":
            result.method = _parse_method(line[10:50])
            result.deposited_date = line[50:59].strip() or None

        elif record == "TITLE" and not result.header.get("title"):
            result.header["title"] = line[10:].strip()

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
                aa = _AA3TO1.get(rn.upper(), "X")
                seqres_chains[chain_id] += aa

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

            if chain_id not in chains:
                chains[chain_id] = ChainInfo(chain_id=chain_id)

            chain = chains[chain_id]
            chain.atom_count += 1
            chain.b_factors.append(b_factor)
            result.total_atoms += 1

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

    # B-factor statistics
    all_bfactors = [b for c in result.chains for b in c.b_factors]
    if all_bfactors:
        result.b_factor_stats = {
            "mean": round(sum(all_bfactors) / len(all_bfactors), 2),
            "min": round(min(all_bfactors), 2),
            "max": round(max(all_bfactors), 2),
        }

    # SEQRES (full construct sequence)
    if seqres_chains:
        ordered = sorted(seqres_chains.keys())
        result.seqres_sequence = "".join(seqres_chains[c] for c in ordered)

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
        "total_atoms": result.total_atoms,
        "total_residues": result.total_residues,
        "seqres_sequence": result.seqres_sequence or None,
        "method": result.method,
        "deposited_date": result.deposited_date,
    }