#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Restore PostgreSQL database from a Protein AI Platform backup.
#
# Supports:
#   - Current custom-format dumps: protein_ai_*.dump -> pg_restore
#   - Legacy plain SQL gzip files: protein_ai_*.sql.gz -> gunzip | psql
#
# Usage:
#   ./scripts/restore.sh backups/protein_ai_20260707T000000Z.dump
#   ./scripts/restore.sh --dry-run backups/protein_ai_20260707T000000Z.dump
#   ./scripts/restore.sh --yes backups/protein_ai_20260707T000000Z.dump
#   ./scripts/restore.sh --from-s3 protein_ai_20260707T000000Z.dump
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"
DOCKER_ENV="$DOCKER_DIR/.env"
BACKUP_BUCKET="${BACKUP_BUCKET:-protein-backups}"
MC_ALIAS="${MC_ALIAS:-myminio}"

ASSUME_YES=false
DRY_RUN=false
FROM_S3=false
S3_KEY=""
BACKUP_FILE=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat <<'EOF'
Usage:
  ./scripts/restore.sh [--dry-run] [--yes] <backup-file.dump|backup-file.sql.gz>
  ./scripts/restore.sh [--dry-run] [--yes] --from-s3 <s3-key>

Options:
  --dry-run  Validate inputs and print restore plan without touching database.
  --yes      Skip interactive confirmation.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --yes|-y) ASSUME_YES=true ;;
        --from-s3)
            FROM_S3=true
            shift
            S3_KEY="${1:-}"
            ;;
        -h|--help) usage; exit 0 ;;
        *)
            BACKUP_FILE="$1"
            ;;
    esac
    shift || true
done

if [[ "$FROM_S3" == true && -z "$S3_KEY" ]]; then
    usage
    exit 1
fi
if [[ "$FROM_S3" == false && -z "$BACKUP_FILE" ]]; then
    usage
    exit 1
fi

if [[ -f "$DOCKER_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$DOCKER_ENV"
    set +a
fi

PGUSER="${POSTGRES_USER:-postgres}"
PGDATABASE="${POSTGRES_DB:-protein_ai}"
TMP_FILE=""

cleanup() {
    if [[ -n "$TMP_FILE" && -f "$TMP_FILE" ]]; then
        rm -f "$TMP_FILE" "$TMP_FILE.sha256"
    fi
}
trap cleanup EXIT

download_from_s3() {
    local key="$1"
    TMP_FILE="/tmp/protein_ai_restore_$(date +%s)_$(basename "$key")"
    echo "==> Downloading from ${MC_ALIAS}/${BACKUP_BUCKET}/${key}"
    if [[ "$DRY_RUN" == true ]]; then
        echo "dry-run: would run mc cp ${MC_ALIAS}/${BACKUP_BUCKET}/${key} $TMP_FILE"
        BACKUP_FILE="$TMP_FILE"
        return
    fi
    mc cp "${MC_ALIAS}/${BACKUP_BUCKET}/${key}" "$TMP_FILE"
    mc cp "${MC_ALIAS}/${BACKUP_BUCKET}/${key}.sha256" "$TMP_FILE.sha256" >/dev/null 2>&1 || true
    BACKUP_FILE="$TMP_FILE"
}

verify_checksum() {
    local backup_file="$1"
    local checksum_file="$backup_file.sha256"
    if [[ ! -f "$checksum_file" ]]; then
        echo -e "${YELLOW}WARNING: checksum file not found: $checksum_file${NC}"
        return
    fi
    if command -v shasum >/dev/null 2>&1; then
        (cd "$(dirname "$backup_file")" && shasum -a 256 -c "$(basename "$checksum_file")")
    else
        (cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "$checksum_file")")
    fi
}

detect_format() {
    local backup_file="$1"
    case "$backup_file" in
        *.dump) echo "custom" ;;
        *.sql.gz) echo "plain-gzip" ;;
        *)
            if file "$backup_file" | grep -qi "PostgreSQL custom database dump"; then
                echo "custom"
            elif file "$backup_file" | grep -qi "gzip compressed"; then
                echo "plain-gzip"
            else
                echo "unknown"
            fi
            ;;
    esac
}

compose_exec() {
    (
        cd "$DOCKER_DIR"
        docker compose --env-file .env -f docker-compose.yml exec -T postgres "$@"
    )
}

drop_and_recreate_db() {
    echo "==> Dropping and recreating database: $PGDATABASE"
    compose_exec psql -U "$PGUSER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PGDATABASE}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    compose_exec dropdb -U "$PGUSER" --if-exists "$PGDATABASE"
    compose_exec createdb -U "$PGUSER" "$PGDATABASE"
}

restore_custom() {
    local backup_file="$1"
    drop_and_recreate_db
    echo "==> Restoring custom dump with pg_restore"
    docker compose --env-file "$DOCKER_ENV" -f "$DOCKER_DIR/docker-compose.yml" exec -T postgres \
        pg_restore -U "$PGUSER" -d "$PGDATABASE" --no-owner --no-acl < "$backup_file"
}

restore_plain_gzip() {
    local backup_file="$1"
    drop_and_recreate_db
    echo "==> Restoring legacy gzip SQL with psql"
    gunzip -c "$backup_file" | docker compose --env-file "$DOCKER_ENV" -f "$DOCKER_DIR/docker-compose.yml" exec -T postgres \
        psql -U "$PGUSER" -d "$PGDATABASE"
}

if [[ "$FROM_S3" == true ]]; then
    download_from_s3 "$S3_KEY"
fi

if [[ "$DRY_RUN" == false && ! -f "$BACKUP_FILE" ]]; then
    echo -e "${RED}Error: backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

FORMAT="$(detect_format "$BACKUP_FILE")"
if [[ "$FORMAT" == "unknown" ]]; then
    echo -e "${RED}Error: unsupported backup format: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}==> Restore target: docker compose postgres service${NC}"
echo -e "${YELLOW}==> Database: $PGDATABASE user=$PGUSER${NC}"
echo -e "${YELLOW}==> Backup: $BACKUP_FILE format=$FORMAT${NC}"
echo -e "${YELLOW}==> WARNING: this will DROP and recreate the database.${NC}"

if [[ "$DRY_RUN" == true ]]; then
    echo "dry-run: restore plan validated; no database changes made."
    exit 0
fi

verify_checksum "$BACKUP_FILE"

if [[ "$ASSUME_YES" != true ]]; then
    read -rp "Continue? Type 'yes' to restore: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

case "$FORMAT" in
    custom) restore_custom "$BACKUP_FILE" ;;
    plain-gzip) restore_plain_gzip "$BACKUP_FILE" ;;
esac

echo -e "${GREEN}==> Restore complete.${NC}"
