"""Score and filter jobs against profile with role-aware matching."""
from __future__ import annotations

import re

from src.log import get_logger
from src.models import Job, ScoredJob

log = get_logger(__name__)


def _normalize(s: str) -> str:
    return (s or "").lower().strip()


LOCATION_ALIASES: dict[str, list[str]] = {
    "bangalore": ["bangalore", "bengaluru", "bengalore"],
    "gurgaon": ["gurgaon", "gurugram"],
    "noida": ["noida"],
    "hyderabad": ["hyderabad"],
    "pune": ["pune"],
    "remote": ["remote", "anywhere", "work from home", "wfh"],
}

FRESHER_PHRASES: list[str] = [
    "fresher", "0-2 years", "0-1 years", "0 - 2", "0 - 1",
    "entry level", "entry-level", "no experience", "fresh graduate",
    "recent graduate", "freshers only", "0 years",
]

# Titles that signal a level well above "senior" individual contributor
OVER_LEVEL_TITLES: list[str] = [
    "director", "vice president", "vp ", "vp,", "chief ",
    "head of", "cto", "cfo", "coo", "ceo", "managing director",
    "general manager", "avp", "assistant vice president",
]

# Minimum token length when expanding compound skills to avoid
# tiny tokens like "ai", "api" that match everything.
_MIN_SKILL_TOKEN_LEN = 4


def _expand_locations(locations: list[str]) -> list[str]:
    expanded: list[str] = []
    for loc in locations:
        key = loc.lower().strip()
        if key in LOCATION_ALIASES:
            expanded.extend(LOCATION_ALIASES[key])
        else:
            expanded.append(key)
    return expanded


def _expand_skills(raw_skills: list[str]) -> list[str]:
    """Break compound skills into matchable tokens, filtering short noise."""
    tokens: list[str] = []
    for s in raw_skills:
        low = s.lower()
        tokens.append(low)
        inner = re.findall(r"[a-z0-9]+(?:[\s-][a-z0-9]+)*", low)
        for part in inner:
            part = part.strip()
            if part and part != low and len(part) >= _MIN_SKILL_TOKEN_LEN:
                tokens.append(part)
    return list(dict.fromkeys(tokens))


def _is_fresher_only(desc: str, title: str) -> bool:
    text = _normalize(desc) + " " + _normalize(title)
    for phrase in FRESHER_PHRASES:
        if phrase in text:
            if any(x in text for x in ["senior", "experience", "8+", "10+", "years exp", "l3", "l4"]):
                continue
            return True
    return False


def _is_over_level(title: str, profile_level: str) -> bool:
    """Return True if the job title implies a level clearly above the profile."""
    if profile_level not in ("junior", "intermediate", "senior"):
        return False
    t = _normalize(title)
    return any(tag in t for tag in OVER_LEVEL_TITLES)


def _word_overlap_ratio(role: str, text: str) -> float:
    """Fraction of words in *role* that appear in *text*.

    Requires at least 2 overlapping words to be non-zero, preventing
    single-word false positives like "product" matching everything.
    """
    role_words = set(role.lower().split())
    text_words = set(text.lower().split())
    overlap = role_words & text_words
    if len(overlap) < 2 and len(role_words) > 1:
        return 0.0
    if not role_words:
        return 0.0
    return len(overlap) / len(role_words)


def _best_role_match(
    title: str,
    desc: str,
    core_roles: list[str],
    stretch_roles: list[str],
) -> tuple[float, str, str]:
    """Find the best matching role and return (score_contribution, role, tier).

    Scoring hierarchy:
      - Core role in job TITLE (exact substring)         → 0.40
      - Core role in title (word overlap >= 60%)          → 0.35
      - Stretch role in job TITLE (exact substring)       → 0.20
      - Stretch role in title (word overlap >= 60%)       → 0.18
      - Core role in description only (exact substring)   → 0.15
      - Stretch role in description only                  → 0.08
    """
    title_norm = _normalize(title)
    desc_norm = _normalize(desc)
    best_score = 0.0
    best_role = ""
    best_tier = ""

    for role_raw in core_roles:
        role = role_raw.lower()
        if role in title_norm:
            if 0.40 > best_score:
                best_score, best_role, best_tier = 0.40, role_raw, "core"
            continue
        overlap = _word_overlap_ratio(role, title_norm)
        if overlap >= 0.6 and 0.35 > best_score:
            best_score, best_role, best_tier = 0.35, role_raw, "core"
            continue
        if role in desc_norm and 0.15 > best_score:
            best_score, best_role, best_tier = 0.15, role_raw, "core"

    for role_raw in stretch_roles:
        role = role_raw.lower()
        if role in title_norm:
            if 0.20 > best_score:
                best_score, best_role, best_tier = 0.20, role_raw, "stretch"
            continue
        overlap = _word_overlap_ratio(role, title_norm)
        if overlap >= 0.6 and 0.18 > best_score:
            best_score, best_role, best_tier = 0.18, role_raw, "stretch"
            continue
        if role in desc_norm and 0.08 > best_score:
            best_score, best_role, best_tier = 0.08, role_raw, "stretch"

    return best_score, best_role, best_tier


def score_job(job: Job, profile: dict) -> ScoredJob:
    reasons: list[str] = []
    keywords: list[str] = []
    desc = _normalize(job.description)
    title_norm = _normalize(job.title)
    full_text = desc + " " + title_norm

    skills = _expand_skills(profile.get("profile", {}).get("skills", []))
    core_roles = [r for r in profile.get("core_roles", [])]
    stretch_roles = [r for r in profile.get("stretch_roles", [])]
    locations = _expand_locations(profile.get("locations", []))
    salary_cfg = profile.get("salary_lpa", {})
    compare_salary_only_when_listed = salary_cfg.get("compare_only_when_listed", True)
    profile_level = profile.get("profile", {}).get("level", "senior")

    # Hard filter: fresher-only jobs
    if _is_fresher_only(job.description, job.title):
        return ScoredJob(job=job, score=0.0, match_reasons=[], keyword_suggestions=[])

    # Hard filter: over-level jobs (Director/VP/C-suite) for non-director candidates
    if _is_over_level(job.title, profile_level):
        return ScoredJob(
            job=job, score=0.0,
            match_reasons=["Filtered: seniority above profile level"],
            keyword_suggestions=[],
        )

    # --- Role match (graduated, title-first) ---
    role_score, matched_role, role_tier = _best_role_match(
        job.title, job.description, core_roles, stretch_roles,
    )
    if matched_role:
        label = f"Role match ({role_tier}): {matched_role}"
        reasons.append(label)

    # --- Skills overlap ---
    matched_skills = [s for s in skills if s in full_text]
    unique_matched = list(dict.fromkeys(matched_skills))
    for s in unique_matched[:5]:
        reasons.append(f"Skill: {s}")
    if len(unique_matched) >= 3:
        reasons.append("Strong skill overlap")
    keywords.extend(unique_matched)

    # --- Seniority fit ---
    has_seniority = False
    for term in ["senior", "lead", "principal", "l3", "l4", "staff", "10+", "8+", "5+",
                 "experience", "mid-level", "mid level", "experienced"]:
        if term in full_text:
            reasons.append("Seniority level fit")
            has_seniority = True
            if term not in keywords:
                keywords.append(term)
            break

    # --- Location match ---
    job_loc = _normalize(job.location)
    has_location = any(alias in job_loc for alias in locations)
    if has_location:
        reasons.append("Location match")

    # --- Salary match ---
    has_salary = False
    min_lpa = salary_cfg.get("min")
    max_lpa = salary_cfg.get("max")
    if compare_salary_only_when_listed and min_lpa is not None and max_lpa is not None:
        salary_markers = ["lpa", "lakh", "salary", "ctc", "inr"]
        if any(m in full_text for m in salary_markers):
            for n in re.findall(r"\d+", job.description):
                try:
                    v = int(n)
                    if min_lpa <= v <= max_lpa:
                        reasons.append("Salary in range (listed)")
                        has_salary = True
                        break
                except ValueError:
                    pass

    # --- Composite score ---
    score = 0.0
    score += role_score                                          # 0 – 0.40
    score += min(0.05 * len(unique_matched), 0.25)               # 0 – 0.25
    if has_seniority:
        score += 0.10                                            # 0.10
    if has_location:
        score += 0.15                                            # 0.15
    if has_salary:
        score += 0.10                                            # 0.10

    # Bonus for strong skill match alongside a core role
    if len(unique_matched) >= 3 and role_tier == "core":
        score += 0.05

    score = min(score, 1.0)

    # Fallback floor: if no structured score but there are some signals
    if not score and (unique_matched or core_roles or stretch_roles):
        score = 0.10

    return ScoredJob(
        job=job,
        score=round(score, 2),
        match_reasons=reasons,
        keyword_suggestions=list(dict.fromkeys(keywords))[:10],
    )


def filter_and_rank(
    jobs: list[Job], profile: dict, min_score: float = 0.2
) -> list[ScoredJob]:
    scored = [score_job(j, profile) for j in jobs]
    result = sorted([s for s in scored if s.score >= min_score], key=lambda s: -s.score)
    log.info("Scored %d jobs → %d above %.0f%% threshold", len(jobs), len(result), min_score * 100)
    return result
