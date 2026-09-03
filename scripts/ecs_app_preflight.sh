#!/usr/bin/env bash
# Read-only ECS app-node preflight for Protein AI Platform.
# Safe to run from Alibaba Cloud Workbench. It does not modify files or services.

set -u

ECS_PUBLIC_IP="${ECS_PUBLIC_IP:-120.27.108.138}"
RDS_HOST="${RDS_HOST:-pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com}"
RDS_PORT="${RDS_PORT:-5432}"
OSS_ENDPOINT="${OSS_ENDPOINT:-oss-cn-beijing.aliyuncs.com}"
APP_PORT="${APP_PORT:-4200}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/protein-ai-platform}"

section() {
  printf '\n== %s ==\n' "$*"
}

run() {
  printf '$ %s\n' "$*"
  "$@" 2>&1 || true
}

check_tcp() {
  local host="$1"
  local port="$2"
  if command -v nc >/dev/null 2>&1; then
    nc -vz -w 5 "$host" "$port" 2>&1 || true
  elif command -v timeout >/dev/null 2>&1; then
    timeout 5 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" >/dev/null 2>&1 \
      && echo "tcp ${host}:${port} ok" \
      || echo "tcp ${host}:${port} failed"
  else
    echo "skip tcp check for ${host}:${port}; nc/timeout unavailable"
  fi
}

section "identity"
run date
run hostname
run whoami
run id

section "os"
run uname -a
if [ -f /etc/os-release ]; then
  run cat /etc/os-release
else
  run cat /etc/issue
fi

section "network"
run ip addr
run ip route
run hostname -I
run getent hosts "$RDS_HOST"
run getent hosts "$OSS_ENDPOINT"
check_tcp "$RDS_HOST" "$RDS_PORT"
check_tcp "$OSS_ENDPOINT" 443

section "ports"
if command -v ss >/dev/null 2>&1; then
  run ss -lntp
else
  run netstat -lntp
fi
check_tcp 127.0.0.1 22
check_tcp 127.0.0.1 80
check_tcp 127.0.0.1 443
check_tcp 127.0.0.1 "$APP_PORT"

section "firewall"
run systemctl is-active firewalld
run firewall-cmd --list-all
run ufw status
run iptables -S

section "disk and memory"
run df -h
run free -h
run du -sh "$DEPLOY_ROOT"

section "runtime"
run command -v git
run git --version
run command -v curl
run curl --version
run command -v tar
run tar --version
run command -v rsync
run rsync --version
run command -v docker
run docker --version
run docker compose version

section "docker state"
run systemctl is-active docker
run systemctl status docker --no-pager
run docker info
run docker ps

section "deploy root"
run ls -la "$DEPLOY_ROOT"
run ls -la "$DEPLOY_ROOT/current"

section "summary hints"
echo "If RDS tcp check fails, confirm RDS public endpoint/CEN/VPC and whitelist for ECS."
echo "If docker is missing, run scripts/ecs_app_prepare.sh from Workbench."
echo "If 80/443/${APP_PORT} are not reachable externally, check ECS security group and local firewall."

