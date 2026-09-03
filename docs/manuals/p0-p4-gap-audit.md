# P0-P4 Gap Audit

- decision: `continue_local_gap_closure_fail_closed_for_external_dependencies`
- network_io: `not_executed`
- destructive_actions: `not_executed`
- live_gate_execution_allowed: `False`

## Phase Summary

| Phase | Items | Ready Local | Partial | Blocked | Open Local Gaps | Covered Local Gaps | External Blockers |
|---|---:|---:|---:|---:|---:|---:|---:|
| `P0` | `4` | `4` | `0` | `0` | `0` | `4` | `7` |
| `P1` | `4` | `4` | `0` | `0` | `0` | `4` | `4` |
| `P2` | `3` | `3` | `0` | `0` | `0` | `6` | `6` |
| `P3` | `2` | `2` | `0` | `0` | `0` | `4` | `4` |
| `P4` | `1` | `1` | `0` | `0` | `0` | `2` | `4` |

## Items

### P0 / specified_mutation_review

- Status: `ready_local_contract`
- Summary: User-requested point mutations are parsed and reviewed separately from generic candidate generation.
- Evidence tokens: `specified_mutation_reviews, specified_mutation_review_computational_hypothesis`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `backend/app/core/agent_graph.py` exists=`True`
  - `backend/tests/test_requested_mutation_review.py` exists=`True`
  - `backend/tests/test_tools_api.py` exists=`True`
- Local gaps:
  - surface the review contract in P0/P1/P2/P3/P4 gap audit exports
- Covered local gaps:
  - surface the review contract in P0/P1/P2/P3/P4 gap audit exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete numbering, pocket, conservation, WT baseline, and experiment feedback evidence for claim upgrade
- Must not claim:
  - specified mutation is experimentally validated by review
  - numbering mismatch can be ignored

### P0 / site_structure_function_mvp

- Status: `ready_local_contract`
- Summary: Residue-level CA geometry, relSASA, HETATM distance, secondary-structure annotation, and distance graph are available with conservative unknowns.
- Evidence tokens: `site_structure_function_features_v1, residue_distance_graph_v1`
- Sources:
  - `backend/app/tools/site_structure_function_features.py` exists=`True`
  - `backend/tests/test_mutation_objective_scores.py` exists=`True`
  - `frontend/src/components/analysis/SiteStructureFunctionFeaturesCard.tsx` exists=`True`
- Local gaps:
  - add downstream SOP/status rollup for pocket/channel/interface unknown fields
- Covered local gaps:
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
- Summary: Candidate table separates activity, stability, risk, evidence, status, and experiment action with schedulability policy.
- Evidence tokens: `candidate_table_generation_v1, experiment_design_schedulability_policy_v1`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `frontend/src/components/analysis/MutationScoreCard.tsx` exists=`True`
  - `frontend/src/lib/report.ts` exists=`True`
- Local gaps:
  - expose schedulability and objective gaps in SOP/status exports
- Covered local gaps:
  - expose schedulability and objective gaps in SOP/status exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - wet-lab validation for promotion
  - matched WT baseline and assay controls for improvement claims
- Must not claim:
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

### P0 / followup_review_routes

- Status: `ready_local_contract`
- Summary: Follow-up questions for Venus comparison, candidate explanation, experiment mismatch, and specified mutations reuse the prior object instead of replanning new candidates.
- Evidence tokens: `_is_p0_followup_review, specified_mutation_reviews`
- Sources:
  - `backend/app/core/agent_graph.py` exists=`True`
  - `backend/tests/test_agent_binder.py` exists=`True`
- Local gaps:
  - add explicit P0 follow-up status line to audit/report exports
- Covered local gaps:
  - add explicit P0 follow-up status line to audit/report exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - prior trace context and structured experiment feedback for conflict explanation
- Must not claim:
  - follow-up generated new validated candidates
  - experiment mismatch is resolved without assay context

### P1 / numbering_registry

- Status: `ready_local_contract`
- Summary: SIFTS/curated rows and inferred mappings are normalized into unified numbering registry rows consumed by numbering gate.
- Evidence tokens: `numbering_registry_rows, unified_numbering_registry_v1`
- Sources:
  - `backend/app/tools/residue_mapping_sifts.py` exists=`True`
  - `backend/app/tools/residue_numbering_gate.py` exists=`True`
  - `backend/tests/test_structure_tools.py` exists=`True`
  - `backend/tests/test_tools_api.py` exists=`True`
- Local gaps:
  - publish numbering registry readiness in P0-P4 audit outputs
- Covered local gaps:
  - publish numbering registry readiness in P0-P4 audit outputs -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete SIFTS coverage or user-confirmed numbering for each target
- Must not claim:
  - inferred mapping is verified SIFTS
  - unmapped residues support strong site claims

### P1 / catalytic_mechanism_profile

- Status: `ready_local_contract`
- Summary: Catalytic role, first-shell state, pending numbering, and mechanism report contract are available from local annotation services.
- Evidence tokens: `catalytic_mechanism_profile_v1, pending_numbering, first_shell_positions`
- Sources:
  - `backend/app/services/annotation_query_service.py` exists=`True`
  - `backend/app/services/annotation_facade.py` exists=`True`
  - `backend/tests/test_annotation_facade.py` exists=`True`
  - `backend/tests/test_data_api.py` exists=`True`
- Local gaps:
  - add explicit second-shell/source-coordinate coverage rollup to audit exports
- Covered local gaps:
  - add explicit second-shell/source-coordinate coverage rollup to audit exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - complete M-CSA-style curated mechanism coverage and user-coordinate verification
- Must not claim:
  - complete M-CSA mechanism map
  - second shell fully computed

### P1 / reaction_profile

- Status: `ready_local_contract`
- Summary: Reaction Profile is available for exact local EC/Rhea-style matches and blocks substrate-scope claims when incomplete.
- Evidence tokens: `reaction_profile_v1, requires_reaction_profile`
- Sources:
  - `backend/app/services/reaction_profile.py` exists=`True`
  - `backend/tests/test_reaction_profile.py` exists=`True`
  - `backend/tests/test_data_api.py` exists=`True`
- Local gaps:
  - connect reaction profile readiness into the P0-P4 audit and report status exports
- Covered local gaps:
  - connect reaction profile readiness into the P0-P4 audit and report status exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - Rhea/ChEBI production coverage and curated substrate/product/cofactor directionality
- Must not claim:
  - substrate spectrum optimized without reaction evidence
  - Rhea/ChEBI production sync complete

### P1 / wt_baseline_registry

- Status: `ready_local_contract`
- Summary: WT baseline registry resolves only exact-condition QC-passed WT feedback and blocks improvement claims without matched baseline.
- Evidence tokens: `wt_baseline_registry_v1, wt_baseline_report_contract_v1`
- Sources:
  - `backend/app/services/wt_baseline_registry.py` exists=`True`
  - `backend/app/tools/wt_baseline_registry.py` exists=`True`
  - `backend/tests/test_wt_baseline_registry.py` exists=`True`
  - `backend/tests/test_tools_api.py` exists=`True`
- Local gaps:
  - show WT baseline readiness next to objective assay gaps in downstream exports
- Covered local gaps:
  - show WT baseline readiness next to objective assay gaps in downstream exports -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - same-batch WT baseline, assay conditions, replicate/QC metadata, BRENDA/SABIO-RK-style curation
- Must not claim:
  - improvement without exact-condition WT baseline
  - approximate baseline is equivalent

### P2 / residue_feature_table_contract

- Status: `ready_local_contract`
- Summary: Residue structure-function rows and residue distance graph are present as traceable contracts.
- Evidence tokens: `site_structure_function_features_v1, residue_distance_graph_v1, p2_structure_feature_gap_summary_v1`
- Sources:
  - `backend/app/tools/site_structure_function_features.py` exists=`True`
  - `backend/tests/test_mutation_objective_scores.py` exists=`True`
- Local gaps:
  - Expose a structure-feature gap summary in downstream SOP/status exports so pocket/channel/interface, conservation, ddG, and MD-derived fields remain explicit until computed.
  - Expose the calculator/source boundary in downstream SOP/status exports and continue widening residue feature fields only when a structured calculator or curated source exists.
- Covered local gaps:
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
- Summary: Activity, stability, specificity, pH, expression, and risk scores are component-local; no total score is emitted.
- Evidence tokens: `mutation_objective_score_v1, p2_objective_score_readiness_summary_v1, p2_objective_assay_gap_summary_v1, no_composite_score, unknown_policy`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `backend/tests/test_mutation_objective_scores.py` exists=`True`
- Local gaps:
  - Expose unknown-component blocking state in downstream SOP/status exports and keep unknown objective components blocking instead of neutral.
  - Expose objective assay gaps beside project feedback readiness in downstream SOP/status exports.
- Covered local gaps:
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
- Summary: Candidate rows are grouped as high-confidence, exploratory, or blocked using residue features and objective score contracts.
- Evidence tokens: `candidate_table_generation_v1, p2_engineering_scorecard_contract_v1, p2_candidate_readiness_summary_v1, experiment_design_schedulability_policy_v1`
- Sources:
  - `backend/app/tools/mutation_priority_score.py` exists=`True`
  - `frontend/src/components/analysis/MutationScoreCard.tsx` exists=`True`
  - `frontend/src/lib/report.ts` exists=`True`
- Local gaps:
  - Expose experiment design schedulability policy in downstream SOP views.
  - Keep candidate table promotion tied to candidate_status and assay readiness.
- Covered local gaps:
  - Expose experiment design schedulability policy in downstream SOP views. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Keep candidate table promotion tied to candidate_status and assay readiness. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - wet-lab validation for candidate promotion
- Must not claim:
  - blocked candidates are schedulable
  - candidate table is wet-lab validated

### P3 / dbtl_trace_contract

- Status: `ready_local_contract`
- Summary: Project DBTL trace aggregates existing checkpoints, feedback, calibration, formal decision, and next-round preview as read-only memory.
- Evidence tokens: `dbtl_trace_v1, dbtl_project_model_v1, dbtl_project_memory_readiness_v1, dbtl_trace_summary_v1, dbtl_readiness_bridge_v1`
- Sources:
  - `backend/app/services/dbtl_trace.py` exists=`True`
  - `backend/tests/test_project_dbtl_trace.py` exists=`True`
  - `frontend/src/pages/ProjectDetailPage.tsx` exists=`True`
  - `frontend/src/pages/ProjectListPage.tsx` exists=`True`
- Local gaps:
  - Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved.
  - Expose project memory readiness in downstream SOP/status views.
- Covered local gaps:
  - Expose raw-trace approval state in downstream SOP/status exports and keep raw trace read-only until formal DBTL tables are product-approved. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
  - Expose project memory readiness in downstream SOP/status views. -> `covered_by_contract_status_export` via `p0_p4_contract_status_export_v1`
- External blockers:
  - product decision for formal DBTL write model
- Must not claim:
  - formal Project/Round/Variant tables exist
  - trace has trained a model

### P3 / feedback_import_and_next_round_contract

- Status: `ready_local_contract`
- Summary: Experiment feedback import gates training/claim eligibility, and next-round library planning is constrained by validated singleton evidence.
- Evidence tokens: `experiment_feedback_import_v1, dbtl_feedback_readiness_summary_v1, next_round_library_design_v1, next_round_combination_evidence_contract_v1`
- Sources:
  - `backend/app/services/experiment_feedback.py` exists=`True`
  - `backend/app/tools/feedback_iteration_planner.py` exists=`True`
  - `backend/tests/test_experiment_feedback_import_contract.py` exists=`True`
  - `frontend/src/pages/DataBrowser.tsx` exists=`True`
  - `frontend/src/pages/ProjectDetailPage.tsx` exists=`True`
- Local gaps:
  - Expose feedback readiness in downstream SOP/status exports.
  - Expose pair/higher-order gate state in downstream SOP/status exports and keep pair/higher-order designs blocked until singleton and structure evidence pass.
- Covered local gaps:
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
- Summary: P4 is defined as production-grade closed-loop operation: active learning batches, model calibration registry, manufacturing constraints, and approved live-gate execution.
- Evidence tokens: `p4_closed_loop_readiness_v1, p4_active_learning_batch_contract_v1, p4_model_calibration_registry_contract_v1, p4_manufacturing_constraint_schema_v1, live_gate_approval, model_retrained, p4_operator_review_contract_v1`
- Sources:
  - `backend/app/services/dbtl_trace.py` exists=`True`
  - `frontend/src/lib/report.ts` exists=`True`
  - `docs/manuals/remaining-backlog-go-no-go-summary.json` exists=`True`
- Local gaps:
  - Expose P4 contract status and operator review state in downstream SOP/status exports.
  - Expose live-gate approval block state in downstream SOP/status exports and keep live gate approval blocked until an explicit operator review is recorded.
- Covered local gaps:
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

## Remaining External Backlog

- status: `external_required`
- counts: `{"external_required": 7, "ready": 2}`

### formal_domain_https
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: formal domain cutover has not started because PUBLIC_BASE_URL is missing
- Missing requirements:
  - PUBLIC_BASE_URL
  - DNS A/CNAME record
  - TLS certificate

### gpu_gromacs_md_live
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: GROMACS topology live gate is not available on this host: GROMACS_NOT_INSTALLED
- Missing requirements:
  - NVIDIA/GROMACS runtime
  - real WT/mutant PDB inputs
  - long-running MD worker capacity

### md_blackbox_live_e2e
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: MD black-box long-task gate is available but not armed; no live MD task was submitted
- Missing requirements:
  - MD_BLACKBOX_TASK_ID for resume or ALLOW_MD_BLACKBOX_SUBMIT=true for new submission
  - MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD

### ligand_runtime_live
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: ligand preprocessing/docking/topology runtime is not complete on this host
- Missing requirements:
  - conformer_generation
  - pdbqt_preparation
  - vina_docking
  - ligand_topology
  - gromacs_md

### oss_minio_live_e2e
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: OSS/MinIO E2E gate is available, but endpoint credentials or live bucket permission are not present in this shell
- Missing requirements:
  - MINIO_ACCESS_KEY/MINIO_SECRET_KEY or ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET
  - live bucket permission

### admin_authenticated_screenshots
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: admin screenshots still require an authenticated admin session
- Missing requirements:
  - SCREENSHOT_EMAIL
  - SCREENSHOT_PASSWORD

### maintenance_window_drills
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: real rollback, offsite backup, and external storage restore drills need an approved maintenance window
- Missing requirements:
  - MAINTENANCE_WINDOW_ID
  - ALLOW_PRODUCTION_DRILL=true
  - REMOTE_BACKUP_TARGET or OFFSITE_BACKUP_TARGET
  - EXTERNAL_STORAGE_RESTORE_TARGET

## Next Local Actions
- Keep downstream contract-status export explicit for P0 follow-up, P1 evidence readiness, and P2/P3/P4 readiness contracts.
- Keep P2/P3/P4 local contracts source-bound and fail-closed while widening visibility.
- Do not execute live gates until remaining-backlog external inputs are complete and operator-approved.

## Must Not Claim
- P0-P4 production system is fully complete
- live gates have run
- model has been trained or retrained
- wet-lab validation or manufacturing constraints are proven by this audit
