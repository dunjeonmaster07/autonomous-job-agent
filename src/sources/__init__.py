from .base import JobSearchBase
from .jsearch import JSearchSource
from .mock import MockSource
from .serpapi import SerpApiSource
from .adzuna import AdzunaSource
from .remotive import RemotiveSource
from .linkedin_rapid import LinkedInRapidSource

from src.log import get_logger

log = get_logger(__name__)

__all__ = [
    "JobSearchBase", "JSearchSource", "MockSource", "SerpApiSource",
    "AdzunaSource", "RemotiveSource", "LinkedInRapidSource",
    "get_sources",
]


def get_sources(profile: dict, env_getter) -> list[JobSearchBase]:
    sources: list[JobSearchBase] = []

    if env_getter("SERPAPI_KEY"):
        sources.append(SerpApiSource(profile, env_getter))
        log.info("Registered source: SerpAPI (Google Jobs)")

    if env_getter("JSEARCH_API_KEY"):
        sources.append(JSearchSource(profile, env_getter))
        log.info("Registered source: JSearch")

    if env_getter("ADZUNA_APP_ID") and env_getter("ADZUNA_APP_KEY"):
        sources.append(AdzunaSource(profile, env_getter))
        log.info("Registered source: Adzuna")

    if env_getter("RAPIDAPI_KEY"):
        sources.append(LinkedInRapidSource(profile, env_getter))
        log.info("Registered source: LinkedIn (RapidAPI)")

    # Remotive is free — always include when user has "Remote" in locations
    profile_locations = [loc.lower() for loc in profile.get("locations", [])]
    if "remote" in profile_locations:
        sources.append(RemotiveSource(profile))
        log.info("Registered source: Remotive (free, remote jobs)")

    if not sources:
        sources.append(MockSource(profile))
        log.info("No API keys found — using MockSource")

    return sources
