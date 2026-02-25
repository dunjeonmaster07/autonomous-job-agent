"""Adzuna job search — aggregator with India coverage.

Free tier: 250 requests/day.  Sign up at https://developer.adzuna.com/
"""
from __future__ import annotations

import hashlib

import requests

from src.log import get_logger
from src.models import Job
from src.retry import retry
from src.sources.base import JobSearchBase

log = get_logger(__name__)

COUNTRY = "in"
BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search"


class AdzunaSource(JobSearchBase):
    def __init__(self, profile: dict, env_getter) -> None:
        self.profile = profile
        self.app_id: str = env_getter("ADZUNA_APP_ID")
        self.app_key: str = env_getter("ADZUNA_APP_KEY")

    @retry(max_attempts=3, base_delay=2.0, retryable=(requests.RequestException, OSError))
    def _fetch(self, query: str, location: str, page: int, per_page: int) -> list[Job]:
        params: dict = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": per_page,
            "content-type": "application/json",
        }
        if location:
            params["where"] = location

        r = requests.get(f"{BASE_URL}/{page}", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs: list[Job] = []
        for hit in data.get("results", []):
            title = hit.get("title", "")
            company = (hit.get("company") or {}).get("display_name", "")
            loc = (hit.get("location") or {}).get("display_name", "")
            raw_id = hit.get("id", f"{title}{company}{loc}")
            job_id = hashlib.sha256(str(raw_id).encode()).hexdigest()[:12]

            salary_text = ""
            sal_min = hit.get("salary_min")
            sal_max = hit.get("salary_max")
            if sal_min and sal_max:
                salary_text = f"{sal_min}-{sal_max}"
            elif sal_min:
                salary_text = str(sal_min)

            jobs.append(
                Job(
                    id=job_id,
                    title=title,
                    company=company,
                    location=loc,
                    url=hit.get("redirect_url", ""),
                    description=hit.get("description", ""),
                    posted_at=hit.get("created"),
                    salary=salary_text or None,
                    source="adzuna",
                    raw=hit,
                )
            )
        return jobs

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        core_roles = self.profile.get("core_roles", [])
        if core_roles:
            query = " OR ".join(core_roles[:3])

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        search_locs = locations[:2] if locations else [""]
        for loc in search_locs:
            if len(all_jobs) >= limit:
                break
            try:
                batch = self._fetch(query, loc, page=1, per_page=min(limit, 20))
                for j in batch:
                    if j.id not in seen_ids:
                        seen_ids.add(j.id)
                        all_jobs.append(j)
                log.debug("Adzuna loc=%r returned %d jobs", loc, len(batch))
            except Exception as exc:
                log.warning("Adzuna loc=%r error: %s", loc, exc)
                continue

        return all_jobs[:limit]
