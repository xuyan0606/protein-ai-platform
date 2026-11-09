#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Verify a Protein AI Platform PostgreSQL backup without restoring production.
#
# Checks:
#   - Backup file exists
#   - Optional .sha256 checksum matches
#   - Format is supported
#   - Custom dump can be listed by pg_restore
#
# Usage:
#   ./scripts/verify_backup.sh --plan-only
#   ./scripts/verify_backup.sh backups/protein_ai_20260707T000000Z.dump
#   ./scripts/verify_backup.sh --compose backups/protein_ai_20260707T000000Z.dump
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"

USE_COMPOSE=false
PLAN_ONLY=false
BACKUP_FILE=""

usage() {
    cat <<'EOF'
Usage:
  ./scripts/verify_backup.sh [--plan-only] [--compose] [backup-file.dump|backup-file.sql.gz]

Options:
  --plan-only  Print required inputs and commands without reading backup contents.
  --compose    Run pg_restore --list inside the docker compose postgres service.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan-only) PLAN_ONLY=true ;;
        --compose) USE_COMPOSE=true ;;
        -h|--help) usage; exit 0 ;;
        *) BACKUP_FILE="$1" ;;
    esac
    shift
done

if [[ -z "$BACKUP_FILE" ]]; then
    if [[ "$PLAN_ONLY" == true ]]; then
        printf "mode\tplan-only\n"
        printf "input\tbackup_file\tmissing\tpass backups/protein_ai_YYYYMMDDTHHMMSSZ.dump or .sql.gz\n"
        printf "input\tchecksum_file\tmissing\tpreferred: <backup-file>.sha256\n"
        printf "safe_action\tmake backup-local\tcreate a new PostgreSQL custom dump and checksum\n"
        printf "safe_action\tmake verify-backup BACKUP_FILE=...\tverify checksum and dump readability\n"
        printf "executable_when\tbackup file is present and either pg_restore exists locally or --compose can reach postgres\n"
        printf "summary\tblocked\tmissing backup file input\n"
        exit 0
    fi
    usage
    exit 1
fi

if [[ "$PLAN_ONLY" == true ]]; then
    printf "mode\tplan-only\n"
    printf "input\tbackup_file\tset\t%s\n" "$BACKUP_FILE"
    printf "input\tchecksum_file\tpreferred\t%s.sha256\n" "$BACKUP_FILE"
    printf "planned_step\tbackup_exists\t[[ -f '%s' ]]\n" "$BACKUP_FILE"
    printf "planned_step\tchecksum\tshasum -a 256 -c '%s.sha256'\n" "$(basename "$BACKUP_FILE")"
    if [[ "$USE_COMPOSE" == true ]]; then
        printf "planned_step\tpg_restore_list\tdocker compose exec postgres pg_restore --list < '%s'\n" "$BACKUP_FILE"
    else
        printf "planned_step\tpg_restore_list\tpg_restore --list '%s'\n" "$BACKUP_FILE"
    fi
    printf "summary\tplanned\tbackup verification not executed\n"
    exit 0
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "backup\tmissing\t$BACKUP_FILE"
    exit 1
fi

BACKUP_FILE="$(cd "$(dirname "$BACKUP_FILE")" && pwd)/$(basename "$BACKUP_FILE")"

verify_checksum() {
    local backup_file="$1"
    local checksum_file="$backup_file.sha256"
    if [[ ! -f "$checksum_file" ]]; then
        printf "checksum\twarning\tmissing %s\n" "$checksum_file"
        return
    fi
    if command -v shasum >/dev/null 2>&1; then
        if (cd "$(dirname "$backup_file")" && shasum -a 256 -c "$(basename "$checksum_file")" >/dev/null 2>&1); then
            printf "checksum\tok\t%s\n" "$checksum_file"
            return
        fi
    elif command -v sha256sum >/dev/null 2>&1; then
        if (cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "$checksum_file")" >/dev/null 2>&1); then
            printf "checksum\tok\t%s\n" "$checksum_file"
            return
        fi
    else
        printf "checksum\tblocked\tmissing shasum or sha256sum\n"
        exit 1
    fi

    # Older checksum sidecars stored the absolute path from the machine where
    # the backup was created. Verify by digest so restored workspaces can still
    # trust migrated backups without editing the sidecar file.
    local expected actual
    expected="$(awk 'NR == 1 {print $1}' "$checksum_file")"
    if command -v shasum >/dev/null 2>&1; then
        actual="$(shasum -a 256 "$backup_file" | awk '{print $1}')"
    else
        actual="$(sha256sum "$backup_file" | awk '{print $1}')"
    fi
    if [[ -n "$expected" && "$actual" == "$expected" ]]; then
        printf "checksum\tok\t%s\tlegacy-path\n" "$checksum_file"
        return
    fi
    printf "checksum\tfailed\t%s\n" "$checksum_file"
    exit 1
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

verify_custom_dump() {
    local backup_file="$1"
    if [[ "$USE_COMPOSE" == true ]]; then
        (
            cd "$DOCKER_DIR"
            docker compose --env-file .env -f docker-compose.yml exec -T postgres \
                pg_restore --list < "$backup_file" >/dev/null
        )
    else
        if ! command -v pg_restore >/dev/null 2>&1; then
            printf "pg_restore\tmissing\tinstall PostgreSQL client tools or use --compose\n"
            exit 1
        fi
        pg_restore --list "$backup_file" >/dev/null
    fi
    printf "pg_restore_list\tok\t%s\n" "$backup_file"
}

FORMAT="$(detect_format "$BACKUP_FILE")"
printf "backup\tfound\t%s\n" "$BACKUP_FILE"
printf "format\t%s\t%s\n" "$FORMAT" "$BACKUP_FILE"

if [[ "$FORMAT" == "unknown" ]]; then
    printf "summary\tblocked\tunsupported backup format\n"
    exit 1
fi

verify_checksum "$BACKUP_FILE"

case "$FORMAT" in
    custom) verify_custom_dump "$BACKUP_FILE" ;;
    plain-gzip)
        gunzip -t "$BACKUP_FILE"
        printf "gzip_test\tok\t%s\n" "$BACKUP_FILE"
        ;;
esac

printf "summary\tok\tbackup verification passed\n"
