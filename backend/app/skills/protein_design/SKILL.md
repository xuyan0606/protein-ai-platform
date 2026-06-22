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

### Step 4: Validate Designs
1. `esmfold_folding`: Predict structures and assess foldability (pLDDT > 70)
2. Check for:
   - Aggregation-prone regions
   - Stability metrics
   - Expression feasibility

## Expected Outputs
| Step | Tool | Output |
|------|------|--------|
| 1 | `sequence_search` | Target structure/properties |
| 2 | `predict_properties` | Baseline properties |
| 3 | Design tools | Candidate sequences |
| 4 | `esmfold_folding` | Predicted structures |
| 5 | Validation | pLDDT, stability scores |

## Decision Tree
- Binder design with known target structure → use structure-based design
- Sequence optimization without structure → sequence-based approaches
- De novo design from scratch → AI generative models
- Improve existing protein → mutation scanning + iterative optimization
