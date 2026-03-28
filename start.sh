#!/bin/bash
# MedGuard AI — Start Script (ports 8100 + 3100 to avoid conflicts)

echo "=== MedGuard AI ==="
echo ""

# Kill any existing MedGuard processes
kill $(lsof -t -i:8100) 2>/dev/null
kill $(lsof -t -i:3100) 2>/dev/null

# Seed database if not already seeded
cd "$(dirname "$0")/backend"
if [ ! -f data/medguard.db ]; then
    echo "[1/3] Seeding demo data..."
    python -m scripts.seed_demo
else
    echo "[1/3] Database already exists (delete data/medguard.db to re-seed)"
fi

# Start backend on port 8100
echo "[2/3] Starting backend on http://localhost:8100 ..."
uvicorn src.main:app --host 0.0.0.0 --port 8100 &
BACKEND_PID=$!
sleep 2

# Start frontend on port 3100
echo "[3/3] Starting frontend on http://localhost:3100 ..."
cd "$(dirname "$0")/frontend"
npx next dev -p 3100 &
FRONTEND_PID=$!
sleep 3

echo ""
echo "=== MedGuard AI Running ==="
echo "  Dashboard:  http://localhost:3100"
echo "  API:        http://localhost:8100"
echo "  Health:     http://localhost:8100/health"
echo "  Swagger:    http://localhost:8100/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Wait and cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
