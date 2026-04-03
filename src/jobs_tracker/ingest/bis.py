from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import feedparser

from ..models import Job
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")


class BISIngester(BaseIngester):
    """
    BIS publishes a public RSS feed at bis.org/doclist/vacancies.rss.
    All jobs are in Basel — no location filter needed.
    """

    name = "bis"

    def fetch(self) -> List[Job]:
        rss_url = self.cfg.get("rss_url", "https://www.bis.org/doclist/vacancies.rss")
        feed = feedparser.parse(rss_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"BIS RSS feed error: {feed.bozo_exception}")
            return []

        jobs: List[Job] = []
        for entry in feed.entries:
            job_id = self._extract_id(entry)
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            desc = entry.get("description", "")
            deadline = self._parse_deadline(desc)
            posted = self._parse_date(entry)

            job = Job(
                id=f"bis:{job_id}",
                employer="bis",
                title=title,
                url=link,
                location="Basel, Switzerland",
                site="BIS Headquarters",
                posted_date=posted,
                deadline=deadline,
                summary=desc[:400] if desc else None,
            )
            job.compute_hash()
            jobs.append(job)

        return jobs

    @staticmethod
    def _extract_id(entry: Dict[str, Any]) -> str:
        """Extract job ref from URL like .../jr100370.htm → jr100370."""
        link = entry.get("link", "")
        if "/" in link:
            slug = link.rstrip("/").rsplit("/", 1)[-1]
            return slug.replace(".htm", "")
        return link

    @staticmethod
    def _parse_deadline(desc: str) -> Any:
        """Parse 'Application deadline: 2026-04-07' from description."""
        import re
        m = re.search(r"deadline:\s*(\d{4}-\d{2}-\d{2})", desc)
        if m:
            from datetime import date as dt_date
            try:
                return dt_date.fromisoformat(m.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_date(entry: Dict[str, Any]) -> Any:
        """Extract published date from dc:date or published_parsed."""
        from datetime import date as dt_date
        raw = entry.get("dc_date") or entry.get("published", "")
        if raw:
            try:
                return dt_date.fromisoformat(raw[:10])
            except ValueError:
                pass
        pp = entry.get("published_parsed")
        if pp:
            try:
                return dt_date(*pp[:3])
            except (TypeError, ValueError):
                pass
        return None
