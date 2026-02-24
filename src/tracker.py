"""Track applications in a structured table (CSV) with file locking."""
from __future__ import annotations

import csv
import fcntl
from datetime import datetime, timezone
from pathlib import Path

from src.config import DATA_DIR
from src.log import get_logger
from src.models import ScoredJob

log = get_logger(__name__)

APPLICATIONS_CSV: Path = DATA_DIR / "applications.csv"
HEADERS: list[str] = [
    "job_id", "title", "company", "url", "applied_at",
    "status", "cover_letter_path", "score",
]


def _lock(f, exclusive: bool = True) -> None:
    """Advisory file lock (Unix fcntl)."""
    try:
        op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(f.fileno(), op)
    except (OSError, AttributeError):
        pass


def _unlock(f) -> None:
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (OSError, AttributeError):
        pass


def ensure_tracker() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not APPLICATIONS_CSV.exists():
        with open(APPLICATIONS_CSV, "w", newline="", encoding="utf-8") as f:
            _lock(f)
            csv.writer(f).writerow(HEADERS)
            _unlock(f)
        log.info("Created application tracker → %s", APPLICATIONS_CSV.name)


def record_application(
    scored: ScoredJob,
    cover_letter_path: str | None = None,
    status: str = "suggested",
) -> None:
    ensure_tracker()
    row = {
        "job_id": scored.job.id,
        "title": scored.job.title,
        "company": scored.job.company,
        "url": scored.job.url,
        "applied_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "status": status,
        "cover_letter_path": cover_letter_path or "",
        "score": f"{scored.score:.2f}",
    }
    with open(APPLICATIONS_CSV, "a", newline="", encoding="utf-8") as f:
        _lock(f)
        csv.DictWriter(f, fieldnames=HEADERS).writerow(row)
        _unlock(f)
    log.debug("Tracked: %s @ %s [%s]", scored.job.title, scored.job.company, status)


def get_applications() -> list[dict[str, str]]:
    ensure_tracker()
    with open(APPLICATIONS_CSV, "r", encoding="utf-8") as f:
        _lock(f, exclusive=False)
        rows = list(csv.DictReader(f))
        _unlock(f)
    return rows


def get_applied_job_ids() -> set[str]:
    return {r["job_id"] for r in get_applications()}


def update_status(job_id: str, status: str) -> bool:
    """Update status of an existing application (e.g. suggested -> applied)."""
    ensure_tracker()
    rows = list(get_applications())
    found = False
    for r in rows:
        if r.get("job_id") == job_id:
            r["status"] = status
            found = True
            break
    if not found:
        return False
    with open(APPLICATIONS_CSV, "w", newline="", encoding="utf-8") as f:
        _lock(f)
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(rows)
        _unlock(f)
    log.debug("Updated %s → %s", job_id, status)
    return True
