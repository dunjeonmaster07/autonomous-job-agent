"""Score and filter jobs against profile; suggest keywords."""
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


def _expand_locations(locations: list[str]) -> list[str]:
    """Turn profile locations into all known aliases (lowered)."""
    expanded: list[str] = []
    for loc in locations:
        key = loc.lower().strip()
        if key in LOCATION_ALIASES:
            expanded.extend(LOCATION_ALIASES[key])
        else:
            expanded.append(key)
    return expanded


def _expand_skills(raw_skills: list[str]) -> list[str]:
    """Break compound skills into individual matchable tokens."""
    tokens: list[str] = []
    for s in raw_skills:
        low = s.lower()
        tokens.append(low)
        inner = re.findall(r"[a-z0-9]+(?:[\s-][a-z0-9]+)*", low)
        for part in inner:
            part = part.strip()
            if part and part != low and len(part) > 2:
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


def score_job(job: Job, profile: dict) -> ScoredJob:
    reasons: list[str] = []
    keywords: list[str] = []
    desc = _normalize(job.description) + " " + _normalize(job.title)
    title_norm = _normalize(job.title)
    skills = _expand_skills(profile.get("profile", {}).get("skills", []))
    preferred_roles = [r.lower() for r in profile.get("preferred_roles", [])]
    locations = _expand_locations(profile.get("locations", []))
    salary_cfg = profile.get("salary_lpa", {})
    compare_salary_only_when_listed = salary_cfg.get("compare_only_when_listed", True)

    if _is_fresher_only(job.description, job.title):
        return ScoredJob(job=job, score=0.0, match_reasons=[], keyword_suggestions=[])

    for role in preferred_roles:
        if role in desc or role in title_norm:
            reasons.append(f"Role match: {role}")
            break

    matched_skills = [s for s in skills if s in desc]
    unique_matched = list(dict.fromkeys(matched_skills))
    for s in unique_matched[:5]:
        reasons.append(f"Skill: {s}")
    if len(unique_matched) >= 3:
        reasons.append("Strong skill overlap")
    keywords.extend(unique_matched)

    for term in ["senior", "lead", "principal", "l3", "l4", "staff", "10+", "8+", "5+",
                 "experience", "mid-level", "mid level", "experienced"]:
        if term in desc:
            reasons.append("Seniority level fit")
            if term not in keywords:
                keywords.append(term)
            break

    job_loc = _normalize(job.location)
    if any(alias in job_loc for alias in locations):
        reasons.append("Location match")

    min_lpa = salary_cfg.get("min")
    max_lpa = salary_cfg.get("max")
    if compare_salary_only_when_listed and min_lpa is not None and max_lpa is not None:
        salary_markers = ["lpa", "lakh", "salary", "ctc", "inr"]
        if any(m in desc for m in salary_markers):
            for n in re.findall(r"\d+", job.description):
                try:
                    v = int(n)
                    if min_lpa <= v <= max_lpa:
                        reasons.append("Salary in range (listed)")
                        break
                except ValueError:
                    pass

    has_role = any(r.startswith("Role match") for r in reasons)
    has_location = "Location match" in reasons
    has_seniority = "Seniority level fit" in reasons
    has_salary = any("Salary" in r for r in reasons)

    score = 0.0
    if has_role:
        score += 0.40
    if unique_matched:
        score += min(0.05 * len(unique_matched), 0.25)
    if has_seniority:
        score += 0.15
    if has_location:
        score += 0.15
    if has_salary:
        score += 0.10
    if len(unique_matched) >= 3:
        score += 0.05
    score = min(score, 1.0)

    if not score and (unique_matched or preferred_roles):
        score = 0.15

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
