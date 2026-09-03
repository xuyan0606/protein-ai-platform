# P0-P4 Backlog Ticket Bridge

- schema_version: `p0_p4_backlog_ticket_bridge_v1`
- go_no_go_decision: `defer_waiting_for_external_inputs`
- ready_for_live_gate_execution: `False`
- contract_count: `14`
- linked: `0`
- partially_linked: `10`
- contract_followup_only: `4`

## Contract To Ticket

| Phase | Contract | Status | Ticket Link Status | Tickets | Uncovered Blockers |
|---|---|---|---|---|---|
| `P0` | `specified_mutation_review` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live, RB-003-md_blackbox_live_e2e` | complete numbering, pocket, conservation, WT baseline, and experiment feedback evidence for claim upgrade |
| `P0` | `site_structure_function_mvp` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live, RB-003-md_blackbox_live_e2e` | validated pocket/channel/interface calculator; curated conservation or MSA pipeline |
| `P0` | `multi_objective_candidate_table` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live` | wet-lab validation for promotion; matched WT baseline and assay controls for improvement claims |
| `P0` | `followup_review_routes` | `ready_local_contract` | `partially_linked` | `RB-003-md_blackbox_live_e2e` | prior trace context and structured experiment feedback for conflict explanation |
| `P1` | `numbering_registry` | `ready_local_contract` | `contract_followup_only` | `none` | complete SIFTS coverage or user-confirmed numbering for each target |
| `P1` | `catalytic_mechanism_profile` | `ready_local_contract` | `contract_followup_only` | `none` | complete M-CSA-style curated mechanism coverage and user-coordinate verification |
| `P1` | `reaction_profile` | `ready_local_contract` | `contract_followup_only` | `none` | Rhea/ChEBI production coverage and curated substrate/product/cofactor directionality |
| `P1` | `wt_baseline_registry` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live` | same-batch WT baseline, assay conditions, replicate/QC metadata, BRENDA/SABIO-RK-style curation |
| `P2` | `residue_feature_table_contract` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live, RB-003-md_blackbox_live_e2e` | curated conservation database or MSA pipeline; validated pocket/channel/tunnel calculation |
| `P2` | `objective_score_contract` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live` | matched WT baseline for claim upgrade; objective-specific assay data |
| `P2` | `candidate_table_generation_contract` | `ready_local_contract` | `contract_followup_only` | `none` | wet-lab validation for candidate promotion |
| `P3` | `dbtl_trace_contract` | `ready_local_contract` | `partially_linked` | `RB-007-maintenance_window_drills` | product decision for formal DBTL write model |
| `P3` | `feedback_import_and_next_round_contract` | `ready_local_contract` | `partially_linked` | `RB-002-gpu_gromacs_md_live` | QC-passed replicated wet-lab feedback; assay condition completeness; formal Go/Watch/No-Go decisions |
| `P4` | `industrial_closed_loop_readiness` | `ready_local_contract` | `partially_linked` | `RB-001-formal_domain_https, RB-005-oss_minio_live_e2e, RB-007-maintenance_window_drills` | approved production learning policy; sufficient training-eligible feedback; manufacturing/process constraint owner input |

## Ticket To Contract

### RB-001-formal_domain_https
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `linked_to_contracts`
- Contracts:
  - `P4/industrial_closed_loop_readiness`: `direct_blocker_support`, covered blockers: maintenance window and live gate approval

### RB-002-gpu_gromacs_md_live
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `linked_to_contracts`
- Contracts:
  - `P0/specified_mutation_review`: `supporting_evidence_only`, covered blockers: none
  - `P0/site_structure_function_mvp`: `direct_blocker_support`, covered blockers: real ddG/packing/MD RMSF artifacts
  - `P0/multi_objective_candidate_table`: `supporting_evidence_only`, covered blockers: none
  - `P1/wt_baseline_registry`: `supporting_evidence_only`, covered blockers: none
  - `P2/residue_feature_table_contract`: `direct_blocker_support`, covered blockers: real ddG or MD RMSF artifacts
  - `P2/objective_score_contract`: `supporting_evidence_only`, covered blockers: none
  - `P3/feedback_import_and_next_round_contract`: `supporting_evidence_only`, covered blockers: none

### RB-003-md_blackbox_live_e2e
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `linked_to_contracts`
- Contracts:
  - `P0/specified_mutation_review`: `supporting_evidence_only`, covered blockers: none
  - `P0/site_structure_function_mvp`: `supporting_evidence_only`, covered blockers: none
  - `P0/followup_review_routes`: `supporting_evidence_only`, covered blockers: none
  - `P2/residue_feature_table_contract`: `supporting_evidence_only`, covered blockers: none

### RB-004-ligand_runtime_live
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `operator_ticket_only`
- No P0-P4 contract is claimed to be resolved by this ticket.

### RB-005-oss_minio_live_e2e
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `linked_to_contracts`
- Contracts:
  - `P4/industrial_closed_loop_readiness`: `direct_blocker_support`, covered blockers: maintenance window and live gate approval

### RB-006-admin_authenticated_screenshots
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `operator_ticket_only`
- No P0-P4 contract is claimed to be resolved by this ticket.

### RB-007-maintenance_window_drills
- Status: `started_blocked_waiting_for_operator_input`
- Contract impact: `linked_to_contracts`
- Contracts:
  - `P3/dbtl_trace_contract`: `supporting_approval_only`, covered blockers: none
  - `P4/industrial_closed_loop_readiness`: `direct_blocker_support`, covered blockers: maintenance window and live gate approval

## Boundary

- This bridge is read-only and does not execute live gates.
- `ready_local_contract` remains distinct from live complete, wet-lab validated, or model retrained.
- Uncovered blockers remain blockers even when a related operator ticket becomes ready.
