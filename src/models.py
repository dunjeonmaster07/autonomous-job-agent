"""Data models for jobs and applications."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    posted_at: str | None = None
    salary: str | None = None
    source: str = "unknown"
    raw: dict = field(default_factory=dict)


@dataclass
class ScoredJob:
    job: Job
    score: float
    match_reasons: list[str]
    keyword_suggestions: list[str]
