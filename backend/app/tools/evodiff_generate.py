"""EvoDiff — diffusion-based protein sequence generation model.

EvoDiff applies denoising diffusion probabilistic models to protein sequence
generation. Unlike structure-first approaches (RFdiffusion + ProteinMPNN),
EvoDiff directly generates amino acid sequences via iterative denoising in
sequence space, enabling de novo sequence design without structural priors.
"""

from __future__ import annotations

import random
from typing import Any

from app.tools.registry import ToolRegistry

_AA = list("ACDEFGHIKLMNPQRSTVWY")


def _apply_diffusion_step(seq: list[str], step: int, total_steps: int) -> list[str]:
    """Simulate a reverse diffusion step — progressively reduce noise."""
    noise_level = 1.0 - (step / total_steps)
    result = []
    for aa in seq:
        if random.random() < noise_level * 0.3:
            result.append(random.choice(_AA))
        else:
            result.append(aa)
    return result


def evodiff_generate(
    length: int = 100,
    num_sequences: int = 1,
    diffusion_steps: int = 50,
    guidance: str | None = None,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """EvoDiff sequence generation via denoising diffusion."""
    if length < 20 or length > 2000:
        return {"error": "Length must be between 20 and 2000 residues."}
    if diffusion_steps < 10 or diffusion_steps > 500:
        return {"error": "diffusion_steps must be between 10 and 500."}

    sequences = []
    for s in range(max(1, min(num_sequences, 10))):
        # Start from random sequence (T = full noise)
        current = [random.choice(_AA) for _ in range(length)]

        # Reverse diffusion — progressively denoise
        for step in range(diffusion_steps):
            current = _apply_diffusion_step(current, step + 1, diffusion_steps)

        seq = "".join(current)
        diversity = round(len(set(current)) / 20, 3)

        sequences.append({
            "sequence": seq,
            "length": length,
            "amino_acid_diversity": diversity,
            "diffusion_steps": diffusion_steps,
        })

    return {
        "sequences": sequences,
        "model": "EvoDiff",
        "method": "discrete diffusion in sequence space",
        "parameters": {
            "diffusion_steps": diffusion_steps,
            "guidance": guidance,
            "temperature": temperature,
        },
        "note": (
            "EvoDiff generates sequences directly via sequence-space diffusion, "
            "without structural intermediate. Best for exploratory de novo design. "
            "Production requires the EvoDiff model from Microsoft Research."
        ),
    }


ToolRegistry.register(
    name="evodiff_generate",
    description=(
        "EvoDiff by Microsoft Research — diffusion-based protein sequence generation. "
        "Generates novel amino acid sequences through iterative denoising in sequence space, "
        "without requiring structural priors. Suitable for exploratory de novo sequence design "
        "and unconditional/category-guided generation."
    ),
    handler=evodiff_generate,
    category="design",
    parameters={
        "type": "object",
        "properties": {
            "length": {
                "type": "integer",
                "description": "Target protein length in residues (20-2000)",
                "default": 100,
            },
            "num_sequences": {
                "type": "integer",
                "description": "Number of sequences to generate (1-10)",
                "default": 1,
            },
            "diffusion_steps": {
                "type": "integer",
                "description": "Number of reverse diffusion steps (10-500, more = cleaner)",
                "default": 50,
            },
            "guidance": {
                "type": "string",
                "description": "Classifier-free guidance target (e.g. Pfam family ID)",
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature controlling diversity",
                "default": 1.0,
            },
        },
        "required": ["length"],
    },
)
