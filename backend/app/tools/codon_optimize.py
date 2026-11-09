"""Deterministic host-aware codon adaptation for protein coding sequences."""

from __future__ import annotations

from collections import Counter

from app.tools.registry import ToolRegistry


AA = "ACDEFGHIKLMNPQRSTVWY"
CODONS = {
    "A": ["GCT", "GCC", "GCA", "GCG"], "C": ["TGT", "TGC"],
    "D": ["GAT", "GAC"], "E": ["GAA", "GAG"], "F": ["TTT", "TTC"],
    "G": ["GGT", "GGC", "GGA", "GGG"], "H": ["CAT", "CAC"],
    "I": ["ATT", "ATC", "ATA"], "K": ["AAA", "AAG"],
    "L": ["TTA", "TTG", "CTT", "CTC", "CTA", "CTG"],
    "M": ["ATG"], "N": ["AAT", "AAC"], "P": ["CCT", "CCC", "CCA", "CCG"],
    "Q": ["CAA", "CAG"], "R": ["CGT", "CGC", "CGA", "CGG", "AGA", "AGG"],
    "S": ["TCT", "TCC", "TCA", "TCG", "AGT", "AGC"],
    "T": ["ACT", "ACC", "ACA", "ACG"], "V": ["GTT", "GTC", "GTA", "GTG"],
    "W": ["TGG"], "Y": ["TAT", "TAC"],
}

# Practical high-frequency choices. These are adaptation defaults, not a
# substitute for a measured host-specific codon usage table.
PREFERRED = {
    "pichia_gs115": {"A": "GCC", "C": "TGC", "D": "GAC", "E": "GAG", "F": "TTC", "G": "GGC", "H": "CAC", "I": "ATC", "K": "AAG", "L": "CTG", "N": "AAC", "P": "CCC", "Q": "CAG", "R": "CGC", "S": "TCC", "T": "ACC", "V": "GTC", "Y": "TAC"},
    "bacillus_licheniformis": {"A": "GCT", "C": "TGC", "D": "GAT", "E": "GAA", "F": "TTC", "G": "GGT", "H": "CAT", "I": "ATT", "K": "AAA", "L": "CTG", "N": "AAC", "P": "CCA", "Q": "CAA", "R": "CGT", "S": "TCT", "T": "ACT", "V": "GTT", "Y": "TAT"},
}

HOST_ALIASES = {
    "gs115": "pichia_gs115", "pichia": "pichia_gs115", "pichia pastoris": "pichia_gs115",
    "毕赤酵母": "pichia_gs115", "bacillus": "bacillus_licheniformis",
    "bacillus licheniformis": "bacillus_licheniformis", "地衣芽孢杆菌": "bacillus_licheniformis",
}


def _normalise_host(host: str) -> str:
    key = "_".join(host.strip().lower().replace("-", " ").split())
    return HOST_ALIASES.get(key, key)


def codon_optimize(sequence: str, host: str, include_stop: bool = True) -> dict:
    """Return an auditable DNA design and codon adaptation summary."""
    protein = "".join(sequence.split()).upper()
    if not protein:
        raise ValueError("EMPTY_SEQUENCE: protein sequence must not be empty")
    invalid = set(protein) - set(AA)
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")
    host_key = _normalise_host(host)
    preferred = PREFERRED.get(host_key)
    if preferred is None:
        raise ValueError(
            f"UNSUPPORTED_HOST: {host}. Supported hosts: Pichia GS115, Bacillus licheniformis"
        )
    codons = [preferred.get(aa, CODONS[aa][0]) for aa in protein]
    if include_stop:
        codons.append("TAA")
    dna = "".join(codons)
    usage = Counter(codons[:-1] if include_stop else codons)
    coding_region = dna[:-3] if include_stop else dna
    gc = sum(base in "GC" for base in coding_region) / max(1, len(coding_region))
    return {
        "protein_sequence": protein,
        "host": host_key,
        "coding_dna": dna,
        "length_aa": len(protein),
        "length_nt": len(dna),
        "gc_fraction": round(gc, 4),
        "codon_usage": dict(sorted(usage.items())),
        "stop_codon": "TAA" if include_stop else None,
        "design_status": "computational_proposal",
        "limitations": ["Uses deterministic preferred codons; verify host-specific usage, repeats, GC extremes, and synthesis constraints before ordering."],
    }


ToolRegistry.register(
    name="codon_optimize",
    description="Adapt a protein sequence to a supported expression host using auditable preferred codons.",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino-acid sequence"},
            "host": {"type": "string", "description": "Expression host: Pichia GS115 or Bacillus licheniformis"},
            "include_stop": {"type": "boolean", "default": True},
        },
        "required": ["sequence", "host"],
    },
    handler=codon_optimize,
    category="expression",
    timeout_seconds=30,
)
