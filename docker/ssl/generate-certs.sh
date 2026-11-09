#!/usr/bin/env bash
# =============================================================================
# generate-certs.sh — Self-signed TLS certificate generator
# =============================================================================
# Usage:
#   ./generate-certs.sh [DOMAIN]
#
# Generates a self-signed certificate valid for 365 days.
# For production, replace with Let's Encrypt certs (see notes below).
# =============================================================================
set -euo pipefail

DOMAIN="${1:-8.139.255.194}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_FILE="${SCRIPT_DIR}/server.crt"
KEY_FILE="${SCRIPT_DIR}/server.key"

echo "==> Generating self-signed TLS certificate for: ${DOMAIN}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "/C=CN/ST=Beijing/O=Kevibotech/CN=${DOMAIN}" \
    -addext "subjectAltName=IP:${DOMAIN},DNS:localhost"

chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo "==> Certificate generated:"
echo "    Cert: ${CERT_FILE}"
echo "    Key:  ${KEY_FILE}"
echo ""
echo "==> For Let's Encrypt (production), run on the server:"
echo "    1. Install certbot: apt install certbot"
echo "    2. Stop nginx: docker compose stop nginx"
echo "    3. certbot certonly --standalone -d ${DOMAIN}"
echo "    4. Copy certs: cp /etc/letsencrypt/live/${DOMAIN}/{fullchain.pem,privkey.pem} ${SCRIPT_DIR}/"
echo "    5. Update nginx.conf to use fullchain.pem and privkey.pem"
echo "    6. Restart: docker compose start nginx"
