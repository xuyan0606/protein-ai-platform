# KWB-EnzymeDesigner v2.12.0 benchmark-ddg-gates

Status: local gate update complete; model-quality claim still blocked.

## Added

- KWB strict mutation holdout benchmark scorecard cache.
- Rosetta/PyRosetta/FoldX ddG backend registry entries.
- ddG backend local config, result schema, readiness report, execution plan and fail-closed adapter.

## Current Readiness

- Benchmark score cache: 1 valid row, 13 invalid/missing rows, not ready for model claim.
- ddG backend: adapter integrated, 0 ready backends, executable Rosetta/PyRosetta/FoldX ready false.
- MSA/cache remains ready from v2.11.0.
- Strict supervised rows remain 25.

## Constraints

- No Rosetta/PyRosetta/FoldX executable was downloaded, installed or invoked.
- No real ddG values were generated.
- No wet-lab feedback rows were made training-eligible.
- `safe_for_model_claim=false` and `release_ready=false` remain correct.
