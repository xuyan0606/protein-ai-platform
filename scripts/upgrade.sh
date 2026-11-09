#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Protein AI Platform upgrade orchestrator.
#
# Local mode:
#   1. Run read-only upgrade readiness checks
#   2. Create a PostgreSQL backup unless --skip-backup is provided
#   3. Rebuild/start docker compose services
#   4. Run Alembic migrations in the backend container
#
# Alibaba mode delegates to deploy-aliyun.sh after readiness checks.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"

MODE="local"
DRY_RUN=false
ASSUME_YES=false
SKIP_BACKUP=false
SKIP_MIGRATIONS=false

usage() {
    cat <<'EOF'
Usage:
  ./scripts/upgrade.sh [--dry-run] [--yes] [--mode local|aliyun-app|aliyun-gpu]

Options:
  --dry-run          Print the upgrade plan without changing services.
  --yes             Skip interactive confirmation.
  --skip-backup     Do not run backup before upgrade.
  --skip-migrations Do not run Alembic migrations after compose up.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            shift
            MODE="${1:-local}"
            ;;
        --dry-run) DRY_RUN=true ;;
        --yes|-y) ASSUME_YES=true ;;
        --skip-backup) SKIP_BACKUP=true ;;
        --skip-migrations) SKIP_MIGRATIONS=true ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
    shift
done

run_or_print() {
    if [[ "$DRY_RUN" == true ]]; then
        echo "dry-run: $*"
    else
        "$@"
    fi
}

confirm() {
    if [[ "$DRY_RUN" == true || "$ASSUME_YES" == true ]]; then
        return
    fi
    echo "This will upgrade mode=$MODE and may restart services."
    read -rp "Continue? Type 'yes' to upgrade: " answer
    if [[ "$answer" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi
}

run_readiness() {
    echo "==> Upgrade readiness"
    run_or_print python3 "$PROJECT_DIR/scripts/check_upgrade_readiness.py"
}

upgrade_local() {
    run_readiness
    confirm

    if [[ "$SKIP_BACKUP" != true ]]; then
        echo "==> Backup before upgrade"
        run_or_print "$PROJECT_DIR/scripts/backup.sh" --compose
    fi

    echo "==> Rebuild/start local compose stack"
    run_or_print bash -lc "cd '$DOCKER_DIR' && docker compose --env-file .env --env-file .env.deploy-data up -d --build"

    if [[ "$SKIP_MIGRATIONS" != true ]]; then
        echo "==> Run backend migrations"
        run_or_print bash -lc "cd '$DOCKER_DIR' && docker compose --env-file .env --env-file .env.deploy-data exec backend alembic upgrade head"
    fi

    echo "==> Post-upgrade readiness"
    run_or_print python3 "$PROJECT_DIR/scripts/check_environment.py"
}

upgrade_aliyun() {
    local role="$1"
    run_readiness
    confirm
    echo "==> Deploy Alibaba role=$role"
    run_or_print "$PROJECT_DIR/deploy-aliyun.sh" "$role" up
}

case "$MODE" in
    local) upgrade_local ;;
    aliyun-app) upgrade_aliyun app ;;
    aliyun-gpu) upgrade_aliyun gpu ;;
    *) echo "Unsupported mode: $MODE" >&2; usage; exit 1 ;;
esac

printf "summary\tok\n"
