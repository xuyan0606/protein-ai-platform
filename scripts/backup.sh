#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PostgreSQL backup script for Protein AI Platform
#
# Produces PostgreSQL custom-format dumps (*.dump) with a matching sha256 file.
#
# Usage:
#   ./scripts/backup.sh                  # direct pg_dump against POSTGRES_HOST
#   ./scripts/backup.sh --compose        # pg_dump inside docker compose postgres
#   ./scripts/backup.sh --s3             # upload dump + checksum to S3/MinIO
#   ./scripts/backup.sh --dry-run        # print resolved plan without dumping
#
# Environment variables:
#   POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_HOST / POSTGRES_PORT
#   BACKUP_DIR / BACKUP_RETENTION_DAYS
#   S3_ENDPOINT / S3_ACCESS_KEY / S3_SECRET_KEY / S3_BUCKET / S3_SECURE
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"
DOCKER_ENV="$DOCKER_DIR/.env"
COMPOSE_FILE="$DOCKER_DIR/docker-compose.yml"

USE_COMPOSE=false
UPLOAD_S3=false
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage:
  ./scripts/backup.sh [--compose] [--s3] [--dry-run]

Options:
  --compose  Run pg_dump inside the docker compose postgres service.
  --s3       Upload dump and checksum to S3/MinIO using aws-cli.
  --dry-run  Print planned operation without writing a backup.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --compose) USE_COMPOSE=true ;;
        --s3) UPLOAD_S3=true ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
    shift
done

if [[ -f "$DOCKER_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$DOCKER_ENV"
    set +a
fi

PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGDATABASE="${POSTGRES_DB:-protein_ai}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="$BACKUP_DIR/protein_ai_$TIMESTAMP.dump"
CHECKSUM_FILE="$DUMP_FILE.sha256"

export PGPASSWORD

echo "[$(date -Iseconds)] Backup mode: $([[ "$USE_COMPOSE" == true ]] && echo compose || echo direct)"
echo "[$(date -Iseconds)] Database: $PGDATABASE user=$PGUSER host=$PGHOST port=$PGPORT"
echo "[$(date -Iseconds)] Output: $DUMP_FILE"

if [[ "$DRY_RUN" == true ]]; then
    echo "[$(date -Iseconds)] Dry run complete; no backup created."
    exit 0
fi

mkdir -p "$BACKUP_DIR"

if [[ "$USE_COMPOSE" == true ]]; then
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        echo "Missing compose file: $COMPOSE_FILE" >&2
        exit 1
    fi
    (
        cd "$DOCKER_DIR"
        docker compose --env-file .env -f docker-compose.yml exec -T postgres \
            pg_dump \
                --username="$PGUSER" \
                --dbname="$PGDATABASE" \
                --no-owner \
                --no-acl \
                --compress=9 \
                --format=custom
    ) > "$DUMP_FILE"
else
    if ! command -v pg_dump >/dev/null 2>&1; then
        echo "pg_dump not found. Install PostgreSQL client tools or use --compose." >&2
        exit 1
    fi
    pg_dump \
        --host="$PGHOST" \
        --port="$PGPORT" \
        --username="$PGUSER" \
        --dbname="$PGDATABASE" \
        --no-owner \
        --no-acl \
        --compress=9 \
        --format=custom \
        --file="$DUMP_FILE"
fi

if command -v shasum >/dev/null 2>&1; then
    (
        cd "$BACKUP_DIR"
        shasum -a 256 "$(basename "$DUMP_FILE")" > "$(basename "$CHECKSUM_FILE")"
    )
else
    (
        cd "$BACKUP_DIR"
        sha256sum "$(basename "$DUMP_FILE")" > "$(basename "$CHECKSUM_FILE")"
    )
fi

echo "[$(date -Iseconds)] Backup saved: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"
echo "[$(date -Iseconds)] Checksum saved: $CHECKSUM_FILE"

if [[ "$UPLOAD_S3" == true ]]; then
    S3_ENDPOINT="${S3_ENDPOINT:-localhost:9000}"
    S3_ACCESS="${S3_ACCESS_KEY:-minioadmin}"
    S3_SECRET="${S3_SECRET_KEY:-minioadmin}"
    S3_BUCKET="${S3_BUCKET:-protein-backups}"
    S3_SECURE="${S3_SECURE:-false}"
    S3_SCHEME="http"
    [[ "$S3_SECURE" == "true" || "$S3_SECURE" == "1" ]] && S3_SCHEME="https"

    if command -v aws >/dev/null 2>&1; then
        AWS_ACCESS_KEY_ID="$S3_ACCESS" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
        aws s3 cp --endpoint-url "$S3_SCHEME://$S3_ENDPOINT" "$DUMP_FILE" "s3://$S3_BUCKET/$(basename "$DUMP_FILE")"
        AWS_ACCESS_KEY_ID="$S3_ACCESS" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
        aws s3 cp --endpoint-url "$S3_SCHEME://$S3_ENDPOINT" "$CHECKSUM_FILE" "s3://$S3_BUCKET/$(basename "$CHECKSUM_FILE")"
        echo "[$(date -Iseconds)] Uploaded dump and checksum to s3://$S3_BUCKET/"
    else
        echo "[$(date -Iseconds)] WARNING: aws-cli not found; skipping S3 upload"
    fi
fi

find "$BACKUP_DIR" \( -name "protein_ai_*.dump" -o -name "protein_ai_*.sql.gz" \) -mtime "+$RETENTION_DAYS" -print0 |
    while IFS= read -r -d '' old; do
        rm -f "$old" "$old.sha256"
        echo "[$(date -Iseconds)] Deleted old backup: $(basename "$old")"
    done

echo "[$(date -Iseconds)] Backup complete. Retention: $RETENTION_DAYS days."
