---
name: sequence_analysis
description: |
  Analyze protein sequences for physicochemical properties, homology, and
  functional annotations. Use when the user provides a protein sequence and
  wants to understand its properties or find related sequences.
  Triggers: "analyze sequence", "what is this protein", "sequence properties",
  "BLAST", "homology", "similar sequences", "FASTA"
category: analysis
tags: [sequence, properties, homology, BLAST]
triggers:
  - sequence
  - FASTA
  - BLAST
  - homology
  - similar
  - MW
  - pI
  - GRAVY
---

# Sequence Analysis

## When to Use
- User pastes a protein sequence and asks "what is this?"
- User wants MW, pI, GRAVY, instability index
- User needs to find homologous sequences
- User wants to annotate a protein sequence

## Workflow

### Step 1: Parse and Validate
Extract the protein sequence from user input (FASTA or raw).
Validate: only standard amino acids (ACDEFGHIKLMNPQRSTVWY).

### Step 2: Predict Properties
Use `predict_properties` to compute:
- Molecular weight (kDa)
- Isoelectric point (pI)
- GRAVY (hydropathy)
- Instability index
- Amino acid composition

### Step 3: Search for Similar Sequences
Use `sequence_search` to find:
- Homologous proteins in databases
- Known functional annotations
- Structural matches

### Step 4: Report
Compile into a structured report with property table and homology results.

## Expected Outputs
| Step | Tool | Output |
|------|------|--------|
| 1 | Parse input | Cleaned sequence |
| 2 | `predict_properties` | MW, pI, GRAVY, instability index, AA% |
| 3 | `sequence_search` | Similar sequences with identity/e-value |

## Interpretation Guide
- MW: < 10 kDa (peptide), 10-50 kDa (small protein), 50-100 kDa (medium), > 100 kDa (large)
- pI: < 5 (acidic), 5-7 (neutral), > 7 (basic)
- GRAVY: < 0 (hydrophilic), 0 to 1 (mixed), > 1 (hydrophobic)
- Instability index: < 40 (stable), > 40 (potentially unstable)
