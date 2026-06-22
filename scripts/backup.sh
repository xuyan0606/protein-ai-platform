#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PostgreSQL auto-backup script for Protein AI Platform
#
# Usage:
#   ./scripts/backup.sh                     # manual run
#   ./scripts/backup.sh --s3                # backup + upload to S3/MinIO
#
# Cron (daily at 2am):
#   0 2 * * * /path/to/scripts/backup.sh --s3 >> /var/log/protein-ai-backup.log 2>&1
#
# Environment variables (fallback to docker-compose defaults):
#   POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_HOST / POSTGRES_PORT
#   BACKUP_DIR           — where to store dumps (default: ./backups)
#   BACKUP_RETENTION_DAYS — delete dumps older than this (default: 30)
#   S3_ENDPOINT / S3_ACCESS_KEY / S3_SECRET_KEY / S3_BUCKET — MinIO or AWS S3
# ---------------------------------------------------------------------------
set -euo pipefail

# ---- Configuration ---------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGDATABASE="${POSTGRES_DB:-protein_ai}"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

export PGPASSWORD

# ---- Ensure backup directory exists ----------------------------------------
mkdir -p "$BACKUP_DIR"

# ---- Dump ------------------------------------------------------------------
echo "[$(date -Iseconds)] Starting backup of $PGDATABASE @ $PGHOST:$PGPORT ..."

DUMP_FILE="$BACKUP_DIR/protein_ai_$TIMESTAMP.sql.gz"
pg_dump \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE" \
    --no-owner \
    --no-acl \
    --compress=9 \
    --format=custom \
    --file="$DUMP_FILE" \
    2>&1

echo "[$(date -Iseconds)] Backup saved: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# ---- Upload to S3/MinIO (if --s3 flag) -------------------------------------
if [[ "${1:-}" == "--s3" ]]; then
    S3_ENDPOINT="${S3_ENDPOINT:-localhost:9000}"
    S3_ACCESS="${S3_ACCESS_KEY:-minioadmin}"
    S3_SECRET="${S3_SECRET_KEY:-minioadmin}"
    S3_BUCKET="${S3_BUCKET:-protein-backups}"

    if command -v aws &>/dev/null; then
        AWS_ACCESS_KEY_ID="$S3_ACCESS" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
        aws s3 cp \
            --endpoint-url "http://$S3_ENDPOINT" \
            --no-verify-ssl \
            "$DUMP_FILE" \
            "s3://$S3_BUCKET/$(basename "$DUMP_FILE")"

        echo "[$(date -Iseconds)] Uploaded to s3://$S3_BUCKET/$(basename "$DUMP_FILE")"
    else
        echo "[$(date -Iseconds)] WARNING: aws-cli not found, skipping S3 upload"
    fi
fi

# ---- Retention -------------------------------------------------------------
DELETED=0
find "$BACKUP_DIR" -name "protein_ai_*.sql.gz" -mtime "+$RETENTION_DAYS" -print0 | while IFS= read -r -d '' old; do
    rm -f "$old"
    echo "[$(date -Iseconds)] Deleted old backup: $(basename "$old")"
    DELETED=$((DELETED + 1))
done

echo "[$(date -Iseconds)] Backup complete. Retention: $RETENTION_DAYS days."
