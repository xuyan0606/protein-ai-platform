"""Predict physicochemical properties of a protein sequence.

Uses Biopython's ProtParam for core calculations (molecular weight, pI,
extinction coefficient, GRAVY, instability index) and implements Chou-Fasman
secondary structure prediction and simplified IUPred disorder prediction
in pure Python as fallback/enhancement.
"""

from __future__ import annotations

import math

from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Try Biopython; fall back to manual computation if unavailable
# ---------------------------------------------------------------------------
try:
    from Bio.SeqUtils.ProtParam import ProteinAnalysis as _BPA

    _BIOPYTHON = True
except ImportError:
    _BIOPYTHON = False

# ---------------------------------------------------------------------------
# Amino-acid property tables (shared by manual fallback and Chou-Fasman)
# ---------------------------------------------------------------------------

_STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

# Monoisotopic residue masses (Da) — average masses used here for ProtParam compat
_AA_MASS: dict[str, float] = {
    "A": 89.0932, "R": 174.2017, "N": 132.1184, "D": 133.1032, "C": 121.1590,
    "E": 147.1299, "Q": 146.1451, "G": 75.0669, "H": 155.1552, "I": 131.1736,
    "L": 131.1736, "K": 146.1882, "M": 149.2124, "F": 165.1900, "P": 115.1310,
    "S": 105.0930, "T": 119.1197, "W": 204.2262, "Y": 181.1894, "V": 117.1469,
}

# Kyte-Doolittle hydropathy
_KD_HYDROPATHY: dict[str, float] = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "E": -3.5, "Q": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

# pKa values (NH2, COOH, and side-chains) for iterative pI calculation
_PKA_N_TERM = 9.69    # average free N-terminus
_PKA_C_TERM = 2.34    # average free C-terminus
_PKA_SIDE: dict[str, float | None] = {
    "D": 3.86, "E": 4.25, "C": 8.33, "Y": 10.0,
    "H": 6.00, "K": 10.53, "R": 12.48,
}

# Instability weights from Guruprasad et al. (1990), Protein Eng. 4:155-161
# Key: dipeptide -> DIWV (dipeptide instability weight value)
_DIWV: dict[str, float] = {
    "AW": 0.0, "CW": 0.0, "DW": 0.0, "EW": 1.0, "FW": 1.0,
    "GW": 5.0, "HW": 1.0, "IW": 1.0, "KW": 0.0, "LW": 0.0,
    "MW": 0.0, "NW": 1.0, "PW": 0.0, "QW": 0.0, "RW": 0.0,
    "SW": 1.0, "TW": 0.0, "VW": 0.0, "WW": 1.0, "YW": 0.0,
    "WA": 0.0, "WC": 1.0, "WD": 1.0, "WE": 0.0, "WF": 3.0,
    "WG": 0.0, "WH": 0.0, "WI": 1.0, "WK": 0.0, "WL": 0.0,
    "WM": 0.0, "WN": 0.0, "WP": 0.0, "WQ": 0.0, "WR": 0.0,
    "WS": 0.0, "WT": 0.0, "WV": 1.0, "WW": 1.0, "WY": 0.0,
    # Instability = sum(DIWV) * 10 / L   (L = sequence length)
    # Default DIWV = 1.0 where not specified (stabilising dipeptide)
}


# ---------------------------------------------------------------------------
# Extinction coefficient residues
# ---------------------------------------------------------------------------
_EC_CYS = 125   # M^-1 cm^-1 per Cys (reduced)
_EC_TYR = 1490
_EC_TRP = 5500
# Cystine (disulfide) pair contribution
_EC_SS = 125  # per disulfide bond (oxidised form)


# ---------------------------------------------------------------------------
# Chou-Fasman conformational parameters  (Chou & Fasman, 1978)
# ---------------------------------------------------------------------------
# P(a) = alpha-helix propensity
# P(b) = beta-sheet propensity
# P(t) = turn propensity
_CHOU_FASMAN: dict[str, dict[str, float]] = {
    "A": {"Pa": 1.42, "Pb": 0.83, "Pt": 0.66},
    "R": {"Pa": 0.98, "Pb": 0.93, "Pt": 0.95},
    "N": {"Pa": 0.67, "Pb": 0.89, "Pt": 1.56},
    "D": {"Pa": 1.01, "Pb": 0.54, "Pt": 1.46},
    "C": {"Pa": 0.70, "Pb": 1.19, "Pt": 1.19},
    "E": {"Pa": 1.51, "Pb": 0.37, "Pt": 0.74},
    "Q": {"Pa": 1.11, "Pb": 1.10, "Pt": 0.98},
    "G": {"Pa": 0.57, "Pb": 0.75, "Pt": 1.56},
    "H": {"Pa": 1.00, "Pb": 0.87, "Pt": 0.95},
    "I": {"Pa": 1.08, "Pb": 1.60, "Pt": 0.47},
    "L": {"Pa": 1.21, "Pb": 1.30, "Pt": 0.59},
    "K": {"Pa": 1.16, "Pb": 0.74, "Pt": 1.01},
    "M": {"Pa": 1.45, "Pb": 1.05, "Pt": 0.60},
    "F": {"Pa": 1.13, "Pb": 1.38, "Pt": 0.60},
    "P": {"Pa": 0.57, "Pb": 0.55, "Pt": 1.52},
    "S": {"Pa": 0.77, "Pb": 0.75, "Pt": 1.43},
    "T": {"Pa": 0.83, "Pb": 1.19, "Pt": 0.96},
    "W": {"Pa": 1.08, "Pb": 1.37, "Pt": 0.96},
    "Y": {"Pa": 0.69, "Pb": 1.47, "Pt": 1.14},
    "V": {"Pa": 1.06, "Pb": 1.70, "Pt": 0.50},
}

# Chou-Fasman nucleation thresholds
_CF_HELIX_THRESHOLD = 1.00    # P(a) > 1.00 favours helix
_CF_SHEET_THRESHOLD = 1.00    # P(b) > 1.00 favours sheet
_CF_HELIX_WINDOW = 6          # sliding window for helix nucleation
_CF_SHEET_WINDOW = 5
# Criteria: 4 out of 6 residues in window must have P(a) > 1.00 for helix nucleation

# Disorder propensity (simplified IUPred — amino-acid scale from Uversky et al.)
# Higher value = higher disorder propensity
_DISORDER_PROPENSITY: dict[str, float] = {
    "A": 0.505, "R": 0.612, "N": 0.588, "D": 0.590, "C": 0.448,
    "Q": 0.570, "E": 0.642, "G": 0.576, "H": 0.560, "I": 0.358,
    "L": 0.380, "K": 0.678, "M": 0.424, "F": 0.383, "P": 0.641,
    "S": 0.548, "T": 0.513, "W": 0.442, "Y": 0.466, "V": 0.381,
}
_DISORDER_WINDOW = 21  # typical IUPred window
_DISORDER_THRESHOLD = 0.5


# ===================================================================
# Helper: pI via Henderson-Hasselbalch iterative solve
# ===================================================================

def _compute_pi(sequence: str) -> float:
    """Calculate isoelectric point by finding the pH where net charge = 0.

    Uses the iterative bisection method with pKa values for:
      - N-terminus (average ~9.69)
      - C-terminus (average ~2.34)
      - charged sidechains (D, E, C, Y, H, K, R)
    """

    def _net_charge(pH: float) -> float:
        charge = 0.0
        # N-terminus
        charge += 1.0 / (1.0 + 10 ** (pH - _PKA_N_TERM))
        # C-terminus
        charge -= 1.0 / (1.0 + 10 ** (_PKA_C_TERM - pH))
        # sidechains
        for aa in sequence:
            pKa = _PKA_SIDE.get(aa)
            if pKa is None:
                continue
            if aa in ("D", "E", "C", "Y"):
                charge -= 1.0 / (1.0 + 10 ** (pKa - pH))
            elif aa in ("H", "K", "R"):
                charge += 1.0 / (1.0 + 10 ** (pH - pKa))
        return charge

    # Bisection search
    lo, hi = 0.0, 14.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        q = _net_charge(mid)
        if abs(q) < 1e-6:
            return round(mid, 2)
        if q > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2.0, 2)


def _compute_extinction(sequence: str) -> dict:
    """Extinction coefficient at 280 nm (M^-1 cm^-1)."""
    nW = sequence.count("W")
    nY = sequence.count("Y")
    nC = sequence.count("C")
    reduced = nW * _EC_TRP + nY * _EC_TYR + nC * _EC_CYS
    n_ss = nC // 2  # maximum number of disulfides
    oxidized = reduced + n_ss * _EC_SS  # pair contribution
    return {"reduced": reduced, "oxidized": oxidized}


def _compute_instability_index(sequence: str) -> float:
    """Instability index (Guruprasad 1990).  II = (10/L) * sum(DIWV_i).

    A value > 40 predicts the protein is unstable in vitro.
    """
    n = len(sequence)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n - 1):
        dp = sequence[i] + sequence[i + 1]
        total += _DIWV.get(dp, 1.0)  # default 1.0 for unlisted stabilising dipeptides
    return (10.0 / n) * total


def _compute_gravy(sequence: str) -> float:
    """GRAVY: Grand Average of HydropathY (Kyte & Doolittle 1982)."""
    n = len(sequence)
    if n == 0:
        return 0.0
    return sum(_KD_HYDROPATHY.get(aa, 0.0) for aa in sequence) / n


def _chou_fasman(sequence: str) -> dict:
    """Chou-Fasman secondary structure prediction.

    Returns estimated helix/sheet/coil percentages and per-residue assignment.
    """
    n = len(sequence)
    if n < 5:
        return {
            "helix_percent": 0.0,
            "sheet_percent": 0.0,
            "coil_percent": 100.0,
            "per_residue": ["C"] * n,
        }

    # Residue-level propensities
    pa = [_CHOU_FASMAN.get(aa, {}).get("Pa", 1.0) for aa in sequence]
    pb = [_CHOU_FASMAN.get(aa, {}).get("Pb", 1.0) for aa in sequence]

    state = ["C"] * n  # default coil

    # --- Helix nucleation ---
    hw = _CF_HELIX_WINDOW
    i = 0
    while i <= n - hw:
        # Count residues with Pa > threshold in this window
        count = sum(1 for j in range(i, i + hw) if pa[j] >= _CF_HELIX_THRESHOLD)
        if count >= 4:
            # Nucleate helix, then extend
            orig_i = i
            start = i
            while i < n and pa[i] >= _CF_HELIX_THRESHOLD:
                state[i] = "H"
                i += 1
            # Extend left (may modify start, so use orig_i for the safety check below)
            while start > 0 and pa[start - 1] >= 0.9:
                start -= 1
                state[start] = "H"
            # Extend right
            while i < n and pa[i] >= 0.9:
                state[i] = "H"
                i += 1
            # Safety: if i never advanced (no residues met threshold), force advance
            if i == orig_i:
                i += 1
        else:
            i += 1

    # --- Sheet nucleation (overwrite if stronger) ---
    sw = _CF_SHEET_WINDOW
    i = 0
    while i <= n - sw:
        count = sum(1 for j in range(i, i + sw) if pb[j] >= _CF_SHEET_THRESHOLD)
        if count >= 3:
            marked = 0
            for j in range(i, min(i + sw, n)):
                if state[j] == "C":  # don't overwrite helices
                    state[j] = "E"
                    marked += 1
            # If nothing was marked (all already H), advance past window to avoid re-checking
            if marked == 0:
                i += sw
                continue
        i += 1

    h_count = state.count("H")
    e_count = state.count("E")
    c_count = n - h_count - e_count

    return {
        "helix_percent": round(h_count / n * 100, 1),
        "sheet_percent": round(e_count / n * 100, 1),
        "coil_percent": round(c_count / n * 100, 1),
        "per_residue": state,
    }


def _iupred_disorder(sequence: str) -> dict:
    """Simplified IUPred-like disorder prediction.

    Averages the disorder propensity in a sliding window and assigns
    'disordered' where the average exceeds the threshold.
    """
    n = len(sequence)
    if n == 0:
        return {"disorder_percent": 0.0, "disordered_regions": [], "per_residue_score": []}

    scores = []
    half = _DISORDER_WINDOW // 2
    for i in range(n):
        total = 0.0
        count = 0
        for j in range(max(0, i - half), min(n, i + half + 1)):
            total += _DISORDER_PROPENSITY.get(sequence[j], 0.5)
            count += 1
        scores.append(total / count if count > 0 else 0.5)

    # Identify contiguous disordered regions
    regions: list[dict] = []
    in_disorder = False
    start = 0
    for i, s in enumerate(scores):
        if s >= _DISORDER_THRESHOLD and not in_disorder:
            start = i
            in_disorder = True
        elif s < _DISORDER_THRESHOLD and in_disorder:
            regions.append({"start": start + 1, "end": i, "length": i - start})
            in_disorder = False
    if in_disorder:
        regions.append({"start": start + 1, "end": n, "length": n - start})

    disordered_residues = sum(r["length"] for r in regions)

    return {
        "disorder_percent": round(disordered_residues / n * 100, 1) if n else 0.0,
        "disordered_regions": regions,
        "mean_disorder_score": round(sum(scores) / n, 3) if n else 0.0,
    }


# ===================================================================
# Main predict_properties
# ===================================================================

def predict_properties(
    sequence: str,
    properties: list[str] | None = None,
) -> dict:
    """Calculate physiochemical properties of a protein sequence.

    Args:
        sequence: amino-acid sequence (single-letter code).
        properties: which properties to compute.  If None, all are computed.
          Supported: molecular_weight, isoelectric_point, extinction_coefficient,
          gravy, instability_index, secondary_structure, disorder,
          amino_acid_composition.

    Returns:
        Dict mapping property name to computed values.
    """
    seq = sequence.strip().upper()
    if not seq:
        raise ValueError("EMPTY_SEQUENCE: sequence must not be empty")

    invalid = set(seq) - _STANDARD_AA
    if invalid:
        raise ValueError(
            f"INVALID_AA: non-standard amino acids found: {''.join(sorted(invalid))}. "
            "Use the 20 standard letters only."
        )

    requested = set(properties) if properties else {
        "molecular_weight", "isoelectric_point", "extinction_coefficient",
        "gravy", "instability_index", "secondary_structure", "disorder",
        "amino_acid_composition",
    }

    result: dict = {"length": len(seq)}

    # --- Biopython path ---
    if _BIOPYTHON:
        try:
            pa = _BPA(seq)

            if "molecular_weight" in requested:
                result["molecular_weight_kda"] = round(pa.molecular_weight() / 1000.0, 2)

            if "isoelectric_point" in requested:
                result["isoelectric_point"] = round(pa.isoelectric_point(), 2)

            if "extinction_coefficient" in requested:
                ec = pa.molar_extinction_coefficient()
                result["extinction_coefficient_M-1cm-1"] = {
                    "reduced": round(ec[0], 0),
                    "oxidized": round(ec[1], 0),
                }

            if "gravy" in requested:
                result["gravy"] = round(pa.gravy(), 4)

            if "instability_index" in requested:
                ii = pa.instability_index()
                result["instability_index"] = round(ii, 2)
                result["stability"] = "stable" if ii < 40 else "unstable"

            if "amino_acid_composition" in requested:
                result["amino_acid_composition_percent"] = {
                    aa: round(pct, 1)
                    for aa, pct in pa.amino_acids_percent.items()
                }

        except Exception:
            # Fall back to manual path below
            pass

    # --- Manual fallback for any not yet computed ---
    if "molecular_weight" in requested and "molecular_weight_kda" not in result:
        mw = sum(_AA_MASS.get(aa, 0.0) for aa in seq)
        mw -= 18.015 * (len(seq) - 1)  # water removal
        result["molecular_weight_kda"] = round(mw / 1000.0, 2)

    if "isoelectric_point" in requested and "isoelectric_point" not in result:
        result["isoelectric_point"] = _compute_pi(seq)

    if "extinction_coefficient" in requested and "extinction_coefficient_M-1cm-1" not in result:
        result["extinction_coefficient_M-1cm-1"] = _compute_extinction(seq)

    if "gravy" in requested and "gravy" not in result:
        result["gravy"] = round(_compute_gravy(seq), 4)

    if "instability_index" in requested and "instability_index" not in result:
        ii = round(_compute_instability_index(seq), 2)
        result["instability_index"] = ii
        result["stability"] = "stable" if ii < 40 else "unstable"

    if "amino_acid_composition" in requested and "amino_acid_composition_percent" not in result:
        n = len(seq)
        result["amino_acid_composition_percent"] = {
            aa: round(seq.count(aa) / n * 100, 1)
            for aa in sorted(set(seq))
        }

    # --- Chou-Fasman (always pure-Python) ---
    if "secondary_structure" in requested:
        result["secondary_structure"] = _chou_fasman(seq)

    # --- Disorder (always pure-Python simplified IUPred) ---
    if "disorder" in requested:
        result["disorder"] = _iupred_disorder(seq)

    result["sequence_preview"] = seq[:60] + ("..." if len(seq) > 60 else "")
    return result


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="predict_properties",
    description=(
        "Predict physicochemical properties of a protein sequence: "
        "molecular weight, isoelectric point, extinction coefficient, "
        "GRAVY hydrophobicity, instability index, Chou-Fasman secondary "
        "structure propensity, disorder prediction (simplified IUPred), "
        "and amino-acid composition."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Amino acid sequence (single-letter code, e.g. MKYLLPTAAAGLLLL)",
            },
            "properties": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "molecular_weight",
                        "isoelectric_point",
                        "extinction_coefficient",
                        "gravy",
                        "instability_index",
                        "secondary_structure",
                        "disorder",
                        "amino_acid_composition",
                    ],
                },
                "description": "Which properties to compute. If omitted, all are computed.",
            },
        },
        "required": ["sequence"],
    },
    handler=predict_properties,
    category="analysis",
    timeout_seconds=60,
    errors=[
        {
            "reason": "invalid_input",
            "code": "EMPTY_SEQUENCE",
            "when": "sequence parameter is empty or contains only whitespace",
            "recovery": "Provide a valid amino acid sequence using single-letter codes.",
        },
        {
            "reason": "validation_failed",
            "code": "INVALID_AA",
            "when": "sequence contains non-standard amino acid characters",
            "recovery": (
                "Ensure sequence uses only standard 20 amino acid letters "
                "(ACDEFGHIKLMNPQRSTVWY)."
            ),
        },
        {
            "reason": "compute_error",
            "code": "COMPUTATION_FAILED",
            "when": "internal calculation error (e.g. empty sequence after cleanup)",
            "recovery": "Check the input sequence and retry.",
        },
    ],
)
