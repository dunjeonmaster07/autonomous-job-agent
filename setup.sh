#!/usr/bin/env bash
# Install dependencies only (no run). Use when you want to set up without triggering a search.
set -e
cd "$(dirname "$0")"

echo "Setting up Autonomous Job Search Agent..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install chromium 2>/dev/null || echo "(Playwright chromium install skipped)"
echo ""
echo "Setup complete. Next steps:"
echo "  Option A (web UI):  streamlit run app.py"
echo "  Option B (CLI):     python onboard.py"
