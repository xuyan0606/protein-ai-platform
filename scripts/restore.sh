#!/usr/bin/env bash
# =============================================================================
# restore.sh — Restore PostgreSQL database from backup
# =============================================================================
# Usage:
#   ./restore.sh <backup-file>              # Restore from local file
#   ./restore.sh --from-s3 <s3-key>         # Restore from MinIO/S3
#
# Prerequisites:
#   - Docker Compose stack must be running
#   - For S3 restore: mc (MinIO Client) configured with target alias
#
# Examples:
#   ./restore.sh backups/protein_ai_20250115_020000.sql.gz
#   ./restore.sh --from-s3 protein_ai_20250115_020000.sql.gz
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="${PROJECT_DIR}/docker"
BACKUP_BUCKET="${BACKUP_BUCKET:-protein-backups}"
MC_ALIAS="${MC_ALIAS:-myminio}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <backup-file.sql.gz>"
    echo "       $0 --from-s3 <s3-key.sql.gz>"
    exit 1
}

restore_from_file() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        echo -e "${RED}Error: File not found: ${backup_file}${NC}"
        exit 1
    fi

    echo -e "${YELLOW}==> Restoring from: ${backup_file}${NC}"
    echo -e "${YELLOW}==> WARNING: This will DROP and recreate the database!${NC}"
    read -rp "Continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi

    # Get database credentials from docker/.env
    source "${DOCKER_DIR}/.env"

    # Drop and recreate database
    echo "==> Dropping existing database..."
    docker compose -f "${DOCKER_DIR}/docker-compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER:-postgres}" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-protein_ai}' AND pid <> pg_backend_pid();" 2>/dev/null || true
    docker compose -f "${DOCKER_DIR}/docker-compose.yml" exec -T postgres \
        dropdb -U "${POSTGRES_USER:-postgres}" --if-exists "${POSTGRES_DB:-protein_ai}"
    docker compose -f "${DOCKER_DIR}/docker-compose.yml" exec -T postgres \
        createdb -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-protein_ai}"

    # Restore
    echo "==> Restoring database..."
    gunzip -c "$backup_file" | docker compose -f "${DOCKER_DIR}/docker-compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-protein_ai}"

    echo -e "${GREEN}==> Restore complete!${NC}"
}

restore_from_s3() {
    local s3_key="$1"
    local tmp_file="/tmp/restore_$(date +%s).sql.gz"

    echo "==> Downloading from S3: ${s3_key}"
    mc cp "${MC_ALIAS}/${BACKUP_BUCKET}/${s3_key}" "$tmp_file"

    restore_from_file "$tmp_file"
    rm -f "$tmp_file"
}

# Main
if [[ $# -lt 1 ]]; then
    usage
fi

if [[ "$1" == "--from-s3" ]]; then
    [[ $# -lt 2 ]] && usage
    restore_from_s3 "$2"
else
    restore_from_file "$1"
fi
