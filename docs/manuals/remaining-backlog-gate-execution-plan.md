# Remaining Backlog Gate Execution Plan

- Created at: `2026-09-01T10:00:29.463605+00:00`
- Mode: `read_only_remaining_backlog_gate_execution_plan`
- Network IO: `not_executed`
- Destructive actions: `not_executed`
- Secrets printed: `false`
- Armed rows: `0`
- Blocked rows: `7`

## formal_domain_https

- Status: `planned`
- Armed: `false`
- Safety note: Requires real DNS and TLS cutover evidence before production HTTPS status can be claimed.
- Missing fields:
  - `formal_domain`
  - `dns_record_owner`
  - `tls_certificate_source`
  - `PUBLIC_BASE_URL`
  - `FRONTEND_URL`
  - `OIDC_ISSUER`
- Redacted values:
  - `FRONTEND_URL` = `<fill>`
  - `OIDC_ISSUER` = `<fill>`
  - `PUBLIC_BASE_URL` = `<fill>`
  - `dns_record_owner` = `<fill>`
  - `formal_domain` = `<fill>`
  - `tls_certificate_source` = `<fill>`

## gpu_gromacs_md_live

- Status: `external_required`
- Armed: `false`
- Safety note: Requires a real GPU/GROMACS runner and real WT/mutant inputs; this plan does not start MD jobs.
- Missing fields:
  - `gpu_node_or_runner`
  - `gromacs_runtime_version`
  - `wt_pdb_input`
  - `mutant_pdb_input`
  - `md_worker_capacity_window`
- Redacted values:
  - `gpu_node_or_runner` = `<fill>`
  - `gromacs_runtime_version` = `<fill>`
  - `md_worker_capacity_window` = `<fill>`
  - `mutant_pdb_input` = `<fill>`
  - `wt_pdb_input` = `<fill>`

## md_blackbox_live_e2e

- Status: `external_required`
- Armed: `false`
- Safety note: Requires live credentials and either an existing task id or explicit submission approval.
- Missing fields:
  - `MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT`
  - `MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL`
  - `credential_secret_reference`
  - `validation_window`
- Redacted values:
  - `MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL` = `<fill>`
  - `MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT` = `<fill>`
  - `credential_secret_reference` = `<secret-reference-provided>`
  - `validation_window` = `<fill>`

## ligand_runtime_live

- Status: `external_required`
- Armed: `false`
- Safety note: Requires the real ligand toolchain runtime; local missing tools remain blocked.
- Missing fields:
  - `ligand_worker_image_or_host`
  - `OpenBabel_or_RDKit_available`
  - `AutoDock_Vina_available`
  - `ACPYPE_or_AmberTools_available`
  - `GROMACS_available`
- Redacted values:
  - `ACPYPE_or_AmberTools_available` = `<fill>`
  - `AutoDock_Vina_available` = `<fill>`
  - `GROMACS_available` = `<fill>`
  - `OpenBabel_or_RDKit_available` = `<fill>`
  - `ligand_worker_image_or_host` = `<fill>`

## oss_minio_live_e2e

- Status: `external_required`
- Armed: `false`
- Safety note: Requires write/read/delete permission in a controlled live bucket scope.
- Missing fields:
  - `storage_endpoint`
  - `bucket_name`
  - `access_key_secret_reference`
  - `write_read_delete_permission_scope`
- Redacted values:
  - `access_key_secret_reference` = `<secret-reference-provided>`
  - `bucket_name` = `<fill>`
  - `storage_endpoint` = `<fill>`
  - `write_read_delete_permission_scope` = `<fill>`

## admin_authenticated_screenshots

- Status: `external_required`
- Armed: `false`
- Safety note: Requires admin credentials through secret references only.
- Missing fields:
  - `SCREENSHOT_EMAIL_secret_reference`
  - `SCREENSHOT_PASSWORD_secret_reference`
  - `FRONTEND_BASE_URL`
- Redacted values:
  - `FRONTEND_BASE_URL` = `<fill>`
  - `SCREENSHOT_EMAIL_secret_reference` = `<secret-reference-provided>`
  - `SCREENSHOT_PASSWORD_secret_reference` = `<secret-reference-provided>`

## maintenance_window_drills

- Status: `external_required`
- Armed: `false`
- Safety note: Requires an approved maintenance window before any production drill.
- Missing fields:
  - `MAINTENANCE_WINDOW_ID`
  - `ALLOW_PRODUCTION_DRILL_approval`
  - `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET`
  - `EXTERNAL_STORAGE_RESTORE_TARGET`
- Redacted values:
  - `ALLOW_PRODUCTION_DRILL_approval` = `<fill>`
  - `EXTERNAL_STORAGE_RESTORE_TARGET` = `<fill>`
  - `MAINTENANCE_WINDOW_ID` = `<fill>`
  - `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET` = `<fill>`
