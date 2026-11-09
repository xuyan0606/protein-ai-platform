#!/usr/bin/env bash
# =============================================================================
# setup-cron.sh — Install automated backup cron job
# =============================================================================
# Usage:
#   ./setup-cron.sh              # Install backup.sh into crontab (daily 2 AM)
#   ./setup-cron.sh --remove     # Remove from crontab
#   ./setup-cron.sh --status     # Check if installed
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
CRON_SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 2 * * *}"  # Default: daily at 2 AM
CRON_TAG="# protein-ai-backup"
CRON_LOG="${SCRIPT_DIR}/../logs/backup.log"

# Ensure backup script exists and is executable
if [[ ! -f "$BACKUP_SCRIPT" ]]; then
    echo "Error: backup.sh not found at ${BACKUP_SCRIPT}"
    exit 1
fi
chmod +x "$BACKUP_SCRIPT"

# Ensure log directory exists
mkdir -p "$(dirname "$CRON_LOG")"

CRON_ENTRY="${CRON_SCHEDULE} ${BACKUP_SCRIPT} >> ${CRON_LOG} 2>&1 ${CRON_TAG}"

case "${1:-}" in
    --remove)
        echo "==> Removing backup cron job..."
        (crontab -l 2>/dev/null | grep -v "$CRON_TAG") | crontab -
        echo "==> Done. Backup cron job removed."
        ;;
    --status)
        if crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
            echo "==> Backup cron job is installed:"
            crontab -l | grep "$CRON_TAG"
        else
            echo "==> Backup cron job is NOT installed."
        fi
        ;;
    *)
        echo "==> Installing backup cron job..."
        echo "    Schedule: ${CRON_SCHEDULE}"
        echo "    Script:   ${BACKUP_SCRIPT}"
        echo "    Log:      ${CRON_LOG}"

        # Remove existing entry if present, then add new one
        (crontab -l 2>/dev/null | grep -v "$CRON_TAG"; echo "$CRON_ENTRY") | crontab -

        echo "==> Done. Verify with: crontab -l"
        echo ""
        echo "==> To customize schedule, set BACKUP_CRON_SCHEDULE env var:"
        echo "    BACKUP_CRON_SCHEDULE='0 3 * * *' $0   # Daily at 3 AM"
        echo "    BACKUP_CRON_SCHEDULE='0 */6 * * *' $0  # Every 6 hours"
        ;;
esac
