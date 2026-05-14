#!/bin/bash
# ─── ROAS Engine: Replace backend with test-passing version ───
# Run this from the roas-engine folder:
#   cd ~/Documents/MSR/BettieAI/projects/roas-engine
#   bash swap_backend.sh

set -e

echo "Replacing backend with test-verified version..."

# Backup old backend
if [ -d "backend-old" ]; then
    rm -rf backend-old
fi
mv backend backend-old

# Move fixed backend into place
mv backend-fixed backend

# Clean up nested duplicates and cache files
rm -rf backend/backend 2>/dev/null
find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find backend -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null
find backend -name "pytest-cache-*" -type d -exec rm -rf {} + 2>/dev/null

echo ""
echo "Done! To run the tests:"
echo "  cd backend"
echo "  python3 -m venv venv"
echo "  source venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  pip install -r requirements-test.txt"
echo "  python -m pytest tests/ -v --tb=short"
echo ""
echo "Old backend backed up to: backend-old/"
