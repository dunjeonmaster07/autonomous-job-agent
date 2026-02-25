"""Mock job source for testing and fallback when APIs return no jobs."""
from __future__ import annotations

from datetime import datetime, timezone

from src.log import get_logger
from src.models import Job
from src.sources.base import JobSearchBase

log = get_logger(__name__)


def _mock_id(suffix: str) -> str:
    """Date-based ID so fallback mock jobs are treated as new each day."""
    return f"mock-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{suffix}"


class MockSource(JobSearchBase):
    def __init__(self, profile: dict, env_getter=None) -> None:
        self.profile = profile

    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        roles = (self.profile.get("core_roles") or self.profile.get("preferred_roles", []))[:3]
        log.info("MockSource generating sample jobs")
        mock_jobs = [
            Job(
                id=_mock_id("1"),
                title=roles[0] if roles else "Software Engineer",
                company="TechCorp India",
                location="Bangalore",
                url="https://example.com/job/1",
                description="Kubernetes, cloud, incident response. 8+ years.",
                posted_at="2 days ago",
                source="mock",
            ),
            Job(
                id=_mock_id("2"),
                title="Customer Reliability Engineer",
                company="CloudScale SaaS",
                location="Hyderabad, Remote",
                url="https://example.com/job/2",
                description="SRE, distributed systems, customer-facing escalations.",
                posted_at="1 week ago",
                source="mock",
            ),
            Job(
                id=_mock_id("3"),
                title="Technical Support Engineer L4",
                company="Enterprise Platform Inc",
                location="Gurgaon",
                url="https://example.com/job/3",
                description="L4 support, root cause analysis, SaaS.",
                posted_at="3 days ago",
                source="mock",
            ),
        ]
        return mock_jobs[:limit]
