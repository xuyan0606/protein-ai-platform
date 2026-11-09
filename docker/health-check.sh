#!/usr/bin/env bash
# =============================================================================
# Protein AI Platform — Health Check & Diagnostics
# =============================================================================
# Usage:
#   ./health-check.sh              # Full check (human-readable)
#   ./health-check.sh --json       # JSON output (for scripting / monitoring)
#   ./health-check.sh --watch 5    # Continuous monitoring every 5s
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'; DIM='\033[2m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}●${NC} $1"; }

_json_entry() {
    # name, status, detail
    printf '{"name":"%s","status":"%s","detail":"%s"}' "$1" "$2" "$3"
}

# ---------------------------------------------------------------------------
# Service health via docker compose ps
# ---------------------------------------------------------------------------
check_service_health() {
    local svc=$1 name=$2
    local status
    status=$(docker compose ps "$svc" 2>/dev/null | tail -1 | grep -oP '(healthy|unhealthy|starting|exited|running)' 2>/dev/null || echo "missing")
    case "$status" in
        healthy)   ok "$name ($status)"; return 0 ;;
        running)   warn "$name ($status — no healthcheck defined)"; return 1 ;;
        starting)  warn "$name ($status — still starting up)"; return 1 ;;
        unhealthy) fail "$name ($status — check logs: docker compose logs $svc)"; return 2 ;;
        exited)    fail "$name ($status — container exited)"; return 2 ;;
        missing)   fail "$name (not deployed)"; return 3 ;;
    esac
}

# ---------------------------------------------------------------------------
# HTTP endpoint check
# ---------------------------------------------------------------------------
check_http() {
    local url=$1 label=$2 expected=${3:-200}
    local code
    code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "$expected" ]; then
        ok "$label → HTTP $code"
        return 0
    else
        fail "$label → HTTP $code (expected $expected)"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Full diagnostic
# ---------------------------------------------------------------------------
run_diagnostic() {
    local mode=${1:-human}
    local problems=0

    echo ""
    echo -e "${BOLD}━━━ Docker Services ━━━${NC}"
    local services=(
        "postgres:PostgreSQL"
        "redis:Redis"
        "minio:MinIO"
        "chromadb:ChromaDB"
        "backend:Backend API"
        "worker:Celery Worker"
        "outline:Outline Wiki"
        "frontend:Frontend SPA"
        "nginx:Nginx Proxy"
    )
    for entry in "${services[@]}"; do
        local svc="${entry%%:*}" name="${entry##*:}"
        check_service_health "$svc" "$name" || problems=$((problems + 1))
    done

    echo ""
    echo -e "${BOLD}━━━ HTTP Endpoints ━━━${NC}"
    check_http "https://localhost/"              "Frontend SPA"      200 || problems=$((problems + 1))
    check_http "https://localhost/api/health"    "Backend API health" 200 || problems=$((problems + 1))
    check_http "https://localhost/wiki/"          "Outline Wiki"      200 || problems=$((problems + 1))
    check_http "https://localhost/auth/oidc"      "OIDC Auth"         200 || problems=$((problems + 1))

    echo ""
    echo -e "${BOLD}━━━ Internal Connectivity ━━━${NC}"

    # Backend → Outline
    if docker exec docker-backend-1 python3 -c "
import urllib.request
try:
    resp = urllib.request.urlopen('http://outline:3001/', timeout=5)
    print(resp.status)
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null | grep -q "200"; then
        ok "Backend → Outline (outline:3001)"
    else
        fail "Backend → Outline (outline:3001)" && problems=$((problems + 1))
    fi

    # Nginx → Backend
    if docker exec docker-nginx-1 wget -q -O - --timeout=3 http://backend:8000/api/health 2>/dev/null | grep -q "ok"; then
        ok "Nginx → Backend (backend:8000)"
    else
        fail "Nginx → Backend (backend:8000)" && problems=$((problems + 1))
    fi

    # Nginx → Outline
    if docker exec docker-nginx-1 wget -q -O - --timeout=3 http://outline:3001/ 2>/dev/null | grep -q "Outline"; then
        ok "Nginx → Outline (outline:3001)"
    else
        fail "Nginx → Outline (outline:3001)" && problems=$((problems + 1))
    fi

    echo ""
    echo -e "${BOLD}━━━ Resource Usage ━━━${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null | head -10

    echo ""
    if [ "$problems" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✓ All checks passed${NC}"
    else
        echo -e "${RED}${BOLD}✗ $problems check(s) failed${NC}"
        echo ""
        echo -e "${YELLOW}Quick fixes:${NC}"
        echo "  • Reload nginx:  docker exec docker-nginx-1 nginx -s reload"
        echo "  • Restart svc:   docker compose restart <service>"
        echo "  • View logs:     docker compose logs --tail=50 <service>"
        echo "  • Full recover:  ./recover.sh"
    fi

    return $problems
}

# ---------------------------------------------------------------------------
# JSON output (machine-readable)
# ---------------------------------------------------------------------------
run_json() {
    echo "{"
    echo '  "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",'
    echo '  "services": ['
    local first=true
    for svc in postgres redis minio chromadb backend worker outline frontend nginx; do
        local status
        status=$(docker compose ps "$svc" 2>/dev/null | tail -1 | grep -oP '(healthy|unhealthy|starting|exited)' 2>/dev/null || echo "missing")
        $first || echo ","
        first=false
        printf '    {"service":"%s","health":"%s"}' "$svc" "$status"
    done
    echo ""
    echo '  ],'
    echo '  "endpoints": ['
    local eps=(
        "https://localhost/:200:Frontend"
        "https://localhost/api/health:200:Backend API"
        "https://localhost/wiki/:200:Outline Wiki"
        "https://localhost/auth/oidc:200:OIDC Auth"
    )
    first=true
    for ep in "${eps[@]}"; do
        local url="${ep%%:*}" rest="${ep#*:}" expected="${rest%%:*}" label="${rest#*:}"
        local code
        code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
        $first || echo ","
        first=false
        printf '    {"url":"%s","status":%s,"expected":%s,"label":"%s"}' "$url" "$code" "$expected" "$label"
    done
    echo ""
    echo '  ]'
    echo "}"
}

# ---------------------------------------------------------------------------
# Watch mode
# ---------------------------------------------------------------------------
run_watch() {
    local interval=${1:-10}
    echo -e "${CYAN}Watching every ${interval}s — Ctrl+C to stop${NC}"
    while true; do
        clear 2>/dev/null || true
        echo -e "${BOLD}Protein AI Platform — Health Monitor${NC}  $(date '+%H:%M:%S')"
        run_diagnostic human
        sleep "$interval"
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-}" in
    --json)
        run_json
        ;;
    --watch)
        run_watch "${2:-10}"
        ;;
    *)
        echo -e "${BOLD}${CYAN}Protein AI Platform — Health Check${NC}"
        run_diagnostic human
        ;;
esac
