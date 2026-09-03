# Remaining Backlog Execution Tickets

- go_no_go_decision: `defer_waiting_for_external_inputs`
- ready_for_live_gate_execution: `False`
- live_gate_execution_allowed: `False`
- command_execution_allowed: `False`
- ticket_count: `7`
- blocked_ticket_count: `7`
- armed_ticket_count: `0`

## Priority Summary

| Priority | Tickets | Blocked | Armed | Items |
|---|---:|---:|---:|---|
| `P0` | `4` | `4` | `0` | `formal_domain_https, gpu_gromacs_md_live, md_blackbox_live_e2e, oss_minio_live_e2e` |
| `P1` | `3` | `3` | `0` | `ligand_runtime_live, admin_authenticated_screenshots, maintenance_window_drills` |

## RB-001-formal_domain_https

- Item: `formal_domain_https`
- Lane: `infra_dns_tls`
- Priority: `P0`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires real DNS and TLS cutover evidence before production HTTPS status can be claimed.
- Missing inputs:
  - `formal_domain`
  - `dns_record_owner`
  - `tls_certificate_source`
  - `PUBLIC_BASE_URL`
  - `FRONTEND_URL`
  - `OIDC_ISSUER`
- Evidence to collect:
  - Run python3 scripts/check_production_config.py --mode production --require-production-safe --env-file docker/.env.aliyun.app.
  - Run FRONTEND_BASE_URL=<https-domain> python3 scripts/run_nightly_live_gates.py --json.
- Validate after collection:
  - `make production-config-gate`
  - `make nightly-live-gates FRONTEND_BASE_URL=https://<domain>`

## RB-002-gpu_gromacs_md_live

- Item: `gpu_gromacs_md_live`
- Lane: `md_runtime`
- Priority: `P0`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires a real GPU/GROMACS runner and real WT/mutant inputs; this plan does not start MD jobs.
- Missing inputs:
  - `gpu_node_or_runner`
  - `gromacs_runtime_version`
  - `wt_pdb_input`
  - `mutant_pdb_input`
  - `md_worker_capacity_window`
- Evidence to collect:
  - Provision the Aliyun GPU/GROMACS node, then run make backend-md-topology-live-gate.
  - After topology validation, submit real WT/mutant replicate batches and summarize ranking reports.
- Validate after collection:
  - `make backend-md-topology-live-gate`

## RB-003-md_blackbox_live_e2e

- Item: `md_blackbox_live_e2e`
- Lane: `md_runtime`
- Priority: `P0`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires live credentials and either an existing task id or explicit submission approval.
- Missing inputs:
  - `MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT`
  - `MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL`
  - `credential_secret_reference` (secret reference only)
  - `validation_window`
- Evidence to collect:
  - Prefer resume mode first: set MD_BLACKBOX_TASK_ID plus live account credentials for an existing completed/running task.
  - For a fresh long-task proof, set ALLOW_MD_BLACKBOX_SUBMIT=true and run during a validation window.
- Validate after collection:
  - `make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id <id> --email <email>'`

## RB-004-ligand_runtime_live

- Item: `ligand_runtime_live`
- Lane: `ligand_runtime`
- Priority: `P1`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires the real ligand toolchain runtime; local missing tools remain blocked.
- Missing inputs:
  - `ligand_worker_image_or_host`
  - `OpenBabel_or_RDKit_available`
  - `AutoDock_Vina_available`
  - `ACPYPE_or_AmberTools_available`
  - `GROMACS_available`
- Evidence to collect:
  - Install or build the ligand worker runtime with OpenBabel or RDKit, AutoDock Vina, ACPYPE/AmberTools, and GROMACS.
  - Then run make backend-ligand-toolchain-live-gate.
  - Or build protein-ai-ligand-worker:aliyun and rerun the read-only readiness check.
- Validate after collection:
  - `make backend-ligand-toolchain-live-gate`

## RB-005-oss_minio_live_e2e

- Item: `oss_minio_live_e2e`
- Lane: `storage`
- Priority: `P0`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires write/read/delete permission in a controlled live bucket scope.
- Missing inputs:
  - `storage_endpoint`
  - `bucket_name`
  - `access_key_secret_reference` (secret reference only)
  - `write_read_delete_permission_scope`
- Evidence to collect:
  - Set live OSS/MinIO endpoint and credentials in the deployment environment.
  - Run python3 scripts/smoke_oss_minio_contract.py --json --require-live or acceptance matrix --include-oss-e2e.
- Validate after collection:
  - `python3 scripts/smoke_oss_minio_contract.py --json --require-live`

## RB-006-admin_authenticated_screenshots

- Item: `admin_authenticated_screenshots`
- Lane: `qa_admin`
- Priority: `P1`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires admin credentials through secret references only.
- Missing inputs:
  - `SCREENSHOT_EMAIL_secret_reference` (secret reference only)
  - `SCREENSHOT_PASSWORD_secret_reference` (secret reference only)
  - `FRONTEND_BASE_URL`
- Evidence to collect:
  - Provide admin screenshot credentials through SCREENSHOT_EMAIL/SCREENSHOT_PASSWORD.
  - Rerun make manual-screenshots FRONTEND_BASE_URL=http://127.0.0.1:4203 and verify /admin final_url.
- Validate after collection:
  - `make manual-screenshots FRONTEND_BASE_URL=<url>`

## RB-007-maintenance_window_drills

- Item: `maintenance_window_drills`
- Lane: `release_ops`
- Priority: `P1`
- Status: `started_blocked_waiting_for_operator_input`
- Operator action: `collect_missing_inputs_and_rerun_validation`
- Safety: Requires an approved maintenance window before any production drill.
- Missing inputs:
  - `MAINTENANCE_WINDOW_ID`
  - `ALLOW_PRODUCTION_DRILL_approval`
  - `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET`
  - `EXTERNAL_STORAGE_RESTORE_TARGET`
- Evidence to collect:
  - Schedule a maintenance window and set MAINTENANCE_WINDOW_ID plus ALLOW_PRODUCTION_DRILL=true.
  - Provide offsite backup and external storage restore targets before running live drills.
- Validate after collection:
  - `make rollback-plan-json`
  - `make restore-drill BACKUP_FILE=<backup>`

Next action: collect missing operator inputs for every blocked ticket, rerun validation, then rerun go/no-go
