# Protein AI Platform

AI-assisted protein research platform for sequence analysis, structure review,
enzyme annotation, mutation prioritization, report publishing, and real
GROMACS-backed molecular dynamics workflows.

## Current Capabilities

- Chat agent with registered protein tools, streaming responses, and optional
  auto-publishing of reports to the project Wiki.
- Project workspace with sequence/file management, Markdown report storage, and
  Outline-backed Wiki collections.
- PDB upload and analysis page with structure parsing, 3D viewing, annotation
  cards, and asynchronous MD task submission.
- Tool registry covering sequence search, structure prediction/design,
  annotation, mutation scoring, docking, benchmarking, and simulation tools.
- Local data layer with PostgreSQL, Redis, MinIO, ChromaDB, and curated fixture
  support for annotation and signal peptide workflows.
- Alibaba Cloud deployment prep for a managed topology:
  `RDS PostgreSQL + Cloud Redis + OSS + separate GPU worker`.
- OIDC bridge for Outline Wiki access using the platform session cookie
  (`pa_token`), including a `/auth/oidc` bootstrap route.

## Manuals

- [管理员手册](docs/manuals/admin-manual.md)
- [研发用户手册](docs/manuals/researcher-manual.md)
- [数据导入手册](docs/manuals/data-import-manual.md)
- [故障处理手册](docs/manuals/troubleshooting-manual.md)

## Quick Start

The integrated stack is served through Nginx on port `4200`.

```bash
cd docker
cp ../backend/.env.example .env
docker compose --env-file .env up -d
```

Open:

- App: `http://localhost:4200`
- API health: `http://localhost:4200/api/health`
- API docs in a direct backend dev run: `http://localhost:8000/docs`

Top-level convenience targets:

```bash
make help
make init-deploy-local-dry-run
make init-deploy-local
make docker-up
make docker-up-with-deploy-env
make deploy-preflight
make deploy-demo-check
make docker-backend-smoke-live
make docker-backend-rebuild-and-smoke
make package-deploy-bundle
make docker-config-aliyun-app
make docker-up-aliyun-app
make docker-config-aliyun-gpu
make docker-up-aliyun-gpu
```

For local frontend development:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 4200
```

For local backend development:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Architecture

```text
Browser
  -> Nginx (host port 4200)
       -> React SPA frontend container (port 3000)
       -> FastAPI backend container (port 8000)
            -> Agent orchestrator
            -> ToolRegistry
            -> PostgreSQL + pgvector
            -> Redis cache and Celery broker
            -> MinIO object storage
            -> ChromaDB vector store
            -> Celery worker for async/long-running tools
       -> Outline Wiki container (proxied under /wiki)
```

For the target Alibaba Cloud production topology, this repo now also ships a
managed-services deployment path:

```text
ECS-App-01 / ECS-App-02
  -> Nginx + Frontend + Backend + CPU Worker + Outline + ChromaDB
  -> RDS PostgreSQL + Cloud Redis + OSS

ECS-GPU-01
  -> dedicated md-worker
  -> same RDS + Redis + OSS
```

See [docs/aliyun-managed-deployment.md](docs/aliyun-managed-deployment.md).

## Authentication And Wiki

The platform uses JWT cookies for browser sessions. The primary access cookie is
`pa_token`; refresh behavior is handled by the backend and frontend API layer.
Backend API authentication accepts a valid bearer token or a valid `pa_token`
cookie, which keeps browser sessions usable when local client state drifts.

Outline is embedded and proxied under `/wiki`. The backend provides a minimal
OIDC provider for Outline:

- `GET /auth/oidc` starts the browser-facing Wiki/OIDC bootstrap flow.
- `GET /api/oidc/authorize` issues an auth code when `pa_token` is valid.
- `GET /wiki/auth/oidc.callback` is the browser-visible callback path.

Anonymous Wiki access is redirected into the platform login/OIDC flow before
Outline is allowed to boot its SPA.

## Tools And Async Tasks

Tool metadata is exposed through:

- `GET /api/tools`
- `GET /api/tools/{name}`
- `GET /api/tools/diagnostics`

Synchronous tools can be called with:

```http
POST /api/tools/{name}/call
```

Async-capable tools can be submitted and polled with:

```http
POST /api/tools/{name}/submit
GET  /api/tools/tasks/{task_id}
```

Async task ownership metadata is persisted through the Redis-backed cache layer,
with a local fallback for degraded single-process development/test runs.
Unknown tasks return `404`, and tasks owned by another user return `403`.
Owned async tasks can also be cancelled with:

```http
POST /api/tools/tasks/{task_id}/cancel
```

Cancellation requests are recorded in task metadata and returned by task polling
as `cancel_requested` / `cancel_requested_at`.
Real MD tasks are routed to the dedicated `md_cpu` Celery queue, consumed by the
`md-worker` service with default concurrency `1`; lighter async tools stay on
the `default` queue.

## Real MD Workflow

`gromacs_md` is a real GROMACS pipeline, not a simulated/random metrics stub.
It requires a real PDB input via `pdb_data`, `pdb_path`, or `pdb_object_name`.
If `gmx`/`gmx_mpi` or a valid PDB is missing, the tool fails explicitly instead
of fabricating MD results.

The Docker backend image installs GROMACS. The pipeline performs:

```text
pdb2gmx -> editconf -> solvate -> grompp/genion
        -> minimization -> equilibration -> production MD
        -> RMSD/RMSF/Rg/SASA parsing
```

The `/pdb` page submits a short baseline async task for validation and can
request cancellation of an active MD task. Production MD should still be treated
as a long-running scientific workflow that needs reviewed parameters, sufficient
trajectory length, and appropriate hardware.

Completed and failed GROMACS runs return an `artifact_manifest` that groups
uploaded outputs into structures, topology, trajectory, analysis, parameters,
logs, and other files for download and reproducibility.

## Environment

Copy `backend/.env.example` to `docker/.env` for Docker Compose, or to
`backend/.env` for direct backend development.

Required for normal operation:

- `SECRET_KEY`
- `PUBLIC_BASE_URL`
- PostgreSQL/Redis/MinIO settings
- At least one LLM provider API key

Common LLM options are `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`,
`OPENAI_API_KEY`, and `KUAPAO_API_KEY`.

For Alibaba Cloud managed deployment, copy these templates:

```bash
make init-deploy-aliyun-dry-run
python3 scripts/init_deployment.py --profile all --public-base-url https://proteinai.example.com
```

Then fill the real RDS, Redis, OSS, and LLM provider values in
`docker/.env.aliyun.app` / `docker/.env.aliyun.gpu`, and use:

```bash
./deploy-aliyun.sh app
./deploy-aliyun.sh gpu
```

or:

```bash
make docker-up-aliyun-app
make docker-up-aliyun-gpu
```

## Deployment Package

Use the package targets when preparing a handoff bundle for another machine or
server:

```bash
make package-preflight
make upgrade-readiness
make package-deploy-bundle-dry-run
make package-deploy-bundle
```

The generated archive is written to `dist/packages/` with a matching
`.sha256` checksum. By default it excludes local dependencies, `.env` files,
keys, logs, databases, runtime storage, backups, and `deploy_data/` so that
real secrets and large scientific datasets are not accidentally shipped.

Each archive contains one top-level directory, `protein-ai-platform/`. On a
server, install it with:

```bash
scripts/install_release_bundle.sh /opt/protein-ai-platform/incoming/protein-ai-platform-<release>.tar.gz
```

The installer validates the checksum and points
`/opt/protein-ai-platform/current` at
`/opt/protein-ai-platform/releases/<release>/protein-ai-platform`.

If a data bundle is intentionally required, run the script directly with:

```bash
python3 scripts/package_deploy_bundle.py --include-deploy-data
```

## Backup And Restore

Local Docker backups use PostgreSQL custom-format dumps plus a SHA-256 checksum:

```bash
make backup-dry-run
make backup-local
```

Verify a backup before trusting it:

```bash
make verify-backup BACKUP_FILE=backups/protein_ai_20260707T000000Z.dump
```

Run a safe restore drill into a temporary database. This does not touch the main
`POSTGRES_DB`:

```bash
make restore-drill-dry-run BACKUP_FILE=backups/protein_ai_20260707T000000Z.dump
make restore-drill BACKUP_FILE=backups/protein_ai_20260707T000000Z.dump
```

Restore is destructive and requires an explicit confirmation unless `--yes` is
provided:

```bash
make restore-dry-run BACKUP_FILE=backups/protein_ai_20260707T000000Z.dump
./scripts/restore.sh backups/protein_ai_20260707T000000Z.dump
```

The restore script also supports legacy `*.sql.gz` plain SQL backups, but new
backups should use the default `*.dump` format.

## Upgrade Flow

Before upgrading a local Docker deployment:

```bash
make upgrade-readiness
make backup-dry-run
make upgrade-dry-run
make rollback-plan
```

To execute the local upgrade after reviewing the plan:

```bash
./scripts/upgrade.sh --mode local
```

For Alibaba Cloud roles:

```bash
./scripts/upgrade.sh --mode aliyun-app --dry-run
./scripts/upgrade.sh --mode aliyun-gpu --dry-run
```

Generate a rollback plan without changing services or databases:

```bash
make rollback-plan
python3 scripts/rollback_plan.py --mode aliyun-app --json
```

The rollback plan is intentionally read-only. It identifies the latest local
deploy package and PostgreSQL dump, prints verification/drill commands, and
marks destructive steps that still require an approved maintenance window.

For local curated data and structure search assets, the stack now supports a
single deploy-data root:

- Docker default host path: `deploy_data/` via `DEPLOY_DATA_HOST_PATH`
- Container path: `/app/deploy_data`
- Direct backend dev now auto-discovers repo-root `deploy_data/` when it exists

When `DEPLOY_DATA_ROOT` is set, the backend auto-discovers these optional
subdirectories/files when they exist:

- `annotations/` -> `LOCAL_ANNOTATION_FIXTURE_PATH`
- `sifts/` -> `SIFTS_MAPPING_PATH`
- `foldseek/` -> `FOLDSEEK_DATABASE_ROOT`
- `smoke/query.pdb` -> `STRUCTURE_SMOKE_PDB_FILE`

See [deploy_data/README.md](deploy_data/README.md) for the expected layout.
For the shortest operator path, see [docs/live-deploy-runbook.md](docs/live-deploy-runbook.md).
To scaffold that layout automatically:

```bash
python scripts/prepare_deploy_data.py
python scripts/prepare_deploy_data.py --with-demo
python scripts/check_deploy_data.py
python scripts/discover_deploy_data_sources.py --root ..
python scripts/refresh_live_deploy_data.py --manifest deploy_data/live_manifest.json --verify
python scripts/import_deploy_data.py --annotations /path/to/annotations --sifts /path/to/sifts --pdb /path/to/pdb --alphafold /path/to/alphafold --foldseek-root /path/to/foldseek --smoke-pdb /path/to/query.pdb
python scripts/download_rcsb_structures.py --ids 4HHB,1TIM --format cif
python scripts/download_alphafold_models.py --ids P19531,P00690 --structure-format cif --with-pae-json
python scripts/download_sifts_mappings.py --ids 1QHP,1QHO,1BLI
python scripts/build_foldseek_db.py --kind pdb
python scripts/write_deploy_env.py
make env-preflight
make deploy-preflight
make docker-up-with-deploy-env
make docker-backend-smoke-live
make docker-backend-rebuild-and-smoke
```

Optional structure-search settings:

- `FOLDSEEK_API_URL` for a remote Foldseek HTTP service
- or `FOLDSEEK_BINARY` plus `FOLDSEEK_DATABASE_PDB` / `FOLDSEEK_DATABASE_ALPHAFOLD` /
  `FOLDSEEK_DATABASE_CUSTOM` for a local Foldseek CLI wrapper
- `FOLDSEEK_DATABASE_ROOT` can be used as a shared base directory when the
  database names map to subdirectories such as `pdb/` or `alphafold/`
- `SIFTS_MAPPING_PATH` can point to a JSON/CSV/TSV file or directory of local
  residue mappings; `/api/pdb/mapping` uses it before falling back to inferred
  coordinate-order mapping
- `LOCAL_ANNOTATION_FIXTURE_PATH` can point to a JSON file or a structured
  directory. Structured local annotation imports now accept `base`,
  `interpro`, `mcsa`, and `signalp` as `.json`, `.csv`, or `.tsv`.

## Verification

Useful local checks:

```bash
make env-preflight
cd frontend && npm run build
cd frontend && npm run smoke:http
cd frontend && node tests/public-smoke.mjs
cd frontend && node tests/live-smoke.mjs
cd backend && python -m compileall app tests
cd backend && .venv/bin/pytest tests -q
cd backend && .venv/bin/python scripts/structure_smoke_readiness.py
cd backend && .venv/bin/python scripts/smoke_structure_data.py
cd docker && docker compose ps
```

`backend/scripts/smoke_structure_data.py` is env-driven:

- it prints `SKIP` when real Foldseek/SIFTS sources are not configured
- `SIFTS_SMOKE_USE_DEMO=1` runs a bundled local SIFTS demo fixture without
  pretending real external structure data exists
- `FOLDSEEK_SMOKE_USE_DEMO=1` validates the degraded `summary_only` Foldseek
  fallback path without pretending a real Foldseek backend exists
- it validates `SIFTS_MAPPING_PATH` when paired with `SIFTS_SMOKE_PDB_ID`
- if `SIFTS_SMOKE_PDB_ID` is unset, it now tries to infer the PDB id from the
  first local mapping filename under `SIFTS_MAPPING_PATH`
- it validates a real Foldseek search when `STRUCTURE_SMOKE_PDB_FILE` and either
  `FOLDSEEK_API_URL` or `FOLDSEEK_BINARY + FOLDSEEK_DATABASE_*` are configured
- `make docker-backend-smoke-live` runs the same live smoke inside the running
  backend container
- `make docker-backend-rebuild-and-smoke` rebuilds the backend container and
  immediately reruns the live smoke in-container

`backend/scripts/structure_smoke_readiness.py` reports whether the current
machine is:

- `demo-ready` for bundled structure smoke fixtures
- or `live-ready` for real SIFTS/Foldseek inputs
- and now also checks whether real annotation exports are present under the
  configured deploy-data root
- demo `annotations` / demo `sifts` are reported as `demo`, not `ready`, so
  `live-ready` is now reserved for actual live-data candidates
- `make backend-readiness` and `make backend-smoke-live` now auto-load
  `backend/.env.deploy-data` when present, so host-side smoke uses the same
  deploy-data wiring as the generated local env override
- `make backend-live-gate` is stricter: it exits non-zero unless readiness
  reaches `summary\tlive-ready`, which is useful for real deployment sign-off
- `make docker-backend-live-gate` does the same strict gate inside the running
  backend container
- `make deploy-live-gate` is stricter still: it fails unless both
  `check_deploy_data.py` reaches `live-data-ready` and backend readiness reaches
  `live-ready`

`scripts/check_deploy_data.py` is the operator-facing preflight for the
host-side `deploy_data/` tree. Use it before backend readiness/smoke commands
to confirm whether the real data layout is complete enough to attempt
`live-ready`.

It also supports a strict mode:

- `python scripts/check_deploy_data.py --require-live`
- or `make deploy-live-gate`

`scripts/discover_deploy_data_sources.py` scans a local workspace for likely
annotation / SIFTS / Foldseek / PDB / AlphaFold candidates that could be staged
into `deploy_data/`. This is useful when the machine already has reference
repos or exported files but the final import paths are not yet clear.

Recent verified baseline:

- Frontend production build passes.
- Frontend HTTP smoke passes against the live stack.
- Playwright `public-smoke` and `live-smoke` pass on the host runtime.
- Backend test suite passes: `292 passed`.
- Backend, frontend, nginx, Outline, PostgreSQL, Redis, MinIO, and ChromaDB run
  healthy in the Docker stack.
- `gromacs_md` no longer generates fake MD metrics and can execute the real
  GROMACS preprocessing chain in the backend runtime.
