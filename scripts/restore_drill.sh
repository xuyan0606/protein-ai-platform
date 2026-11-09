#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Restore drill for PostgreSQL backups.
#
# Restores a backup into a temporary database inside the docker compose
# postgres service, runs a small sanity query, and drops the temporary database
# unless --keep-db is provided. It never touches the main POSTGRES_DB.
#
# Usage:
#   ./scripts/restore_drill.sh --plan-only
#   ./scripts/restore_drill.sh --dry-run backups/protein_ai_20260707T000000Z.dump
#   ./scripts/restore_drill.sh backups/protein_ai_20260707T000000Z.dump
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"
DOCKER_ENV="$DOCKER_DIR/.env"

BACKUP_FILE=""
DRY_RUN=false
PLAN_ONLY=false
KEEP_DB=false
DRILL_DB="${DRILL_DB:-protein_ai_restore_check}"

usage() {
    cat <<'EOF'
Usage:
  ./scripts/restore_drill.sh [--plan-only] [--dry-run] [--keep-db] [--database name] [backup-file.dump|backup-file.sql.gz]

Options:
  --plan-only     Print required inputs and execution gate without touching Docker or backup files.
  --dry-run       Print planned drill without creating a database.
  --keep-db       Keep the temporary restore database after verification.
  --database name Temporary database name. Default: protein_ai_restore_check.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan-only) PLAN_ONLY=true; DRY_RUN=true ;;
        --dry-run) DRY_RUN=true ;;
        --keep-db) KEEP_DB=true ;;
        --database)
            shift
            DRILL_DB="${1:-}"
            ;;
        -h|--help) usage; exit 0 ;;
        *) BACKUP_FILE="$1" ;;
    esac
    shift
done

if [[ -z "$BACKUP_FILE" ]]; then
    if [[ "$PLAN_ONLY" == true ]]; then
        printf "mode\tplan-only\n"
        printf "input\tbackup_file\tmissing\tpass backups/protein_ai_YYYYMMDDTHHMMSSZ.dump or .sql.gz\n"
        printf "input\tdrill_database\tset\t%s\n" "$DRILL_DB"
        printf "safe_action\t./scripts/verify_backup.sh --plan-only BACKUP_FILE\n"
        printf "safe_action\t./scripts/restore_drill.sh --dry-run BACKUP_FILE\n"
        printf "executable_when\tbackup exists, docker compose postgres is reachable, temporary database name is not production\n"
        printf "summary\tblocked\tmissing backup file input\n"
        exit 0
    fi
    usage
    exit 1
fi

if [[ -z "$DRILL_DB" ]]; then
    usage
    exit 1
fi

if ! [[ "$DRILL_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Refusing unsafe drill database name: $DRILL_DB" >&2
    exit 1
fi

if [[ "$DRILL_DB" == "${POSTGRES_DB:-protein_ai}" || "$DRILL_DB" == "postgres" || "$DRILL_DB" == "template1" ]]; then
    echo "Refusing unsafe drill database name: $DRILL_DB" >&2
    exit 1
fi

if [[ -f "$DOCKER_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$DOCKER_ENV"
    set +a
fi

PGUSER="${POSTGRES_USER:-postgres}"
MAIN_DB="${POSTGRES_DB:-protein_ai}"

if [[ "$DRILL_DB" == "$MAIN_DB" || "$DRILL_DB" == "postgres" || "$DRILL_DB" == "template1" ]]; then
    echo "Refusing unsafe drill database name after env load: $DRILL_DB" >&2
    exit 1
fi

detect_format() {
    local backup_file="$1"
    case "$backup_file" in
        *.dump) echo "custom" ;;
        *.sql.gz) echo "plain-gzip" ;;
        *) echo "unknown" ;;
    esac
}

compose_exec() {
    (
        cd "$DOCKER_DIR"
        docker compose --env-file .env -f docker-compose.yml exec -T postgres "$@"
    )
}

run_or_print() {
    if [[ "$DRY_RUN" == true ]]; then
        echo "dry-run: $*"
    else
        "$@"
    fi
}

if [[ "$DRY_RUN" == false && ! -f "$BACKUP_FILE" ]]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

FORMAT="$(detect_format "$BACKUP_FILE")"
if [[ "$FORMAT" == "unknown" ]]; then
    echo "Unsupported backup format: $BACKUP_FILE" >&2
    exit 1
fi

MODE="execute"
if [[ "$PLAN_ONLY" == true ]]; then
    MODE="plan-only"
elif [[ "$DRY_RUN" == true ]]; then
    MODE="dry-run"
fi

printf "mode\t%s\n" "$MODE"
printf "main_db\t%s\n" "$MAIN_DB"
printf "drill_db\t%s\n" "$DRILL_DB"
printf "backup\t%s\n" "$BACKUP_FILE"
printf "format\t%s\n" "$FORMAT"
printf "safety\tmain_db_unchanged\ttrue\n"
printf "safety\ttemporary_db_only\t%s\n" "$DRILL_DB"

run_or_print "$PROJECT_DIR/scripts/verify_backup.sh" --compose "$BACKUP_FILE"
if [[ "$DRY_RUN" == true ]]; then
    echo "dry-run: terminate active sessions for $DRILL_DB"
else
    compose_exec psql -U "$PGUSER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DRILL_DB}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
fi
run_or_print compose_exec dropdb -U "$PGUSER" --if-exists "$DRILL_DB"
run_or_print compose_exec createdb -U "$PGUSER" "$DRILL_DB"

if [[ "$DRY_RUN" == true ]]; then
    echo "dry-run: would restore $BACKUP_FILE into $DRILL_DB"
else
    case "$FORMAT" in
        custom)
            docker compose --env-file "$DOCKER_ENV" -f "$DOCKER_DIR/docker-compose.yml" exec -T postgres \
                pg_restore -U "$PGUSER" -d "$DRILL_DB" --no-owner --no-acl < "$BACKUP_FILE"
            ;;
        plain-gzip)
            gunzip -c "$BACKUP_FILE" | docker compose --env-file "$DOCKER_ENV" -f "$DOCKER_DIR/docker-compose.yml" exec -T postgres \
                psql -U "$PGUSER" -d "$DRILL_DB"
            ;;
    esac
fi

run_or_print compose_exec psql -U "$PGUSER" -d "$DRILL_DB" -c "SELECT current_database(), count(*) FROM information_schema.tables WHERE table_schema='public';"

if [[ "$KEEP_DB" == true ]]; then
    printf "cleanup\tskipped\t%s\n" "$DRILL_DB"
else
    run_or_print compose_exec dropdb -U "$PGUSER" --if-exists "$DRILL_DB"
    printf "cleanup\tok\t%s\n" "$DRILL_DB"
fi

printf "summary\tok\trestore drill completed\n"
