# P2/P3/P4 Roadmap

- decision: `continue_local_contract_hardening_fail_closed_for_live_dependencies`
- network_io: `not_executed`
- destructive_actions: `not_executed`
- live_gate_execution_allowed: `False`

## Phase Summary

| Phase | Items | Ready Local | Partial | Defined Not Started | External Blockers |
|---|---:|---:|---:|---:|---:|
| `P2` | `3` | `3` | `0` | `0` | `6` |
| `P3` | `2` | `2` | `0` | `0` | `4` |
| `P4` | `1` | `1` | `0` | `0` | `4` |

## P2 / residue_feature_table_contract

- Status: `ready_local_contract`
- Summary: Residue structure-function rows and residue distance graph are present as traceable contracts.
- Evidence tokens: `site_structure_function_features_v1, residue_distance_graph_v1, p2_structure_feature_gap_summary_v1`
- Sources:
  - `backend/app/tools/site_structure_function_features.py` exists=`True`
  - `backend/tests/test_mutation_objective_scores.py` exists=`True`
- Next local actions:
  - Expose a structure-feature gap summary in downstream SOP/status exports so pocket/channel/interface, conservation, ddG, and MD-derived fields remain explicit until computed.
  - Expose the calculator/source boundary in downstream SOP/status exports and continue widening residue feature fields only when a structured calculator or curated source exists.
- External blockers:
  - curated conservation database or MSA pipeline
  - validated pocket/channel/tunnel calculation
  - real ddG or MD RMSF artifacts
- Must not claim:
  - complete residue feature table
  - DSSP/MD/conservation coverage when unavailable

## P2 / objective_score_contract

- Status: `ready_local_contract`
- Summary: Activity, stability, specificity, pH, expression, and risk scores are component-local; no total score is emitted.
- Evidence tokens: `mutation_objective_score_v1, p2_objective_score_readiness_summary_v1, p2_objective_assay_gap_summary_v1, no_composite_score, unknown_policy`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `backend/tests/test_mutation_objective_scores.py` exists=`True`
- Next local actions:
  - Expose unknown-component blocking state in downstream SOP/status exports and keep unknown objective components blocking instead of neutral.
  - Expose objective assay gaps beside project feedback readiness in downstream SOP/status exports.
- External blockers:
  - matched WT baseline for claim upgrade
  - objective-specific assay data
- Must not claim:
  - single objective total score
  - measured improvement without assay

## P2 / candidate_table_generation_contract

- Status: `ready_local_contract`
- Summary: Candidate rows are grouped as high-confidence, exploratory, or blocked using residue features and objective score contracts.
- Evidence tokens: `candidate_table_generation_v1, p2_engineering_scorecard_contract_v1, p2_candidate_readiness_summary_v1, experiment_design_schedulability_policy_v1`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `frontend/src/components/analysis/MutationScoreCard.tsx` exists=`True`
  - `frontend/src/lib/report.ts` exists=`True`
- Next local actions:
  - Expose experiment design schedulability policy in downstream SOP views.
  - Keep candidate table promotion tied to candidate_status and assay readiness.
- External blockers:
  - wet-lab validation for candidate promotion
- Must not claim:
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

## P3 / dbtl_trace_contract

- Status: `ready_local_contract`
- Summary: Project DBTL trace aggregates existing checkpoints, feedback, calibration, formal decision, and next-round preview as read-only memory.
- Evidence tokens: `dbtl_trace_v1, dbtl_project_model_v1, dbtl_project_memory_readiness_v1, dbtl_trace_summary_v1, dbtl_readiness_bridge_v1`
- Sources:
  - `backend/app/services/dbtl_trace.py` exists=`True`
  - `backend/tests/test_project_dbtl_trace.py` exists=`True`
  - `frontend/src/pages/ProjectDetailPage.tsx` exists=`True`
  - `frontend/src/pages/ProjectListPage.tsx` exists=`True`
- Next local actions:
  - Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved.
  - Expose project memory readiness in downstream SOP/status views.
- External blockers:
  - product decision for formal DBTL write model
- Must not claim:
  - formal Project/Round/Variant tables exist
  - trace has trained a model

## P3 / feedback_import_and_next_round_contract

- Status: `ready_local_contract`
- Summary: Experiment feedback import gates training/claim eligibility, and next-round library planning is constrained by validated singleton evidence.
- Evidence tokens: `experiment_feedback_import_v1, dbtl_feedback_readiness_summary_v1, next_round_library_design_v1, next_round_combination_evidence_contract_v1`
- Sources:
  - `backend/app/services/experiment_feedback.py` exists=`True`
  - `backend/app/tools/feedback_iteration_planner.py` exists=`True`
  - `backend/tests/test_experiment_feedback_import_contract.py` exists=`True`
  - `frontend/src/pages/DataBrowser.tsx` exists=`True`
  - `frontend/src/pages/ProjectDetailPage.tsx` exists=`True`
- Next local actions:
  - Expose feedback readiness in downstream SOP/status exports.
  - Expose pair/higher-order gate state in downstream SOP/status exports and keep pair/higher-order designs blocked until singleton and structure evidence pass.
- External blockers:
  - QC-passed replicated wet-lab feedback
  - assay condition completeness
  - formal Go/Watch/No-Go decisions
- Must not claim:
  - trained epistasis model
  - higher-order combination readiness without pair data

## P4 / industrial_closed_loop_readiness

- Status: `ready_local_contract`
- Summary: P4 is defined as production-grade closed-loop operation: active learning batches, model calibration registry, manufacturing constraints, and approved live-gate execution.
- Evidence tokens: `p4_closed_loop_readiness_v1, p4_active_learning_batch_contract_v1, p4_model_calibration_registry_contract_v1, p4_manufacturing_constraint_schema_v1, live_gate_approval, model_retrained, p4_operator_review_contract_v1`
- Sources:
  - `backend/app/services/dbtl_trace.py` exists=`True`
  - `frontend/src/lib/report.ts` exists=`True`
  - `docs/manuals/remaining-backlog-go-no-go-summary.json` exists=`True`
- Next local actions:
  - Expose P4 contract status and operator review state in downstream SOP/status exports.
  - Expose live-gate approval block state in downstream SOP/status exports and keep live gate approval blocked until an explicit operator review is recorded.
- External blockers:
  - approved production learning policy
  - sufficient training-eligible feedback
  - maintenance window and live gate approval
  - manufacturing/process constraint owner input
- Must not claim:
  - P4 production loop is running
  - model is retrained
  - manufacturing constraints are validated

Next action: Continue P2/P3 local contract hardening and define P4 contracts; do not execute live gates or claim wet-lab/model-training completion without external evidence.
