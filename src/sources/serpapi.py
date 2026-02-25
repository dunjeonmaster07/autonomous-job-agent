"""SerpAPI Google Jobs search."""
from __future__ import annotations

import hashlib

import requests

from src.log import get_logger
from src.models import Job
from src.retry import retry
from src.sources.base import JobSearchBase

log = get_logger(__name__)


def _best_apply_link(hit: dict) -> str:
    for opts_key in ("apply_options", "related_links"):
        opts = hit.get(opts_key, [])
        if opts and isinstance(opts, list):
            for opt in opts:
                link = opt.get("link", "")
                if link:
                    return link
    return hit.get("share_link", "") or hit.get("link", "")


class SerpApiSource(JobSearchBase):
    def __init__(self, profile: dict, env_getter) -> None:
        self.profile = profile
        self.api_key: str = env_getter("SERPAPI_KEY")

    @retry(max_attempts=3, base_delay=2.0, retryable=(requests.RequestException, OSError))
    def _fetch(self, query: str, location: str, limit: int) -> list[Job]:
        jobs: list[Job] = []
        r = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "api_key": self.api_key,
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        for hit in data.get("jobs_results", [])[:limit]:
            title = hit.get("title", "")
            company = hit.get("company_name", "")
            job_id = hashlib.sha256(
                (title + company + hit.get("location", "")).encode()
            ).hexdigest()[:12]
            jobs.append(
                Job(
                    id=job_id,
                    title=title,
                    company=company,
                    location=hit.get("location", ""),
                    url=_best_apply_link(hit),
                    description=hit.get("description", ""),
                    posted_at=hit.get("detected_extensions", {}).get("posted_at"),
                    source="serpapi",
                    raw=hit,
                )
            )
        return jobs

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        loc_str = (locations[0] + ", India") if locations else "India"
        core_roles = self.profile.get("core_roles", [])
        stretch_roles = self.profile.get("stretch_roles", [])

        # Prioritise core roles; fill remaining budget with stretch roles
        queries: list[str] = []
        for role in core_roles[:4]:
            queries.append(role)
        remaining = 5 - len(queries)
        for role in stretch_roles[:remaining]:
            queries.append(role)
        if not queries:
            queries.append(query)

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        for q in queries:
            if len(all_jobs) >= limit:
                break
            try:
                batch = self._fetch(q, loc_str, limit=10)
                for j in batch:
                    if j.id not in seen_ids:
                        seen_ids.add(j.id)
                        all_jobs.append(j)
                log.debug("SerpAPI query=%r returned %d jobs", q, len(batch))
            except Exception as exc:
                log.warning("SerpAPI query=%r error: %s", q, exc)
                continue

        return all_jobs[:limit]
