#!/usr/bin/env bash
# ECS app-node preparation for Protein AI Platform.
# Intended for Alibaba Cloud Workbench on the ECS instance.
# It installs basic tooling and Docker when missing, creates deploy directories,
# and does not start the application stack.

set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/protein-ai-platform}"
DEPLOY_USER="${DEPLOY_USER:-proteinai}"
INSTALL_DOCKER="${INSTALL_DOCKER:-1}"
CREATE_DEPLOY_USER="${CREATE_DEPLOY_USER:-1}"

log() {
  printf '[prep] %s\n' "$*"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

detect_os() {
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-unknown}"
  else
    echo "unknown"
  fi
}

install_base_packages() {
  local os_id="$1"
  case "$os_id" in
    ubuntu|debian)
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg lsb-release git tar rsync make netcat-openbsd
      ;;
    anolis|alinux|almalinux|rocky|rhel|centos)
      yum install -y ca-certificates curl gnupg git tar rsync make nc
      ;;
    *)
      log "Unknown OS '${os_id}', skip package installation. Install curl/git/tar/rsync/make/nc manually if missing."
      ;;
  esac
}

install_docker_if_needed() {
  local os_id="$1"
  if have docker && docker compose version >/dev/null 2>&1; then
    log "Docker and compose plugin already installed."
    return
  fi
  if [ "$INSTALL_DOCKER" != "1" ]; then
    log "INSTALL_DOCKER != 1, skip Docker installation."
    return
  fi

  case "$os_id" in
    ubuntu|debian)
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL "https://download.docker.com/linux/${os_id}/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      chmod a+r /etc/apt/keyrings/docker.gpg
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${os_id} $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      ;;
    anolis|alinux|almalinux|rocky|rhel|centos)
      if ! have yum-config-manager; then
        yum install -y yum-utils || true
      fi
      if have yum-config-manager; then
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
      fi
      yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      ;;
    *)
      log "Unknown OS '${os_id}', skip Docker installation."
      ;;
  esac

  systemctl enable --now docker
}

create_deploy_user() {
  if [ "$CREATE_DEPLOY_USER" != "1" ]; then
    log "CREATE_DEPLOY_USER != 1, skip deploy user creation."
    return
  fi
  if id "$DEPLOY_USER" >/dev/null 2>&1; then
    log "Deploy user ${DEPLOY_USER} already exists."
  else
    useradd -m -s /bin/bash "$DEPLOY_USER"
    log "Created deploy user ${DEPLOY_USER}."
  fi
  if getent group docker >/dev/null 2>&1; then
    usermod -aG docker "$DEPLOY_USER" || true
  fi
}

prepare_dirs() {
  mkdir -p "$DEPLOY_ROOT/releases" "$DEPLOY_ROOT/shared" "$DEPLOY_ROOT/shared/secrets" "$DEPLOY_ROOT/backups" "$DEPLOY_ROOT/deploy_data"
  chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "$DEPLOY_ROOT" 2>/dev/null || true
  chmod 750 "$DEPLOY_ROOT" "$DEPLOY_ROOT/releases" "$DEPLOY_ROOT/shared" "$DEPLOY_ROOT/backups" "$DEPLOY_ROOT/deploy_data" || true
  chmod 700 "$DEPLOY_ROOT/shared/secrets" || true
}

prepare_oidc_keys() {
  local private_key="$DEPLOY_ROOT/shared/secrets/oidc_private_key.pem"
  local public_key="$DEPLOY_ROOT/shared/secrets/oidc_public_key.pem"
  if [ -s "$private_key" ] && [ -s "$public_key" ]; then
    log "OIDC signing keys already exist under shared/secrets."
    return
  fi
  if ! have openssl; then
    log "openssl not found; skip OIDC key generation. Install openssl or place keys under $DEPLOY_ROOT/shared/secrets before starting."
    return
  fi
  umask 077
  openssl genrsa -out "$private_key" 2048 >/dev/null 2>&1
  openssl rsa -in "$private_key" -pubout -out "$public_key" >/dev/null 2>&1
  # The host directory is root-only; the file itself must be readable by the
  # non-root container user after Compose bind-mounts it as a file secret.
  chmod 644 "$private_key"
  chmod 644 "$public_key"
  log "Generated OIDC signing keys under $DEPLOY_ROOT/shared/secrets."
}

main() {
  if [ "$(id -u)" != "0" ]; then
    echo "Run as root from Workbench." >&2
    exit 1
  fi

  local os_id
  os_id="$(detect_os)"
  log "Detected OS: ${os_id}"

  install_base_packages "$os_id"
  install_docker_if_needed "$os_id"
  create_deploy_user
  prepare_dirs
  prepare_oidc_keys

  log "Versions:"
  docker --version || true
  docker compose version || true
  git --version || true
  curl --version | head -1 || true

  log "Prepared deploy root: ${DEPLOY_ROOT}"
  ls -la "$DEPLOY_ROOT"
  log "Done. This script did not start the application."
}

main "$@"
