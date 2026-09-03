#!/usr/bin/env bash
# =============================================================================
# Protein AI Platform — Disaster Recovery
# =============================================================================
# Auto-detects failures and recovers with exponential backoff.  Designed to
# be called after docker compose up -d if health checks fail.
#
# Usage:
#   ./recover.sh              # Diagnose & attempt recovery
#   ./recover.sh --force      # Force restart everything
#   ./recover.sh --watchdog   # Daemon mode: poll services, auto-heal
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
act()  { echo -e "${CYAN}▸${NC} $1"; }

# ---------------------------------------------------------------------------
# Step 1: Quick service check
# ---------------------------------------------------------------------------
quick_status() {
    docker compose ps "$1" 2>/dev/null | tail -1 | grep -oP '(healthy|unhealthy|starting|exited)' 2>/dev/null || echo "missing"
}

# ---------------------------------------------------------------------------
# Step 2: Restart with exponential backoff and verification
# ---------------------------------------------------------------------------
restart_and_verify() {
    local svc=$1 name=$2 verify_url=${3:-} verify_text=${4:-}
    local max_attempts=5 backoff=2

    for attempt in $(seq 1 $max_attempts); do
        act "Restarting $name (attempt $attempt/$max_attempts)..."

        docker compose restart "$svc" 2>/dev/null

        # Wait for healthy
        local waited=0
        while [ $waited -lt 60 ]; do
            local status
            status=$(quick_status "$svc")
            if [ "$status" = "healthy" ]; then
                ok "$name healthy ($(($waited))s)"
                sleep 2  # Give it a moment to stabilize
                break
            fi
            sleep 2
            waited=$((waited + 2))
        done

        if [ "$(quick_status "$svc")" != "healthy" ]; then
            fail "$name still not healthy after ${waited}s"
            backoff=$((backoff * 2))
            if [ $attempt -lt $max_attempts ]; then
                act "Waiting ${backoff}s before retry..."
                sleep "$backoff"
            fi
            continue
        fi

        # Optional HTTP verification
        if [ -n "$verify_url" ]; then
            local code
            code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$verify_url" 2>/dev/null || echo "000")
            if [ "$code" = "200" ]; then
                ok "$name endpoint OK ($verify_url → HTTP 200)"
                return 0
            else
                fail "$name endpoint returned $code"
            fi
        else
            return 0
        fi

        backoff=$((backoff * 2))
        [ $attempt -lt $max_attempts ] && act "Waiting ${backoff}s before retry..." && sleep "$backoff"
    done

    fail "$name recovery FAILED after $max_attempts attempts"
    return 1
}

# ---------------------------------------------------------------------------
# Step 3: Nginx upstream reload
# ---------------------------------------------------------------------------
reload_nginx() {
    act "Reloading nginx (clearing stale upstream connections)..."
    if docker exec docker-nginx-1 nginx -s reload 2>/dev/null; then
        ok "Nginx reloaded"
        return 0
    else
        fail "Nginx reload failed"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Step 4: Full recovery sequence
# ---------------------------------------------------------------------------
full_recovery() {
    echo -e "\n${BOLD}${CYAN}Protein AI Platform — Recovery${NC}\n"

    local errors=0

    # ---- Infrastructure first -----------------------------------------------
    echo -e "${BOLD}Infrastructure services:${NC}"
    for svc in postgres redis minio; do
        if [ "$(quick_status "$svc")" != "healthy" ]; then
            restart_and_verify "$svc" "$svc" || errors=$((errors + 1))
        else
            ok "$svc (already healthy)"
        fi
    done

    # ---- Application services -----------------------------------------------
    echo -e "\n${BOLD}Application services:${NC}"
    for svc_data in "backend:Backend:https://localhost/api/health:ok" "outline:Outline:https://localhost/wiki/:Outline" "frontend:Frontend SPA:https://localhost/:Protein" "worker:Celery Worker"; do
        local svc="${svc_data%%:*}" rest="${svc_data#*:}"
        local name="${rest%%:*}" verify="${rest#*:}"
        local verify_url="${verify%%:*}" verify_text="${verify#*:}"

        if [ "$(quick_status "$svc")" != "healthy" ]; then
            restart_and_verify "$svc" "$name" "$verify_url" "$verify_text" || errors=$((errors + 1))
        else
            ok "$name (already healthy)"
        fi
    done

    # ---- Nginx reload -------------------------------------------------------
    echo -e "\n${BOLD}Reverse proxy:${NC}"
    reload_nginx || errors=$((errors + 1))

    # ---- ChromaDB (can start last, not critical) ----------------------------
    if [ "$(quick_status "chromadb")" != "healthy" ]; then
        echo -e "\n${BOLD}Vector database:${NC}"
        restart_and_verify "chromadb" "ChromaDB" || errors=$((errors + 1))
    else
        echo -e "\n${BOLD}Vector database:${NC}"
        ok "ChromaDB (already healthy)"
    fi

    # ---- Summary ------------------------------------------------------------
    echo ""
    if [ "$errors" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✓ Recovery complete — all services healthy${NC}"
    else
        echo -e "${RED}${BOLD}✗ Recovery finished with $errors error(s)${NC}"
        echo "  Check logs: docker compose logs --tail=50"
    fi

    return $errors
}

# ---------------------------------------------------------------------------
# Force restart: bring everything down and up
# ---------------------------------------------------------------------------
force_restart() {
    echo -e "\n${BOLD}${CYAN}Force restarting all services...${NC}\n"

    act "Stopping all services..."
    docker compose stop -t 10 2>/dev/null

    act "Starting all services..."
    docker compose up -d 2>/dev/null

    sleep 5
    full_recovery
}

# ---------------------------------------------------------------------------
# Watchdog: poll every N seconds and auto-heal
# ---------------------------------------------------------------------------
watchdog() {
    local interval=${1:-30}
    local max_restarts=${2:-10}
    local restart_count=0

    echo -e "${CYAN}Watchdog started — checking every ${interval}s (max ${max_restarts} auto-restarts)${NC}"

    while true; do
        local unhealthy=""
        unhealthy=$(docker compose ps 2>/dev/null | grep -E "unhealthy|exited" | awk '{print $1}' || echo "")

        if [ -n "$unhealthy" ]; then
            echo -e "\n${YELLOW}[$(date '+%H:%M:%S')] Unhealthy services detected:${NC} $unhealthy"

            if [ "$restart_count" -ge "$max_restarts" ]; then
                echo -e "${RED}Max auto-restarts ($max_restarts) reached. Manual intervention required.${NC}"
                exit 1
            fi

            for svc in $unhealthy; do
                local name="${svc#docker-}"
                name="${name%-1}"
                restart_and_verify "$name" "$name" || true
            done

            reload_nginx || true
            restart_count=$((restart_count + 1))
        fi

        sleep "$interval"
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-}" in
    --force)
        force_restart
        ;;
    --watchdog)
        watchdog "${2:-30}" "${3:-10}"
        ;;
    *)
        full_recovery
        ;;
esac
