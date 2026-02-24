from .base import JobSearchBase
from .jsearch import JSearchSource
from .mock import MockSource
from .serpapi import SerpApiSource

from src.log import get_logger

log = get_logger(__name__)

__all__ = ["JobSearchBase", "JSearchSource", "MockSource", "SerpApiSource", "get_sources"]


def get_sources(profile: dict, env_getter) -> list[JobSearchBase]:
    sources: list[JobSearchBase] = []
    if env_getter("JSEARCH_API_KEY"):
        sources.append(JSearchSource(profile, env_getter))
        log.info("Registered source: JSearch")
    if env_getter("SERPAPI_KEY"):
        sources.append(SerpApiSource(profile, env_getter))
        log.info("Registered source: SerpAPI")
    if not sources:
        sources.append(MockSource(profile))
        log.info("No API keys found — using MockSource")
    return sources
