#!/bin/bash
# ROAS Optimization Engine — One-Click Launcher
# Double-click this file to start the engine in demo mode.

cd "$(dirname "$0")/backend"

echo "============================================"
echo "  ROAS Optimization Engine — Starting..."
echo "============================================"
echo ""

# Kill any existing process on port 8000
echo ">>> Checking for existing processes on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo ">>> Cleared port 8000." || echo ">>> Port 8000 is free."
sleep 1

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ">>> Creating Python virtual environment..."
    python3 -m venv venv
fi

echo ">>> Activating virtual environment..."
source venv/bin/activate

echo ">>> Installing dependencies..."
pip install -q fastapi uvicorn pydantic pydantic-settings apscheduler numpy httpx 2>&1 | tail -3

echo ""
echo "============================================"
echo "  Engine starting on http://localhost:8000"
echo "  Dashboard: http://localhost:8000/docs"
echo "  Press Ctrl+C to stop"
echo "============================================"
echo ""

export DEMO_MODE=true
export PYTHONPATH=.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
