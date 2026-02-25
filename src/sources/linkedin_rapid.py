"""LinkedIn Jobs via RapidAPI — direct LinkedIn listings.

Uses the "linkedin-jobs-search" API on RapidAPI.
Sign up at https://rapidapi.com/jaypat87/api/linkedin-jobs-search
Free tier available.
"""
from __future__ import annotations

import hashlib

import requests

from src.log import get_logger
from src.models import Job
from src.retry import retry
from src.sources.base import JobSearchBase

log = get_logger(__name__)

API_HOST = "linkedin-jobs-search.p.rapidapi.com"
API_URL = f"https://{API_HOST}/"


class LinkedInRapidSource(JobSearchBase):
    def __init__(self, profile: dict, env_getter) -> None:
        self.profile = profile
        self.api_key: str = env_getter("RAPIDAPI_KEY")

    @retry(max_attempts=3, base_delay=2.0, retryable=(requests.RequestException, OSError))
    def _fetch(self, keywords: str, location: str, limit: int) -> list[Job]:
        payload = {
            "search_terms": keywords,
            "location": location,
            "page": "1",
        }
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": API_HOST,
            "Content-Type": "application/json",
        }

        r = requests.post(API_URL, json=payload, headers=headers, timeout=20)
        if r.status_code == 403:
            log.warning("LinkedIn RapidAPI 403 — check subscription at https://rapidapi.com")
            return []
        r.raise_for_status()
        data = r.json()

        jobs: list[Job] = []
        results = data if isinstance(data, list) else data.get("results", data.get("jobs", []))
        for hit in results[:limit]:
            title = hit.get("job_title") or hit.get("title", "")
            company = hit.get("company_name") or hit.get("company", "")
            loc = hit.get("job_location") or hit.get("location", "")
            url = hit.get("linkedin_job_url_cleaned") or hit.get("job_url") or hit.get("url", "")
            desc = hit.get("job_description") or hit.get("description", "")
            posted = hit.get("posted_date") or hit.get("posted_at")

            raw_id = hit.get("job_id") or hit.get("id") or f"{title}{company}{loc}"
            job_id = hashlib.sha256(str(raw_id).encode()).hexdigest()[:12]

            jobs.append(
                Job(
                    id=job_id,
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    description=desc,
                    posted_at=posted,
                    source="linkedin",
                    raw=hit,
                )
            )
        return jobs

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        core_roles = self.profile.get("core_roles", [])
        if core_roles:
            query = " OR ".join(core_roles[:2])

        loc_str = locations[0] if locations else "India"

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        try:
            batch = self._fetch(query, loc_str, limit=limit)
            for j in batch:
                if j.id not in seen_ids:
                    seen_ids.add(j.id)
                    all_jobs.append(j)
            log.debug("LinkedIn RapidAPI returned %d jobs for %r", len(batch), query)
        except Exception as exc:
            log.warning("LinkedIn RapidAPI error: %s", exc)

        # If budget allows, try one stretch role as a separate query
        stretch_roles = self.profile.get("stretch_roles", [])
        if stretch_roles and len(all_jobs) < limit:
            try:
                batch = self._fetch(stretch_roles[0], loc_str, limit=10)
                for j in batch:
                    if j.id not in seen_ids:
                        seen_ids.add(j.id)
                        all_jobs.append(j)
            except Exception as exc:
                log.warning("LinkedIn RapidAPI stretch query error: %s", exc)

        return all_jobs[:limit]
