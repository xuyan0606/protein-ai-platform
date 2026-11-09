.PHONY: help env-preflight production-config-gate production-config-gate-json nightly-live-gates nightly-live-gates-plan nightly-live-gates-md-blackbox-plan nightly-live-gates-fail-closed package-preflight acceptance-matrix acceptance-matrix-json acceptance-matrix-plan acceptance-matrix-fail-closed pytest-runner pytest-runner-json pytest-runner-plan browser-smoke-plan external-gates-plan external-gate external-gates-execute backend-md-blackbox backend-md-blackbox-plan release-acceptance release-acceptance-json release-acceptance-plan release-manual-gate-template release-manual-gate-validate release-manual-gate-evidence-template release-manual-gate-evidence-validate release-go-no-go-summary release-worktree-manifest release-operator-packet-manifest release-operator-packet-manifest-check remaining-backlog-readiness remaining-backlog-readiness-json remaining-backlog-input-packet remaining-backlog-input-template remaining-backlog-input-validate remaining-backlog-execution-plan remaining-backlog-dispatch-checklist remaining-backlog-dispatch-checklist-validate remaining-backlog-operator-packet-manifest remaining-backlog-operator-packet-manifest-check remaining-backlog-go-no-go-summary remaining-backlog-execution-tickets remaining-backlog-execution-tickets-validate remaining-backlog-operator-packet-refresh p2-p3-p4-roadmap p0-p4-gap-audit p0-p4-status-export p0-p4-backlog-ticket-bridge p0-p4-backlog-ticket-bridge-validate upgrade-readiness upgrade-readiness-json upgrade-dry-run rollback-plan rollback-plan-json init-deploy-local init-deploy-local-dry-run init-deploy-aliyun-dry-run backup-dry-run backup-local verify-backup restore-dry-run restore-drill-dry-run restore-drill package-deploy-bundle package-deploy-bundle-dry-run prepare-deploy-data prepare-deploy-data-demo check-deploy-data discover-deploy-data import-deploy-data write-deploy-env refresh-live-deploy-data refresh-live-deploy-data-verify deploy-data-update deploy-data-update-plan deploy-data-update-json download-real-annotations download-alphafold download-sifts build-foldseek-pdb-db build-foldseek-alphafold-db materialize-foldseek-db sync-benchmark-case sync-venus-15b discover-benchmark-assets discover-venus-15b-assets select-benchmark-reference-docs select-venus-15b-reference-docs package-venus-15b-bundle archive-benchmark-bundle archive-venus-15b-bundle manual-screenshots \
	backend-readiness backend-live-gate deploy-live-gate backend-smoke-demo backend-smoke-live docker-backend-smoke-live docker-backend-live-gate docker-backend-rebuild-and-smoke config-test \
	deploy-preflight deploy-demo-check docker-up docker-ps docker-build-ligand-worker docker-config-ligand-worker docker-config-aliyun-app docker-up-aliyun-app docker-ps-aliyun-app docker-config-aliyun-gpu docker-up-aliyun-gpu docker-ps-aliyun-gpu backend-md-blackbox backend-md-topology-smoke backend-md-topology-live-gate backend-ligand-toolchain-smoke backend-ligand-toolchain-live-gate

PYTHON ?= python3
BACKEND_PYTHON ?= backend/.venv/bin/python
LIGAND_RUNTIME_IMAGE ?= protein-ai-ligand-worker:aliyun
DEPLOY_ROOT ?= deploy_data
COMPOSE_DIR ?= docker
COMPOSE_ENV ?= .env
COMPOSE_DEPLOY_ENV ?= .env.deploy-data
COMPOSE_ALIYUN_APP_ENV ?= .env.aliyun.app
COMPOSE_ALIYUN_GPU_ENV ?= .env.aliyun.gpu
MD_BLACKBOX_ARGS ?=

help:
	@echo "Available targets:"
	@echo "  make env-preflight             # read-only environment/package prerequisite check"
	@echo "  make production-config-gate    # validate production config shape without printing secrets"
	@echo "  make nightly-live-gates        # run safe nightly live gates; mutating gates are opt-in via script flags"
	@echo "  make nightly-live-gates-plan   # print nightly live gate plan without executing commands"
	@echo "  make nightly-live-gates-md-blackbox-plan # include MD black-box live gate in the non-executing plan"
	@echo "  make nightly-live-gates-fail-closed # mark missing browser/MD live inputs blocked instead of skipped"
	@echo "  make acceptance-matrix         # run bounded acceptance checks: permissions, MD artifacts, data admin, OSS env"
	@echo "  make acceptance-matrix-plan    # print acceptance matrix without executing commands"
	@echo "  make acceptance-matrix-json    # run acceptance matrix and emit JSON"
	@echo "  make acceptance-matrix-fail-closed # block unarmed browser/MD gates instead of reporting skipped"
	@echo "  make pytest-runner             # run isolated local mirror of CI backend-test"
	@echo "  make pytest-runner-plan        # preview the backend-test runner contract without executing pytest"
	@echo "  make pytest-runner-json        # run local CI mirror and emit JSON"
	@echo "  make browser-smoke-plan        # validate browser smoke contract without opening a browser"
	@echo "  make external-gates-plan       # plan all seven external gates without network or writes"
	@echo "  make external-gate GATE=name   # execute one explicitly armed external gate"
	@echo "  make external-gates-execute    # execute all armed external gates"
	@echo "  make release-acceptance        # run non-destructive release acceptance orchestration"
	@echo "  make release-acceptance-plan   # print release acceptance plan without executing commands"
	@echo "  make release-acceptance-json   # run release acceptance and emit JSON"
	@echo "  make release-manual-gate-template # write template for final release manual gate inputs"
	@echo "  make release-manual-gate-validate # validate final release manual gate inputs without live actions"
	@echo "  make release-manual-gate-evidence-template # write template for manual gate evidence records"
	@echo "  make release-manual-gate-evidence-validate # validate manual gate evidence without live actions"
	@echo "  make release-go-no-go-summary # aggregate manual gate input/evidence status for release decision review"
	@echo "  make release-worktree-manifest # write path-only dirty worktree manifest for release review"
	@echo "  make release-operator-packet-manifest # write checksum manifest for the release operator packet"
	@echo "  make release-operator-packet-manifest-check # verify operator packet manifest freshness without writing"
	@echo "  make remaining-backlog-readiness # aggregate read-only status for external-dependent pending items"
	@echo "  make remaining-backlog-readiness-json # emit aggregate pending-item readiness as JSON"
	@echo "  make remaining-backlog-input-packet # write the external-input packet for pending backlog gates"
	@echo "  make remaining-backlog-input-template # write the operator values template for pending backlog gates"
	@echo "  make remaining-backlog-input-validate # validate operator values without running live gates"
	@echo "  make remaining-backlog-execution-plan # write a redacted runbook for armed pending backlog gates"
	@echo "  make remaining-backlog-dispatch-checklist # group pending backlog inputs by operator lane"
	@echo "  make remaining-backlog-dispatch-checklist-validate # validate dispatch checklist freshness and safety"
	@echo "  make remaining-backlog-operator-packet-manifest # write checksum manifest for remaining backlog operator packet"
	@echo "  make remaining-backlog-operator-packet-manifest-check # verify remaining backlog operator packet manifest freshness"
	@echo "  make remaining-backlog-go-no-go-summary # aggregate remaining backlog go/no-go status without running live gates"
	@echo "  make remaining-backlog-execution-tickets # write per-item remaining backlog execution tickets without live commands"
	@echo "  make remaining-backlog-execution-tickets-validate # validate ticket freshness and safety"
	@echo "  make remaining-backlog-operator-packet-refresh # serially refresh the complete read-only P0-P4/operator packet"
	@echo "  make p2-p3-p4-roadmap # write read-only P2/P3/P4 roadmap and readiness packet"
	@echo "  make p0-p4-gap-audit # write read-only P0-P4 gap audit and remaining blocker summary"
	@echo "  make p0-p4-status-export # write compact read-only P0-P4 SOP/status export"
	@echo "  make p0-p4-backlog-ticket-bridge # link P0-P4 contracts to remaining backlog tickets"
	@echo "  make p0-p4-backlog-ticket-bridge-validate # validate the P0-P4/backlog bridge freshness and safety"
	@echo "  make package-preflight         # strict environment preflight for deployment packaging"
	@echo "  make upgrade-readiness         # read-only upgrade readiness report"
	@echo "  make upgrade-dry-run           # preview local upgrade orchestration"
	@echo "  make rollback-plan             # generate a read-only rollback plan"
	@echo "  make init-deploy-local         # initialize local docker env files with generated secrets"
	@echo "  make init-deploy-local-dry-run # preview local env initialization"
	@echo "  make init-deploy-aliyun-dry-run # preview Alibaba env initialization"
	@echo "  make backup-dry-run            # preview PostgreSQL backup plan"
	@echo "  make backup-local              # create PostgreSQL backup from docker compose postgres"
	@echo "  make verify-backup BACKUP_FILE=... # verify dump/checksum without restoring"
	@echo "  make restore-dry-run BACKUP_FILE=... # validate restore plan without changing DB"
	@echo "  make restore-drill-dry-run BACKUP_FILE=... # preview restore into temp DB"
	@echo "  make package-deploy-bundle     # create sanitized deployable source tarball"
	@echo "  make package-deploy-bundle-dry-run # preview sanitized package contents"
	@echo "  make prepare-deploy-data       # scaffold deploy_data/"
	@echo "  make prepare-deploy-data-demo  # scaffold deploy_data/ with demo assets"
	@echo "  make check-deploy-data         # inspect deploy_data completeness"
	@echo "  make discover-deploy-data      # scan local workspace for likely deploy_data source candidates"
	@echo "  make import-deploy-data        # stage real data sources into deploy_data/"
	@echo "  make write-deploy-env          # generate backend/docker deploy-data env overrides"
	@echo "  make refresh-live-deploy-data  # rebuild deploy_data from deploy_data/live_manifest.json"
	@echo "  make refresh-live-deploy-data-verify # rebuild deploy_data and run live gates/smokes"
	@echo "  make deploy-data-update-plan   # print scheduled deploy_data update plan without network or writes"
	@echo "  make deploy-data-update        # run one deploy_data update and write deploy_data/updates manifest"
	@echo "  make deploy-data-update-json   # run one deploy_data update and emit JSON summary"
	@echo "  make download-real-annotations # usage hint for real UniProt/InterPro annotation downloads"
	@echo "  make download-alphafold        # usage hint for AlphaFold downloads"
	@echo "  make download-sifts            # usage hint for PDBe/SIFTS downloads"
	@echo "  make build-foldseek-pdb-db     # build local Foldseek DB from deploy_data/pdb"
	@echo "  make build-foldseek-alphafold-db # build local Foldseek DB from deploy_data/alphafold"
	@echo "  make materialize-foldseek-db   # replace Foldseek symlinks with real files for Docker portability"
	@echo "  make sync-benchmark-case CASE_ID=venus-15b # sync one benchmark bundle into deploy_data"
	@echo "  make sync-venus-15b            # sync Venus-15B benchmark bundle and rebuild Foldseek if needed"
	@echo "  make discover-benchmark-assets CASE_ID=venus-15b SEARCH_ROOT=/Users/xuyan/科为博 # scan local workspace for candidate benchmark files"
	@echo "  make discover-venus-15b-assets # scan local workspace for Venus-15B candidate files"
	@echo "  make select-benchmark-reference-docs CASE_ID=venus-15b # auto-stage selected reference docs into incoming/reference_docs/"
	@echo "  make select-venus-15b-reference-docs # auto-stage selected Venus-15B reference docs"
	@echo "  make package-venus-15b-bundle  # rebuild Venus-15B deploy bundle under deploy_data/benchmarks/"
	@echo "  make archive-benchmark-bundle CASE_ID=venus-15b # archive one benchmark deploy bundle"
	@echo "  make archive-venus-15b-bundle  # archive Venus-15B deploy bundle to tar.gz"
	@echo "  make backend-readiness         # backend live/demo readiness report"
	@echo "  make backend-live-gate         # fail unless host-side readiness is truly live-ready"
	@echo "  make deploy-live-gate          # fail unless both deploy_data and backend readiness are truly live-ready"
	@echo "  make backend-smoke-demo        # run demo SIFTS/Foldseek smoke"
	@echo "  make backend-smoke-live        # run live SIFTS/Foldseek smoke"
	@echo "  make docker-backend-smoke-live # run live SIFTS/Foldseek smoke inside backend container"
	@echo "  make docker-backend-live-gate  # fail unless backend container readiness is truly live-ready"
	@echo "  make docker-backend-rebuild-and-smoke # rebuild backend container and run live smoke inside it"
	@echo "  make backend-md-blackbox      # run external HTTP black-box MD verification; pass MD_BLACKBOX_ARGS='--task-id ... --email ...'"
	@echo "  make backend-md-topology-smoke # run host GROMACS pdb2gmx topology smoke; unavailable is non-fatal"
	@echo "  make backend-md-topology-live-gate # fail unless host GROMACS pdb2gmx topology smoke validates"
	@echo "  make backend-ligand-toolchain-smoke # inspect SDF ligand and required docking/MD ligand tools; missing tools are non-fatal"
	@echo "  make backend-ligand-toolchain-live-gate # fail unless ligand preprocessing/docking/topology toolchain is ready"
	@echo "  make config-test              # run config validation tests"
	@echo "  make deploy-preflight         # host deploy_data check + backend readiness"
	@echo "  make deploy-demo-check        # scaffold demo data + run readiness/smoke"
	@echo "  make docker-up                # docker compose up -d"
	@echo "  make docker-ps                # docker compose ps"
	@echo "  make docker-config-ligand-worker # validate local compose ligand-worker config without printing secrets"
	@echo "  make docker-build-ligand-worker # build dedicated ligand worker image"
	@echo "  make manual-screenshots FRONTEND_BASE_URL=http://127.0.0.1:4203 # capture docs screenshots + manifest"
	@echo "  make docker-up-with-deploy-env # docker compose with .env.deploy-data overlay"
	@echo "  make docker-config-aliyun-app # validate Alibaba app-node compose without printing secrets"
	@echo "  make docker-up-aliyun-app     # start Alibaba app-node stack"
	@echo "  make docker-ps-aliyun-app     # show Alibaba app-node stack status"
	@echo "  make docker-config-aliyun-gpu # validate Alibaba GPU/scientific-worker compose without printing secrets"
	@echo "  make docker-up-aliyun-gpu     # start Alibaba GPU-worker stack"
	@echo "  make docker-ps-aliyun-gpu     # show Alibaba GPU-worker stack status"

env-preflight:
	$(PYTHON) scripts/check_environment.py

production-config-gate:
	$(PYTHON) scripts/check_production_config.py --mode production --require-production-safe --skip-domain-https

production-config-gate-json:
	$(PYTHON) scripts/check_production_config.py --mode production --require-production-safe --skip-domain-https --json

nightly-live-gates:
	$(PYTHON) scripts/run_nightly_live_gates.py

nightly-live-gates-plan:
	$(PYTHON) scripts/run_nightly_live_gates.py --plan-only

nightly-live-gates-md-blackbox-plan:
	$(PYTHON) scripts/run_nightly_live_gates.py --plan-only --include-md-blackbox

nightly-live-gates-fail-closed:
	$(PYTHON) scripts/run_nightly_live_gates.py --fail-closed-external

acceptance-matrix:
	$(PYTHON) scripts/run_acceptance_matrix.py

acceptance-matrix-json:
	$(PYTHON) scripts/run_acceptance_matrix.py --json

acceptance-matrix-plan:
	$(PYTHON) scripts/run_acceptance_matrix.py --plan-only

acceptance-matrix-fail-closed:
	$(PYTHON) scripts/run_acceptance_matrix.py --fail-closed-external --json

pytest-runner:
	$(PYTHON) scripts/run_pytest_runner.py

pytest-runner-json:
	$(PYTHON) scripts/run_pytest_runner.py --json

pytest-runner-plan:
	$(PYTHON) scripts/run_pytest_runner.py --plan-only --json

browser-smoke-plan:
	node frontend/tests/live-contract.mjs --plan-only --json

external-gates-plan:
	$(PYTHON) scripts/run_external_gate.py --plan-only --all

external-gate:
	@test -n "$(GATE)" || (echo 'GATE is required' >&2; exit 2)
	$(PYTHON) scripts/run_external_gate.py --execute --gate $(GATE)

external-gates-execute:
	$(PYTHON) scripts/run_external_gate.py --execute --all

release-acceptance:
	$(PYTHON) scripts/run_release_acceptance.py

release-acceptance-json:
	$(PYTHON) scripts/run_release_acceptance.py --json

release-acceptance-plan:
	$(PYTHON) scripts/run_release_acceptance.py --plan-only

release-manual-gate-template:
	$(PYTHON) scripts/validate_release_manual_gate_inputs.py --write-template --json

release-manual-gate-validate:
	$(PYTHON) scripts/validate_release_manual_gate_inputs.py --json

release-manual-gate-evidence-template:
	$(PYTHON) scripts/validate_release_manual_gate_evidence.py --write-template --json

release-manual-gate-evidence-validate:
	$(PYTHON) scripts/validate_release_manual_gate_evidence.py --json

release-go-no-go-summary:
	$(PYTHON) scripts/build_release_go_no_go_summary.py --json

release-worktree-manifest:
	$(PYTHON) scripts/build_release_worktree_manifest.py --json

release-operator-packet-manifest:
	$(PYTHON) scripts/build_release_operator_packet_manifest.py --json

release-operator-packet-manifest-check:
	$(PYTHON) scripts/build_release_operator_packet_manifest.py --check --json

remaining-backlog-readiness:
	LIGAND_RUNTIME_IMAGE=$(LIGAND_RUNTIME_IMAGE) $(PYTHON) scripts/check_remaining_backlog_readiness.py --deploy-root $(DEPLOY_ROOT)

remaining-backlog-readiness-json:
	LIGAND_RUNTIME_IMAGE=$(LIGAND_RUNTIME_IMAGE) $(PYTHON) scripts/check_remaining_backlog_readiness.py --deploy-root $(DEPLOY_ROOT) --json

remaining-backlog-input-packet:
	$(PYTHON) scripts/build_remaining_backlog_external_input_packet.py --deploy-root $(DEPLOY_ROOT)

remaining-backlog-input-template:
	$(PYTHON) scripts/validate_remaining_backlog_external_inputs.py --write-template

remaining-backlog-input-validate:
	$(PYTHON) scripts/validate_remaining_backlog_external_inputs.py

remaining-backlog-execution-plan:
	$(PYTHON) scripts/build_remaining_backlog_gate_execution_plan.py

remaining-backlog-dispatch-checklist:
	$(PYTHON) scripts/build_remaining_backlog_operator_dispatch_checklist.py

remaining-backlog-dispatch-checklist-validate:
	$(PYTHON) scripts/validate_remaining_backlog_operator_dispatch_checklist.py --require-success

remaining-backlog-operator-packet-manifest:
	$(PYTHON) scripts/build_remaining_backlog_operator_packet_manifest.py --json

remaining-backlog-operator-packet-manifest-check:
	$(PYTHON) scripts/build_remaining_backlog_operator_packet_manifest.py --check --json

remaining-backlog-go-no-go-summary:
	$(PYTHON) scripts/build_remaining_backlog_go_no_go_summary.py --json

remaining-backlog-execution-tickets:
	$(PYTHON) scripts/build_remaining_backlog_execution_tickets.py --json

remaining-backlog-execution-tickets-validate:
	$(PYTHON) scripts/validate_remaining_backlog_execution_tickets.py --require-success

remaining-backlog-operator-packet-refresh:
	$(MAKE) p2-p3-p4-roadmap
	$(MAKE) p0-p4-gap-audit
	$(MAKE) p0-p4-status-export
	$(MAKE) remaining-backlog-input-template
	$(MAKE) remaining-backlog-readiness-json
	$(MAKE) remaining-backlog-input-packet
	$(MAKE) remaining-backlog-input-validate
	$(MAKE) remaining-backlog-execution-plan
	$(MAKE) remaining-backlog-dispatch-checklist
	$(MAKE) remaining-backlog-dispatch-checklist-validate
	$(MAKE) remaining-backlog-operator-packet-manifest
	$(MAKE) remaining-backlog-go-no-go-summary
	$(MAKE) remaining-backlog-execution-tickets
	$(MAKE) remaining-backlog-execution-tickets-validate
	$(MAKE) p0-p4-backlog-ticket-bridge
	$(MAKE) p0-p4-backlog-ticket-bridge-validate
	$(MAKE) remaining-backlog-operator-packet-manifest
	$(MAKE) remaining-backlog-operator-packet-manifest-check

p2-p3-p4-roadmap:
	$(PYTHON) scripts/build_p2_p3_p4_roadmap.py --json

p0-p4-gap-audit:
	$(PYTHON) scripts/build_p0_p4_gap_audit.py --json

p0-p4-status-export:
	$(PYTHON) scripts/build_p0_p4_status_export.py --json

p0-p4-backlog-ticket-bridge:
	$(PYTHON) scripts/build_p0_p4_backlog_ticket_bridge.py --json

p0-p4-backlog-ticket-bridge-validate:
	$(PYTHON) scripts/validate_p0_p4_backlog_ticket_bridge.py --require-success

package-preflight:
	$(PYTHON) scripts/check_environment.py --require-ready

upgrade-readiness:
	$(PYTHON) scripts/check_upgrade_readiness.py

upgrade-readiness-json:
	$(PYTHON) scripts/check_upgrade_readiness.py --json

upgrade-dry-run:
	./scripts/upgrade.sh --dry-run

rollback-plan:
	$(PYTHON) scripts/rollback_plan.py

rollback-plan-json:
	$(PYTHON) scripts/rollback_plan.py --json

init-deploy-local:
	$(PYTHON) scripts/init_deployment.py --profile local

init-deploy-local-dry-run:
	$(PYTHON) scripts/init_deployment.py --profile local --dry-run

init-deploy-aliyun-dry-run:
	$(PYTHON) scripts/init_deployment.py --profile all --public-base-url https://proteinai.example.com --dry-run

backup-dry-run:
	./scripts/backup.sh --compose --dry-run

backup-local:
	./scripts/backup.sh --compose

verify-backup:
	./scripts/verify_backup.sh --compose $(BACKUP_FILE)

restore-dry-run:
	./scripts/restore.sh --dry-run $(BACKUP_FILE)

restore-drill-dry-run:
	./scripts/restore_drill.sh --dry-run $(BACKUP_FILE)

restore-drill:
	./scripts/restore_drill.sh $(BACKUP_FILE)

package-deploy-bundle:
	$(PYTHON) scripts/package_deploy_bundle.py

package-deploy-bundle-dry-run:
	$(PYTHON) scripts/package_deploy_bundle.py --dry-run

prepare-deploy-data:
	$(PYTHON) scripts/prepare_deploy_data.py --output $(DEPLOY_ROOT)

prepare-deploy-data-demo:
	$(PYTHON) scripts/prepare_deploy_data.py --output $(DEPLOY_ROOT) --with-demo

check-deploy-data:
	$(PYTHON) scripts/check_deploy_data.py --root $(DEPLOY_ROOT)

discover-deploy-data:
	$(PYTHON) scripts/discover_deploy_data_sources.py --root ..

import-deploy-data:
	@echo "Usage example:"
	@echo "  python3 scripts/import_deploy_data.py --annotations /path/to/annotations --sifts /path/to/sifts --foldseek-root /path/to/foldseek --smoke-pdb /path/to/query.pdb"

write-deploy-env:
	$(PYTHON) scripts/write_deploy_env.py --deploy-root $(DEPLOY_ROOT)

refresh-live-deploy-data:
	$(PYTHON) scripts/refresh_live_deploy_data.py --deploy-root $(DEPLOY_ROOT)

refresh-live-deploy-data-verify:
	$(PYTHON) scripts/refresh_live_deploy_data.py --deploy-root $(DEPLOY_ROOT) --verify --docker-verify

deploy-data-update-plan:
	$(PYTHON) scripts/run_deploy_data_update.py --deploy-root $(DEPLOY_ROOT) --plan-only

deploy-data-update:
	$(PYTHON) scripts/run_deploy_data_update.py --deploy-root $(DEPLOY_ROOT)

deploy-data-update-json:
	$(PYTHON) scripts/run_deploy_data_update.py --deploy-root $(DEPLOY_ROOT) --json

download-real-annotations:
	@echo "Usage example:"
	@echo "  python3 scripts/download_real_annotations.py --ids P00692,P19531,P00691"

download-alphafold:
	@echo "Usage example:"
	@echo "  python3 scripts/download_alphafold_models.py --ids P19531,P00690 --structure-format cif --with-pae-json"

download-sifts:
	@echo "Usage example:"
	@echo "  python3 scripts/download_sifts_mappings.py --ids 1QHP,1QHO,1BLI"

build-foldseek-pdb-db:
	$(PYTHON) scripts/build_foldseek_db.py --kind pdb --deploy-root $(DEPLOY_ROOT)

build-foldseek-alphafold-db:
	$(PYTHON) scripts/build_foldseek_db.py --kind alphafold --deploy-root $(DEPLOY_ROOT)

materialize-foldseek-db:
	$(PYTHON) scripts/materialize_foldseek_links.py --root $(DEPLOY_ROOT)/foldseek

sync-benchmark-case:
	$(PYTHON) scripts/sync_benchmark_case.py --case-id $(CASE_ID)

sync-venus-15b:
	$(PYTHON) scripts/sync_benchmark_case.py --case-id venus-15b --rebuild-foldseek

discover-benchmark-assets:
	$(PYTHON) scripts/discover_benchmark_assets.py --case-id $(CASE_ID) --search-root $(SEARCH_ROOT)

discover-venus-15b-assets:
	$(PYTHON) scripts/discover_benchmark_assets.py --case-id venus-15b --search-root /Users/xuyan/科为博

select-benchmark-reference-docs:
	$(PYTHON) scripts/select_benchmark_reference_docs.py --case-id $(CASE_ID)

select-venus-15b-reference-docs:
	$(PYTHON) scripts/select_benchmark_reference_docs.py --case-id venus-15b

package-venus-15b-bundle:
	$(PYTHON) scripts/sync_benchmark_case.py --case-id venus-15b

archive-benchmark-bundle:
	$(PYTHON) scripts/archive_benchmark_bundle.py --case-id $(CASE_ID)

archive-venus-15b-bundle:
	$(PYTHON) scripts/archive_benchmark_bundle.py --case-id venus-15b

backend-readiness:
	cd backend && set -a && DEPLOY_DATA_ROOT=../$(DEPLOY_ROOT) && [ -f $(BACKEND_DEPLOY_ENV) ] && . ./$(BACKEND_DEPLOY_ENV) || true && set +a && .venv/bin/python scripts/structure_smoke_readiness.py

backend-live-gate:
	cd backend && set -a && DEPLOY_DATA_ROOT=../$(DEPLOY_ROOT) && [ -f $(BACKEND_DEPLOY_ENV) ] && . ./$(BACKEND_DEPLOY_ENV) || true && set +a && .venv/bin/python scripts/structure_smoke_readiness.py --require-live

deploy-live-gate:
	$(PYTHON) scripts/check_deploy_data.py --root $(DEPLOY_ROOT) --require-live
	cd backend && set -a && DEPLOY_DATA_ROOT=../$(DEPLOY_ROOT) && [ -f $(BACKEND_DEPLOY_ENV) ] && . ./$(BACKEND_DEPLOY_ENV) || true && set +a && .venv/bin/python scripts/structure_smoke_readiness.py --require-live

backend-smoke-demo:
	cd backend && DEPLOY_DATA_ROOT=../$(DEPLOY_ROOT) SIFTS_SMOKE_USE_DEMO=1 FOLDSEEK_SMOKE_USE_DEMO=1 .venv/bin/python scripts/smoke_structure_data.py

backend-smoke-live:
	cd backend && set -a && DEPLOY_DATA_ROOT=../$(DEPLOY_ROOT) && [ -f $(BACKEND_DEPLOY_ENV) ] && . ./$(BACKEND_DEPLOY_ENV) || true && set +a && .venv/bin/python scripts/smoke_structure_data.py

docker-backend-smoke-live:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) exec backend sh -lc 'cd /app && /opt/venv/bin/python scripts/smoke_structure_data.py'

docker-backend-live-gate:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) exec backend sh -lc 'cd /app && /opt/venv/bin/python scripts/structure_smoke_readiness.py --require-live'

docker-backend-rebuild-and-smoke:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) up -d --build backend
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) exec backend sh -lc 'cd /app && /opt/venv/bin/python scripts/smoke_structure_data.py'

backend-md-blackbox:
	cd backend && .venv/bin/python scripts/verify_md_blackbox.py $(MD_BLACKBOX_ARGS)

backend-md-blackbox-plan:
	cd backend && .venv/bin/python scripts/verify_md_blackbox.py --plan-only --json $(MD_BLACKBOX_ARGS)

backend-md-topology-smoke:
	cd backend && .venv/bin/python scripts/smoke_md_topology.py

backend-md-topology-live-gate:
	cd backend && .venv/bin/python scripts/smoke_md_topology.py --require-live

backend-ligand-toolchain-smoke:
	cd backend && .venv/bin/python scripts/smoke_ligand_toolchain.py

backend-ligand-toolchain-live-gate:
	LIGAND_RUNTIME_IMAGE=$(LIGAND_RUNTIME_IMAGE) $(PYTHON) scripts/check_remaining_backlog_readiness.py --json --require-ligand-ready

config-test:
	cd backend && .venv/bin/pytest tests/test_config_validation.py -q

deploy-preflight: check-deploy-data
	cd backend && set -a && [ -f $(BACKEND_DEPLOY_ENV) ] && . ./$(BACKEND_DEPLOY_ENV) || true && set +a && .venv/bin/python scripts/structure_smoke_readiness.py

deploy-demo-check: prepare-deploy-data-demo check-deploy-data backend-readiness backend-smoke-demo

docker-up:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) up -d

docker-ps:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) ps

docker-up-with-deploy-env:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) up -d

docker-config-ligand-worker:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) config --quiet

docker-build-ligand-worker:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_DEPLOY_ENV) build ligand-worker

manual-screenshots:
	FRONTEND_BASE_URL=$(FRONTEND_BASE_URL) node scripts/capture_manual_screenshots.mjs

docker-config-aliyun-app:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_APP_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-app.yml config --quiet

docker-up-aliyun-app:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_APP_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-app.yml up -d --build

docker-ps-aliyun-app:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_APP_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-app.yml ps

docker-config-aliyun-gpu:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_GPU_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-gpu.yml config --quiet

docker-up-aliyun-gpu:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_GPU_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-gpu.yml up -d --build

docker-ps-aliyun-gpu:
	cd $(COMPOSE_DIR) && docker compose --env-file $(COMPOSE_ENV) --env-file $(COMPOSE_ALIYUN_GPU_ENV) --env-file $(COMPOSE_DEPLOY_ENV) -f docker-compose.aliyun-gpu.yml ps

BACKEND_DEPLOY_ENV ?= .env.deploy-data
