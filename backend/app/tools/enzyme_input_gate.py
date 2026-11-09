"""Protein-sequence intake validation for enzyme engineering workflows."""

from __future__ import annotations

import hashlib
from collections import Counter

from app.tools.registry import ToolRegistry


_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
_NUCLEOTIDE = frozenset("ACGTUN")


def _normalize_sequence(raw: str) -> str:
    lines = [line.strip() for line in str(raw or "").splitlines()]
    return "".join(line for line in lines if line and not line.startswith(">")) \
        .replace(" ", "").replace("-", "").upper()


def enzyme_input_gate(sequence: str, minimum_length: int = 20) -> dict:
    """Validate and normalize a protein sequence without inferring function."""
    normalized = _normalize_sequence(sequence)
    errors: list[str] = []
    warnings: list[str] = []

    invalid = sorted(set(normalized) - _STANDARD_AA)
    if not normalized:
        errors.append("missing_sequence")
    elif invalid:
        errors.append("non_standard_amino_acids:" + "".join(invalid))
    elif set(normalized) <= _NUCLEOTIDE and len(normalized) >= minimum_length - 2:
        errors.append("sequence_looks_like_nucleotide")
    elif len(normalized) < minimum_length:
        errors.append("sequence_too_short")

    if normalized and not invalid:
        frequencies = Counter(normalized)
        if max(frequencies.values()) / len(normalized) >= 0.70 or len(frequencies) <= 4:
            warnings.append("low_complexity_sequence")
        if len(normalized) > 5000:
            warnings.append("unusually_long_protein_sequence")

    status = "blocked" if errors else ("needs_review" if warnings else "ready")
    return {
        "status": status,
        "sequence": normalized,
        "length": len(normalized),
        "sequence_sha256": hashlib.sha256(normalized.encode("ascii")).hexdigest() if normalized else "",
        "errors": errors,
        "warnings": warnings,
        "claim_eligible": status == "ready",
        "evidence_level": "input_validation",
        "scientific_boundary": "Sequence validity does not establish enzyme identity, activity, or structure.",
    }


ToolRegistry.register(
    name="enzyme_input_gate",
    description="Normalize FASTA/protein input and block invalid, nucleotide-like, short, or review-required low-complexity sequences.",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "minimum_length": {"type": "integer", "default": 20},
        },
        "required": ["sequence"],
    },
    handler=enzyme_input_gate,
    category="analysis",
    timeout_seconds=30,
)
