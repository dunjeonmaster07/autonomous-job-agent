"""
Run agent daily at 11 AM IST and send email report to TO_EMAIL.

Usage:
  - Cron (recommended): run at 11 AM IST every day. Install with: python setup_cron.py
      Then: 0 11 * * * TZ=Asia/Kolkata cd /path/to/project && .venv/bin/python src/run_daily.py --once
  - Or run this script in background: python src/run_daily.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _project_root)

from dotenv import load_dotenv

load_dotenv(os.path.join(_project_root, ".env"))

from src.agent import run
from src.config import get_env
from src.email_report import send_report_email
from src.log import get_logger

log = get_logger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore[assignment,misc]

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None
TARGET_HOUR_IST = int(os.environ.get("DAILY_RUN_HOUR_IST", "11"))
TARGET_MINUTE = 0


def run_once_and_email() -> dict:
    result = run(
        max_jobs=50,
        min_score=0.2,
        generate_letters=True,
        top_letters=10,
        write_report=True,
        auto_apply=True,
    )
    body = result.get("report_preview", "") or ""
    body += f"\n\n---\nSummary: Jobs found: {result.get('jobs_found', 0)} | Scored (\u226575%): {result.get('scored_count', 0)} | Applied via browser: {result.get('browser_applied', 0)}"
    to = get_env("TO_EMAIL")
    if not to:
        log.warning("TO_EMAIL not set in .env — skipping email")
        return result
    ok, msg = send_report_email(body, to_email=to)
    if not ok:
        log.error("Email failed: %s", msg)
    return result


def next_run_ist() -> datetime:
    if IST is None:
        return datetime.now() + timedelta(hours=24)
    now = datetime.now(IST)
    target = now.replace(hour=TARGET_HOUR_IST, minute=TARGET_MINUTE, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return target


def main() -> None:
    log.info("Scheduler: run daily at %d:%02d IST", TARGET_HOUR_IST, TARGET_MINUTE)
    while True:
        if IST is None:
            time.sleep(86400)
            log.info("Running agent...")
            run_once_and_email()
            continue
        target = next_run_ist()
        now = datetime.now(IST)
        wait_secs = (target - now).total_seconds()
        if wait_secs < 0:
            wait_secs = 86400 + wait_secs
        log.info("Next run at %s IST (in %.1f hours)", target, wait_secs / 3600)
        time.sleep(min(wait_secs, 86400))
        now = datetime.now(IST)
        if now.hour == TARGET_HOUR_IST and now.minute < 30:
            log.info("Running agent...")
            run_once_and_email()
            log.info("Done. Next run tomorrow.")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once_and_email()
        sys.exit(0)
    main()
