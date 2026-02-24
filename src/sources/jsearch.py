"""JSearch API (RapidAPI) — aggregated job listings."""
from __future__ import annotations

import hashlib

import requests

from src.log import get_logger
from src.models import Job
from src.retry import retry
from src.sources.base import JobSearchBase

log = get_logger(__name__)


class JSearchSource(JobSearchBase):
    BASE = "https://jsearch.p.rapidapi.com"

    def __init__(self, profile: dict, env_getter) -> None:
        self.profile = profile
        self.api_key: str = env_getter("JSEARCH_API_KEY")

    @retry(max_attempts=3, base_delay=2.0, retryable=(requests.RequestException, OSError))
    def _fetch_location(self, query: str, loc: str, limit: int) -> list[Job]:
        r = requests.get(
            f"{self.BASE}/search",
            params={"query": f"{query} {loc}", "num_pages": "1"},
            headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            timeout=15,
        )
        if r.status_code == 403:
            log.warning("JSearch 403 — subscribe at https://rapidapi.com/letscrape-6bRDu3Sgupt/api/jsearch")
            return []
        r.raise_for_status()
        data = r.json()
        jobs: list[Job] = []
        for hit in data.get("data", [])[:limit]:
            j = hit.get("job_id") or hit.get("job_title", "")
            job_id = hashlib.sha256(j.encode()).hexdigest()[:12]
            jobs.append(
                Job(
                    id=job_id,
                    title=hit.get("job_title", ""),
                    company=hit.get("employer_name", ""),
                    location=hit.get("job_city") or hit.get("job_country", ""),
                    url=hit.get("job_apply_link", ""),
                    description=hit.get("job_description", ""),
                    posted_at=hit.get("job_posted_at_timestamp"),
                    source="jsearch",
                    raw=hit,
                )
            )
        return jobs

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        jobs: list[Job] = []
        for loc in locations[:3]:
            try:
                batch = self._fetch_location(query, loc, limit)
                jobs.extend(batch)
                log.debug("JSearch loc=%r returned %d jobs", loc, len(batch))
            except Exception as exc:
                log.warning("JSearch loc=%r error: %s", loc, exc)
                continue
        return jobs[:limit]
