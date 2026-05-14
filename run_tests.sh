#!/bin/bash
# ─── ROAS Engine Test Runner ───
# Run this from the project root: ./run_tests.sh

set -e

echo "=================================="
echo "  ROAS Engine — Test Suite"
echo "=================================="
echo ""

cd "$(dirname "$0")/backend"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt
pip install -q -r requirements-test.txt

echo ""
echo "──────────────────────────────────"
echo "  Running Tests"
echo "──────────────────────────────────"
echo ""

# Run all tests with coverage
python -m pytest tests/ \
    -v \
    --tb=short \
    --cov=app/optimizers \
    --cov=app/models \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    "$@"

echo ""
echo "──────────────────────────────────"
echo "  Tests Complete!"
echo "──────────────────────────────────"
echo ""
echo "Coverage report: backend/htmlcov/index.html"
