# Remaining Backlog External Input Packet

- Created at: `2026-09-01T10:00:29.407139+00:00`
- Mode: `read_only_external_input_packet`
- Network IO: `not_executed`
- Destructive actions: `not_executed`
- Summary: `{"bucket_counts": {"external_dependency": 7, "local_capable": 2}, "counts": {"external_required": 6, "planned": 1, "ready": 2}, "destructive_actions": "not_executed", "network_io": "not_executed", "status": "external_required", "total": 9}`

## Priority Summary

| Priority | Items | Required Input Fields |
|---|---:|---:|
| `P0` | `formal_domain_https, gpu_gromacs_md_live, md_blackbox_live_e2e, oss_minio_live_e2e` | `19` |
| `P1` | `ligand_runtime_live, admin_authenticated_screenshots, maintenance_window_drills` | `12` |

## 1. formal_domain_https

- Priority: `P0`
- Status: `planned`
- Bucket: `external_dependency`
- Detail: PUBLIC_BASE_URL already points at an HTTPS domain; run full production config and browser gates after certificate deployment
- Required input fields:
  - `formal_domain`
  - `dns_record_owner`
  - `tls_certificate_source`
  - `PUBLIC_BASE_URL`
  - `FRONTEND_URL`
  - `OIDC_ISSUER`
- Validation commands:
  - `make production-config-gate`
  - `make nightly-live-gates FRONTEND_BASE_URL=https://<domain>`
- Next actions:
  - Run python3 scripts/check_production_config.py --mode production --require-production-safe --env-file docker/.env.aliyun.app.
  - Run FRONTEND_BASE_URL=<https-domain> python3 scripts/run_nightly_live_gates.py --json.
- Source: `docker/.env.aliyun.app`

## 2. gpu_gromacs_md_live

- Priority: `P0`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: GROMACS topology live gate is not available on this host: GROMACS_NOT_INSTALLED
- Required input fields:
  - `gpu_node_or_runner`
  - `gromacs_runtime_version`
  - `wt_pdb_input`
  - `mutant_pdb_input`
  - `md_worker_capacity_window`
- Current missing requirements:
  - `NVIDIA/GROMACS runtime`
  - `real WT/mutant PDB inputs`
  - `long-running MD worker capacity`
- Validation commands:
  - `make backend-md-topology-live-gate`
- Next actions:
  - Provision the Aliyun GPU/GROMACS node, then run make backend-md-topology-live-gate.
  - After topology validation, submit real WT/mutant replicate batches and summarize ranking reports.
- Source: `backend/scripts/smoke_md_topology.py`

## 3. md_blackbox_live_e2e

- Priority: `P0`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: MD black-box long-task gate is available but not armed; no live MD task was submitted
- Required input fields:
  - `MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT`
  - `MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL`
  - `credential_secret_reference`
  - `validation_window`
- Current missing requirements:
  - `MD_BLACKBOX_TASK_ID for resume or ALLOW_MD_BLACKBOX_SUBMIT=true for new submission`
  - `MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD`
- Validation commands:
  - `make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id <id> --email <email>'`
- Next actions:
  - Prefer resume mode first: set MD_BLACKBOX_TASK_ID plus live account credentials for an existing completed/running task.
  - For a fresh long-task proof, set ALLOW_MD_BLACKBOX_SUBMIT=true and run during a validation window.
- Source: `backend/scripts/verify_md_blackbox.py --base-url https://proteinai.example.com`

## 4. ligand_runtime_live

- Priority: `P1`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: ligand preprocessing/docking/topology runtime is not complete on this host
- Required input fields:
  - `ligand_worker_image_or_host`
  - `OpenBabel_or_RDKit_available`
  - `AutoDock_Vina_available`
  - `ACPYPE_or_AmberTools_available`
  - `GROMACS_available`
- Current missing requirements:
  - `conformer_generation`
  - `pdbqt_preparation`
  - `vina_docking`
  - `ligand_topology`
  - `gromacs_md`
- Validation commands:
  - `make backend-ligand-toolchain-live-gate`
- Next actions:
  - Install or build the ligand worker runtime with OpenBabel or RDKit, AutoDock Vina, ACPYPE/AmberTools, and GROMACS.
  - Then run make backend-ligand-toolchain-live-gate.
  - Or build protein-ai-ligand-worker:aliyun and rerun the read-only readiness check.
- Source: `permission denied while trying to connect to the docker API at unix:///Users/keweibo/.docker/run/docker.sock`

## 5. oss_minio_live_e2e

- Priority: `P0`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: OSS/MinIO E2E gate is available, but endpoint credentials or live bucket permission are not present in this shell
- Required input fields:
  - `storage_endpoint`
  - `bucket_name`
  - `access_key_secret_reference`
  - `write_read_delete_permission_scope`
- Current missing requirements:
  - `MINIO_ACCESS_KEY/MINIO_SECRET_KEY or ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET`
  - `live bucket permission`
- Validation commands:
  - `python3 scripts/smoke_oss_minio_contract.py --json --require-live`
- Next actions:
  - Set live OSS/MinIO endpoint and credentials in the deployment environment.
  - Run python3 scripts/smoke_oss_minio_contract.py --json --require-live or acceptance matrix --include-oss-e2e.
- Source: `scripts/smoke_oss_minio_contract.py`

## 6. admin_authenticated_screenshots

- Priority: `P1`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: admin screenshots still require an authenticated admin session
- Required input fields:
  - `SCREENSHOT_EMAIL_secret_reference`
  - `SCREENSHOT_PASSWORD_secret_reference`
  - `FRONTEND_BASE_URL`
- Current missing requirements:
  - `SCREENSHOT_EMAIL`
  - `SCREENSHOT_PASSWORD`
- Validation commands:
  - `make manual-screenshots FRONTEND_BASE_URL=<url>`
- Next actions:
  - Provide admin screenshot credentials through SCREENSHOT_EMAIL/SCREENSHOT_PASSWORD.
  - Rerun make manual-screenshots FRONTEND_BASE_URL=http://127.0.0.1:4203 and verify /admin final_url.
- Source: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/docs/manuals/screenshots/manifest.json`

## 7. maintenance_window_drills

- Priority: `P1`
- Status: `external_required`
- Bucket: `external_dependency`
- Detail: real rollback, offsite backup, and external storage restore drills need an approved maintenance window
- Required input fields:
  - `MAINTENANCE_WINDOW_ID`
  - `ALLOW_PRODUCTION_DRILL_approval`
  - `REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET`
  - `EXTERNAL_STORAGE_RESTORE_TARGET`
- Current missing requirements:
  - `MAINTENANCE_WINDOW_ID`
  - `ALLOW_PRODUCTION_DRILL=true`
  - `REMOTE_BACKUP_TARGET or OFFSITE_BACKUP_TARGET`
  - `EXTERNAL_STORAGE_RESTORE_TARGET`
- Validation commands:
  - `make rollback-plan-json`
  - `make restore-drill BACKUP_FILE=<backup>`
- Next actions:
  - Schedule a maintenance window and set MAINTENANCE_WINDOW_ID plus ALLOW_PRODUCTION_DRILL=true.
  - Provide offsite backup and external storage restore targets before running live drills.
