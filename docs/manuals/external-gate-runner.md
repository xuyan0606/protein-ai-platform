# External Gate Runner

The runner is fail-closed. `make external-gates-plan` is read-only and never
contacts an external service. Execution requires `--execute`, complete inputs,
and an `armed` result from the gate contract. `pending`, `submitted`, `proxy`,
`demo-ready`, capability-only, and manual states are never promoted to pass.

## Commands

```bash
make external-gates-plan
make external-gate GATE=production_https
make external-gates-execute
```

`external-gate` requires a single `GATE` value. The runner uses only its
contract-defined argv; it does not evaluate shell strings. Missing inputs block
the gate without starting a subprocess. `maintenance_restore` remains
`manual_required` even when its inputs are complete.

## Gate input contract

Values below are environment variables. Non-secret values may be supplied in
the process environment. Secret values must be supplied only as environment
variables (or the runner's supported credentials-stdin mechanism); never put
them in command arguments, source files, or reports.

| Gate | Non-secret inputs | Secret environment variables |
| --- | --- | --- |
| `production_https` | `PUBLIC_BASE_URL`, `FRONTEND_URL`, `OIDC_ISSUER` | none |
| `foldseek_live` | `FOLDSEEK_RUNTIME`, `FOLDSEEK_DATABASE_ROOT` | none |
| `gpu_md` | `GPU_RUNNER`, `WT_PDB_INPUT`, `MUTANT_PDB_INPUT`, `MD_VALIDATION_WINDOW`, `ALLOW_MD_BLACKBOX_SUBMIT=true` | `MD_BLACKBOX_PASSWORD` |
| `ligand_runtime` | `LIGAND_RUNTIME_IMAGE` | none |
| `oss_minio` | `OSS_ENDPOINT`, `OSS_BUCKET` | `OSS_ACCESS_KEY`, `OSS_SECRET_KEY` |
| `admin_screenshot` | `FRONTEND_BASE_URL` | `SCREENSHOT_EMAIL`, `SCREENSHOT_PASSWORD` |
| `maintenance_restore` | `MAINTENANCE_WINDOW_ID`, `ALLOW_PRODUCTION_DRILL=true`, `OFFSITE_BACKUP_TARGET`, `OFFSITE_RESTORE_TARGET`, `EXTERNAL_STORAGE_BACKUP_REF`, `EXTERNAL_STORAGE_RESTORE_TARGET` | none |

For `gpu_md`, an existing task/resume identifier is preferred; the runner must
not submit a new black-box task unless the explicit authorization variable is
present. OSS checks use a random temporary prefix and must verify write, read,
hash, and cleanup.

## Evidence output

Each run writes a directory under
`docs/manuals/external-gate-runs/<run-id>/` containing structured summaries,
per-gate results, and an evidence manifest. The manifest records relative path,
byte size, and SHA-256. Reports record input presence (not values), command
identifiers, exit status, final gate status, and evidence paths. Secret values,
full environment snapshots, credentials, and unredacted stdout/stderr must not
be archived. A cleanup failure or incomplete terminal evidence is `failed`.

## Prohibited actions

- Do not use plan output, mocks, proxy results, demos, or capability checks as live evidence.
- Do not add arbitrary shell commands, network URLs, object keys, or destructive actions to a gate.
- Do not create cloud resources, request domains/certificates, install GPU drivers, or switch production storage paths.
- Do not stop production services, restore over production, delete user objects, or bypass an approved maintenance window.
- Do not treat a submitted/pending MD job as passed; verify terminal status and owned downloadable artifacts.
- Do not publish secrets in logs, JSON, Markdown, commits, screenshots, or issue comments.

Production rollback, off-site restore, and external-storage shadow restore are
operator actions. The runner may prepare or validate evidence, but a human must
approve and perform any destructive production step separately.
