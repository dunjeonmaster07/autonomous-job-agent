#!/usr/bin/env python3
"""Entry point to run the job search agent."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.log import get_logger
from src.config import PROFILE_PATH

log = get_logger(__name__)


def _check_setup() -> bool:
    """Return True if first-run setup is needed."""
    if not PROFILE_PATH.exists():
        print()
        print("  No profile found. Run the setup wizard first:")
        print("    python onboard.py")
        print()
        return True
    return False


if __name__ == "__main__":
    if _check_setup():
        sys.exit(1)

    from src.agent import run

    result = run(
        max_jobs=30,
        min_score=0.2,
        generate_letters=True,
        top_letters=10,
        write_report=True,
        auto_apply=True,
    )
    log.info("Run complete.")
    log.info("  Jobs found: %d", result["jobs_found"])
    log.info("  Scored (above threshold): %d", result["scored_count"])
    log.info("  Cover letters generated: %d", result["cover_letters_generated"])
    log.info("  Browser applied: %d", result.get("browser_applied", 0))
    if result["report_path"]:
        log.info("  Report: %s", result["report_path"])
