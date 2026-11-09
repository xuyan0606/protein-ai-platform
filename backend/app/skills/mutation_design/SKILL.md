---
name: mutation_design
description: >
  Systematic mutation design methodology — how to select residues, choose
  substitutions, prioritize candidates, and validate experimentally.
  Triggers: "mutation design", "which residues to mutate", "mutant library",
  "site-saturation", "rational design", "residue selection", "targeting"
category: engineering
tags: [mutation, rational_design, library, screening, priority]
triggers:
  - mutate
  - mutation
  - mutant
  - library
  - saturation
  - rational design
  - residue
  - substitution
---

# Mutation Design — Systematic Methodology

## Residue Selection Framework

### Multi-Dimensional Scoring (5 Dimensions)
Every candidate residue is scored 0-10 on each dimension:

1. **Surface Exposure** (ASA %)
   - 10: >80% exposed (excellent target, low risk)
   - 5: 30-80% (moderate, may affect local packing)
   - 0: <30% (buried — high risk, avoid unless core engineering)

2. **Distance from Active Site** (Å)
   - 10: >20 Å (distant, very safe)
   - 5: 10-20 Å (moderate — check for allosteric effects)
   - 0: <10 Å (active site proximal — HIGH risk to activity)

3. **Evolutionary Conservation** (ConSurf score)
   - 10: Variable (score 1-3, safe to mutate)
   - 5: Average (score 4-6, check function)
   - 0: Conserved (score 7-9, likely essential — DO NOT MUTATE)

4. **Mutation ΔΔG** (kcal/mol, predicted)
   - 10: Stabilizing (ΔΔG < -1.0)
   - 5: Neutral (-1.0 to +1.0)
   - 0: Destabilizing (> +1.0, avoid)

5. **Functional Relevance** (known/predicted)
   - 10: No known function in the region
   - 5: Part of a functional domain but not the core
   - 0: Catalytic, substrate-binding, metal-binding, or structurally essential

### Composite Priority Score
```
Priority = (ASA_score × 0.20) + (Distance_score × 0.25) +
           (Conservation_score × 0.25) + (ΔΔG_score × 0.15) +
           (Functional_score × 0.15)
```
Residues with Priority > 7.0 are Tier 1 candidates.
Residues with Priority 5.0-7.0 are Tier 2 candidates.

## Residue Categories: NEVER Mutate
1. Catalytic triad/center residues (for α-amylase: Asp, Glu, Asp)
2. Metal-binding residues (Ca²⁺, Zn²⁺ coordination)
3. Cysteine residues involved in disulfide bonds
4. cis-Proline residues (structural)
5. Gly residues with unusual φ/ψ angles
6. Totally invariant residues across the enzyme family (ConSurf 9)

## Residue Categories: High-Value Targets
1. Surface Lys/Arg in flexible loops → E/D/Q for pH lowering
2. Surface Gly in loops → Pro for thermostability
3. Unpaired Cys → removal or pairing
4. Core cavities → filling with larger hydrophobic residues
5. Surface Asn/Gln → Asp/Glu for acid resistance

## Experimental Design
- **Tier 1**: 5-8 single mutants (High Priority score)
- **Tier 2**: 3-5 single mutants + 2-3 combinatorial (Medium Priority)
- **Controls**: Wild-type, empty vector, known-inactive mutant
- **Replicates**: Minimum n=3 for activity assays
- **Screening order**: Primary (activity at both pH) → Secondary (kinetics)
  → Tertiary (stability) → Quaternary (structure validation)
