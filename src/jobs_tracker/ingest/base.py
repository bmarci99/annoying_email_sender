from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models import Job

logger = logging.getLogger("jobs_tracker")


class BaseIngester(ABC):
    """Common interface for every employer scraper."""

    name: str = "base"

    def __init__(self, cfg: Dict[str, Any], http_cfg: Dict[str, Any] | None = None):
        self.cfg = cfg
        self.http_cfg = http_cfg or {}

    @abstractmethod
    def fetch(self) -> List[Job]:
        """Scrape / fetch all current job listings. Must be idempotent."""
        ...

    def safe_fetch(self) -> List[Job]:
        """Fetch with top-level error handling so one source never crashes the pipeline."""
        try:
            jobs = self.fetch()
            logger.info(f"[green]{self.name}[/green]: fetched {len(jobs)} jobs")
            return jobs
        except Exception:
            logger.exception(f"[red]{self.name}[/red]: ingestion failed")
            return []
