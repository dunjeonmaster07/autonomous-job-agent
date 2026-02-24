#!/usr/bin/env python3
"""
Install cron job for daily run at DAILY_RUN_HOUR_IST (from .env).
Uses TZ=Asia/Kolkata so the run happens at the correct IST hour.
Run once: python setup_cron.py
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Project root
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
hour = int(os.environ.get("DAILY_RUN_HOUR_IST", "11"))
venv_python = ROOT / ".venv" / "bin" / "python"
run_script = ROOT / "src" / "run_daily.py"
entry = f"0 {hour} * * * TZ=Asia/Kolkata cd {ROOT} && {venv_python} {run_script} --once"


def main():
    if not venv_python.exists():
        print("Error: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt")
        return 1
    try:
        out = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        existing = (out.stdout or "").strip() if out.returncode == 0 else ""
        if entry in existing:
            print("Cron entry already present. No change.")
            return 0
        new_crontab = (existing + "\n" + entry).strip() if existing else entry
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            _write_crontab_file(new_crontab)
            print("Could not install crontab automatically. Run manually:")
            print(f"  crontab {ROOT / 'crontab.txt'}")
            return 1
        print(f"Cron installed: daily at {hour}:00 IST")
        print(f"  Entry: {entry}")
        return 0
    except subprocess.TimeoutExpired:
        _write_crontab_file(entry)
        print("Crontab timed out. To install manually, run:")
        print(f"  crontab {ROOT / 'crontab.txt'}")
        return 1
    except FileNotFoundError:
        print("crontab not found. On Windows use Task Scheduler; on Mac/Linux ensure cron is available.")
        _write_crontab_file(entry)
        return 1


def _write_crontab_file(content: str) -> None:
    path = ROOT / "crontab.txt"
    path.write_text(content + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    raise SystemExit(main())
