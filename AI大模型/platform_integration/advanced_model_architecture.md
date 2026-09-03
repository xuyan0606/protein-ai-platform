# Advanced Model Architecture

P62 starts the top-tier model direction while staying local-only and
fail-closed.

## Target Architecture

- Sequence PLM embedding slot: ESM2 / ESM C style embeddings.
- Structure-aware embedding slot: SaProt or equivalent structure-aware tokens.
- MSA/conservation slot: MMseqs2 or trusted cache with database version and
  checksums.
- Structure GNN slot: residue-neighborhood graph around the mutation site.
- ddG slot: ThermoMPNN baseline, then Rosetta/PyRosetta/FoldX when licensed and
  runtime-verified.
- Feedback calibration slot: KWB wet-lab and plate-level feedback only.
- Multi-head prediction: mutation rank, stability, activity safety,
  substrate fit, assay success.
- Decision layer: Pareto front, uncertainty, evidence tier and Go/Watch/No-Go.

## Current Implementation

`prototype/kwb_enzyme_designer_advanced_model.py` is an interface and behavior
scaffold. It computes deterministic placeholder head scores from available
modalities and reports missing modalities explicitly.

It does not contain trained neural weights.

## No Shortcuts

- No fabricated MSA.
- No copied model outputs as wet-lab labels.
- No Rosetta/FoldX claims without artifacts.
- No customer or production claim while `safe_for_model_claim=false`.

## Next Code Steps

1. Add feature-cache writers for PLM, MSA, structure graph and ddG artifacts.
2. Add adapter interfaces for ESM/SaProt/ThermoMPNN/Rosetta/FoldX.
3. Add ranking metrics and calibration reports once reviewed labels exist.
4. Train heads only after P61 unlock requirements pass.
