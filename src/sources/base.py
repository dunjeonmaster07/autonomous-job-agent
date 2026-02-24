from abc import ABC, abstractmethod

from src.models import Job


class JobSearchBase(ABC):
    @abstractmethod
    def search(self, query: str, locations: list[str], limit: int = 20) -> list[Job]:
        pass
