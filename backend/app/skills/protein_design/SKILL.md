---
name: protein_design
description: |
  Design novel proteins including binder design, sequence generation, and
  backbone optimization. Use when the user asks about designing new proteins,
  creating binders, optimizing sequences, or de novo protein generation.
  Triggers: "design protein", "binder", "de novo", "generate sequence",
  "optimize", "backbone", "scaffold"
category: design
tags: [design, binder, sequence_generation, backbone]
triggers:
  - design
  - binder
  - de novo
  - generate
  - scaffold
  - backbone
  - optimize sequence
---

# Protein Design

## When to Use
- User wants to design a binder against a specific target
- User needs new protein sequences with desired properties
- User wants to optimize an existing sequence
- User asks about backbone generation

## Workflow

### Step 1: Define Design Goals
Identify:
- Target protein (if binding)
- Desired properties (stability, affinity, solubility)
- Constraints (length range, scaffold type)

### Step 2: Analyze Starting Point
If designing a binder:
1. Use `sequence_search` to find the target's structure
2. Use `predict_properties` to understand target properties

### Step 3: Generate Designs
For sequence design:
- Use appropriate design tools (ProteinMPNN for inverse folding, RFdiffusion for backbone generation)

For property optimization:
- Use `mutation_scan` to identify beneficial mutations
- Use `predict_properties` to validate designs

### Step 4: Validate Designs (Multi-Tool Cross-Validation)
1. `esmfold_folding`: Predict structures and assess foldability (pLDDT > 70)
2. **Cross-validate with a second structure predictor** (AlphaFold2 or OmegaFold)
   to catch single-model blind spots. Require consensus: both tools agree on fold (RMSD < 1.0Å)
3. Check for:
   - Aggregation-prone regions
   - Stability metrics
   - Expression feasibility
   - **Local environment changes near functional residues** (hydration, rigidity, electrostatics)

### Step 5: Functional Integrity Assessment (Redesign Tasks)
When redesigning an existing protein (e.g., ProteinMPNN inverse folding with locked residues):
- **Trade-off analysis**: compare original vs. designed on BOTH physicochemical properties
  (expression, solubility, Tm) AND functional activity (kcat, binding affinity, etc.)
- **Non-active-site risk**: mutations outside the functional site can still impair activity via:
  - Hydration shell disruption (altered water dynamics near functional surface)
  - Backbone rigidity/flexibility propagation to the active site
  - Long-range allosteric coupling from distal residues
- **Protective strategy**: preserve not only known functional residues but also their
  surrounding hydration shell and local backbone geometry (±5Å radius)
- Reference case: ProteinMPNN AFPIII redesign (BioRxiv 2026) — 100% expression success
  and +7°C Tm improvement, but thermal hysteresis activity dropped to 30-40% of WT
  despite all ice-binding site residues being locked

## Expected Outputs
| Step | Tool | Output |
|------|------|--------|
| 1 | `sequence_search` | Target structure/properties |
| 2 | `predict_properties` | Baseline properties |
| 3 | Design tools | Candidate sequences |
| 4 | `esmfold_folding` + cross-validation | Predicted structures + consensus |
| 5 | Functional integrity check | Trade-off table + risk assessment |
| 6 | Validation | pLDDT, stability scores, activity estimate |

## Decision Tree
- Binder design with known target structure → use structure-based design
- Sequence optimization without structure → sequence-based approaches
- De novo design from scratch → AI generative models (consider iTHR for ice-binding proteins)
- Improve existing protein → mutation scanning + iterative optimization
- Redesign scaffold while preserving function → ProteinMPNN with locked residues + cross-validation
