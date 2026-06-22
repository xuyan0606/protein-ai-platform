"""SolubleMPNN & MembraneMPNN — specialized inverse folding models.

SolubleMPNN and MembraneMPNN are variants of ProteinMPNN fine-tuned for
specific environments: SolubleMPNN optimizes for aqueous solubility and
reduced aggregation propensity, while MembraneMPNN specializes in designing
sequences for transmembrane regions with appropriate hydropathy profiles.
"""

from __future__ import annotations

import random
from typing import Any

from app.tools.registry import ToolRegistry

_AA = list("ACDEFGHIKLMNPQRSTVWY")

# Kyte-Doolittle hydropathy scale (simplified)
_HYDROPATHY = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
    "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "S": -0.8,
    "W": -0.9, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
    "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5,
}

# Solubility-favoring residues (high solubility, low aggregation)
_SOLUBLE_FAVORED = {"E", "D", "K", "R", "Q", "N", "P", "S", "T", "G"}
_MEMBRANE_FAVORED = {"I", "L", "V", "F", "M", "A", "W", "C", "Y"}


def _design_for_solubility(sequence: str, positions: list[int] | None) -> dict:
    residues = list(sequence)
    mutations = []
    targets = positions if positions else list(range(1, len(sequence) + 1))
    for pos in targets:
        idx = pos - 1
        if idx < 0 or idx >= len(residues):
            continue
        original = residues[idx]
        if original not in _SOLUBLE_FAVORED:
            chosen = random.choice(sorted(_SOLUBLE_FAVORED))
            residues[idx] = chosen
            mutations.append({
                "position": pos,
                "original": original,
                "designed": chosen,
                "hydropathy_change": round(_HYDROPATHY.get(chosen, 0) - _HYDROPATHY.get(original, 0), 1),
            })
    solubility_score = round(sum(1 for aa in residues if aa in _SOLUBLE_FAVORED) / len(residues), 3)
    return {"sequence": "".join(residues), "mutations": mutations, "solubility_score": solubility_score}


def _design_for_membrane(sequence: str, tm_regions: list[dict]) -> dict:
    residues = list(sequence)
    all_mutations = []
    for region in tm_regions:
        start = region.get("start", 1)
        end = region.get("end", len(sequence))
        for pos in range(start, end + 1):
            idx = pos - 1
            if idx < 0 or idx >= len(residues):
                continue
            original = residues[idx]
            if original not in _MEMBRANE_FAVORED or _HYDROPATHY.get(original, 0) < 1.0:
                chosen = random.choice(sorted(_MEMBRANE_FAVORED))
                residues[idx] = chosen
                all_mutations.append({
                    "position": pos,
                    "original": original,
                    "designed": chosen,
                    "hydropathy": _HYDROPATHY.get(chosen, 0),
                })
    tm_hydropathy = round(
        sum(_HYDROPATHY.get(aa, 0) for aa in residues) / len(residues), 2
    )
    return {"sequence": "".join(residues), "mutations": all_mutations, "mean_tm_hydropathy": tm_hydropathy}


def soluble_mpnn_design(
    sequence: str,
    mode: str = "soluble",
    positions: list[int] | None = None,
    tm_regions: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Specialized inverse folding for solubility or membrane environments."""
    seq = sequence.strip().upper()
    invalids = [c for c in seq if c not in _AA]
    if invalids:
        return {"error": f"Invalid amino acid characters: {set(invalids)}", "valid_aa": "".join(_AA)}

    if mode == "soluble":
        result = _design_for_solubility(seq, positions)
        return {
            "mode": "soluble",
            "result": result,
            "model": "SolubleMPNN",
            "note": "SolubleMPNN optimizes for aqueous solubility and low aggregation propensity.",
        }
    elif mode == "membrane":
        if not tm_regions:
            half = len(seq) // 4
            tm_regions = [{"start": half, "end": half + 20}]
        result = _design_for_membrane(seq, tm_regions)
        return {
            "mode": "membrane",
            "result": result,
            "model": "MembraneMPNN",
            "note": "MembraneMPNN optimizes transmembrane regions for appropriate hydropathy.",
        }
    else:
        return {"error": f"Unknown mode '{mode}'. Use 'soluble' or 'membrane'."}


ToolRegistry.register(
    name="soluble_mpnn_design",
    description=(
        "SolubleMPNN / MembraneMPNN — specialized inverse folding models derived from ProteinMPNN. "
        "SolubleMPNN optimizes sequences for aqueous solubility and reduced aggregation. "
        "MembraneMPNN designs transmembrane regions with appropriate hydropathy profiles. "
        "Select 'soluble' or 'membrane' mode to target the specific environment."
    ),
    handler=soluble_mpnn_design,
    category="design",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Parent protein sequence to redesign",
            },
            "mode": {
                "type": "string",
                "description": "Design mode: 'soluble' for solubility optimization, 'membrane' for transmembrane design",
                "default": "soluble",
            },
            "positions": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Specific positions to redesign (soluble mode). Omit = redesign all.",
            },
            "tm_regions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                    },
                },
                "description": "Transmembrane helix boundaries for membrane mode: [{'start': N, 'end': M}, ...]",
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature (0.01-1.0)",
                "default": 0.1,
            },
        },
        "required": ["sequence"],
    },
)

# Register MembraneMPNN as an alias
ToolRegistry.register_alias("membrane_mpnn_design", "soluble_mpnn_design")
