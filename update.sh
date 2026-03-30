#!/usr/bin/env bash
# Pull latest code and refresh dependencies — servers keep running.
# uvicorn --reload auto-detects Python changes; Vite HMR handles the UI.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " SEO Blog Engine — Update"
echo " ================================"
echo ""

echo "[1/3] Pulling latest code..."
git pull

echo "[2/3] Updating API dependencies..."
pip install -r api/requirements.txt --quiet

echo "[3/3] Updating UI dependencies..."
cd ui && npm install --silent && cd ..

echo ""
echo " Done. uvicorn will auto-reload changed Python files."
echo " The UI hot-reloads automatically via Vite HMR."
echo " No server restart needed."
echo ""
