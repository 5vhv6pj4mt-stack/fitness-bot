#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/oracle/fitness-bot"
WEBAPP_DIR="$REPO_DIR/webapp"

echo "=== Deploy started: $(date) ==="

cd "$REPO_DIR"
git pull --ff-only

cd "$WEBAPP_DIR"
npm ci --prefer-offline --ignore-scripts
npm run build

sudo systemctl restart fitness-webapp-api

for i in 1 2 3 4 5; do
    if curl -sf http://127.0.0.1:8001/api/health > /dev/null 2>&1; then
        echo "API is up."
        break
    fi
    echo "Waiting for API... ($i/5)"
    sleep 2
done

echo "=== Deploy finished: $(date) ==="
