#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# init_outline.sh — Initialize Outline knowledge base for Protein AI Platform
# ---------------------------------------------------------------------------
# Creates the Outline PostgreSQL database, MinIO bucket, and runs migrations.
#
# Usage:
#   bash scripts/init_outline.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration (override with env vars)
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"

echo "=== Initializing Outline Knowledge Base ==="

# 1. Create the 'outline' database in PostgreSQL
echo ""
echo "[1/3] Creating outline database..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d postgres \
  -c "SELECT 1 FROM pg_database WHERE datname='outline'" \
  | grep -q 1 \
  && echo "  Database 'outline' already exists, skipping." \
  || {
    PGPASSWORD="$POSTGRES_PASSWORD" psql \
      -h "$POSTGRES_HOST" \
      -p "$POSTGRES_PORT" \
      -U "$POSTGRES_USER" \
      -d postgres \
      -c "CREATE DATABASE outline"
    echo "  Database 'outline' created."
  }

# 2. Create MinIO bucket for Outline uploads
echo ""
echo "[2/3] Creating MinIO bucket 'outline-uploads'..."
if command -v mc &>/dev/null; then
  mc alias set localminio http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null || true
  if mc ls "localminio/outline-uploads" &>/dev/null; then
    echo "  Bucket 'outline-uploads' already exists, skipping."
  else
    mc mb "localminio/outline-uploads"
    echo "  Bucket 'outline-uploads' created."
  fi
else
  echo "  MinIO client (mc) not found. Install it with: brew install minio-mc"
  echo "  Or create the bucket manually at http://localhost:9001"
fi

# 3. Run Outline database migrations
echo ""
echo "[3/3] Running Outline migrations..."
echo "  (Outline container must be running: docker compose up -d outline)"
echo "  Run this command manually:"
echo "    docker compose -f docker/docker-compose.dev.yml exec outline yarn db:migrate"

echo ""
echo "=== Done ==="
echo "Outline should be available at http://localhost/wiki (with nginx)"
echo "or directly at http://localhost:3001 (dev mode)"