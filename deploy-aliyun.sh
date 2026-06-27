#!/usr/bin/env bash
# =============================================================================
# Protein AI Platform — Alibaba Cloud ECS Deployment
# =============================================================================
# Run this on a fresh Alibaba Cloud ECS (Ubuntu 22.04 / CentOS 7+).
#
# Usage:
#   chmod +x deploy-aliyun.sh
#   ./deploy-aliyun.sh
#
# What it does:
#   1. Install Docker + Docker Compose
#   2. Configure Alibaba Cloud Docker registry mirror
#   3. Build all images
#   4. Start the full stack (nginx, backend, frontend, postgres, redis, minio, chromadb)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- Pre-flight checks ----
if [ ! -f docker/.env ]; then
    err "Missing docker/.env — copy docker/.env.example to docker/.env and fill in your secrets"
    echo ""
    echo "  cp docker/.env.example docker/.env"
    echo "  vim docker/.env   # set SECRET_KEY, DEEPSEEK_API_KEY, passwords"
    exit 1
fi

# ---- Step 1: Install Docker (if not present) ----
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker "$USER"
    log "Docker installed. You may need to re-login for group permissions."
else
    log "Docker already installed: $(docker --version)"
fi

# ---- Step 2: Configure Docker Hub mirror (Alibaba Cloud) ----
DOCKER_DAEMON="/etc/docker/daemon.json"
if [ ! -f "$DOCKER_DAEMON" ] || ! grep -q "registry-mirrors" "$DOCKER_DAEMON" 2>/dev/null; then
    log "Configuring Alibaba Cloud Docker registry mirror..."
    sudo mkdir -p /etc/docker
    sudo tee "$DOCKER_DAEMON" > /dev/null <<'DAEMON'
{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com",
    "https://docker.m.daocloud.io"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DAEMON
    sudo systemctl restart docker
    log "Docker mirror configured."
fi

# ---- Step 3: Build and start ----
log "Building Docker images..."
cd docker

docker compose build --parallel

log "Starting all services..."
docker compose --env-file .env up -d

log "Waiting for services to be healthy..."
sleep 10

# ---- Step 4: Health check ----
log "Checking service status..."
docker compose ps

echo ""
log "Testing endpoints..."

# Backend
if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
    log "Backend:   http://localhost:8000/docs  ✓"
else
    warn "Backend may still be starting (check: docker compose logs backend)"
fi

# Frontend (via nginx)
if curl -sf http://localhost:80/ > /dev/null 2>&1; then
    log "Frontend:  http://localhost:80/       ✓"
else
    warn "Frontend may still be starting (check: docker compose logs frontend)"
fi

# MinIO
if curl -sf http://localhost:9001/ > /dev/null 2>&1; then
    log "MinIO:     http://localhost:9001/      ✓"
fi

echo ""
log "Deployment complete!"
echo ""
echo "  Frontend:  http://<ECS_PUBLIC_IP>/"
echo "  API Docs:  http://<ECS_PUBLIC_IP>/api/docs"
echo "  MinIO:     http://<ECS_PUBLIC_IP>:9001/"
echo ""
echo "Next steps:"
echo "  1. Open ECS security group ports: 80 (HTTP), 443 (HTTPS)"
echo "  2. (Optional) Point your domain to ECS public IP"
echo "  3. (Optional) Set up HTTPS: apt install certbot && certbot --nginx"
echo "  4. Check logs: docker compose -f docker/docker-compose.yml logs -f"
echo ""
echo "First request to ML tools will be slow (~30s) while the ESM-2 model loads."
echo "Subsequent requests will be fast."
