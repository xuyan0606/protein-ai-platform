---
name: thermostability
description: >
  Engineering protein thermostability — improving Tm, half-life at elevated
  temperature, and thermal unfolding resistance. Covers disulfide engineering,
  hydrophobic core packing, helix stabilization, Gly→Pro substitutions,
  and salt bridge optimization.
  Triggers: "thermostability", "Tm", "melting temperature", "heat resistance",
  "thermal stability", "耐热", "热稳定", "temperature", "unfolding"
category: engineering
tags: [thermostability, Tm, disulfide, packing, unfolding]
triggers:
  - thermostability
  - Tm
  - thermal
  - heat
  - 耐热
  - 热稳定
  - temperature
  - unfolding
  - melting
---

# Thermostability Engineering — Principles and Strategies

## Core Principles

### 1. Disulfide Bond Engineering (Most Potent)
Introducing Cys-Cys pairs is the single most effective stabilization strategy:
- **Typical Tm increase**: 5-15°C per additional disulfide
- **Design rules**:
  - Cα-Cα distance < 6.0 Å between candidate sites
  - Cβ-Cβ distance < 4.5 Å
  - Avoid catalytic/binding site residues
  - Target flexible loops or domain interfaces
  - Gly/Ser → Cys is usually well-tolerated
- **Warning**: Wrong disulfide placement can cause misfolding → always validate
  with MD simulation

### 2. Hydrophobic Core Optimization
- Cavity-filling mutations: small→large hydrophobic (A→V/L/I, V→I/L)
- Core repacking with computational design tools (Rosetta, FoldX)
- Expected ΔTm: 2-5°C per optimized cavity
- Must check for steric clashes and backbone strain

### 3. Helix and Loop Stabilization
- **Gly→Pro/Pro** in loops and helix termini: reduces backbone entropy
  - Expected ΔTm: 2-8°C per Pro introduction
  - Target: Gly residues in flexible loops (B-factor > 40)
- **Helix capping**: N-cap (Ser/Thr/Asn) and C-cap (Gly) motifs
- **Helix dipole stabilization**: D/E at N-terminus, K/R at C-terminus

### 4. Salt Bridge Network Engineering
- Surface salt bridges: D/E paired with R/K at 2.5-4.0 Å
- Salt bridge networks (3+ residues) are especially stabilizing
- Expected ΔTm: 3-5°C per network
- More effective at high temperatures due to reduced dielectric constant

### 5. Other Stabilizing Strategies
- Loop truncation: remove unnecessary surface loops (if not functional)
- Oligomerization interface optimization: strengthen subunit contacts
- Metal binding site introduction: Ca²⁺/Zn²⁺ binding adds stability
- Glycosylation site introduction (for eukaryotic expression)

## Stability-Activity Tradeoff
**CRITICAL**: Thermostability mutations often reduce catalytic activity:
- Rigidifying mutations near the active site reduce conformational flexibility
  needed for catalysis
- Solution: prioritize mutations in regions FAR from the active site (>15 Å)
- Always measure both Tm AND kcat/Km for each mutant

## Priority Order for Thermostability Engineering
1. Disulfide bonds (highest impact, moderate risk)
2. Cavity-filling in hydrophobic core (high impact, low risk)
3. Gly→Pro in surface loops (moderate impact, low risk)
4. Surface salt bridges (moderate impact, very low risk)
5. Helix capping/N-cap optimization (low impact, very low risk)

## Key Metrics
- Tm measurement: DSC (gold standard), DSF (high-throughput screen)
- Half-life (t1/2) at target temperature
- Residual activity after thermal challenge (e.g., 30 min at 60°C)
- Reversibility of thermal unfolding
