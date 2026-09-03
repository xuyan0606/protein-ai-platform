# Advanced Feature Cache Plan

P63 defines where future top-tier model features land.

## Feature Families

- `sequence_plm_embeddings`: ESM2, ESM C, ESM3-open, SaProt, ProSST and ProtSSN embedding/token adapters.
- `msa_conservation`: MMseqs2, HMMER/HH profile, HH-suite profile or trusted MSA/conservation cache.
- `structure_graph`: reviewed chain mapping, structure tokens and residue-neighborhood graph.
- `ddg_stability`: ThermoMPNN, Rosetta, PyRosetta or FoldX ddG artifacts.
- `structure_affinity_complex`: Boltz-2, Chai-1 and AlphaFold 3 benchmark/isolated complex prediction artifacts.
- `kinetics_function`: CatPred kinetics and CLEAN/DeepEC-style EC/function consistency artifacts.
- `candidate_generation`: LigandMPNN, ProteinMPNN and RFdiffusion-family candidate generation artifacts.
- `benchmark_score_cache`: ProteinGym, FLIP/FLIP2, ATOM3D MSP, FireProtDB and ProThermDB evaluation artifacts.
- `wet_lab_feedback_calibration`: KWB experiment and plate feedback features.

## Cache Policy

Feature files are usable only when:

- source inputs are recorded
- runtime/license/data gates pass
- artifact checksums are present
- validator reports pass
- evidence tier is explicit

## Current Status

The cache plan is scaffold-only. Directories and manifests exist, but no feature
family is complete. This is not yet top-tier technology in the claimable sense:
the platform has landing zones for top-tier tools, but the real feature artifacts,
validators, licenses, runtimes and wet-lab calibration are still missing.

## Research Direction

Priority order for implementation:

- P0: MMseqs2/trusted MSA cache, reviewed structure graph, ProteinGym-style benchmark cache, KWB wet-lab feedback schema.
- P1: ThermoMPNN stability proxy, Boltz-2 complex/affinity adapter, ESMC/SaProt/ProSST embedding adapters, CatPred kinetics adapter.
- P2: LigandMPNN/ProteinMPNN/RFdiffusion candidate generation after protected-site, biosecurity and human approval gates.

AlphaFold 3, Rosetta/PyRosetta, FoldX, Chai-1, ProSST and CLEAN must remain
license/runtime-isolated until reviewed. RosettaFold or AlphaFold-style structure
prediction does not equal Rosetta ddG.

## Forbidden Shortcuts

- No fabricated embeddings.
- No single-sequence conservation.
- No predicted ddG as wet-lab labels.
- No Rosetta/FoldX claim without runtime artifacts.
- No production use without release and governance gates.
