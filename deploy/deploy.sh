#!/usr/bin/env bash
# Pull the latest code, rebuild, and restart the stack.
# Safe to re-run any time you push new commits.
#   bash /opt/haha/deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/haha}"
# 80/443/8080/8443 are blocked on the competition host; 8000 is open.
HOST_PORT="${HOST_PORT:-8000}"
export HOST_PORT
cd "${APP_DIR}"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

[ -f .env ] || { echo "Missing ${APP_DIR}/.env — copy .env.example and fill it in."; exit 1; }

log "Pulling latest code"
git pull --ff-only

log "Building and starting containers"
docker compose -f deploy/docker-compose.yml up -d --build

log "Waiting for the app to report healthy"
for i in $(seq 1 40); do
    if curl -fsS "http://localhost:${HOST_PORT}/_stcore/health" >/dev/null 2>&1; then
        echo "Healthy after ${i}0s."
        break
    fi
    if [ "$i" -eq 40 ] ; then
        echo "App did not become healthy in time. Recent logs:"
        docker compose -f deploy/docker-compose.yml logs --tail=50
        exit 1
    fi
    sleep 10
done

log "Pruning old images"
docker image prune -f >/dev/null

log "Status"
docker compose -f deploy/docker-compose.yml ps
# api.ipify.org is unreachable from mainland China, so try a domestic
# endpoint before falling back to a placeholder.
PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -fsS --max-time 5 https://myip.ipip.net 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+){3}' | head -1 \
    || echo 'YOUR_SERVER_IP')"
[ -n "${PUBLIC_IP}" ] || PUBLIC_IP='YOUR_SERVER_IP'
echo
echo "Live at: http://${PUBLIC_IP}:${HOST_PORT}/"
echo "Review mode (only if AGENT_REVIEW_MODE_ENABLED=true): http://${PUBLIC_IP}:${HOST_PORT}/?review_mode=1"
