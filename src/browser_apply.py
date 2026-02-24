"""
Browser automation to submit applications (hybrid mode).
Uses Playwright to open job URLs, detect the platform (LinkedIn, Naukri, Workday,
Greenhouse, Lever, Indeed, aggregator, or generic), and attempt the apply flow.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from src.config import get_resume_path, get_env, load_profile
from src.log import get_logger
from src.models import ScoredJob
from src.tracker import update_status

log = get_logger(__name__)


def _visible(locator) -> bool:
    """Safe visibility check that never throws."""
    try:
        return locator.count() > 0 and locator.first.is_visible(timeout=2000)
    except Exception:
        return False


def _click_first_visible(page, selectors: list[str], *, timeout: int = 3000) -> bool:
    """Try clicking the first visible element matching any selector."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout):
                loc.click()
                return True
        except Exception:
            continue
    return False


def _detect_platform(url: str) -> str:
    """Classify the URL into a known platform type."""
    u = url.lower()
    if "linkedin.com" in u:
        return "linkedin"
    if "naukri.com" in u:
        return "naukri"
    if "myworkdayjobs.com" in u or "workday.com" in u or "wd1." in u or "wd3." in u or "wd5." in u:
        return "workday"
    if "greenhouse.io" in u or "boards.greenhouse" in u:
        return "greenhouse"
    if "lever.co" in u or "jobs.lever" in u:
        return "lever"
    if "indeed.com" in u:
        return "indeed"
    if any(agg in u for agg in ["simplyhired", "talent.com", "jobrapido", "bebee.com",
                                  "builtin.com", "remote.co", "talentify"]):
        return "aggregator"
    return "generic"


def apply_via_browser(
    scored_jobs: list[ScoredJob],
    cover_letter_paths: dict[str, str],
    *,
    headless: bool = False,
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    resume_path = get_resume_path()
    linkedin_user = get_env("LINKEDIN_EMAIL")
    linkedin_pass = get_env("LINKEDIN_PASSWORD")
    naukri_user = get_env("NAUKRI_EMAIL")
    naukri_pass = get_env("NAUKRI_PASSWORD")
    apply_email = get_env("APPLY_EMAIL")
    apply_pass = get_env("APPLY_PASSWORD")

    try:
        _pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if _pw and ("sandbox" in _pw or "cursor" in _pw.lower() or not Path(_pw).exists()):
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        from playwright.sync_api import sync_playwright
    except ImportError:
        for s in scored_jobs:
            results.append((s.job.id, False, "Playwright not installed"))
        return results

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--incognito"])
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        for scored in scored_jobs:
            job_id = scored.job.id
            url = scored.job.url
            if not url:
                results.append((job_id, False, "No URL for this job"))
                continue

            cover_path = cover_letter_paths.get(job_id)
            cover_text = ""
            if cover_path and Path(cover_path).exists():
                cover_text = Path(cover_path).read_text(encoding="utf-8", errors="ignore")

            platform = _detect_platform(url)
            log.info("Applying: %s @ %s → %s", scored.job.title, scored.job.company, platform)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(2)

                if platform == "linkedin":
                    ok, msg = _try_linkedin(page, linkedin_user, linkedin_pass, resume_path, cover_text)
                elif platform == "naukri":
                    ok, msg = _try_naukri(page, naukri_user, naukri_pass, resume_path, cover_text)
                elif platform == "workday":
                    ok, msg = _try_workday(page, apply_email, resume_path)
                elif platform == "greenhouse":
                    ok, msg = _try_greenhouse(page, apply_email, resume_path, cover_text)
                elif platform == "lever":
                    ok, msg = _try_lever(page, apply_email, resume_path, cover_text)
                elif platform == "indeed":
                    ok, msg = _try_indeed(page, apply_email, resume_path)
                elif platform == "aggregator":
                    ok, msg = _try_aggregator(page, apply_email, resume_path, cover_text)
                else:
                    ok, msg = _try_generic(page, apply_email, apply_pass, resume_path, cover_text)

                results.append((job_id, ok, msg))
                if ok:
                    update_status(job_id, "applied")
                    log.info("  ✓ %s", msg)
                else:
                    log.warning("  ✗ %s", msg)
            except Exception as e:
                err = str(e)[:150].split("\n")[0]
                results.append((job_id, False, err))
                log.error("  ✗ %s", err)

        browser.close()
    return results


# ---------------------------------------------------------------------------
# Platform-specific handlers
# ---------------------------------------------------------------------------

def _try_linkedin(page, email: str, password: str, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    if not email or not password:
        return False, "LinkedIn credentials not set"
    if "login" in page.url:
        try:
            page.get_by_label("Email or phone").fill(email)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
        except Exception as e:
            return False, f"LinkedIn login failed: {str(e)[:80]}"

    try:
        easy = page.get_by_role("button", name="Easy Apply")
        if not _visible(easy):
            return False, "Easy Apply button not found"
        easy.first.click()
        time.sleep(2)
    except Exception:
        return False, "Easy Apply button not found"

    try:
        for _ in range(10):
            if resume_path:
                fi = page.locator('input[type="file"]')
                if _visible(fi):
                    fi.first.set_input_files(str(resume_path))
                    time.sleep(1)
            if cover_text:
                ta = page.locator("textarea")
                if _visible(ta):
                    ta.first.fill(cover_text[:3000])
            submit = page.get_by_role("button", name="Submit application")
            if _visible(submit):
                submit.first.click()
                time.sleep(2)
                return True, "Submitted via Easy Apply"
            nxt = page.get_by_role("button", name="Next").or_(page.get_by_role("button", name="Review"))
            if _visible(nxt):
                nxt.first.click()
                time.sleep(2)
            else:
                break
        return False, "Easy Apply form incomplete"
    except Exception as e:
        return False, f"Easy Apply error: {str(e)[:80]}"


def _try_naukri(page, email: str, password: str, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    if not email or not password:
        return False, "Naukri credentials not set"
    if "login" in page.url:
        try:
            page.get_by_placeholder("Enter your active Email ID").fill(email)
            page.get_by_placeholder("Enter your password").fill(password)
            page.get_by_role("button", name="Login").click()
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
        except Exception as e:
            return False, f"Naukri login failed: {str(e)[:80]}"
    try:
        apply_btn = page.locator('button:has-text("Apply"), a:has-text("Apply")').first
        if _visible(apply_btn):
            apply_btn.click()
            time.sleep(3)
            if resume_path:
                fi = page.locator('input[type="file"]')
                if _visible(fi):
                    fi.first.set_input_files(str(resume_path))
            sub = page.locator('button:has-text("Submit")')
            if _visible(sub):
                sub.first.click()
                time.sleep(2)
                return True, "Applied on Naukri"
            return True, "Apply clicked on Naukri"
        return False, "Apply button not found on Naukri"
    except Exception as e:
        return False, f"Naukri error: {str(e)[:80]}"


def _try_workday(page, email: str, resume_path: Path | None) -> tuple[bool, str]:
    try:
        time.sleep(2)
        applied = _click_first_visible(page, [
            'a[data-automation-id="jobPostingApplyButton"]',
            'button[data-automation-id="jobPostingApplyButton"]',
            'a:has-text("Apply")',
            'button:has-text("Apply")',
        ])
        if not applied:
            return False, "Workday Apply button not found"
        time.sleep(3)

        if email:
            email_field = page.locator('input[data-automation-id="email"], input[type="email"], input[name="email"]').first
            if _visible(email_field):
                email_field.fill(email)
                time.sleep(1)

        if resume_path:
            fi = page.locator('input[type="file"]')
            if _visible(fi):
                fi.first.set_input_files(str(resume_path))
                time.sleep(2)

        _click_first_visible(page, [
            'button[data-automation-id="bottom-navigation-next-button"]',
            'button:has-text("Submit")',
            'button:has-text("Next")',
            'button:has-text("Continue")',
        ])
        time.sleep(2)
        return True, "Applied on Workday (form started)"
    except Exception as e:
        return False, f"Workday error: {str(e)[:80]}"


def _get_candidate_names() -> tuple[str, str]:
    try:
        profile = load_profile()
        full = profile.get("profile", {}).get("name", "")
    except Exception:
        full = os.environ.get("CANDIDATE_NAME", "")
    parts = full.strip().split(maxsplit=1)
    return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")


def _try_greenhouse(page, email: str, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    try:
        time.sleep(2)
        first, last = _get_candidate_names()
        if email:
            if first:
                for sel in ['#first_name', 'input[name="first_name"]']:
                    loc = page.locator(sel).first
                    if _visible(loc):
                        loc.fill(first)
                        break
            if last:
                for sel in ['#last_name', 'input[name="last_name"]']:
                    loc = page.locator(sel).first
                    if _visible(loc):
                        loc.fill(last)
                        break
            for sel in ['#email', 'input[name="email"]', 'input[type="email"]']:
                loc = page.locator(sel).first
                if _visible(loc):
                    loc.fill(email)
                    break

        if resume_path:
            fi = page.locator('input[type="file"]')
            if _visible(fi):
                fi.first.set_input_files(str(resume_path))
                time.sleep(2)

        if cover_text:
            ta = page.locator('textarea[name*="cover"], textarea')
            if _visible(ta):
                ta.first.fill(cover_text[:3000])

        sub = page.locator('input[type="submit"], button[type="submit"], button:has-text("Submit")')
        if _visible(sub):
            sub.first.click()
            time.sleep(3)
            return True, "Applied on Greenhouse"
        return False, "Greenhouse submit button not found"
    except Exception as e:
        return False, f"Greenhouse error: {str(e)[:80]}"


def _try_lever(page, email: str, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    try:
        apply_btn = page.locator('a.postings-btn, a:has-text("Apply for this job"), a:has-text("Apply")')
        if _visible(apply_btn):
            apply_btn.first.click()
            time.sleep(3)

        if email:
            first, last = _get_candidate_names()
            full_name = f"{first} {last}".strip()
            if full_name:
                for sel in ['input[name="name"]']:
                    loc = page.locator(sel).first
                    if _visible(loc):
                        loc.fill(full_name)
                        break
            for sel in ['input[name="email"], input[type="email"]']:
                loc = page.locator(sel).first
                if _visible(loc):
                    loc.fill(email)
                    break

        if resume_path:
            fi = page.locator('input[type="file"]')
            if _visible(fi):
                fi.first.set_input_files(str(resume_path))
                time.sleep(2)

        if cover_text:
            ta = page.locator('textarea[name="comments"], textarea')
            if _visible(ta):
                ta.first.fill(cover_text[:3000])

        sub = page.locator('button[type="submit"], button:has-text("Submit application")')
        if _visible(sub):
            sub.first.click()
            time.sleep(3)
            return True, "Applied on Lever"
        return False, "Lever submit button not found"
    except Exception as e:
        return False, f"Lever error: {str(e)[:80]}"


def _try_indeed(page, email: str, resume_path: Path | None) -> tuple[bool, str]:
    try:
        time.sleep(2)
        applied = _click_first_visible(page, [
            'button[id*="apply"], button:has-text("Apply now")',
            'a:has-text("Apply now")',
            'button:has-text("Apply on company site")',
            'a:has-text("Apply on company site")',
            '#applyButtonLinkContainer a',
        ])
        if applied:
            time.sleep(3)
            current = page.url.lower()
            if "indeed.com" not in current:
                return _try_generic(page, email, None, resume_path, "")
            if resume_path:
                fi = page.locator('input[type="file"]')
                if _visible(fi):
                    fi.first.set_input_files(str(resume_path))
                    time.sleep(1)
            cont = page.locator('button:has-text("Continue"), button:has-text("Submit"), button[id*="continue"]')
            if _visible(cont):
                cont.first.click()
                time.sleep(2)
            return True, "Apply clicked on Indeed"
        return False, "Indeed Apply button not found"
    except Exception as e:
        return False, f"Indeed error: {str(e)[:80]}"


def _try_aggregator(page, email: str, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    try:
        time.sleep(2)
        applied = _click_first_visible(page, [
            'a:has-text("Apply")',
            'button:has-text("Apply")',
            'a:has-text("Apply Now")',
            'button:has-text("Apply Now")',
            'a:has-text("Apply on company site")',
            'a[class*="apply"]',
        ])
        if applied:
            time.sleep(4)
            return True, "Apply clicked on aggregator"
        return False, "No Apply button on aggregator"
    except Exception as e:
        return False, f"Aggregator error: {str(e)[:80]}"


def _try_generic(page, email: str, password: str | None, resume_path: Path | None, cover_text: str) -> tuple[bool, str]:
    try:
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first
        pass_input = page.locator('input[type="password"]').first
        if email and password and _visible(email_input) and _visible(pass_input):
            email_input.fill(email)
            pass_input.fill(password)
            _click_first_visible(page, [
                'button:has-text("Login")', 'button:has-text("Sign in")',
                'button[type="submit"]', 'input[type="submit"]',
            ])
            time.sleep(3)

        for label in ["Apply", "Apply Now", "Apply for this job", "Submit Application", "Submit"]:
            btn = page.locator(f'button:has-text("{label}"), a:has-text("{label}")').first
            if _visible(btn):
                btn.click()
                time.sleep(3)
                if resume_path:
                    fi = page.locator('input[type="file"]')
                    if _visible(fi):
                        fi.first.set_input_files(str(resume_path))
                        time.sleep(1)
                if cover_text:
                    ta = page.locator("textarea")
                    if _visible(ta):
                        ta.first.fill(cover_text[:3000])
                sub = page.locator('button:has-text("Submit"), input[type="submit"]')
                if _visible(sub):
                    sub.first.click()
                    time.sleep(2)
                    return True, "Applied (generic form)"
                return True, "Apply clicked on career page"
        return False, "No Apply button found on page"
    except Exception as e:
        return False, f"Generic error: {str(e)[:80]}"
