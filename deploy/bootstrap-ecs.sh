#!/usr/bin/env bash
# Prepare a fresh ECS host for the HAHA app. Run ONCE, as root, on the server.
#   bash bootstrap-ecs.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Hahazehua/feiyi-heritage-ai.git}"
APP_DIR="${APP_DIR:-/opt/haha}"
# Wave 4 lives on a feature branch, not on main.
BRANCH="${BRANCH:-feat/latest-complete-mvp}"
# 80/443/8080/8443 are blocked on the competition host; 8000 is open.
HOST_PORT="${HOST_PORT:-8000}"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "Run this as root."; exit 1; }

log "1/6 Updating base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl git ufw

log "2/6 Installing Docker Engine + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker --version
docker compose version

log "3/6 Configuring firewall (allow 22, ${HOST_PORT}; deny everything else inbound)"
ufw allow 22/tcp
ufw allow "${HOST_PORT}/tcp"
ufw --force enable
ufw status verbose

log "4/6 Cloning repository (${BRANCH}) into ${APP_DIR}"
if [ -d "${APP_DIR}/.git" ]; then
    git -C "${APP_DIR}" fetch origin "${BRANCH}"
    git -C "${APP_DIR}" checkout "${BRANCH}"
    git -C "${APP_DIR}" pull --ff-only
else
    git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
fi

log "5/6 Creating .env"
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"
    echo "Created ${APP_DIR}/.env from the example."
    echo "EDIT IT NOW and put your real DEEPSEEK_API_KEY in before deploying:"
    echo "    nano ${APP_DIR}/.env"
else
    echo ".env already exists, leaving it untouched."
fi

log "6/6 Bootstrap complete"
cat <<EOF

Next:
  1. nano ${APP_DIR}/.env          # set DEEPSEEK_API_KEY
  2. bash ${APP_DIR}/deploy/deploy.sh

Also make sure your cloud console security group allows inbound TCP ${HOST_PORT}
and 22. The host firewall alone is not enough on most ECS providers.
EOF
