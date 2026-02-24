#!/usr/bin/env bash
# One-command bootstrap: install deps, set up daily cron, run agent once.
# Usage: ./run_autonomous.sh
set -e
cd "$(dirname "$0")"

echo "=== Autonomous Job Search Agent — Setup & First Run ==="
echo ""

# 1. Virtual environment
if [ ! -d ".venv" ]; then
  echo "[1/4] Creating virtual environment..."
  python3 -m venv .venv
else
  echo "[1/4] Virtual environment found."
fi

# 2. Dependencies
echo "[2/4] Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install chromium 2>/dev/null || echo "  (Playwright chromium install skipped — run manually if needed)"

# 3. Cron
echo "[3/4] Setting up daily schedule..."
.venv/bin/python setup_cron.py || echo "  (Cron setup skipped — see setup_cron.py for manual install)"

# 4. Run
echo "[4/4] Running agent..."
echo ""
.venv/bin/python run_agent.py
echo ""
echo "Done! The agent will now run daily at the hour set in .env (DAILY_RUN_HOUR_IST)."
echo "Reports are saved to reports/ and emailed to TO_EMAIL."
