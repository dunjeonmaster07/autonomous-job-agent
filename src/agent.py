"""
Autonomous job search agent.

Runs: search → filter/score → cover letters → (optional) browser apply → track → daily report.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.config import load_profile, get_env, ensure_dirs, try_load_encrypted_env, DATA_DIR
from src.log import get_logger
from src.models import Job
from src.sources import get_sources
from src.scorer import filter_and_rank
from src.cover_letter import generate_cover_letter, save_cover_letter
from src.tracker import ensure_tracker, get_applied_job_ids, record_application
from src.report import build_daily_report, write_daily_report

log = get_logger(__name__)


def _search_source(source, query: str, locations: list[str], limit: int) -> list[Job]:
    """Wrapper for parallel source searching."""
    name = source.__class__.__name__
    try:
        results = source.search(query, locations, limit=limit)
        log.info("[%s] returned %d jobs", name, len(results))
        return results
    except Exception as exc:
        log.error("[%s] FAILED: %s", name, exc)
        return []


def run(
    *,
    max_jobs: int = 30,
    min_score: float | None = None,
    generate_letters: bool = True,
    top_letters: int = 10,
    write_report: bool = True,
    auto_apply: bool = True,
) -> dict[str, Any]:
    try_load_encrypted_env()
    ensure_dirs()
    ensure_tracker()
    profile = load_profile()

    if not profile.get("preferred_roles"):
        log.error("No preferred roles in profile — save your profile first")
        return {
            "jobs_found": 0, "scored_count": 0,
            "cover_letters_generated": 0, "browser_applied": 0,
            "report_path": None,
            "report_preview": "**No roles configured.** Go to Setup and save your profile first.",
        }

    sources = get_sources(profile, get_env)

    list_min = min_score if min_score is not None else 0.2
    auto_apply_min: float = profile.get("min_score_auto_apply", 0.75)

    # 1. Search — parallel across sources
    query = " OR ".join(profile.get("preferred_roles", ["Software Engineer"]))
    locations: list[str] = profile.get("locations", [])
    all_jobs: list[Job] = []
    seen: set[str] = set()

    log.info("Searching %d source(s) in parallel...", len(sources))
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {
            pool.submit(_search_source, src, query, locations, limit=30): src
            for src in sources
        }
        for future in as_completed(futures):
            for job in future.result():
                if job.id not in seen:
                    seen.add(job.id)
                    all_jobs.append(job)

    log.info("Total unique jobs from APIs: %d", len(all_jobs))
    if not all_jobs:
        log.warning("Falling back to MockSource (no real jobs returned)")
        from src.sources.mock import MockSource

        for job in MockSource(profile).search(query, locations, limit=15):
            if job.id not in seen:
                seen.add(job.id)
                all_jobs.append(job)
    all_jobs = all_jobs[:max_jobs]

    # 2. Filter and rank
    applied_ids = get_applied_job_ids()
    new_jobs = [j for j in all_jobs if j.id not in applied_ids]
    scored = filter_and_rank(new_jobs, profile, min_score=list_min)

    # 3. Cover letters for top matches; track as "suggested"
    cover_paths: dict[str, str] = {}
    for s in scored[:top_letters]:
        if s.job.id in applied_ids:
            continue
        if not generate_letters:
            continue
        content = generate_cover_letter(s, profile)
        path = save_cover_letter(s, content)
        cover_paths[s.job.id] = str(path)
        record_application(s, cover_letter_path=str(path), status="suggested")
        applied_ids.add(s.job.id)

    # 4. Auto-apply via browser
    browser_applied = 0
    applied_job_ids: set[str] = set()
    apply_results: dict[str, str] = {}
    if auto_apply and auto_apply_min > 0:
        to_apply = [s for s in scored if s.score >= auto_apply_min]
        if to_apply:
            try:
                from src.browser_apply import apply_via_browser

                headless = os.environ.get("RUN_HEADLESS", "true").lower() in ("1", "true", "yes")
                results = apply_via_browser(to_apply, cover_paths, headless=headless)
                for jid, ok, msg in results:
                    apply_results[jid] = msg
                    if ok:
                        applied_job_ids.add(jid)
                        browser_applied += 1
            except Exception as e:
                log.error("Browser apply failed: %s", e)
                for s in to_apply:
                    apply_results[s.job.id] = str(e)[:150]
    for s in scored:
        if s.job.id not in apply_results:
            apply_results[s.job.id] = f"Below auto-apply threshold ({int(auto_apply_min*100)}%) or not in apply batch"

    # 5. Daily report
    report_content = build_daily_report(
        scored,
        cover_paths,
        applied_job_ids=applied_job_ids,
        apply_results=apply_results,
    )
    report_path = None
    if write_report:
        report_path = write_daily_report(report_content)

    # 6. Send email report
    if write_report and report_content:
        try:
            from src.email_report import send_report_email

            ok, msg = send_report_email(report_content)
            log.info("Email: %s", msg)
        except Exception as e:
            log.error("Email failed: %s", str(e)[:100])

    # 7. Clean up cover letter files
    removed = 0
    for f in DATA_DIR.glob("cover_*.txt"):
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        log.debug("Cleaned up %d cover letter file(s)", removed)

    log.info(
        "Run complete — found=%d, scored=%d, letters=%d, applied=%d",
        len(all_jobs), len(scored), len(cover_paths), browser_applied,
    )

    return {
        "jobs_found": len(all_jobs),
        "scored_count": len(scored),
        "cover_letters_generated": len(cover_paths),
        "browser_applied": browser_applied,
        "report_path": str(report_path) if report_path else None,
        "report_preview": report_content[:2000] + "..." if len(report_content) > 2000 else report_content,
    }


if __name__ == "__main__":
    result = run()
    log.info(
        "Jobs found: %d, Scored: %d, Cover letters: %d, Browser applied: %d",
        result["jobs_found"], result["scored_count"],
        result["cover_letters_generated"], result.get("browser_applied", 0),
    )
    if result["report_path"]:
        log.info("Report: %s", result["report_path"])
