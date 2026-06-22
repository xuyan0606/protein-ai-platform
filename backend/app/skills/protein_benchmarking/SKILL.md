---
name: protein_benchmarking
description: >
  Comparative protein analysis — benchmark query protein against known
  homologs using BLAST, MSA, structural alignment, and conservation analysis.
  Triggers: "compare", "homolog", "benchmark", "MSA", "conservation",
  "alignment", "family", "同源", "比对", "保守"
category: analysis
tags: [benchmark, MSA, homology, conservation, structural_alignment]
triggers:
  - compare
  - homolog
  - benchmark
  - MSA
  - alignment
  - 同源
  - 比对
  - 保守
  - family
---

# Protein Benchmarking — Comparative Analysis Protocol

## Protocol for Deep Enzyme Characterization

### Step 1: Family Identification
- Run BLAST against Swiss-Prot to identify the enzyme family (e.g., GH13)
- Extract EC number, catalytic mechanism, and known structural features
- Identify the closest characterized homologs (>40% identity preferred)

### Step 2: Multiple Sequence Alignment (MSA)
- Align query with top 10-20 BLAST hits
- Identify:
  - Absolutely conserved residues (likely catalytic or structural)
  - Family-specific conserved motifs
  - Variable regions (safe engineering targets)
  - Insertion/deletion regions

### Step 3: Structural Comparison
- If experimental structures exist for homologs:
  - Superimpose structures (TM-align or similar)
  - Calculate RMSD for catalytic residues (<1.0 Å expected)
  - Map conserved surface patches (likely functional)
  - Identify structural differences in loops and surface regions

### Step 4: Conservation Scoring
- Per-residue ConSurf score or equivalent (1-9 scale)
- Map scores onto the predicted structure
- Color-code: Red (conserved, do not mutate), Yellow (moderate), Green (variable, safe)

### Step 5: Benchmark Metrics
- Compare key properties against characterized family members:
  - Optimal pH range
  - Temperature optimum
  - Specific activity on standard substrates
  - Known mutations that altered pH/stability/activity
  - Structural features unique to the query

## Known Family-Specific Information

### GH13 α-Amylase Family
- EC 3.2.1.1
- Catalytic mechanism: Retaining (double displacement)
- Catalytic residues: Asp (nucleophile), Glu (acid/base), Asp (stabilizer)
- Conserved regions: 4-7 (varies by subfamily)
- Ca²⁺ binding: 1-3 conserved sites
- Substrate: α-1,4-glucan (starch, amylose, amylopectin)
- Domain architecture: A (catalytic TIM barrel), B (small, variable), C
  (C-terminal β-sandwich)
- Known pH engineering successes:
  - Bacillus licheniformis α-amylase: surface K→E mutations shifted pH
    optimum from 6.5 to 5.0
  - Aspergillus oryzae α-amylase: His→Asn near active site improved acid
    stability
- Key references: Nielsen et al. (2001), Shaw et al. (1999), Bessler et al.
  (2003)

### Common pH Engineering Targets in GH13
1. Domain B loop residues (residues ~170-210 in most α-amylases)
2. Surface residues near the substrate binding cleft entrance
3. Residues interacting with the catalytic acid/base Glu
4. Ca²⁺-binding loop (DO NOT mutate the coordinating residues)

## Output Format for Benchmark Reports
```
## Enzyme Family: [Family Name]
- EC: [Number]
- Closest homolog: [Name] ([Identity]% identity)
- Catalytic residues: [List with positions]
- Conserved motifs: [List]
- Variable regions: [List with residue numbers]
- Engineering-safe regions: [List with rationale]
- Known engineering successes: [List with literature references]
```
