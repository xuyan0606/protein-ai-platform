---
name: enzyme_kinetics
description: >
  Engineering enzyme catalytic properties — improving kcat, Km, kcat/Km,
  substrate specificity, and understanding stability-activity tradeoffs.
  Triggers: "kcat", "Km", "catalytic efficiency", "specific activity",
  "比活力", "酶活", "enzyme activity", "turnover", "substrate specificity"
category: engineering
tags: [kinetics, kcat, Km, activity, specificity, tradeoff]
triggers:
  - kcat
  - Km
  - activity
  - 酶活
  - 比活力
  - catalytic
  - turnover
  - specificity
---

# Enzyme Kinetics Engineering — Principles and Strategies

## Core Principles

### 1. Stability-Activity Tradeoff
This is the CENTRAL challenge in enzyme engineering:
- Stabilizing mutations often reduce conformational flexibility needed for
  catalysis
- Active site dynamics are essential for substrate binding, transition state
  stabilization, and product release
- **Rule of thumb**: Mutations >12 Å from the active site rarely affect
  activity; mutations <8 Å must be carefully evaluated

### 2. Improving Catalytic Efficiency (kcat/Km)
- **Transition state stabilization**: Strengthen interactions with the
  transition state more than the ground state
- **Product release enhancement**: Reduce product inhibition by weakening
  product binding (common bottleneck in glycoside hydrolases)
- **Proton transfer optimization**: Align catalytic acid/base pKa with the
  reaction pH

### 3. Substrate Specificity Engineering
- Active site pocket reshaping: mutate residues lining the substrate binding
  pocket
- Loop remodeling near the active site entrance
- For GH13 α-amylases: the -1 and +1 subsites are most critical for
  substrate recognition

### 4. pH-Activity Relationship
- Measure activity at pH 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0 to map the
  full pH-activity curve
- kcat/Km vs pH reveals catalytic residue pKa values
- The pH optimum ≠ protein pI — it depends on catalytic residue protonation
  state, not overall charge

## Assay Design for Engineering Campaigns
- Primary screen: high-throughput activity assay at both target pH and
  original pH
- Secondary screen: kcat, Km, kcat/Km for top 10% of hits
- Tertiary screen: Tm, t1/2 at target temperature, pH stability
- Final candidates: full kinetic characterization + structural validation

## Key Metrics
- kcat/Km: the true measure of catalytic efficiency
- pH 4.0/6.0 activity ratio: target >0.5 for successful pH shift
- Residual activity after 24h at target pH and temperature
