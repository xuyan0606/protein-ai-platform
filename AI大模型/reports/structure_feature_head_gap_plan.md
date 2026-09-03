# Structure Feature Head Gap Plan

Generated: 2026-09-03T07:33:44.745895+00:00

This is a fail-closed, read-only readiness plan. It does not write chain mapping decisions or open coordinate claims.

## Summary

- Status: blocked
- Heads ready for structure-feature training: 0/5
- Reviewed structure graph rows: 34
- Strict MSA site feature rows: 0
- Effective strict structure-feature rows: 0
- Remaining chain-mapping backlog: 475
- Next strict evidence candidates: 9
- Coordinate claims allowed: false
- Safe for model claim: false

## Head Readiness

| head | labels | effective structure-feature rows | effective gap | next strict batch potential | blocker |
|---|---:|---:|---:|---:|---|
| mutation_rank | 0 | 0 | 100 | 0 | MQ-U001 reviewed numbering and real label provenance |
| stability | 0 | 0 | 100 | 0 | FireProt license/dedup/import receipt + wet-lab authorization |
| activity_risk | 6 | 0 | 100 | 6 | metric-level human authorization and feedback preflight |
| substrate_fit | 0 | 0 | 100 | 0 | no substrate-fit label source approved |
| assay_success | 0 | 0 | 100 | 0 | plate intake QC and human extraction |

## Next 9 Strict Evidence Chain Candidates

| # | structure | UniProt | packet | suggested chain | bucket | resolution |
|---:|---|---|---|---|---|---:|
| 1 | 13FO | Q9WXZ2 | structure_chain_multi_select_005 | D | multi_chain_needs_selection |  |
| 2 | 10GH | Q78DX7 | structure_chain_multi_select_007 | A | multi_chain_needs_selection |  |
| 3 | 135L | P00703 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.3 |
| 4 | 193L | P00698 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.33 |
| 5 | 194L | P00698 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.4 |
| 6 | 121P | P01112 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.54 |
| 7 | 16PK | P07378 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.6 |
| 8 | 11AP | O70348 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.8 |
| 9 | 1A3H | O85465 | structure_chain_single_mismatch_001 | A | single_chain_ca_length_mismatch | 1.57 |

## Blockers

- remaining_structure_chain_mapping_rows_require_reviewed_decisions
- strict_evidence_candidates_still_require_explicit_human_decisions
- five_head_training_gap_plan_blocked
- source_reports_safe_for_model_claim_false
- coordinate_claims_remain_closed_until_reviewed_chain_mappings_and_label_gates_pass

## Policy

Fail-closed structure feature gap plan only. This report does not write chain mapping decisions, approve coordinate claims, import labels, train models, or relax model-quality gates.
