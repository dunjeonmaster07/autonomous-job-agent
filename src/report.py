"""Generate daily report of top job matches."""
from __future__ import annotations

from datetime import datetime, timezone

from src.config import REPORTS_DIR
from src.log import get_logger
from src.models import ScoredJob
from src.tracker import get_applications

log = get_logger(__name__)

_APPLY_FAIL_REASONS: dict[str, str] = {
    "executable doesn't exist": "Browser not installed — run `playwright install chromium`",
    "browsertype.launch": "Browser not installed — run `playwright install chromium`",
    "playwright not installed": "Playwright missing — `pip install playwright && playwright install chromium`",
    "no resume": "No resume found — add PDF/DOCX to `resume/` folder",
    "no credentials": "Credentials missing — set in `.env`",
    "timeout": "Page timed out",
    "no apply button": "No Apply button detected on page",
    "aggregator": "Aggregator site — apply via direct link",
    "below auto-apply": "Score below auto-apply threshold",
}


def _short_reason(reason: str) -> str:
    low = reason.lower()
    for key, msg in _APPLY_FAIL_REASONS.items():
        if key in low:
            return msg
    return reason[:80] + ("\u2026" if len(reason) > 80 else "")


def _short_url_label(url: str) -> str:
    try:
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        host = host.replace("www.", "")
        parts = host.split(".")
        return parts[0].capitalize() if parts else "Link"
    except Exception:
        return "Link"


def _dedupe_apps(apps: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for a in reversed(apps):
        k = (a.get("title", ""), a.get("company", ""))
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out


def build_daily_report(
    scored_jobs: list[ScoredJob],
    cover_letter_paths: dict[str, str],
    *,
    applied_job_ids: set[str] | None = None,
    apply_results: dict[str, str] | None = None,
) -> str:
    applied_job_ids = applied_job_ids or set()
    apply_results = apply_results or {}
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [f"# Job Search Report \u2014 {date}", ""]

    top = scored_jobs[:15]
    applied_count = sum(1 for s in top if s.job.id in applied_job_ids)
    pending_count = len(top) - applied_count

    lines.append(f"**{len(scored_jobs)}** jobs scored | **{applied_count}** auto-applied | **{pending_count}** pending")
    lines.append("")

    any_failed = False
    if top:
        lines.append("## Top Matches")
        lines.append("")
        for s in top:
            jid = s.job.id
            applied = jid in applied_job_ids
            if not applied:
                any_failed = True
            status = "Applied" if applied else "Pending"
            badge = "\u2705" if applied else "\U0001f517"
            reason = _short_reason(apply_results.get(jid, "")) if not applied and apply_results.get(jid) else ""
            url = s.job.url
            link_label = _short_url_label(url)

            lines.append(f"### {badge} {s.job.title} @ {s.job.company}")
            lines.append(f"- **Score:** {s.score:.0%} \u2014 {status}")
            lines.append(f"- **Location:** {s.job.location}")
            lines.append(f"- **Why:** {', '.join(s.match_reasons[:4])}")
            lines.append(f"- **Keywords:** {', '.join(s.keyword_suggestions[:4])}")
            if url:
                lines.append(f"- **Apply:** [{link_label}]({url})")
            if reason:
                lines.append(f"- _Note: {reason}_")
            lines.append("")

    if top:
        lines.append("---")
        lines.append("")
        lines.append("## Quick Reference")
        lines.append("")
        lines.append("| # | Role | Company | Location | Score | Status | Apply |")
        lines.append("|--:|------|---------|----------|------:|--------|-------|")
        for i, s in enumerate(top, 1):
            title = s.job.title[:40] + ("\u2026" if len(s.job.title) > 40 else "")
            company = s.job.company[:22] + ("\u2026" if len(s.job.company) > 22 else "")
            loc = s.job.location.split(",")[0][:18]
            status = "Applied" if s.job.id in applied_job_ids else "Pending"
            link = f"[{_short_url_label(s.job.url)}]({s.job.url})" if s.job.url else "\u2014"
            lines.append(f"| {i} | {title} | {company} | {loc} | {s.score:.0%} | {status} | {link} |")
        lines.append("")

    all_apps = get_applications()
    if all_apps:
        lines.append("---")
        lines.append("")
        lines.append("## Application History")
        lines.append("")
        for a in _dedupe_apps(all_apps[-15:])[:10]:
            title, company = a.get("title", ""), a.get("company", "")
            url, status, at = a.get("url", ""), a.get("status", ""), a.get("applied_at", "")
            link = f"[Apply]({url})" if url else ""
            lines.append(f"- **{title}** @ {company} \u2014 _{status}_ \u2014 {at} {link}")
        lines.append("")

    if any_failed:
        lines.append("---")
        lines.append("")
        lines.append("## Troubleshooting")
        lines.append("")
        lines.append("If the agent couldn\u2019t apply to some jobs:")
        lines.append("")
        lines.append("1. **Browser:** `playwright install chromium` in the project folder")
        lines.append("2. **Resume:** Place a PDF or DOCX in `resume/`")
        lines.append("3. **Credentials:** Set `LINKEDIN_EMAIL`, `NAUKRI_EMAIL`, `APPLY_EMAIL` in `.env`")
        lines.append("4. **Manual:** Use the Apply links above for jobs the agent couldn\u2019t reach")
        lines.append("")

    log.info("Built daily report: %d jobs, %d applied", len(scored_jobs), applied_count)
    return "\n".join(lines)


def write_daily_report(content: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"daily_{date}.md"
    path.write_text(content, encoding="utf-8")
    log.info("Report written → %s", path)
    return path
