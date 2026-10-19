# Report Upgrade Candidate Inventory

Date: 2026-10-19

## Candidate scope

The candidate is limited to the report evidence, structure analysis, BLAST lifecycle, wet-lab plan, frontend evidence rendering, and release-gate paths listed below. The source worktree remains dirty and this inventory is not a release manifest.

- Backend report and evidence: `backend/app/services/report_*.py`, `backend/app/services/wet_lab_report_contract.py`, `backend/app/services/blast_*.py`, `backend/app/services/task_evidence.py`, `backend/app/core/agent_graph.py`.
- Backend structure and BLAST tools: `backend/app/tools/ligand_contact_analysis.py`, `backend/app/tools/structure_pocket_interface_analysis.py`, `backend/app/tools/disulfide_saltbridge_scan.py`, `backend/app/tools/blast_search.py`, `backend/app/tools/site_structure_function_features.py`, `backend/app/tools/structure_search_foldseek.py`, `backend/app/tools/residue_mapping_sifts.py`.
- Report and structure tests: the corresponding `backend/tests/test_report_*`, `test_wet_lab_report_contract.py`, `test_blast_resume.py`, `test_ligand_contact_analysis.py`, `test_pocket_interface_analysis.py`, `test_release_*.py`, `test_pdb_api.py`, and `test_structure_tools.py` files.
- Frontend report consumption: `frontend/src/components/analysis/`, `frontend/src/components/chat/ToolCallCard.tsx`, `frontend/src/lib/api.ts`, and the evidence/PDB smoke fixtures.
- Release controls: `scripts/check_report_version_alignment.py`, `scripts/release_provenance.py`, `scripts/build_release_worktree_manifest.py`, `scripts/run_release_acceptance.py`, `scripts/tests/`, `schemas/release-manifest.v1.schema.json`, deployment compose files, and `deploy-aliyun.sh`.
- Documentation and evidence: `docs/manuals/report-*.md`, `docs/manuals/release-provenance-runbook.md`, `output/report-analysis-upgrade-20261017/`, and this inventory.

## Explicit exclusions

The candidate does not include the unrelated model training, external research datasets, caches, generated training reports, or exploratory Playwright artifacts present in the source worktree. No user or agent changes were deleted or reset to create this inventory.

## Verification snapshot

- Source branch: `feature/4track-upgrade-20260627`
- Source revision: `2fb2e331`
- Source state: dirty; approximately 462 status entries at inventory time
- Formal release manifest: absent
- Frontend build: passed
- Frontend lint: passed
- Frontend base and evidence smoke: passed with a temporary local Vite server
- Backend report/release subset: 36 passed under the available Python 3.9 environment
- Release script subset: 11 passed
- Python 3.12 compileall: passed; pytest and backend dependencies are not installed locally

## Release blockers

- A clean candidate checkout and formal `RELEASE-MANIFEST.json` are still required.
- Production image references must be immutable digests and must match the manifest.
- The production Chroma service is now pinned to `chromadb/chroma:0.6.3` (digest `sha256:e0e78dc7609a599b63c99753442c7d01b1d3d369ce0e3bf3e0540536fec4fa7a`) and is healthy. The old container is retained as `docker-chromadb-legacy-20261019` for rollback evidence.
- A stopped-window backup of the actual live SQLite path `/data/chroma.sqlite3` exists at `chroma-live-data-stopped-20261019T003540Z.sqlite3`, SHA-256 `5b1ad20275d1ddf0961e0ec35a8671014ec9e2b192efa7e4883a7108feebc630`.
- The old SQLite schema is not readable by 0.6.3 (`KeyError('_type')`); the new empty 0.6.3 database passes heartbeat, collection creation, and add/get checks. Historical collection migration/rebuild remains required before claiming literature data recovery.

## Maintenance update

- A consistent production SQLite copy was created during a controlled Chroma stop/restart: `chroma-live-data-stopped-20261019T003540Z.sqlite3`, SHA-256 `5b1ad20275d1ddf0961e0ec35a8671014ec9e2b192efa7e4883a7108feebc630`.
- The target Chroma container and all existing application containers are healthy; `/api/health` returns `status=ok` and `/chat/agent` returns HTTP 200.
- Backend-to-Chroma heartbeat and collection listing pass against the new empty 0.6.3 service. The old SQLite schema is incompatible, but a read-only audit found zero embedding, metadata, and full-text rows, so the retained backup contains no historical literature payload requiring migration.
- Report release remains blocked by clean candidate/manifest/image-digest/online-acceptance gates; this inventory is not a release manifest.

### Online Chroma smoke

- The production backend `LiteratureStore` completed a temporary write, stats read, semantic query, and delete against `protein_literature_specter2`: `0 -> 1 -> query hit -> delete -> 0`.
- The smoke left no test document. The service is operational with an empty rebuilt collection; a read-only audit confirmed no historical literature payload exists in the verified backup.

## Temporary candidate artifacts

The following files were generated outside the worktree for review only:

- `/private/tmp/protein-ai-report-candidate-20261019.patch` — tracked report/release changes, SHA-256 `5d2ad42b66c562c8a955dc83328b63b2224e681137856e1ae55cda0a53530127`.
- `/private/tmp/protein-ai-report-candidate-untracked-20261019.tar.gz` — selected new report/release files, SHA-256 `18c6189772a3fea48be3e5660e4e81c240dc502481960b9a73df3401c2f74471`.

The tracked patch passes `git apply --check --cached` against the current index. It was not applied to the source worktree, and no release commit or manifest was created.

## Latest verification

- Isolated candidate code commit: `4321caac4e6efeacd8a0cae8bf7b5eec395d8ab9`; verification record commit: `077f4866129e4ffb4f2fd0080da2733a9aa225d2` (detached worktree; not pushed or deployed).
- Backend Python 3.12 report/structure/BLAST/Chroma/release suite: `113 passed`.
- Frontend candidate `npm run build` and `npm run lint`: passed using the existing dependency tree; generated `frontend/dist` is candidate-local output.
- Chroma compatibility adapter handles both legacy Collection-like objects and 0.6.x string collection names; focused LiteratureStore tests pass.
- Online switch evidence: `chroma-switch-receipt.json`. It is operational evidence, not a release manifest or application deployment authorization.
- A read-only SQLite audit of the retained backup found one collection (`protein_literature_specter2`) and zero rows in `embeddings`, `embedding_metadata`, and full-text content. The old schema is incompatible, but this backup contains no historical literature payload to migrate; this statement is scoped to its verified SHA-256 receipt.
