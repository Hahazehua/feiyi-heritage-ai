#!/usr/bin/env bash
# Pull the latest code, rebuild, and restart the stack.
# Safe to re-run any time you push new commits.
#   bash /opt/haha/deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/haha}"
cd "${APP_DIR}"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

[ -f .env ] || { echo "Missing ${APP_DIR}/.env — copy .env.example and fill it in."; exit 1; }

log "Pulling latest code"
git pull --ff-only

log "Building and starting containers"
docker compose -f deploy/docker-compose.yml up -d --build

log "Waiting for the app to report healthy"
for i in $(seq 1 40); do
    if curl -fsS http://localhost/_stcore/health >/dev/null 2>&1; then
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
PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo 'YOUR_SERVER_IP')"
echo
echo "Live at: http://${PUBLIC_IP}/"
echo "Review mode (only if AGENT_REVIEW_MODE_ENABLED=true): http://${PUBLIC_IP}/?review_mode=1"
