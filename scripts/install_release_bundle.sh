#!/usr/bin/env bash
# Install a Protein AI Platform source bundle into a versioned release.
# This script does not start containers.

set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/protein-ai-platform}"
BUNDLE_PATH="${1:-}"

log() {
  printf '[install-release] %s\n' "$*"
}

fail() {
  printf '[install-release] ERROR: %s\n' "$*" >&2
  exit 1
}

if [ -z "$BUNDLE_PATH" ]; then
  fail "Usage: DEPLOY_ROOT=/opt/protein-ai-platform $0 /path/to/protein-ai-platform-<release>.tar.gz"
fi

BUNDLE_PATH="$(cd "$(dirname "$BUNDLE_PATH")" && pwd)/$(basename "$BUNDLE_PATH")"
[ -f "$BUNDLE_PATH" ] || fail "Bundle not found: $BUNDLE_PATH"

CHECKSUM_PATH="${BUNDLE_PATH}.sha256"
[ -f "$CHECKSUM_PATH" ] || fail "Checksum not found: $CHECKSUM_PATH"

mkdir -p "$DEPLOY_ROOT/releases"
cd "$(dirname "$BUNDLE_PATH")"
sha256sum -c "$(basename "$CHECKSUM_PATH")"

bundle_name="$(basename "$BUNDLE_PATH")"
release_id="${bundle_name%.tar.gz}"
release_id="${release_id#protein-ai-platform-}"
release_dir="$DEPLOY_ROOT/releases/$release_id"
project_dir="$release_dir/protein-ai-platform"

root_count="$(tar -tzf "$BUNDLE_PATH" | awk -F/ 'NF {print $1}' | sort -u | wc -l | tr -d ' ')"
root_name="$(tar -tzf "$BUNDLE_PATH" | awk -F/ 'NF {print $1}' | sort -u)"
[ "$root_count" = "1" ] || fail "Bundle must contain one top-level directory, found: $root_name"
[ "$root_name" = "protein-ai-platform" ] || fail "Unexpected bundle top-level directory: $root_name"

old_current=""
if [ -e "$DEPLOY_ROOT/current" ] || [ -L "$DEPLOY_ROOT/current" ]; then
  old_current="$(readlink -f "$DEPLOY_ROOT/current" 2>/dev/null || true)"
fi

rm -rf "$release_dir"
mkdir -p "$release_dir"
tar -xzf "$BUNDLE_PATH" -C "$release_dir"
[ -f "$project_dir/docker/docker-compose.aliyun-app.yml" ] || fail "Unpacked project docker compose not found."

if [ -n "$old_current" ] && [ -d "$old_current" ]; then
  for file in docker/.env docker/.env.deploy-data docker/.env.aliyun.app docker/.env.aliyun.gpu backend/.env.deploy-data; do
    if [ -f "$old_current/$file" ]; then
      mkdir -p "$project_dir/$(dirname "$file")"
      cp -p "$old_current/$file" "$project_dir/$file"
    fi
  done
  if [ -d "$old_current/docker/ssl" ]; then
    mkdir -p "$project_dir/docker/ssl"
    cp -a "$old_current/docker/ssl/." "$project_dir/docker/ssl/"
  fi
fi

ln -sfn "$project_dir" "$DEPLOY_ROOT/current"
log "current -> $(readlink -f "$DEPLOY_ROOT/current")"

if [ -f "$project_dir/docker/.env" ] && [ -f "$project_dir/docker/.env.deploy-data" ] && [ -f "$project_dir/docker/.env.aliyun.app" ]; then
  (
    cd "$project_dir/docker"
    docker compose --env-file .env --env-file .env.deploy-data --env-file .env.aliyun.app -f docker-compose.aliyun-app.yml config --quiet
  )
  log "aliyun app compose config ok"
else
  log "env files are not complete; skipped compose config"
fi

log "installed release $release_id"
