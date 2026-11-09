---
name: ph_engineering
description: >
  Engineering protein pH optima — shifting optimal pH, improving acid/alkaline
  stability and activity. Covers surface charge engineering, catalytic residue
  pKa tuning, His-mediated pH switches, and acid-stabilizing mutations.
  Triggers: "pH", "最适pH", "acidic", "alkaline", "acid stability",
  "pH optimum", "protonation", "pKa", "acidophile", "alkaliphile"
category: engineering
tags: [pH, pKa, acid_stability, surface_charge, protonation]
triggers:
  - pH
  - acidic
  - alkaline
  - pKa
  - acid
  - 最适pH
  - 酸性
  - 碱性
  - 耐酸
  - 耐碱
---

# pH Engineering — Principles and Strategies

## Core Principles

### 1. Surface Charge Engineering (Most Effective & Safest)
The dominant strategy for shifting pH optimum is altering the enzyme's surface
electrostatic potential:

- **Lowering optimal pH** → Add negative surface charge (K/R → D/E/Q/N)
  - Classical example: Bacillus α-amylase pH optimum shifted from 6.0 to 4.5
    by mutating surface Lys/Arg to Glu/Asp
  - Each K→E mutation typically shifts local pKa by 0.5-1.0 units
  - Target solvent-exposed residues with ASA > 50%

- **Raising optimal pH** → Add positive surface charge (D/E → K/R/H)
  - Less common but used for alkaline adaptation

### 2. Catalytic Residue pKa Modulation
The active site's catalytic residues must maintain correct protonation at the
new pH:

- **Acid/base catalyst pKa shifts**: Mutate residues within 5-8 Å of the
  catalytic site to alter the local electrostatic environment
  - Adding negative charge near a catalytic acid (Glu/Asp) lowers its pKa
  - Removing positive charge near a catalytic base (His/Lys) raises its pKa

- **His residues are pH switches**: His has pKa ≈ 6.0 and is HIGHLY sensitive
  in the pH 4-7 range
  - If His is NOT catalytically essential but is near the active site,
    H→N/F/Q can eliminate pH-dependent activity loss
  - If His IS the catalytic residue, focus on modifying its microenvironment

### 3. GH13 α-Amylase Specific Strategies
- Conserved catalytic triad: Asp (nucleophile), Glu (proton donor), Asp
  (transition state stabilizer) — NEVER mutate these
- Ca²⁺ binding sites (usually 2-3 per molecule) — NEVER disrupt
- Key surface regions for charge engineering:
  - Domain B loop (often the most flexible and pH-sensitive region)
  - C-terminal β-sheet surface
  - Substrate binding groove entrance

### 4. Acid Stabilization
- Introduce additional salt bridges on the surface (D/E paired with R/K at
  appropriate distance)
- Replace acid-labile residues: Asn/Gln can deamidate at low pH →
  consider N→D, Q→E where structurally feasible
- Reduce flexible loops that may unfold at low pH — Pro introduction at loop
  termini

## Decision Tree for pH Lowering

1. Calculate pI of target protein
2. If pI > target pH → surface charge engineering is viable
3. Identify all solvent-exposed K/R (ASA > 50%)
4. Rank by distance from active site (mutate distant ones first)
5. Compute ΔΔG for K→E, K→Q, R→Q mutations
6. Select top 5-8 candidates that do NOT:
   - Contact the active site directly
   - Form critical salt bridges
   - Are conserved across the enzyme family
7. Experimental: test single mutants first, then combine best performers

## Key Metrics
- Target pH shift magnitude: 1 unit = 3-5 surface charge mutations; 2 units = 6-12
- Expected activity retention at new pH: 40-80% of wild-type Vmax at original pH
- Stability risk: Low for surface mutations (ΔΔG typically -0.5 to +2.0 kcal/mol)
