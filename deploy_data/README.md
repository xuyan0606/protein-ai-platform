## Deploy Data Layout

Drop real external data here to move the stack from `demo-ready` to `live-ready`.

Expected layout:

```text
deploy_data/
  annotations/
    metadata.json
    base.json|csv|tsv
    interpro.json|csv|tsv
    mcsa.json|csv|tsv
    signalp.json|csv|tsv
  sifts/
    1abc.json|csv|tsv
    mappings.json|csv|tsv
    residue_mappings.json|csv|tsv
  pdb/
    *.pdb
    *.cif
  alphafold/
    AF-*.pdb
    AF-*.cif
    *.json
  foldseek/
    pdb/
    alphafold/
    custom/
  lipase/
    lipase.db
  benchmarks/
    <case-id>/
      bundle_manifest.json
      README.md
      source/
      docs/
      assets/
    <case-id>.tar.gz
  smoke/
    query.pdb
```

Notes:

- Docker mounts this directory into `/app/deploy_data` for `backend`, `worker`, and `md-worker`.
- Staging files into `deploy_data/` is not an export-safe or training-safe data release. It only makes source assets discoverable by the app.
- SQLite-to-PostgreSQL domain import is a full domain restore, not an A-only/high-confidence export. Use explicit export-safe API endpoints for training/export candidates.
- With `DEPLOY_DATA_ROOT` set, the app auto-discovers:
  - `annotations/` as `LOCAL_ANNOTATION_FIXTURE_PATH`
  - `sifts/` as `SIFTS_MAPPING_PATH`
  - `foldseek/` as `FOLDSEEK_DATABASE_ROOT`
  - `smoke/query.pdb` as `STRUCTURE_SMOKE_PDB_FILE`
  - `lipase/lipase.db` as `LIPASE_DB_PATH`
- Preflight layout check:
  - `python scripts/check_deploy_data.py`
  - `python scripts/check_deploy_data.py --require-live`
- Candidate source discovery:
  - `python scripts/discover_deploy_data_sources.py --root ..`
- Rebuild the current curated live dataset from one manifest:
  - `python scripts/refresh_live_deploy_data.py --manifest deploy_data/live_manifest.json --verify`
- Stage real data into the standard layout:
  - `python scripts/import_deploy_data.py --annotations /path/to/annotations --sifts /path/to/sifts --pdb /path/to/pdb --alphafold /path/to/alphafold --foldseek-root /path/to/foldseek --smoke-pdb /path/to/query.pdb`
- Download official experimental structures from RCSB into `deploy_data/pdb/`:
  - `python scripts/download_rcsb_structures.py --ids 4HHB,1TIM --format cif`
  - `python scripts/download_rcsb_structures.py --id-file ./pdb_ids.txt --format pdb`
- Download official AlphaFold models into `deploy_data/alphafold/`:
  - `python scripts/download_alphafold_models.py --ids P19531,P00690 --structure-format cif --with-pae-json`
- Download official PDBe/SIFTS UniProt mappings into `deploy_data/sifts/`:
  - `python scripts/download_sifts_mappings.py --ids 1QHP,1QHO,1BLI`
- Build real local annotations from official UniProt/InterPro sources:
  - `python scripts/download_real_annotations.py --ids P00692,P19531,P00691`
- Build a local Foldseek DB from staged structures:
  - `python scripts/build_foldseek_db.py --kind pdb`
  - `python scripts/build_foldseek_db.py --kind alphafold`
- Generate env override files from the staged layout:
  - `python scripts/write_deploy_env.py`
- If your Foldseek DB was built locally with `createindex`, materialize any symlinks before Docker deployment:
  - `python scripts/materialize_foldseek_links.py`
- Readiness check:
  - `cd backend && .venv/bin/python scripts/structure_smoke_readiness.py`
- Smoke check:
  - `cd backend && .venv/bin/python scripts/smoke_structure_data.py`
  - or use `make backend-readiness` / `make backend-smoke-live`, which auto-load `backend/.env.deploy-data` when present
  - use `make backend-live-gate` when you want the command to fail unless the current host-side data is truly `live-ready`
  - use `make docker-backend-live-gate` when you want the same strict gate inside the backend container
  - use `make deploy-live-gate` when you want both host-side `deploy_data` and backend runtime readiness to pass strict live gates together

Recommended order:

1. `python scripts/prepare_deploy_data.py`
2. Drop real exports/databases into `deploy_data/`
3. Put curated experimental structures in `deploy_data/pdb/`
4. Put curated AlphaFold models in `deploy_data/alphafold/`
5. `python scripts/discover_deploy_data_sources.py --root ..`
6. `python scripts/check_deploy_data.py`
7. `python scripts/download_sifts_mappings.py --ids ...`
8. `python scripts/download_alphafold_models.py --ids ...`
9. `python scripts/download_real_annotations.py --ids ...`
10. `python scripts/build_foldseek_db.py --kind pdb`
11. `python scripts/build_foldseek_db.py --kind alphafold`
12. `python scripts/materialize_foldseek_links.py`
13. `python scripts/write_deploy_env.py`
14. `cd backend && .venv/bin/python scripts/structure_smoke_readiness.py`
15. `cd backend && .venv/bin/python scripts/smoke_structure_data.py`
16. `make docker-up-with-deploy-env`
17. `make docker-backend-smoke-live`

Practical rule:

- `deploy_data/pdb/`: real experimental structures you want to keep and deploy with the project
- `deploy_data/alphafold/`: curated AlphaFold models and companion metadata
- `backend/storage/uploads/`: runtime upload cache only, not long-term deploy data
- `deploy_data/live_manifest.json`: machine-migratable seed list for rebuilding the live dataset from official sources
- `deploy_data/benchmarks/<case-id>/`: portable real-case bundle with copied source files and staged assets for one benchmark case
- `deploy_data/benchmarks/<case-id>.tar.gz`: compressed bundle archive for handoff or migration

Or use the bundled shortcuts:

- `make deploy-preflight`
- `make deploy-demo-check`
- `make deploy-live-gate`
- `make discover-deploy-data`
- `make refresh-live-deploy-data`
- `make refresh-live-deploy-data-verify`
- `make download-real-annotations`
- `make download-alphafold`
- `make download-sifts`
- `make build-foldseek-pdb-db`
- `make build-foldseek-alphafold-db`
- `make docker-backend-smoke-live`
- `make docker-backend-live-gate`
- `make docker-backend-rebuild-and-smoke`

Status interpretation:

- `summary demo-data-only`: `deploy_data/` currently contains bundled/demo assets, useful for smoke/demo, not proof of live data readiness.
- `summary partial`: some required live data classes are still missing.
- `foldseek partial`: Foldseek files exist, but non-portable symlinks were detected and should be materialized before Docker deployment.
- `summary live-data-ready`: host-side data layout looks complete enough to attempt backend `live-ready`.
