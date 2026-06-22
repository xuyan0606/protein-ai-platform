"""DiffDock molecular docking prediction — async GPU tool.

For MVP: implements a simplified docking score based on molecular property
analysis (ligand topology + protein binding-site estimation). Production
connects to the DiffDock public inference API or local GPU instance.

Calculates:
  - Docking score (estimated binding affinity)
  - Predicted binding-site residues
  - Confidence score
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import settings
from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Amino-acid property tables (for binding-site prediction)
# ---------------------------------------------------------------------------
# Residue binding propensity: higher = more likely in binding site
_BINDING_PROPENSITY: dict[str, float] = {
    "H": 0.42, "C": 0.37, "M": 0.28, "W": 0.28, "Y": 0.26,
    "F": 0.25, "R": 0.21, "K": 0.13, "N": 0.07, "Q": 0.06,
    "D": 0.06, "E": 0.05, "S": 0.05, "T": 0.05, "P": 0.04,
    "L": 0.04, "I": 0.04, "V": 0.03, "A": 0.03, "G": 0.01,
}

# Amino-acid volumes (for pocket detection)
_AA_VOLUME: dict[str, float] = {
    "A": 88.6, "R": 173.4, "N": 117.7, "D": 111.1, "C": 108.5,
    "Q": 143.9, "E": 138.4, "G": 60.1,  "H": 153.2, "I": 166.7,
    "L": 166.7, "K": 168.6, "M": 162.9, "F": 189.9, "P": 122.7,
    "S": 89.0,  "T": 116.1, "W": 227.8, "Y": 193.6, "V": 140.0,
}

# Kyte-Doolittle hydropathy
_KD: dict[str, float] = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "E": -3.5, "Q": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}


# ---------------------------------------------------------------------------
# Ligand property estimation from SMILES  (simplified)
# ---------------------------------------------------------------------------

def _ligand_properties_from_smiles(smiles: str) -> dict[str, Any]:
    """Estimate ligand molecular properties from SMILES string.

    Calculates: molecular weight, logP, H-bond donors/acceptors, rotatable bonds,
    ring count, atom count, and topological polar surface area (tPSA) estimate.
    """
    # Atom type counts
    carbons = len(re.findall(r"[cC](?![laros])", smiles))
    # Include aromatic carbons
    carbons += len(re.findall(r"[cC]", smiles))

    nitrogens = len(re.findall(r"[nN]", smiles))
    oxygens = len(re.findall(r"[oO]", smiles))
    sulfurs = len(re.findall(r"s", smiles))
    halogens = len(re.findall(r"[FClBrI]", smiles))
    phosphorus = len(re.findall(r"P", smiles))

    # Heavy atom count
    heavy_atoms = carbons + nitrogens + oxygens + sulfurs + halogens + phosphorus

    # Count H-bond donors: OH, NH, SH
    hbd = len(re.findall(r"[OH]|N[H]|SH", smiles))

    # Count H-bond acceptors: O, N (not in amides? simplified)
    hba = oxygens + nitrogens

    # Count rings (simplified: count ring closures from numbers in SMILES)
    ring_numbers = re.findall(r"\d", smiles)
    ring_count = len(set(ring_numbers)) if ring_numbers else 0

    # Estimate double/triple bonds
    double_bonds = len(re.findall(r"=", smiles))
    triple_bonds = len(re.findall(r"#", smiles))

    # Rotatable bonds: single bonds between heavy atoms (not in rings) — rough estimate
    rotatable = max(0, heavy_atoms - ring_count * 2 - 2)

    # MW estimate (atomic masses)
    MW_C = 12.01
    MW_N = 14.01
    MW_O = 16.00
    MW_S = 32.07
    MW_F = 19.00
    MW_Cl = 35.45
    MW_Br = 79.90
    MW_I = 126.90
    MW_P = 30.97
    MW_H = 1.008

    # Estimate H count from heavy atoms and bonds
    h_count = heavy_atoms * 2 - double_bonds * 2 - triple_bonds * 4 + ring_count * 2
    h_count = max(0, h_count)

    mw = (
        carbons * MW_C + nitrogens * MW_N + oxygens * MW_O +
        sulfurs * MW_S + halogens * MW_F + phosphorus * MW_P + h_count * MW_H
    )

    # Simplified tPSA estimate
    tpsa = (
        nitrogens * 3.24 + oxygens * 17.07 + sulfurs * 25.3
        + phosphorus * 9.81
    )

    # Simplified logP estimate (rough)
    logp = (
        0.5 * carbons
        - 0.5 * nitrogens
        - 1.0 * oxygens
        + 0.5 * sulfurs
        + 0.5 * halogens
    ) / max(heavy_atoms, 1) * 5

    return {
        "molecular_weight": round(mw, 1),
        "heavy_atoms": heavy_atoms,
        "h_bond_donors": hbd,
        "h_bond_acceptors": hba,
        "rotatable_bonds": rotatable,
        "ring_count": ring_count,
        "tpsa_estimate": round(tpsa, 1),
        "logP_estimate": round(max(-3, min(7, logp)), 1),
        "lipinski_violations": sum([
            1 if mw > 500 else 0,
            1 if logp > 5 else 0,
            1 if hbd > 5 else 0,
            1 if hba > 10 else 0,
        ]),
    }


# ---------------------------------------------------------------------------
# Binding-site prediction from PDB
# ---------------------------------------------------------------------------

def _parse_pdb_sequence(pdb_text: str) -> str | None:
    """Extract amino-acid sequence from PDB ATOM records (CA atoms only)."""
    seq_parts: list[str] = []
    current_res = None
    current_chain = None

    for line in pdb_text.split("\n"):
        if not line.startswith("ATOM"):
            continue
        if len(line) < 22:
            continue
        atom_name = line[12:16].strip()
        if atom_name != "CA":
            continue

        res_name = line[17:20].strip()
        chain = line[21:22].strip() if len(line) > 21 else "A"
        res_num = line[22:26].strip()

        # Convert 3-letter to 1-letter code
        aa_map = {
            "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
            "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
            "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
            "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
        }
        aa = aa_map.get(res_name, "X")

        key = (chain, res_num)
        if key != current_res or chain != current_chain:
            seq_parts.append(aa)
            current_res = key
            current_chain = chain

    return "".join(seq_parts) if seq_parts else None


def _predict_binding_site(sequence: str) -> dict[str, Any]:
    """Predict likely binding-site residues based on residue properties.

    Uses a simple sliding-window propensity score combining:
      - Binding propensity (empirical frequency in binding sites)
      - Sequence conservation proxies (hydropathy clusters)
      - Surface exposure proxies (hydrophilicity)

    Returns top-ranked residues and regions.
    """
    n = len(sequence)
    if n == 0:
        return {
            "predicted_residues": [],
            "predicted_regions": [],
            "confidence": "low",
        }

    # Per-residue binding score
    scores: list[float] = []
    for aa in sequence:
        bp = _BINDING_PROPENSITY.get(aa, 0.05)
        hp = _KD.get(aa, 0.0)
        # Negatively charged / polar in hydrophilic patch → higher binding
        if hp < 0 and aa in "RHKDE":
            bp += 0.05
        # Aromatic → often at interfaces
        if aa in "WYFH":
            bp += 0.03
        scores.append(bp)

    # Smooth with window
    window = 9
    half = window // 2
    smoothed: list[float] = []
    for i in range(n):
        total = 0.0
        count = 0
        for j in range(max(0, i - half), min(n, i + half + 1)):
            total += scores[j]
            count += 1
        smoothed.append(total / count)

    # Top-ranked residues (top 25% or at least 5)
    threshold = sorted(smoothed, reverse=True)[max(0, n // 4 - 1)] if n > 0 else 0
    top_residues = [
        {"position": i + 1, "residue": sequence[i], "binding_score": round(smoothed[i], 3)}
        for i in range(n)
        if smoothed[i] >= threshold
    ]

    # Find contiguous binding regions (>= 3 consecutive top residues)
    regions: list[dict] = []
    in_region = False
    start = 0
    for i in range(n):
        if smoothed[i] >= threshold and not in_region:
            start = i
            in_region = True
        elif smoothed[i] < threshold and in_region:
            length = i - start
            if length >= 3:
                regions.append({
                    "start": start + 1,
                    "end": i,
                    "length": length,
                    "sequence": sequence[start:i],
                    "mean_score": round(sum(smoothed[start:i]) / length, 3),
                })
            in_region = False
    if in_region:
        length = n - start
        if length >= 3:
            regions.append({
                "start": start + 1,
                "end": n,
                "length": length,
                "sequence": sequence[start:],
                "mean_score": round(sum(smoothed[start:]) / length, 3),
            })

    # Confidence
    max_score = max(smoothed) if smoothed else 0
    conf = "high" if max_score > 0.3 else "medium" if max_score > 0.15 else "low"

    return {
        "predicted_residues": top_residues[:20],  # top 20
        "predicted_regions": regions,
        "confidence": conf,
    }


def _estimate_affinity(
    ligand_props: dict[str, Any],
    binding_site: dict[str, Any],
) -> dict[str, Any]:
    """Estimate binding affinity from ligand and binding-site properties.

    Simplified free-energy scoring function combining:
      - Ligand size/contact area
      - Polarity complementarity
      - Estimated desolvation cost
    """
    # Contact area proxy
    contact_atoms = min(ligand_props["heavy_atoms"], 40)
    contact_area = contact_atoms * 12  # ~12 A^2 per heavy atom contact

    # Ligand desolvation penalty
    desolv = ligand_props["tpsa_estimate"] * 0.02

    # Hydrogen bond contribution
    hb_contribution = -(ligand_props["h_bond_donors"] + ligand_props["h_bond_acceptors"]) * 0.5

    # Hydrophobic effect (if ligand has low tPSA and protein has hydrophobic pocket)
    hydrophobicity = -0.2 * (1 - ligand_props["tpsa_estimate"] / max(ligand_props["molecular_weight"], 1))

    # Lipinski penalty
    lipinski_penalty = ligand_props.get("lipinski_violations", 0) * 0.8

    # Free energy estimate (kcal/mol)
    dG = (
        -0.2 * contact_atoms
        + desolv
        + hb_contribution
        + hydrophobicity
        + lipinski_penalty
    )

    # Clip to reasonable range
    dG = max(-14, min(0, round(dG, 1)))

    # Convert to binding affinity (Kd in nM)
    # dG = -RT ln(Kd)  =>  Kd = exp(-dG / (RT))
    # RT ≈ 0.593 kcal/mol at 298K
    RT = 0.593
    Kd_nM = math.exp(-dG / RT)
    # Clip to reasonable range (0.1 nM to 1M)
    Kd_nM = max(0.1, min(1e9, Kd_nM))

    # Format Kd
    if Kd_nM < 1:
        kd_str = f"{Kd_nM * 1000:.1f} pM"
    elif Kd_nM < 1000:
        kd_str = f"{Kd_nM:.1f} nM"
    elif Kd_nM < 1e6:
        kd_str = f"{Kd_nM / 1000:.1f} uM"
    else:
        kd_str = f"{Kd_nM / 1e6:.1f} mM"

    # Confidence based on how drug-like the ligand is
    if ligand_props["lipinski_violations"] == 0 and 200 < ligand_props["molecular_weight"] < 500:
        conf = "medium"
    else:
        conf = "low"  # simplified model; real DiffDock would give high confidence

    return {
        "predicted_dG_kcal_per_mol": dG,
        "predicted_Kd": kd_str,
        "predicted_Kd_nM": round(Kd_nM, 1),
        "confidence": conf,
        "binding_site_confidence": binding_site.get("confidence", "unknown"),
    }


# ===================================================================
# Main diffdock_docking
# ===================================================================

async def diffdock_docking(
    ligand_smiles: str,
    protein_pdb: str,
) -> dict:
    """Predict protein-ligand docking using simplified molecular docking analysis.

    For MVP, calculates:
      - Ligand molecular properties from SMILES
      - Predicted binding-site residues from protein PDB
      - Estimated binding affinity (dG and Kd)

    Production backend connects to DiffDock public inference API.

    Args:
        ligand_smiles: SMILES string of the ligand molecule.
        protein_pdb: Protein structure in PDB format (text).

    Returns:
        Dict with docking_score, predicted_affinity, binding_site, ligand_properties.
    """
    smiles = ligand_smiles.strip()
    pdb = protein_pdb.strip()

    if not smiles:
        raise ValueError("EMPTY_LIGAND: ligand_smiles must not be empty")

    if not pdb:
        raise ValueError("EMPTY_PROTEIN: protein_pdb must not be empty")

    # Basic SMILES validation
    if not re.match(r"^[A-Za-z0-9\[\]\(\)=#:/\\.@+\-,\%]+$", smiles):
        raise ValueError(
            "INVALID_SMILES: the SMILES string contains unexpected characters. "
            "Provide a valid SMILES representation."
        )

    # Basic PDB validation
    has_atom = any(line.startswith("ATOM") or line.startswith("HETATM") for line in pdb.split("\n"))
    if not has_atom:
        raise ValueError(
            "INVALID_PDB: protein_pdb must contain ATOM or HETATM records in PDB format."
        )

    # --- Ligand property analysis ---
    ligand_props = _ligand_properties_from_smiles(smiles)

    # --- Protein binding-site prediction ---
    protein_seq = _parse_pdb_sequence(pdb)
    if protein_seq:
        binding_site = _predict_binding_site(protein_seq)
    else:
        binding_site = {
            "predicted_residues": [],
            "predicted_regions": [],
            "confidence": "unknown",
            "error": "Could not parse sequence from PDB",
        }

    # --- Affinity prediction ---
    affinity = _estimate_affinity(ligand_props, binding_site)

    # --- Combined docking score (0-100 scale) ---
    # Normalize: best possible dG = -14 kcal/mol
    dG_norm = (affinity["predicted_dG_kcal_per_mol"] + 14) / 14  # 0 to 1
    docking_score = round(dG_norm * 100, 1)

    return {
        "docking_score": docking_score,
        "docking_score_interpretation": (
            "excellent" if docking_score >= 80 else
            "good" if docking_score >= 60 else
            "moderate" if docking_score >= 40 else
            "weak"
        ),
        "predicted_affinity": affinity,
        "binding_site": binding_site,
        "ligand_properties": ligand_props,
        "model": "Simplified Docking (MVP)",
        "note": (
            "MVP uses simplified molecular docking scoring. "
            "For production accuracy, connect to DiffDock GPU inference API."
        ),
    }


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="diffdock_docking",
    description=(
        "Predict protein-ligand binding using simplified molecular docking. "
        "Analyzes ligand SMILES for drug-likeness (Lipinski rules), predicts "
        "protein binding-site residues from PDB structure, and estimates "
        "binding affinity (delta-G and Kd). Production backend: DiffDock GPU inference."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ligand_smiles": {
                "type": "string",
                "description": "SMILES representation of the ligand molecule",
            },
            "protein_pdb": {
                "type": "string",
                "description": "Protein structure in PDB format (ATOM records)",
            },
        },
        "required": ["ligand_smiles", "protein_pdb"],
    },
    handler=diffdock_docking,
    is_async=True,
    category="docking",
    timeout_seconds=60,
    annotations={
        "gpu_required": False,
        "production_gpu_required": True,
        "estimated_duration_mvp": "1-5 seconds",
        "estimated_duration_production": "30-300 seconds",
    },
    errors=[
        {
            "reason": "invalid_input",
            "code": "EMPTY_LIGAND",
            "when": "ligand_smiles is empty or whitespace-only",
            "recovery": "Provide a valid SMILES string for the ligand molecule.",
        },
        {
            "reason": "invalid_input",
            "code": "EMPTY_PROTEIN",
            "when": "protein_pdb is empty or whitespace-only",
            "recovery": "Provide valid PDB format text with ATOM records.",
        },
        {
            "reason": "invalid_input",
            "code": "INVALID_SMILES",
            "when": "the SMILES string contains unexpected characters",
            "recovery": "Verify the SMILES string is valid (e.g. use an online SMILES validator).",
        },
        {
            "reason": "invalid_input",
            "code": "INVALID_PDB",
            "when": "protein_pdb does not contain ATOM/HETATM records",
            "recovery": "Provide a valid PDB structure file with atomic coordinates.",
        },
        {
            "reason": "compute_error",
            "code": "DOCKING_FAILED",
            "when": "ligand or protein processing failed",
            "recovery": "Check input formats and retry. For large structures, trim to binding region.",
        },
    ],
)
