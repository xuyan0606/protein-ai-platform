# Live Deploy Runbook

This project now supports a reproducible live-data deployment flow built around
`deploy_data/` plus one manifest file.

If you are deploying with the Alibaba Cloud managed topology
(`RDS + Redis + OSS + separate GPU worker`), pair this runbook with
[docs/aliyun-managed-deployment.md](aliyun-managed-deployment.md).

## What Is Fixed

- Live data root: `deploy_data/`
- Rebuild manifest: `deploy_data/live_manifest.json`
- Host env override: `backend/.env.deploy-data`
- Docker env override: `docker/.env.deploy-data`
- Local Foldseek DBs:
  - `deploy_data/foldseek/pdb`
  - `deploy_data/foldseek/alphafold`

## One Command

On a machine that already has the project checked out:

```bash
cd /Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台
python3 scripts/refresh_live_deploy_data.py --manifest deploy_data/live_manifest.json --verify --docker-verify
```

This command will:

1. Download real `PDB` structures from `RCSB`
2. Download real `SIFTS` mappings from `PDBe`
3. Download real `AlphaFold` models from `AlphaFold DB`
4. Build real local annotations from `UniProt` and `InterPro`
5. Rebuild local `Foldseek` databases
6. Materialize any non-portable Foldseek symlinks
7. Regenerate backend/docker deploy-data env files
8. Run host live gate and smoke
9. Run Docker live gate and smoke

## Faster Re-Verification

If files are already present and you only want to rebuild indices plus re-run
verification:

```bash
python3 scripts/refresh_live_deploy_data.py --skip-downloads --verify --docker-verify
```

## Make Targets

Equivalent shortcuts:

```bash
make refresh-live-deploy-data
make refresh-live-deploy-data-verify
make deploy-live-gate
make backend-smoke-live
make docker-backend-live-gate
make docker-backend-smoke-live
```

## Custom Benchmark Bundles

For real business cases that are not part of the public `PDB` / `AlphaFold DB`
seed set, the project now supports a local benchmark bundle sync flow.

Example for `Venus-15B`:

```bash
cd /Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台
python3 scripts/sync_benchmark_case.py --case-id venus-15b --rebuild-foldseek
```

Drop future files into:

- `Venus-15B淀粉酶项目/incoming/alphafold/`
- `Venus-15B淀粉酶项目/incoming/sifts/`
- `Venus-15B淀粉酶项目/incoming/annotations/`

They will be synced into:

- `deploy_data/alphafold/local_cases/venus-15b/`
- `deploy_data/sifts/local_cases/venus-15b/`
- `deploy_data/annotations/local_cases/venus-15b/`

## Manifest Maintenance

Edit this file when you want to change the curated live seed set:

- [deploy_data/live_manifest.json](/Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/deploy_data/live_manifest.json)

Current manifest controls:

- `pdb_ids`
- `uniprot_ids`
- `alphafold_structure_format`
- `download_pae_json`

## Current Verified State

As of `2026-07-06`, the following passed on this machine:

- Host `deploy-live-gate`
- Host `backend-smoke-live`
- Docker `docker-backend-live-gate`
- Docker `docker-backend-smoke-live`

## Troubleshooting

- If host live gate says `FOLDSEEK_BINARY unset`, regenerate env overrides:

```bash
python3 scripts/write_deploy_env.py --deploy-root deploy_data
```

- If Docker smoke still uses demo `1abc.json`, rebuild backend image:

```bash
make docker-backend-rebuild-and-smoke
```

- If Foldseek DB portability is questioned, materialize links explicitly:

```bash
python3 scripts/materialize_foldseek_links.py --root deploy_data/foldseek
```
