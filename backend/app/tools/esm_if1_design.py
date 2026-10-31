"""Secondary-structure heuristic sequence sampler standing in for ESM-IF1.

The ESM-IF1 model is not wired in. This module samples residues from
per-SS8 amino acid pools and does not use backbone geometry or a language model.
"""

from __future__ import annotations

import random
from typing import Any

from app.tools.registry import ToolRegistry

_AA = list("ACDEFGHIKLMNPQRSTVWY")
_SS8_TO_AA = {
    "H": list("ALERKMQ"),   # alpha helix
    "G": list("ALERKMQ"),   # 3-10 helix
    "I": list("ALERKMQ"),   # pi helix
    "E": list("VITFYW"),    # extended strand
    "B": list("VITFY"),     # beta bridge
    "T": list("PGSNDT"),    # turn
    "S": list("PGSNDT"),    # bend
    "C": list("GPNDST"),    # coil/loop
}


def _design_from_ss(ss_sequence: str, length: int, temperature: float) -> list[dict]:
    """Design sequence from secondary structure annotation."""
    residues = []
    for i, ss in enumerate(ss_sequence):
        candidates = _SS8_TO_AA.get(ss, _AA)
        chosen = random.choice(candidates)
        residues.append({
            "position": i + 1,
            "amino_acid": chosen,
            "ss_type": ss,
            "confidence": round(random.uniform(0.5, 0.99), 3),
        })
    return residues


def esm_if1_design(
    pdb_data: str | None = None,
    structure_coords: list[dict] | None = None,
    secondary_structure: str | None = None,
    temperature: float = 0.1,
    num_variants: int = 1,
) -> dict[str, Any]:
    """Heuristic SS-based sequence sampling. Not ESM-IF1 inference."""
    length = 0

    if pdb_data:
        # Count Cα atoms as approximate length
        ca_count = pdb_data.count("CA ") + pdb_data.count("CA\n")
        length = ca_count if ca_count > 0 else 100
    elif structure_coords:
        length = len(structure_coords)
    elif secondary_structure:
        ss = secondary_structure.strip().upper()
        length = len(ss)
        invalid = [c for c in ss if c not in _SS8_TO_AA]
        if invalid:
            return {"error": f"Invalid SS8 code(s): {set(invalid)}. Valid: {list(_SS8_TO_AA.keys())}"}
    else:
        return {"error": "One of pdb_data, structure_coords, or secondary_structure is required."}

    if length < 5 or length > 2000:
        return {"error": f"Structure length {length} out of range (5-2000)."}

    # Generate secondary structure if from coords/PDB
    ss_seq = secondary_structure
    if not ss_seq:
        ss_types = list(_SS8_TO_AA.keys())
        weights = [0.35, 0.05, 0.01, 0.25, 0.05, 0.08, 0.03, 0.18]  # H, G, I, E, B, T, S, C
        ss_seq = "".join(random.choices(ss_types, weights=weights, k=length))

    variants = []
    for v in range(max(1, min(num_variants, 10))):
        residues = _design_from_ss(ss_seq, length, temperature)
        seq = "".join(r["amino_acid"] for r in residues)
        variants.append({
            "variant": v + 1,
            "sequence": seq,
            "length": length,
            "residues": residues,
            "mean_confidence": round(sum(r["confidence"] for r in residues) / length, 3),
        })

    return {
        "variants": variants,
        "model": "SS8-heuristic-sampler",
        "is_real_inference": False,
        "input_type": "PDB" if pdb_data else ("coords" if structure_coords else "SS8_annotation"),
        "temperature": temperature,
        "note": (
            "Heuristic sampler: residues are drawn from secondary-structure amino acid pools, "
            "ignoring backbone geometry. ESM-IF1 is not connected; these sequences are not "
            "inverse-folding predictions and do not indicate stability or activity."
        ),
    }


ToolRegistry.register(
    name="esm_if1_design",
    description=(
        "Heuristic sequence sampler (ESM-IF1 is not connected). Accepts PDB structures, Cα "
        "coordinate lists, or DSSP 8-state secondary structure annotations. Samples sequences "
        "from secondary-structure amino acid pools with pseudo-confidence values; "
        "not a backbone-conditioned inverse-folding prediction."
    ),
    handler=esm_if1_design,
    category="design",
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {
                "type": "string",
                "description": "PDB file content or path to structure",
            },
            "structure_coords": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                    },
                },
                "description": "Cα coordinates as [{x, y, z}, ...]",
            },
            "secondary_structure": {
                "type": "string",
                "description": "DSSP 8-state secondary structure string (H/G/I/E/B/T/S/C)",
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature (0.01-1.0)",
                "default": 0.1,
            },
            "num_variants": {
                "type": "integer",
                "description": "Number of sequence variants (1-10)",
                "default": 1,
            },
        },
        "required": [],
    },
)
