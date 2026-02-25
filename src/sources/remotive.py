"""Remotive — free API for remote tech jobs (no API key required).

Docs: https://remotive.com/api/remote-jobs
"""
from __future__ import annotations

import hashlib

import requests

from src.log import get_logger
from src.models import Job
from src.retry import retry
from src.sources.base import JobSearchBase

log = get_logger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

# Map broad profile skills/roles to Remotive categories for tighter results.
_CATEGORY_MAP: dict[str, str] = {
    "devops": "devops",
    "sre": "devops",
    "cloud": "devops",
    "software": "software-dev",
    "engineer": "software-dev",
    "python": "software-dev",
    "product": "product",
    "data": "data",
    "qa": "qa",
    "support": "customer-support",
    "customer": "customer-support",
}


def _guess_category(roles: list[str], skills: list[str]) -> str:
    """Pick the most relevant Remotive category from profile signals."""
    for text in roles + skills:
        for keyword, category in _CATEGORY_MAP.items():
            if keyword in text.lower():
                return category
    return ""


class RemotiveSource(JobSearchBase):
    def __init__(self, profile: dict, env_getter=None) -> None:
        self.profile = profile

    @retry(max_attempts=2, base_delay=1.5, retryable=(requests.RequestException, OSError))
    def _fetch(self, search: str, category: str, limit: int) -> list[Job]:
        params: dict = {"limit": limit}
        if search:
            params["search"] = search
        if category:
            params["category"] = category

        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs: list[Job] = []
        for hit in data.get("jobs", []):
            title = hit.get("title", "")
            company = hit.get("company_name", "")
            raw_id = hit.get("id", f"{title}{company}")
            job_id = hashlib.sha256(str(raw_id).encode()).hexdigest()[:12]

            tags = hit.get("tags", [])
            desc = hit.get("description", "")
            if tags:
                desc += " " + " ".join(tags)

            jobs.append(
                Job(
                    id=job_id,
                    title=title,
                    company=company,
                    location=hit.get("candidate_required_location", "Remote"),
                    url=hit.get("url", ""),
                    description=desc,
                    posted_at=hit.get("publication_date"),
                    source="remotive",
                    raw=hit,
                )
            )
        return jobs

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        core_roles = self.profile.get("core_roles", [])
        stretch_roles = self.profile.get("stretch_roles", [])
        skills = self.profile.get("profile", {}).get("skills", [])

        # Remotive works best with short, broad search terms — not full role titles.
        # Extract distinctive keywords from core roles.
        search_terms: list[str] = []
        generic = {"senior", "junior", "lead", "staff", "principal", "manager",
                    "engineer", "specialist", "consultant", "ii", "iii", "iv"}
        for role in core_roles[:2]:
            words = role.lower().split()
            distinctive = [w for w in words if w not in generic]
            if distinctive:
                search_terms.append(distinctive[0])
        if not search_terms:
            search_terms.append(query.split()[0] if query else "engineer")

        # Use category only as a fallback (combining it with search is too restrictive
        # on Remotive's relatively small dataset).
        category = _guess_category(core_roles + stretch_roles, skills)

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()
        for term in search_terms:
            try:
                batch = self._fetch(term, category="", limit=limit)
                for j in batch:
                    if j.id not in seen_ids:
                        seen_ids.add(j.id)
                        all_jobs.append(j)
                log.debug("Remotive search=%r returned %d jobs", term, len(batch))
            except Exception as exc:
                log.warning("Remotive search=%r error: %s", term, exc)

        # If keyword search yielded nothing, try category-only
        if not all_jobs and category:
            try:
                batch = self._fetch("", category, limit=limit)
                for j in batch:
                    if j.id not in seen_ids:
                        seen_ids.add(j.id)
                        all_jobs.append(j)
                log.debug("Remotive category=%r fallback returned %d jobs", category, len(batch))
            except Exception as exc:
                log.warning("Remotive category fallback error: %s", exc)

        return all_jobs[:limit]
