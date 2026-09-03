# KWB-EnzymeDesigner v2.3.0 Feature Cache Adapters

## Purpose

This card records the P63 advanced feature cache and adapter scaffold.

## Added

- advanced feature cache manifest schema
- adapter scaffold base class
- feature cache plan report
- adapter requirement JSONL
- cache roots for PLM, MSA, structure graph, ddG, complex/affinity, kinetics/function, candidate generation, benchmark and wet-lab feedback features
- GitHub/Google research watchlist mapped to local fail-closed adapters

## Current State

All feature families remain blocked until real runtime/license/data/model gates
pass. This version creates the landing zone for future top-tier features; it
does not generate those features.

Current technology level is not yet top-tier as a model-quality claim. The
system now knows where ESMC/ESM3, SaProt/ProSST, MMseqs2, ThermoMPNN,
Rosetta/PyRosetta/FoldX, Boltz-2, CatPred, LigandMPNN and ProteinGym-style
artifacts should land, but none of those artifacts are executable evidence yet.

## Implementation Priority

- P0: MSA/cache, reviewed structure graph, ProteinGym-style benchmark cache, KWB feedback calibration.
- P1: ThermoMPNN, Boltz-2, ESMC/SaProt/ProSST and CatPred adapters.
- P2: LigandMPNN/ProteinMPNN/RFdiffusion generation, behind human approval and biosecurity gates.

## Policy

No external model execution, no synthetic feature files, no model-quality claim.
