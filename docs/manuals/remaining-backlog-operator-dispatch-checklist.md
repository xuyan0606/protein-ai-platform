# Remaining Backlog Operator Dispatch Checklist

- Created at: `2026-09-01T10:00:29.490837+00:00`
- Mode: `read_only_remaining_backlog_operator_dispatch_checklist`
- Network IO: `not_executed`
- Destructive actions: `not_executed`
- Secrets printed: `false`
- Live commands included: `false`
- Blocked rows: `7`
- Armed rows: `0`

## infra_dns_tls

- Scope: Formal domain, TLS, and identity config
- Items: `formal_domain_https`
- Waiting for input: `1`
- Armed: `0`

### formal_domain_https

- Priority: `P0`
- Source status: `planned`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires real DNS and TLS cutover evidence before production HTTPS status can be claimed.
- Fields to collect:
  - `formal_domain`
  - `dns_record_owner`
  - `tls_certificate_source`
  - `PUBLIC_BASE_URL`
  - `FRONTEND_URL`
  - `OIDC_ISSUER`
- Validate after collection:
  - `make production-config-gate`
  - `make nightly-live-gates FRONTEND_BASE_URL=https://<domain>`

## ligand_runtime

- Scope: Ligand preprocessing, docking, topology runtime
- Items: `ligand_runtime_live`
- Waiting for input: `1`
- Armed: `0`

### ligand_runtime_live

- Priority: `P1`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires the real ligand toolchain runtime; local missing tools remain blocked.
- Fields to collect:
  - `ligand_worker_image_or_host`
  - `OpenBabel_or_RDKit_available`
  - `AutoDock_Vina_available`
  - `ACPYPE_or_AmberTools_available`
  - `GROMACS_available`
- Missing requirements:
  - conformer_generation
  - pdbqt_preparation
  - vina_docking
  - ligand_topology
  - gromacs_md
- Validate after collection:
  - `make backend-ligand-toolchain-live-gate`

## md_runtime

- Scope: GPU/GROMACS and MD live validation
- Items: `gpu_gromacs_md_live, md_blackbox_live_e2e`
- Waiting for input: `2`
- Armed: `0`

### gpu_gromacs_md_live

- Priority: `P0`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires a real GPU/GROMACS runner and real WT/mutant inputs; this plan does not start MD jobs.
- Fields to collect:
  - `gpu_node_or_runner`
  - `gromacs_runtime_version`
  - `wt_pdb_input`
  - `mutant_pdb_input`
  - `md_worker_capacity_window`
- Missing requirements:
  - NVIDIA/GROMACS runtime
  - real WT/mutant PDB inputs
  - long-running MD worker capacity
- Validate after collection:
  - `make backend-md-topology-live-gate`

### md_blackbox_live_e2e

- Priority: `P0`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires live credentials and either an existing task id or explicit submission approval.
- Fields to collect:
  - `MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT`
  - `MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL`
  - `credential_secret_reference` (secret reference only)
  - `validation_window`
- Missing requirements:
  - MD_BLACKBOX_TASK_ID for resume or ALLOW_MD_BLACKBOX_SUBMIT=true for new submission
  - MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD
- Validate after collection:
  - `make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id <id> --email <email>'`

## qa_admin

- Scope: Authenticated admin screenshot evidence
- Items: `admin_authenticated_screenshots`
- Waiting for input: `1`
- Armed: `0`

### admin_authenticated_screenshots

- Priority: `P1`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires admin credentials through secret references only.
- Fields to collect:
  - `SCREENSHOT_EMAIL_secret_reference` (secret reference only)
  - `SCREENSHOT_PASSWORD_secret_reference` (secret reference only)
  - `FRONTEND_BASE_URL`
- Missing requirements:
  - SCREENSHOT_EMAIL
  - SCREENSHOT_PASSWORD
- Validate after collection:
  - `make manual-screenshots FRONTEND_BASE_URL=<url>`

## release_ops

- Scope: Maintenance window and drill evidence
- Items: `maintenance_window_drills`
- Waiting for input: `1`
- Armed: `0`

### maintenance_window_drills

- Priority: `P1`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires an approved maintenance window before any production drill.
- Fields to collect:
  - `MAINTENANCE_WINDOW_ID`
  - `ALLOW_PRODUCTION_DRILL_approval`
  - `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET`
  - `EXTERNAL_STORAGE_RESTORE_TARGET`
- Missing requirements:
  - MAINTENANCE_WINDOW_ID
  - ALLOW_PRODUCTION_DRILL=true
  - REMOTE_BACKUP_TARGET or OFFSITE_BACKUP_TARGET
  - EXTERNAL_STORAGE_RESTORE_TARGET
- Validate after collection:
  - `make rollback-plan-json`
  - `make restore-drill BACKUP_FILE=<backup>`

## storage

- Scope: OSS/MinIO live storage scope
- Items: `oss_minio_live_e2e`
- Waiting for input: `1`
- Armed: `0`

### oss_minio_live_e2e

- Priority: `P0`
- Source status: `external_required`
- Dispatch status: `waiting_for_operator_input`
- Safety note: Requires write/read/delete permission in a controlled live bucket scope.
- Fields to collect:
  - `storage_endpoint`
  - `bucket_name`
  - `access_key_secret_reference` (secret reference only)
  - `write_read_delete_permission_scope`
- Missing requirements:
  - MINIO_ACCESS_KEY/MINIO_SECRET_KEY or ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET
  - live bucket permission
- Validate after collection:
  - `python3 scripts/smoke_oss_minio_contract.py --json --require-live`
