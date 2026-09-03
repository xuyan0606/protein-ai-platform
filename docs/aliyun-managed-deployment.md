# Alibaba Cloud Managed Deployment

This repo now includes deployment assets aligned with the `阿里云冗余 GPU 部署与分子动力学方案` document:

- `ECS-App-01` / `ECS-App-02`: app node stack
- `ECS-GPU-01`: dedicated MD / GPU worker
- managed `RDS PostgreSQL`
- managed `Redis`
- managed `OSS`
- local `Outline` and `ChromaDB` on the app node for the current stage

## Files Added For This Topology

- `docker/docker-compose.aliyun-app.yml`
- `docker/docker-compose.aliyun-gpu.yml`
- `docker/.env.aliyun.app.example`
- `docker/.env.aliyun.gpu.example`
- `deploy-aliyun.sh`

The existing `docker/docker-compose.yml` is still the integrated local/full-stack deployment and remains useful for local verification.

## Topology Mapping

```text
Browser
  -> ECS-App-01 Nginx / Frontend / Backend / CPU Worker / Outline / ChromaDB
       -> RDS PostgreSQL
       -> Cloud Redis
       -> OSS

ECS-App-02
  -> same image + same compose + same managed services
  -> used for release, failover, rollback

ECS-GPU-01
  -> dedicated md-worker
  -> dedicated ligand-worker
  -> same Redis / RDS / OSS
  -> no public ingress required
```

## Step 1: Prepare Shared Data And Env Files

From the repo root:

```bash
python3 scripts/write_deploy_env.py --deploy-root deploy_data
cp docker/.env.example docker/.env
cp docker/.env.aliyun.app.example docker/.env.aliyun.app
cp docker/.env.aliyun.gpu.example docker/.env.aliyun.gpu
```

Fill these files before the first deploy:

- `docker/.env`
- `docker/.env.deploy-data`
- `docker/.env.aliyun.app`
- `docker/.env.aliyun.gpu`

## Step 2: Deploy App Nodes

Use the same app compose on both `ECS-App-01` and `ECS-App-02`:

```bash
./deploy-aliyun.sh app config
./deploy-aliyun.sh app
```

Equivalent `make` commands:

```bash
make docker-config-aliyun-app
make docker-up-aliyun-app
make docker-ps-aliyun-app
```

One-time Outline migration after the first app-node start:

```bash
cd docker
docker compose --env-file .env --env-file .env.aliyun.app --env-file .env.deploy-data -f docker-compose.aliyun-app.yml exec outline yarn db:migrate
```

## Step 3: Deploy GPU / Scientific Worker Node

On `ECS-GPU-01`:

```bash
./deploy-aliyun.sh gpu config
./deploy-aliyun.sh gpu
```

Equivalent `make` commands:

```bash
make docker-config-aliyun-gpu
make docker-up-aliyun-gpu
make docker-ps-aliyun-gpu
```

The `make docker-config-*` targets validate compose files with `--quiet` so secrets from `.env` files are not printed to the terminal.

Install `NVIDIA Container Toolkit` first if the node should execute real GPU workloads inside Docker.

The GPU/scientific worker compose now starts two isolated Celery workers:

| Service | Queue | Purpose |
|---------|-------|---------|
| `md-worker` | `md_cpu` | GROMACS topology/live MD tasks |
| `ligand-worker` | `ligand_cpu` | OpenBabel 2D->3D, Vina docking prep, ligand topology tooling |

The ligand worker uses `docker/Dockerfile.ligand-worker` so OpenBabel/Vina/ACPYPE packages do not bloat the app backend image.

## OSS Notes

Backend storage now supports:

- `MINIO_SECURE=true`
- `MINIO_REGION=<region>`

That means backend `MINIO_*` vars can point to OSS directly.

Outline uses its own S3-compatible envs:

- `AWS_S3_UPLOAD_BUCKET_NAME`
- `AWS_S3_UPLOAD_BUCKET_URL`
- `AWS_S3_FORCE_PATH_STYLE`
- `AWS_REGION`

If OSS uploads fail because of endpoint style, adjust `ALIYUN_OSS_FORCE_PATH_STYLE` in `docker/.env.aliyun.app`.

## What Stays Local On The App Node

Per the current phase of the architecture plan, these remain local to `ECS-App-01` / `ECS-App-02`:

- `Outline`
- `ChromaDB`
- `model_cache`

These should be treated as rebuildable. Persistent business data should live in:

- `RDS`
- `Redis`
- `OSS`

## Recommended Verification

App node:

```bash
make deploy-live-gate
curl -fsS http://localhost:4200/api/health
```

GPU node:

```bash
make backend-smoke-live
make backend-ligand-toolchain-smoke
```

Functional checks to run after deployment:

- login
- `/wiki`
- `/pdb`
- one short `gromacs_md` async task
- one `ligand_preprocess` preflight task
- artifact download from OSS-backed storage
