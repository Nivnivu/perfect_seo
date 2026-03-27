#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " SEO Blog Engine"
echo " ================================"
echo ""

# Free port 8000 if something is already using it
PORT_PID=$(netstat -ano 2>/dev/null | grep "127.0.0.1:8000 " | awk '{print $5}' | head -1)
if [ -n "$PORT_PID" ] && [ "$PORT_PID" != "0" ]; then
  echo " Freeing port 8000 (PID $PORT_PID)..."
  cmd //c "taskkill /PID $PORT_PID /F" 2>/dev/null || true
  sleep 1
fi

# Install API dependencies
echo "[1/3] Installing API dependencies..."
pip install -r api/requirements.txt --quiet

# Install UI dependencies
echo "[2/3] Installing UI dependencies..."
cd ui
npm install --silent
cd ..

# Start both servers
echo "[3/3] Starting servers..."
echo ""
echo "  API  →  http://localhost:8000"
echo "  UI   →  http://localhost:5173"
echo "  Docs →  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$API_PID" "$UI_PID" 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

python -m uvicorn api.main:app --reload --port 8000 &
API_PID=$!

cd ui && npm run dev &
UI_PID=$!

# Auto-open browser after a short delay
sleep 3 && cmd //c "start http://localhost:5173" 2>/dev/null &

wait "$API_PID" "$UI_PID"
