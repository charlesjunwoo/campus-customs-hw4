#!/usr/bin/env bash
# Start the Campus Customs API (:8000) and web app (:5173). Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x backend/.venv/bin/python ]; then
  echo "Create the backend venv first:"
  echo "  cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi
[ -d frontend/node_modules ] || { echo "Run: cd frontend && npm install"; exit 1; }

# Kill the whole process group on exit so no server is left holding a port.
trap 'kill 0 2>/dev/null || true' EXIT INT TERM

(cd backend && .venv/bin/uvicorn main:app --reload --port 8000) &
(cd frontend && npm run dev -- --port 5173 --strictPort) &

echo "Open http://127.0.0.1:5173  (API docs: http://127.0.0.1:8000/docs)"
wait
