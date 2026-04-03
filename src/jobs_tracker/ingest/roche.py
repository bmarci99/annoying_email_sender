from __future__ import annotations

import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, List

from ..models import Job
from ..util.http import fetch_with_retry, make_client
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")


class RocheIngester(BaseIngester):
    """
    Roche uses Workday as their ATS.  The external career site at
    roche.wd3.myworkdayjobs.com exposes a JSON API at:

        POST /wday/cxs/roche/roche-ext/jobs

    We POST with a location filter for Switzerland and paginate through results.
    Fallback: scrape the server-rendered Workday HTML.
    """

    name = "roche"

    def fetch(self) -> List[Job]:
        api_url = self.cfg.get(
            "api_url",
            "https://roche.wd3.myworkdayjobs.com/wday/cxs/roche/roche-ext/jobs",
        )
        careers_url = self.cfg.get(
            "careers_url",
            "https://roche.wd3.myworkdayjobs.com/en-US/roche-ext",
        )
        location_ids = self.cfg.get("location_ids", [])
        limit = self.cfg.get("limit", 200)

        # Try the Workday JSON API first
        jobs = self._fetch_via_api(api_url, careers_url, location_ids, limit)
        if jobs:
            return jobs

        # Fallback: scrape the HTML listing
        logger.info("Roche API unavailable, falling back to HTML scrape")
        return self._fetch_via_html(careers_url)

    # ---- primary: Workday JSON API ----------------------------------------

    def _fetch_via_api(
        self, api_url: str, careers_base: str, location_ids: list, limit: int
    ) -> List[Job]:
        client = make_client(
            self.http_cfg,
            headers={"Content-Type": "application/json"},
        )

        all_jobs: List[Job] = []
        offset = 0
        page_size = 20

        try:
            while offset < limit:
                payload = {
                    "appliedFacets": {"locations": location_ids} if location_ids else {},
                    "limit": page_size,
                    "offset": offset,
                    "searchText": "",
                }
                try:
                    r = fetch_with_retry(
                        client, api_url, method="POST", json=payload
                    )
                except Exception:
                    logger.debug("Workday API POST failed", exc_info=True)
                    return []  # signal fallback

                data = r.json()
                postings = data.get("jobPostings", [])
                if not postings:
                    break

                for p in postings:
                    job = self._parse_posting(p, careers_base)
                    if job:
                        all_jobs.append(job)

                total = data.get("total", 0)
                offset += page_size
                if offset >= total:
                    break
        finally:
            client.close()

        return all_jobs

    def _parse_posting(self, p: Dict[str, Any], careers_base: str) -> Job | None:
        title = p.get("title", "").strip()
        external_path = p.get("externalPath", "")
        if not title or not external_path:
            return None

        url = f"{careers_base}{external_path}"
        posted = self._parse_iso_date(p.get("postedOn", ""))
        loc_list = p.get("locationsText", "")
        bullet_id = p.get("bulletFields", [""])[0] if p.get("bulletFields") else ""

        job = Job(
            id=f"roche:{_extract_job_id(external_path)}",
            employer="roche",
            title=title,
            url=url,
            location=loc_list if loc_list else "Switzerland",
            posted_date=posted,
            employment_type=bullet_id,
        )
        job.compute_hash()
        return job

    # ---- fallback: HTML scraping ------------------------------------------

    def _fetch_via_html(self, careers_url: str, location: str) -> List[Job]:
        from bs4 import BeautifulSoup

        client = make_client(self.http_cfg)
        jobs: List[Job] = []

        try:
            r = fetch_with_retry(client, careers_url)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.select("a[data-automation-id='jobTitle']"):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title:
                    continue

                url = href if href.startswith("http") else f"https://roche.wd3.myworkdayjobs.com{href}"

                # Check for Switzerland mention in nearby text
                parent = a.find_parent(["li", "div"])
                parent_text = parent.get_text(" ", strip=True) if parent else ""

                if location.lower() not in parent_text.lower():
                    continue

                job = Job(
                    id=f"roche:{_extract_job_id(href)}",
                    employer="roche",
                    title=title,
                    url=url,
                    location="Switzerland",
                )
                job.compute_hash()
                jobs.append(job)
        finally:
            client.close()

        return jobs

    @staticmethod
    def _parse_iso_date(raw: str) -> dt_date | None:
        if not raw:
            return None
        try:
            return dt_date.fromisoformat(raw[:10])
        except (ValueError, TypeError):
            return None


def _extract_job_id(path: str) -> str:
    """Extract Workday job ID from path like /job/Title_JR-123456."""
    m = re.search(r"(JR[_-]\d+)", path, re.IGNORECASE)
    if m:
        return m.group(1)
    parts = path.rstrip("/").rsplit("/", 1)
    return parts[-1][:80] if parts else path[:80]
