from __future__ import annotations

import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, List

import feedparser

from ..models import Job
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")

# Title pattern: "Job Title - based in Location (Entity: EIB - Job ID: 111275)"
_TITLE_RE = re.compile(
    r"^(?P<title>.+?)\s*-\s*based in (?P<location>[^(]+?)\s*\(Entity:\s*(?P<entity>.+?)\s*-\s*Job ID:\s*(?P<job_id>\d+)\)$"
)
# Fallback: "Job Title (Entity: EIB/EIF - Job ID: 111287)"
_TITLE_FALLBACK_RE = re.compile(
    r"^(?P<title>.+?)\s*\(Entity:\s*(?P<entity>.+?)\s*-\s*Job ID:\s*(?P<job_id>\d+)\)$"
)


class EIBIngester(BaseIngester):
    """
    EIB publishes an Atom feed at eib.org/en/about/jobs/index.rss.
    All jobs are in Luxembourg — no location filter needed.
    """

    name = "eib"

    def fetch(self) -> List[Job]:
        rss_url = self.cfg.get(
            "rss_url", "https://www.eib.org/en/about/jobs/index.rss"
        )
        feed = feedparser.parse(rss_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"EIB Atom feed error: {feed.bozo_exception}")
            return []

        jobs: List[Job] = []
        seen_ids: set[str] = set()

        for entry in feed.entries:
            title_raw = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title_raw or not link:
                continue

            m = _TITLE_RE.match(title_raw)
            if m:
                title = m.group("title").strip()
                location = m.group("location").strip()
                job_id = m.group("job_id")
            else:
                m2 = _TITLE_FALLBACK_RE.match(title_raw)
                if m2:
                    title = m2.group("title").strip()
                    location = "Luxembourg"
                    job_id = m2.group("job_id")
                else:
                    title = title_raw
                    location = "Luxembourg"
                    job_id = self._extract_id(entry)

            canonical_id = f"eib:{job_id}"
            if canonical_id in seen_ids:
                continue
            seen_ids.add(canonical_id)

            posted = self._parse_date(entry, "published")
            deadline = self._parse_deadline(entry)

            job = Job(
                id=canonical_id,
                employer="eib",
                title=title,
                url=link,
                location=location,
                site="European Investment Bank",
                posted_date=posted,
                deadline=deadline,
            )
            job.compute_hash()
            jobs.append(job)

        return jobs

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_id(entry: Dict[str, Any]) -> str:
        """Extract numeric job ID from entry link, id field, or URL."""
        link = entry.get("link", "")
        m = re.search(r"JobOpeningId=(\d+)", link)
        if m:
            return m.group(1)
        eid = entry.get("id", "")
        m = re.search(r"(\d{5,7})", eid)
        if m:
            return m.group(1)
        return eid[:60]

    @staticmethod
    def _parse_deadline(entry: Dict[str, Any]) -> dt_date | None:
        """Extract deadline from HTML content or fall back to <updated>."""
        content = ""
        if entry.get("content"):
            content = entry["content"][0].get("value", "")

        # HTML content has "Deadline: ... 23rd April 2026"
        m = re.search(
            r"Deadline.*?(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})", content
        )
        if m:
            from dateutil.parser import parse as dateparse

            try:
                return dateparse(f"{m.group(1)} {m.group(2)} {m.group(3)}").date()
            except (ValueError, OverflowError):
                pass

        # Fall back to <updated> which is the expiry date
        raw = entry.get("updated", "")
        if raw:
            try:
                return dt_date.fromisoformat(raw[:10])
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_date(entry: Dict[str, Any], field: str = "published") -> dt_date | None:
        raw = entry.get(field, "")
        if raw:
            try:
                return dt_date.fromisoformat(raw[:10])
            except ValueError:
                pass
        pp = entry.get(f"{field}_parsed")
        if pp:
            try:
                return dt_date(*pp[:3])
            except (TypeError, ValueError):
                pass
        return None
