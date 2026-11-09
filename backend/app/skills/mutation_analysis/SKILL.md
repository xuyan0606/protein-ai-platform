---
name: mutation_analysis
description: |
  Analyze protein mutations by predicting property changes, stability effects,
  and functional impacts. Use when the user asks about mutations, variants,
  mutagenesis, or wants to understand how changing a residue affects a protein.
  Triggers: "analyze mutation", "mutation effect", "mutant", "variant", "ddG",
  "site-directed mutagenesis", "point mutation", "substitution"
category: analysis
tags: [mutation, stability, ddG, variant]
triggers:
  - mutation
  - mutant
  - variant
  - ddG
  - mutagenesis
  - substitution
  - point mutation
---

# Mutation Analysis

## When to Use
- User provides a protein sequence and wants to scan mutation effects
- User asks about a specific point mutation (e.g., "R248Q in p53")
- User wants to identify stabilizing or destabilizing mutations
- User needs to understand the functional impact of a variant

## Workflow

### Step 1: Understand the Mutation
Parse the user's input to identify:
- Protein sequence or accession
- Mutation position and type (if specific)
- Goal: stability, function, binding change?

### Step 2: Run Mutation Scan
Use the `mutation_scan` tool to systematically evaluate single-point mutations.
The tool returns ΔΔG values for each possible mutation at each position.

### Step 3: Analyze Results
Key metrics:
- ΔΔG < -1.0 kcal/mol: Stabilizing mutation
- ΔΔG > 2.0 kcal/mol: Destabilizing mutation
- ΔΔG between -1 and 2: Neutral effect

### Step 4 (Optional): Structure Prediction
For key mutations, run `esmfold_folding` to visualize structural changes.

## Expected Outputs
| Step | Tool | Output |
|------|------|--------|
| 1 | `sequence_search` | Protein metadata |
| 2 | `mutation_scan` | ΔΔG values for all positions |
| 3 | `predict_properties` | Property comparison (WT vs mutant) |
| 4 | `esmfold_folding` | PDB structure for visualization |

## Error Handling
| Symptom | Cause | Solution |
|---------|-------|---------|
| Tool returns empty | Invalid sequence format | Validate FASTA format |
| ΔΔG values all 0 | Sequence too short | Minimum 20 residues |
| Timeout | Large protein | Use sliding window approach |
