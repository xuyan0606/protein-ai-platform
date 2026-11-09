"""Guarded sequence-level screening for host expression and secretion."""

from __future__ import annotations

from app.tools.codon_optimize import _normalise_host
from app.tools.registry import ToolRegistry


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPATHY = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "Q": -3.5, "E": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
SUPPORTED_HOSTS = {"pichia_gs115", "bacillus_licheniformis"}


def _validate(sequence: str, host: str) -> tuple[str, str]:
    protein = "".join(sequence.split()).upper()
    if not protein:
        raise ValueError("EMPTY_SEQUENCE: protein sequence must not be empty")
    invalid = set(protein) - STANDARD_AA
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")
    host_key = _normalise_host(host)
    if host_key not in SUPPORTED_HOSTS:
        raise ValueError(
            f"UNSUPPORTED_HOST: {host}. Supported hosts: Pichia GS115, Bacillus licheniformis"
        )
    return protein, host_key


def _hydrophobic_windows(sequence: str, window: int = 8) -> list[tuple[int, float]]:
    if len(sequence) < window:
        return []
    return [
        (index + 1, sum(HYDROPATHY[aa] for aa in sequence[index:index + window]) / window)
        for index in range(len(sequence) - window + 1)
    ]


def _signal_features(sequence: str) -> dict:
    n_terminal = sequence[:40]
    windows = _hydrophobic_windows(n_terminal)
    strongest_start, strongest_score = max(windows, key=lambda item: item[1], default=(None, 0.0))
    cleavage_candidates = []
    small = set("ASTGCV")
    for cut in range(15, min(36, len(n_terminal))):
        if n_terminal[cut - 3] in small and n_terminal[cut - 1] in small:
            cleavage_candidates.append(cut)
    return {
        "n_region_basic_count": sum(aa in "KR" for aa in n_terminal[:8]),
        "strongest_hydrophobic_window_start": strongest_start,
        "strongest_hydrophobic_window_score": round(strongest_score, 3),
        "signal_like_hydrophobic_core": strongest_score >= 1.5,
        "candidate_cleavage_after_positions": cleavage_candidates,
    }


def secretion_efficiency_predict(sequence: str, host: str) -> dict:
    """Screen N-terminal secretion signals without reporting calibrated efficiency."""
    protein, host_key = _validate(sequence, host)
    features = _signal_features(protein)
    evidence_count = sum([
        features["n_region_basic_count"] > 0,
        features["signal_like_hydrophobic_core"],
        bool(features["candidate_cleavage_after_positions"]),
    ])
    motif_risks = []
    if host_key == "pichia_gs115":
        motif_risks = [motif for motif in ("KR", "RR") if motif in protein[15:80]]
    return {
        "host": host_key,
        "signal_features": features,
        "screening_class": ("signal_like" if evidence_count == 3 else "partial_signal" if evidence_count else "no_signal_detected"),
        "screening_score": round(evidence_count / 3, 3),
        "potential_processing_motifs": motif_risks,
        "predicted_secretion_efficiency": None,
        "status": "screening_only",
        "limitations": [
            "This rule-based screen is not a calibrated secretion-efficiency model.",
            "Validate cleavage, secretion titre, and host proteolysis experimentally.",
        ],
    }


def host_expression_yield_predict(sequence: str, host: str, coding_dna: str | None = None) -> dict:
    """Rank expression risks without inventing an absolute yield value."""
    protein, host_key = _validate(sequence, host)
    windows = _hydrophobic_windows(protein, window=11)
    high_hydrophobic_windows = sum(score >= 1.6 for _, score in windows)
    risk_factors = []
    if len(protein) > 800:
        risk_factors.append("long_protein")
    if high_hydrophobic_windows > max(1, len(protein) // 100):
        risk_factors.append("multiple_hydrophobic_segments")
    if protein.count("C") > max(6, len(protein) * 0.04):
        risk_factors.append("high_cysteine_content")
    if abs(sum(aa in "KR" for aa in protein) - sum(aa in "DE" for aa in protein)) > len(protein) * 0.2:
        risk_factors.append("strong_charge_imbalance")

    dna_summary = None
    if coding_dna is not None:
        dna = "".join(coding_dna.split()).upper()
        if set(dna) - set("ACGT") or len(dna) % 3:
            raise ValueError("INVALID_CODING_DNA: use A/C/G/T and a length divisible by three")
        dna_summary = {
            "length_nt": len(dna),
            "gc_fraction": round(sum(base in "GC" for base in dna) / max(1, len(dna)), 4),
        }
    score = max(0.0, 1.0 - 0.2 * len(risk_factors))
    return {
        "host": host_key,
        "sequence_length": len(protein),
        "risk_factors": risk_factors,
        "expression_readiness_score": round(score, 3),
        "risk_class": "low" if score >= 0.8 else "moderate" if score >= 0.5 else "high",
        "coding_dna_summary": dna_summary,
        "predicted_expression_yield": None,
        "status": "screening_only",
        "limitations": [
            "Readiness is a sequence risk screen, not an absolute expression-yield prediction.",
            "Host strain, vector, promoter, copy number, medium, and induction conditions are not modeled.",
        ],
    }


ToolRegistry.register(
    name="secretion_efficiency_predict",
    description="Screen an N-terminal sequence for host secretion-signal evidence and processing risks.",
    parameters={
        "type": "object",
        "properties": {"sequence": {"type": "string"}, "host": {"type": "string"}},
        "required": ["sequence", "host"],
    },
    handler=secretion_efficiency_predict,
    category="expression",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="host_expression_yield_predict",
    description="Screen host-expression risks without claiming an uncalibrated absolute yield.",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "host": {"type": "string"},
            "coding_dna": {"type": "string"},
        },
        "required": ["sequence", "host"],
    },
    handler=host_expression_yield_predict,
    category="expression",
    timeout_seconds=30,
)
