# Top-Tier Model Execution Board

P65 starts all architecture workstreams from the Google/GitHub research phase.

## Started Workstreams

- P0 MSA/cache validator.
- P0 reviewed structure graph builder.
- P0 ProteinGym-style benchmark cache.
- P0 KWB plate/well wet-lab feedback calibration.
- P1 Boltz-2 structure/affinity adapter.
- P1 ThermoMPNN/ThermoMPNN-D stability adapters.
- P1 ESMC/SaProt/ProSST representation adapters.
- P1 CatPred kinetics/function adapter.
- P2 LigandMPNN/ProteinMPNN candidate generation gate.
- P2 RFdiffusion2 enzyme scaffold generation gate.
- Cross-cutting Rosetta/PyRosetta/FoldX ddG backend gate.
- Cross-cutting license/runtime/model-weight governance gate.

## Execution Rule

All workstreams are local starts only. A start packet is not a reviewed decision,
not a runtime approval, not a model-quality claim and not a production release.

## Current Expected State

The normal state is `started_blocked`. Workstreams become ready only after their
real artifacts exist and their validators pass.

## Forbidden Shortcuts

- Do not generate fake MSA, embeddings, ddG, kinetics or benchmark scores.
- Do not mark AlphaFold 3, Rosetta/PyRosetta/FoldX, ProSST, CLEAN or RFdiffusion2
  as commercial-ready without legal/runtime/model-weight evidence.
- Do not export order-ready or customer-ready sequences from candidate generation.
- Do not sync or deploy production without explicit authorization.
