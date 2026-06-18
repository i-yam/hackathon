#!/usr/bin/env bash
# run_demo.sh — starts the A3 Bau-Fenster Planer API + static frontend server
# Run with:  bash run_demo.sh   (Git Bash on Windows, or any POSIX shell)
set -e
cd "$(dirname "$0")"

# ── activate venv ─────────────────────────────────────────────────────────────
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate          # Windows (Git Bash)
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate              # Linux / macOS
else
  echo "ERROR: virtualenv not found at .venv/"; exit 1
fi

# ── print URLs ────────────────────────────────────────────────────────────────
FRONTEND_FILE="A3%20Bau-Fenster%20Planer.dc.html"
echo ""
echo "  A3 Bau-Fenster Planer — Demo"
echo "  ============================================="
echo "  Backend API:  http://localhost:8000/docs"
echo "  Frontend:     http://localhost:3000/${FRONTEND_FILE}"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# ── kill background jobs on exit ──────────────────────────────────────────────
cleanup() { kill "$(jobs -p)" 2>/dev/null; }
trap cleanup INT TERM EXIT

# ── start servers ─────────────────────────────────────────────────────────────
# API — loaded from old/ as a package so both sys.path entries in api.py fire
python -m uvicorn old.api:app --port 8000 --reload &

# Static file server — serves old/ so support.js + dc components are co-located
python -m http.server 3000 --directory old &

wait
