# Model Quality Unlock Runbook

This local-only runbook defines the minimum work needed before
KWB-EnzymeDesigner can make a model-quality claim. It does not authorize
production sync or external tool execution.

## Current Hard Blockers

- Reviewed numbering: `numbering_curation_decisions.jsonl` has 0 valid rows.
- Strict supervised rows: current safe entrypoint has 25 rows; model-claim
  threshold is 100.
- MSA/conservation: runtime is not ready and trusted cache validation has 158
  invalid rows.
- Real feedback: experiment and plate feedback intake have 0 training-eligible
  rows.
- ddG backend: Rosetta/PyRosetta/FoldX are not integrated as executable tools.
- Production sync: not authorized and `release_ready=false`.

## Required Unlock Order

1. Add reviewed numbering decisions.
2. Make MSA runtime or trusted cache ready.
3. Add schema-valid experiment feedback.
4. Add a licensed/runtime-verified ddG backend or an approved ThermoMPNN
   baseline.
5. Rerun the safe pipeline, benchmark matrix and claim readiness matrix.
6. Only then review production sync.

## Rosetta/PyRosetta/FoldX ddG

Accepted backends:

- Rosetta command-line ddG protocol
- PyRosetta adapter
- FoldX BuildModel/AnalyseComplex style adapter
- ThermoMPNN as an external stability baseline, not a Rosetta replacement

Minimum evidence:

- license decision
- runtime path or Python module check
- input PDB checksum
- verified chain and residue numbering
- mutation list
- parameters
- ddG table
- runtime log
- artifact checksum

Forbidden:

- saying Rosetta ddG was run without an auditable artifact
- using predicted ddG as wet-lab stability labels
- using restricted/unreviewed tools in production claims

## MSA/Conservation

Allowed routes:

- local `mmseqs` binary with a real homolog database
- Docker MMseqs2 image after explicit approval and daemon readiness
- trusted precomputed MSA/conservation cache

The cache must cover all 158 targets with source database metadata, version,
MSA files, conservation files and checksums.

Forbidden:

- single-sequence conservation
- fabricated MSA files
- missing source database version
- Docker pulls/downloads without approval

## Experiment Feedback

Feedback rows must be schema-valid and include real assay source, numbering,
condition, unit, replicate and QC fields. Summaries or model reports cannot be
copied directly into training labels.

## Production Sync

Production sync is P31. It requires explicit user authorization, release-ready
local manifest, backup, rollback plan, minimal file set and smoke test plan.
Until then, all artifacts stay local-only.
