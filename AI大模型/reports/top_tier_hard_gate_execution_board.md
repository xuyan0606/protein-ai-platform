# Top-Tier Hard-Gate Execution Board

Generated: 2026-09-03T07:33:45.031005+00:00

This board turns the current top-tier model blockers into execution lanes. It is fail-closed.

## Summary

- Gates: 6
- Blocked gates: 6
- Ready gates: 0
- Human/external authorization gates: 6
- Safe for model claim: false
- Release ready: false

## Gates

| priority | gate | owner | status | key missing |
|---|---|---|---|---|
| P0 | HTG-001-reviewed-numbering-real-labels | sequence_data_agent | blocked | Create reviewed numbering decisions backed by real canonical/isoform/literature evidence.; Reach >=100 claim-eligible real supervised rows with synthetic_or_unreceipted_rows=0. |
| P0 | HTG-002-wet-lab-training-eligible-feedback | wet_lab_feedback_agent | blocked | Metric-level human authorization rows for 12 real wet-lab candidates.; Schema-valid feedback preflight and apply-plan rows. |
| P0 | HTG-003-benchmark-scorecard-claim-cache | benchmark_agent | blocked | 13 benchmark dataset/cache registrations with checksums.; 13 license decisions and leakage/split records. |
| P0 | HTG-004-physical-ddg-runtime | ddg_backend_agent | blocked | Approved license/runtime receipt for at least one physical backend.; Executable or Python module discovery for Rosetta/PyRosetta/FoldX. |
| P0 | HTG-005-substrate-fit-label-source | substrate_fit_agent | blocked | Approved substrate_fit label schema with explicit substrate identity and assay context.; Reviewed substrate-specific wet-lab/plate rows. |
| P1 | HTG-006-structure-feature-expansion | structure_feature_agent | blocked | Human-reviewed chain mappings for the next strict evidence candidates.; At least 100 effective rows per head after label gates also pass. |

## Policy

Fail-closed hard-gate execution board only. It does not write reviewed decisions, approve wet-lab rows, import labels, approve benchmarks, execute Rosetta/FoldX, train models, deploy services, sync production, or relax model-quality gates.
