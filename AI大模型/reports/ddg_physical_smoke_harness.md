# P205 Physical ddG Smoke Harness

Created: `2026-09-03T07:32:13.392010+00:00`

This harness prepares the non-human execution contract for Rosetta/PyRosetta/FoldX physical ddG smoke jobs. It does not approve licenses, fabricate ddG values, import training labels, or open model/release claims.

| Backend | Harness | Runtime receipt | Ready plan rows | Can execute now | Smoke passed | Blockers |
| --- | --- | --- | ---: | --- | --- | --- |
| rosetta | implemented | present | 0 | False | True | ddg_execution_plan_has_no_ready_rows, reviewed structure/mutation data gate not ready for this backend |
| pyrosetta | implemented | present | 0 | False | True | ddg_execution_plan_has_no_ready_rows |
| foldx | implemented | missing | 0 | False | False | approved_runtime_receipt_row_missing, approved_runtime_receipt_status_missing, ddg_execution_plan_has_no_ready_rows, reviewed structure/mutation data gate not ready for this backend |

## Current Boundary

- Harness contract rows: 3
- Contract implemented rows: 3
- Can execute physical smoke now rows: 0
- Physical smoke passed rows: 2
- `safe_for_model_claim=false`; `release_ready=false`.
