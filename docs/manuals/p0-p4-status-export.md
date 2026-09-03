# P0-P4 Status Export

- schema_version: `p0_p4_status_export_v1`
- decision: `continue_local_gap_closure_fail_closed_for_external_dependencies`
- network_io: `not_executed`
- live_gate_execution_allowed: `False`

## Phase Status

| Phase | Label | Status | Ready / Items | Open Local Followups | Covered Local Followups | External Blockers |
|---|---|---|---:|---:|---:|---:|
| `P0` | Venus-level review experience | `ready_local_contract` | `4 / 4` | `0` | `4` | `6` |
| `P1` | enzyme-specific evidence layer | `ready_local_contract` | `4 / 4` | `0` | `4` | `4` |
| `P2` | structure-function scoring system | `ready_local_contract` | `3 / 3` | `0` | `6` | `6` |
| `P3` | DBTL project memory | `ready_local_contract` | `2 / 2` | `0` | `4` | `4` |
| `P4` | production closed-loop readiness | `ready_local_contract` | `1 / 1` | `0` | `2` | `4` |

## Phase Details

### P0 / Venus-level review experience
- Status: `ready_local_contract`
- Items: `specified_mutation_review, site_structure_function_mvp, multi_objective_candidate_table, followup_review_routes`
- Covered local followups: `4`
- External blockers:
  - complete numbering, pocket, conservation, WT baseline, and experiment feedback evidence for claim upgrade
  - validated pocket/channel/interface calculator
  - curated conservation or MSA pipeline
  - real ddG/packing/MD RMSF artifacts
  - wet-lab validation for promotion
  - matched WT baseline and assay controls for improvement claims
- Must not claim:
  - specified mutation is experimentally validated by review
  - numbering mismatch can be ignored
  - complete residue feature table
  - DSSP/pocket/conservation/ddG/MD coverage when unavailable
  - blocked candidates are schedulable
  - candidate table is wet-lab validated
  - follow-up generated new validated candidates
  - experiment mismatch is resolved without assay context

### P1 / enzyme-specific evidence layer
- Status: `ready_local_contract`
- Items: `numbering_registry, catalytic_mechanism_profile, reaction_profile, wt_baseline_registry`
- Covered local followups: `4`
- External blockers:
  - complete SIFTS coverage or user-confirmed numbering for each target
  - complete M-CSA-style curated mechanism coverage and user-coordinate verification
  - Rhea/ChEBI production coverage and curated substrate/product/cofactor directionality
  - same-batch WT baseline, assay conditions, replicate/QC metadata, BRENDA/SABIO-RK-style curation
- Must not claim:
  - inferred mapping is verified SIFTS
  - unmapped residues support strong site claims
  - complete M-CSA mechanism map
  - second shell fully computed
  - substrate spectrum optimized without reaction evidence
  - Rhea/ChEBI production sync complete
  - improvement without exact-condition WT baseline
  - approximate baseline is equivalent

### P2 / structure-function scoring system
- Status: `ready_local_contract`
- Items: `residue_feature_table_contract, objective_score_contract, candidate_table_generation_contract`
- Covered local followups: `6`
- External blockers:
  - curated conservation database or MSA pipeline
  - validated pocket/channel/tunnel calculation
  - real ddG or MD RMSF artifacts
  - matched WT baseline for claim upgrade
  - objective-specific assay data
  - wet-lab validation for candidate promotion
- Must not claim:
  - complete residue feature table
  - DSSP/MD/conservation coverage when unavailable
  - single objective total score
  - measured improvement without assay
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

### P3 / DBTL project memory
- Status: `ready_local_contract`
- Items: `dbtl_trace_contract, feedback_import_and_next_round_contract`
- Covered local followups: `4`
- External blockers:
  - product decision for formal DBTL write model
  - QC-passed replicated wet-lab feedback
  - assay condition completeness
  - formal Go/Watch/No-Go decisions
- Must not claim:
  - formal Project/Round/Variant tables exist
  - trace has trained a model
  - trained epistasis model
  - higher-order combination readiness without pair data

### P4 / production closed-loop readiness
- Status: `ready_local_contract`
- Items: `industrial_closed_loop_readiness`
- Covered local followups: `2`
- External blockers:
  - approved production learning policy
  - sufficient training-eligible feedback
  - maintenance window and live gate approval
  - manufacturing/process constraint owner input
- Must not claim:
  - P4 production loop is running
  - model is retrained
  - manufacturing constraints are validated

## Contract Status Items

### P0 / specified_mutation_review
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `specified_mutation_reviews, specified_mutation_review_computational_hypothesis`
- Covered local followups:
  - surface the review contract in P0/P1/P2/P3/P4 gap audit exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete numbering, pocket, conservation, WT baseline, and experiment feedback evidence for claim upgrade
- Must not claim:
  - specified mutation is experimentally validated by review
  - numbering mismatch can be ignored

### P0 / site_structure_function_mvp
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `site_structure_function_features_v1, residue_distance_graph_v1`
- Covered local followups:
  - add downstream SOP/status rollup for pocket/channel/interface unknown fields -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - validated pocket/channel/interface calculator
  - curated conservation or MSA pipeline
  - real ddG/packing/MD RMSF artifacts
- Must not claim:
  - complete residue feature table
  - DSSP/pocket/conservation/ddG/MD coverage when unavailable

### P0 / multi_objective_candidate_table
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `candidate_table_generation_v1, experiment_design_schedulability_policy_v1`
- Covered local followups:
  - expose schedulability and objective gaps in SOP/status exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - wet-lab validation for promotion
  - matched WT baseline and assay controls for improvement claims
- Must not claim:
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

### P0 / followup_review_routes
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `_is_p0_followup_review, specified_mutation_reviews`
- Covered local followups:
  - add explicit P0 follow-up status line to audit/report exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - prior trace context and structured experiment feedback for conflict explanation
- Must not claim:
  - follow-up generated new validated candidates
  - experiment mismatch is resolved without assay context

### P1 / numbering_registry
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `numbering_registry_rows, unified_numbering_registry_v1`
- Covered local followups:
  - publish numbering registry readiness in P0-P4 audit outputs -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete SIFTS coverage or user-confirmed numbering for each target
- Must not claim:
  - inferred mapping is verified SIFTS
  - unmapped residues support strong site claims

### P1 / catalytic_mechanism_profile
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `catalytic_mechanism_profile_v1, pending_numbering, first_shell_positions`
- Covered local followups:
  - add explicit second-shell/source-coordinate coverage rollup to audit exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete M-CSA-style curated mechanism coverage and user-coordinate verification
- Must not claim:
  - complete M-CSA mechanism map
  - second shell fully computed

### P1 / reaction_profile
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `reaction_profile_v1, requires_reaction_profile`
- Covered local followups:
  - connect reaction profile readiness into the P0-P4 audit and report status exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - Rhea/ChEBI production coverage and curated substrate/product/cofactor directionality
- Must not claim:
  - substrate spectrum optimized without reaction evidence
  - Rhea/ChEBI production sync complete

### P1 / wt_baseline_registry
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `wt_baseline_registry_v1, wt_baseline_report_contract_v1`
- Covered local followups:
  - show WT baseline readiness next to objective assay gaps in downstream exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - same-batch WT baseline, assay conditions, replicate/QC metadata, BRENDA/SABIO-RK-style curation
- Must not claim:
  - improvement without exact-condition WT baseline
  - approximate baseline is equivalent

### P2 / residue_feature_table_contract
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `site_structure_function_features_v1, residue_distance_graph_v1, p2_structure_feature_gap_summary_v1`
- Covered local followups:
  - Expose a structure-feature gap summary in downstream SOP/status exports so pocket/channel/interface, conservation, ddG, and MD-derived fields remain explicit until computed. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose the calculator/source boundary in downstream SOP/status exports and continue widening residue feature fields only when a structured calculator or curated source exists. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - curated conservation database or MSA pipeline
  - validated pocket/channel/tunnel calculation
  - real ddG or MD RMSF artifacts
- Must not claim:
  - complete residue feature table
  - DSSP/MD/conservation coverage when unavailable

### P2 / objective_score_contract
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `mutation_objective_score_v1, p2_objective_score_readiness_summary_v1, p2_objective_assay_gap_summary_v1, no_composite_score, unknown_policy`
- Covered local followups:
  - Expose unknown-component blocking state in downstream SOP/status exports and keep unknown objective components blocking instead of neutral. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose objective assay gaps beside project feedback readiness in downstream SOP/status exports. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - matched WT baseline for claim upgrade
  - objective-specific assay data
- Must not claim:
  - single objective total score
  - measured improvement without assay

### P2 / candidate_table_generation_contract
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `candidate_table_generation_v1, p2_engineering_scorecard_contract_v1, p2_candidate_readiness_summary_v1, experiment_design_schedulability_policy_v1`
- Covered local followups:
  - Expose experiment design schedulability policy in downstream SOP views. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Keep candidate table promotion tied to candidate_status and assay readiness. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - wet-lab validation for candidate promotion
- Must not claim:
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

### P3 / dbtl_trace_contract
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `dbtl_trace_v1, dbtl_project_model_v1, dbtl_project_memory_readiness_v1, dbtl_trace_summary_v1, dbtl_readiness_bridge_v1`
- Covered local followups:
  - Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose project memory readiness in downstream SOP/status views. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - product decision for formal DBTL write model
- Must not claim:
  - formal Project/Round/Variant tables exist
  - trace has trained a model

### P3 / feedback_import_and_next_round_contract
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `experiment_feedback_import_v1, dbtl_feedback_readiness_summary_v1, next_round_library_design_v1, next_round_combination_evidence_contract_v1`
- Covered local followups:
  - Expose feedback readiness in downstream SOP/status exports. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose pair/higher-order gate state in downstream SOP/status exports and keep pair/higher-order designs blocked until singleton and structure evidence pass. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - QC-passed replicated wet-lab feedback
  - assay condition completeness
  - formal Go/Watch/No-Go decisions
- Must not claim:
  - trained epistasis model
  - higher-order combination readiness without pair data

### P4 / industrial_closed_loop_readiness
- Status: `ready_local_contract`
- Read only: `true`
- Approval required: `true`
- Approval state: `blocked_until_explicit_review`
- Evidence tokens: `p4_closed_loop_readiness_v1, p4_active_learning_batch_contract_v1, p4_model_calibration_registry_contract_v1, p4_manufacturing_constraint_schema_v1, live_gate_approval, model_retrained, p4_operator_review_contract_v1`
- Covered local followups:
  - Expose P4 contract status and operator review state in downstream SOP/status exports. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose live-gate approval block state in downstream SOP/status exports and keep live gate approval blocked until an explicit operator review is recorded. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - approved production learning policy
  - sufficient training-eligible feedback
  - maintenance window and live gate approval
  - manufacturing/process constraint owner input
- Must not claim:
  - P4 production loop is running
  - model is retrained
  - manufacturing constraints are validated

## Remaining Backlog

- counts: `{"external_required": 7, "ready": 2}`
- external followups: `formal_domain_https, gpu_gromacs_md_live, md_blackbox_live_e2e, ligand_runtime_live, oss_minio_live_e2e, admin_authenticated_screenshots, maintenance_window_drills`

## Contract

- schema_version: `p0_p4_status_export_contract_v1`
- read_only: `true`
- ready local contract must not be described as live complete.

## Must Not Claim
- ready local contract means production complete
- live gates have run
- model has been trained or retrained
- wet-lab validation is proven by status export
- manufacturing constraints are validated
