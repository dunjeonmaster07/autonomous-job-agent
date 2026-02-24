#!/usr/bin/env bash
# ──────────────────────────────────────────────────
#  One-touch launcher for Job Search Agent
#
#  Usage:   ./start.sh
# ──────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "  Installing dependencies..."
pip install -q -r requirements.txt

python3 -c "from src.config import ensure_dirs; ensure_dirs()" 2>/dev/null || true

echo ""
echo "  ✓ Opening Job Search Agent in your browser..."
echo "    Close this terminal or press Ctrl+C to stop."
echo ""

streamlit run app.py
