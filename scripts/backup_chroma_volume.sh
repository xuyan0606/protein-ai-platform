#!/usr/bin/env bash
# Archive the Chroma data directory from an existing container without
# requiring an additional image on the production host.

set -euo pipefail

CONTAINER_ID="${1:-}"
BACKUP_DIR="${2:-}"

if [ -z "$CONTAINER_ID" ] || [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <container-id> <backup-directory>" >&2
    exit 2
fi

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$BACKUP_DIR/chroma-${timestamp}-${CONTAINER_ID:0:12}.tar.gz"
tmp_archive="${archive}.partial"
checksum="${archive}.sha256"
receipt="${archive%.tar.gz}.json"

image="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER_ID")"
container_name="$(docker inspect --format '{{.Name}}' "$CONTAINER_ID" | sed 's#^/##')"
volume_identity="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/chroma/chroma"}}{{.Name}}|{{.Source}}{{end}}{{end}}' "$CONTAINER_ID")"
volume_name="${volume_identity%%|*}"
volume_source="${volume_identity#*|}"
[ -n "$volume_identity" ] || { echo "Chroma volume mount was not found" >&2; exit 1; }

rm -f "$tmp_archive" "$archive" "$checksum" "$receipt"
docker cp "$CONTAINER_ID:/chroma/chroma" - | gzip -n > "$tmp_archive"
test -s "$tmp_archive"
tar -tzf "$tmp_archive" >/dev/null
mv "$tmp_archive" "$archive"

digest="$(sha256sum "$archive" | awk '{print $1}')"
printf '%s  %s\n' "$digest" "$(basename "$archive")" > "$checksum"

ARCHIVE_NAME="$(basename "$archive")" \
ARCHIVE_SHA256="$digest" \
ARCHIVE_SIZE_BYTES="$(stat -c '%s' "$archive" 2>/dev/null || stat -f '%z' "$archive")" \
CONTAINER_ID="$CONTAINER_ID" \
CONTAINER_NAME="$container_name" \
IMAGE="$image" \
VOLUME_NAME="$volume_name" \
VOLUME_SOURCE="$volume_source" \
CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
python3 - "$receipt" <<'PY'
import json
import os
import sys

payload = {
    "created_at": os.environ["CREATED_AT"],
    "container_id": os.environ["CONTAINER_ID"],
    "container_name": os.environ["CONTAINER_NAME"],
    "image": os.environ["IMAGE"],
    "volume_name": os.environ["VOLUME_NAME"],
    "volume_source": os.environ["VOLUME_SOURCE"],
    "archive": os.environ["ARCHIVE_NAME"],
    "archive_sha256": os.environ["ARCHIVE_SHA256"],
    "archive_size_bytes": int(os.environ["ARCHIVE_SIZE_BYTES"]),
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

chmod 600 "$archive" "$checksum" "$receipt"
printf '%s\n' "$archive"
