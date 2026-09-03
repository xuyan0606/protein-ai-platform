#!/usr/bin/env bash
# =============================================================================
# Protein AI Platform — One-Click Launcher
# =============================================================================
# Usage:
#   ./start.sh                 # Start (or restart) everything
#   ./start.sh --rebuild       # Rebuild images first, then start
#   ./start.sh --clean         # Wipe volumes & rebuild from scratch (DANGER)
#   ./start.sh --stop          # Stop all services
#   ./start.sh --status        # Show health dashboard
#   ./start.sh --logs <svc>    # Tail logs for a service
#
# Design goals:
#   • Fast — parallel health polling, smart waits (no fixed timeouts)
#   • Safe — detects failures, attempts auto-recovery
#   • Clear — colored output, one step per line, no noise
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Colors & helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BLUE='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'; DIM='\033[2m'

BANNER="${BLUE}${BOLD}Protein AI Platform${NC}"
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
step() { echo -e "\n${CYAN}${BOLD}━ $1${NC}"; }
info() { echo -e "  ${CYAN}▸${NC} $1"; }

# ---------------------------------------------------------------------------
# Utility: wait for a single service to become healthy
# ---------------------------------------------------------------------------
wait_healthy() {
    local svc=$1 name=$2 timeout=${3:-120}
    local elapsed=0 interval=2

    while [ $elapsed -lt $timeout ]; do
        local status
        status=$(docker compose ps "$svc" 2>/dev/null | tail -1 | grep -oP '(healthy|unhealthy|exited)' 2>/dev/null || echo "starting")
        case "$status" in
            healthy)   ok "$name (${elapsed}s)"; return 0 ;;
            unhealthy) fail "$name went unhealthy after ${elapsed}s"; return 1 ;;
            exited)    fail "$name exited after ${elapsed}s"; return 1 ;;
        esac
        sleep "$interval"
        elapsed=$((elapsed + interval))
        # Speed up polls after 10s
        [ $elapsed -gt 10 ] && interval=1
    done

    fail "$name still not healthy after ${timeout}s"
    docker compose logs --tail=5 "$svc" 2>/dev/null | tail -3 | while read line; do echo "         $line"; done
    return 1
}

# ---------------------------------------------------------------------------
# Utility: wait for multiple services in parallel (fast!)
# ---------------------------------------------------------------------------
wait_all_healthy() {
    local timeout=${1:-120} names=("${@:2}")
    local pids=() results=()

    for entry in "${names[@]}"; do
        local svc="${entry%%:*}" name="${entry##*:}"
        wait_healthy "$svc" "$name" "$timeout" &
        pids+=($!)
    done

    local failed=0
    for pid in "${pids[@]}"; do
        wait "$pid" || failed=$((failed + 1))
    done
    return $failed
}

# ---------------------------------------------------------------------------
# Step 1: Ensure Colima (Docker runtime) is running
# ---------------------------------------------------------------------------
ensure_docker() {
    step "Step 1: Docker Runtime"

    if command -v colima &>/dev/null; then
        if ! colima status &>/dev/null; then
            info "Starting Colima..."
            colima start --cpu 4 --memory 8 2>/dev/null
        fi
        ok "Colima ready"
    elif docker info &>/dev/null 2>&1; then
        ok "Docker ready"
    else
        fail "Docker not running. Install Colima or Docker Desktop."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Step 2: Build images (only with --rebuild or --clean)
# ---------------------------------------------------------------------------
build_images() {
    local mode=${1:-}
    [ "$mode" != "--rebuild" ] && [ "$mode" != "--clean" ] && return 0

    step "Step 2: Building images"

    # Inline .dockerignore check — warn if build context is too large
    local ctx_size
    ctx_size=$(du -sh "$SCRIPT_DIR/.." 2>/dev/null | awk '{print $1}' || echo "?")
    info "Project size: $ctx_size (build context optimized by .dockerignore)"

    docker compose build backend frontend worker 2>&1 | \
        grep -E "^(#|Step|Successfully|ERROR|DONE)" | head -30 || {
        warn "Build had warnings — proceeding anyway (cached layers may be outdated)"
    }
    ok "Images ready"
}

# ---------------------------------------------------------------------------
# Step 3: Clean volumes (only with --clean — DESTRUCTIVE)
# ---------------------------------------------------------------------------
clean_volumes() {
    [ "$1" != "--clean" ] && return 0

    echo ""
    echo -e "${RED}${BOLD}⚠ DANGER: Removing all data volumes!${NC}"
    echo -e "  This will delete PostgreSQL, Redis, MinIO, ChromaDB, and Outline data."
    read -rp "  Type 'yes' to confirm: " confirm
    [ "$confirm" != "yes" ] && echo "  Cancelled." && exit 0

    docker compose down -v 2>/dev/null || true
    ok "Volumes cleaned"
}

# ---------------------------------------------------------------------------
# Step 4: Start containers
# ---------------------------------------------------------------------------
start_containers() {
    step "Step 4: Starting containers"

    docker compose up -d 2>&1
    ok "Containers launched"
}

# ---------------------------------------------------------------------------
# Step 5: Inject frontend nginx config
# ---------------------------------------------------------------------------
inject_frontend_nginx() {
    step "Step 5: Frontend nginx config"

    # Give frontend container a moment to initialize
    sleep 3

    if [ -f "nginx-frontend.conf" ]; then
        docker cp nginx-frontend.conf docker-frontend-1:/etc/nginx/conf.d/default.conf 2>/dev/null && \
        docker exec docker-frontend-1 nginx -s reload 2>/dev/null && \
        ok "Frontend nginx injected" || \
        warn "Frontend injection skipped (container not ready — harmless)"
    else
        warn "nginx-frontend.conf not found — frontend will use built-in config"
    fi
}

# ---------------------------------------------------------------------------
# Step 6: Health checks (parallel by tier)
# ---------------------------------------------------------------------------
health_checks() {
    step "Step 6: Health checks"

    # Tier 1: Infrastructure (must be up first)
    echo -e "  ${DIM}Tier 1 — Infrastructure${NC}"
    wait_all_healthy 60 \
        "postgres:PostgreSQL" \
        "redis:Redis" \
        "minio:MinIO"
    local tier1_ok=$?

    # Tier 2: Application (depends on infrastructure)
    echo -e "  ${DIM}Tier 2 — Application${NC}"
    wait_all_healthy 90 \
        "backend:Backend API" \
        "worker:Worker" \
        "outline:Outline" \
        "chromadb:ChromaDB"
    local tier2_ok=$?

    # Tier 3: Frontend (last, depends on backend)
    echo -e "  ${DIM}Tier 3 — Frontend${NC}"
    wait_all_healthy 60 \
        "frontend:Frontend SPA" \
        "nginx:Nginx Proxy"
    local tier3_ok=$?

    local total_failed=$((tier1_ok + tier2_ok + tier3_ok))
    if [ "$total_failed" -gt 0 ]; then
        warn "$total_failed service(s) not healthy — attempting recovery..."
        ./recover.sh 2>/dev/null || true
    fi
}

# ---------------------------------------------------------------------------
# Step 7: Nginx reload (clear stale upstream connections)
# ---------------------------------------------------------------------------
nginx_reload() {
    step "Step 7: Nginx reload"

    docker exec docker-nginx-1 nginx -s reload 2>/dev/null && \
        ok "Nginx reloaded (stale upstreams cleared)" || \
        warn "Nginx reload skipped (not running)"
}

# ---------------------------------------------------------------------------
# Step 8: Endpoint verification
# ---------------------------------------------------------------------------
verify_endpoints() {
    step "Step 8: Endpoint verification"

    local eps=(
        "https://localhost/:200:Frontend SPA"
        "https://localhost/api/health:200:Backend health"
        "https://localhost/wiki/:200:Outline Wiki"
        "https://localhost/auth/oidc:200:OIDC Auth"
    )
    local all_ok=true

    for ep in "${eps[@]}"; do
        local url="${ep%%:*}" rest="${ep#*:}" expected="${rest%%:*}" label="${rest#*:}"
        local code
        code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
        if [ "$code" = "$expected" ]; then
            ok "$label (HTTP $code)"
        else
            fail "$label → HTTP $code (expected $expected)"
            all_ok=false
        fi
    done

    $all_ok || warn "Some endpoints failed — run ./health-check.sh for diagnostics"
}

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║  ✓  Protein AI Platform Ready                 ║${NC}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Frontend:${NC}  https://localhost/"
    echo -e "  ${BOLD}Wiki:${NC}      https://localhost/wiki/"
    echo -e "  ${BOLD}API Docs:${NC}  https://localhost/api/docs"
    echo -e "  ${BOLD}Health:${NC}   https://localhost/api/health"
    echo ""
    echo -e "  ${BOLD}Commands:${NC}"
    echo "    ./start.sh --status    # Health dashboard"
    echo "    ./start.sh --logs svc   # Tail service logs"
    echo "    ./start.sh --stop       # Stop everything"
    echo "    ./recover.sh            # Auto-heal if something breaks"
    echo "    ./health-check.sh       # Full diagnostics"
}

# ===========================================================================
# Main
# ===========================================================================

echo -e "\n  ${BANNER}"
echo -e "  ${DIM}$(date '+%Y-%m-%d %H:%M:%S')${NC}"

case "${1:-}" in
    # ---- Status dashboard ---------------------------------------------------
    --status)
        ./health-check.sh 2>/dev/null || bash health-check.sh 2>/dev/null || {
            echo "Health check script not found. Quick check:"
            docker compose ps 2>/dev/null
        }
        exit 0
        ;;

    # ---- Logs ---------------------------------------------------------------
    --logs)
        shift
        docker compose logs --tail=100 -f "${@}" 2>/dev/null
        exit 0
        ;;

    # ---- Stop ---------------------------------------------------------------
    --stop)
        step "Stopping all services..."
        docker compose stop -t 10 2>/dev/null
        ok "All services stopped"
        exit 0
        ;;

    # ---- Restart one service ------------------------------------------------
    --restart)
        shift
        step "Restarting $*..."
        docker compose restart "$@" 2>/dev/null
        ok "Done"
        exit 0
        ;;
esac

# ---- Full startup flow -----------------------------------------------------
ensure_docker
build_images "${1:-}"
clean_volumes "${1:-}"
start_containers
inject_frontend_nginx
health_checks
nginx_reload
verify_endpoints
print_summary
