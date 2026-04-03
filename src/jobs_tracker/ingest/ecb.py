from __future__ import annotations

import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from ..models import Job
from ..util.http import fetch_with_retry, make_client
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")


class ECBIngester(BaseIngester):
    """
    Scrapes talent.ecb.europa.eu/careers/SearchJobs.
    ECB is in Frankfurt — no country filter (user wants all ECB jobs).
    """

    name = "ecb"

    def fetch(self) -> List[Job]:
        search_url = self.cfg.get(
            "search_url", "https://talent.ecb.europa.eu/careers/SearchJobs"
        )
        base_url = self.cfg.get("base_url", "https://talent.ecb.europa.eu")
        client = make_client(self.http_cfg)

        jobs: List[Job] = []
        try:
            r = fetch_with_retry(client, search_url)
            jobs = self._parse(r.text, base_url)
        finally:
            client.close()

        return jobs

    def _parse(self, html: str, base_url: str) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")

        jobs: List[Job] = []

        # ECB uses links like /careers/JobDetail/Title-Here/13389
        for a in soup.select('a[href*="/careers/JobDetail/"]'):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title or not href:
                continue

            url = href if href.startswith("http") else f"{base_url}{href}"
            job_id = self._extract_id(href)

            # Deadline and category come from nearby text
            card = a.find_parent(["div", "li", "section"])
            deadline = None
            department = ""
            if card:
                card_text = card.get_text("\n", strip=True)
                deadline = self._parse_deadline(card_text)
                department = self._extract_department(card_text, title)

            job = Job(
                id=f"ecb:{job_id}",
                employer="ecb",
                title=title,
                url=url,
                location="Frankfurt, Germany",
                site="European Central Bank",
                department=department,
                deadline=deadline,
            )
            job.compute_hash()
            jobs.append(job)

        # dedup by id
        seen: Dict[str, Job] = {}
        for j in jobs:
            seen.setdefault(j.id, j)
        return list(seen.values())

    @staticmethod
    def _extract_id(href: str) -> str:
        """Extract numeric job ID from /careers/JobDetail/..../13389."""
        m = re.search(r"/(\d{4,6})(?:\?|$|#)", href)
        if m:
            return m.group(1)
        parts = href.rstrip("/").rsplit("/", 1)
        return parts[-1][:60] if parts else href[:60]

    @staticmethod
    def _parse_deadline(text: str) -> dt_date | None:
        m = re.search(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", text)
        if m:
            from dateutil.parser import parse as dateparse
            try:
                return dateparse(m.group(0)).date()
            except (ValueError, OverflowError):
                pass
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            try:
                return dt_date.fromisoformat(m.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _extract_department(text: str, title: str) -> str:
        """Best-effort department extraction from card text."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            if line == title or re.match(r"\d", line) or "Apply" in line or "Share" in line:
                continue
            if len(line) < 80 and line != "":
                return line
        return ""
