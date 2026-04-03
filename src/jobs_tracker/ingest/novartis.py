from __future__ import annotations

import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..models import Job
from ..util.http import fetch_with_retry, make_client
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")


class NovartisIngester(BaseIngester):
    """
    Scrapes novartis.com/careers/career-search with country[] params.
    Paginated HTML — stops when a page yields zero jobs.
    """

    name = "novartis"

    def fetch(self) -> List[Job]:
        base_url = self.cfg.get(
            "base_url", "https://www.novartis.com/careers/career-search"
        )
        countries = self.cfg.get("countries", ["LOC_CH"])
        max_pages = self.cfg.get("max_pages", 50)

        careers_url = self._build_url(base_url, countries)
        client = make_client(self.http_cfg)

        jobs: List[Job] = []
        try:
            for page in range(max_pages):
                url = _set_page(careers_url, page)
                r = fetch_with_retry(client, url)
                page_jobs = self._parse_page(r.text)

                if not page_jobs:
                    break
                jobs.extend(page_jobs)
                logger.debug(f"novartis page {page}: {len(page_jobs)} jobs")
        finally:
            client.close()

        # dedup by url
        seen: Dict[str, Job] = {}
        for j in jobs:
            seen.setdefault(str(j.url), j)
        return list(seen.values())

    # ------------------------------------------------------------------

    @staticmethod
    def _build_url(base: str, countries: List[str]) -> str:
        params = [("search_api_fulltext", "")]
        for c in countries:
            params.append(("country[]", c))
        params.append(("field_job_posted_date", "All"))
        params.append(("op", "Submit"))
        return f"{base}?{urlencode(params, doseq=True)}"

    def _parse_page(
        self, html: str, base_url: str = "https://www.novartis.com"
    ) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select('a[href^="/careers/career-search/job/details/"]')

        jobs: List[Job] = []
        seen: set[str] = set()

        for a in links:
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not href or not title:
                continue

            details_url = href if href.startswith("http") else f"{base_url}{href}"
            if details_url in seen:
                continue
            seen.add(details_url)

            req_id = self._extract_req_id(details_url)
            chunks = self._extract_row_chunks(a, title)

            business = chunks[0] if len(chunks) > 0 else ""
            location = chunks[1] if len(chunks) > 1 else ""
            site = chunks[2] if len(chunks) > 2 else ""
            date_str = chunks[3] if len(chunks) > 3 else ""

            job = Job(
                id=f"novartis:{req_id}" if req_id else f"novartis:{_url_slug(details_url)}",
                employer="novartis",
                title=title,
                url=details_url,
                location=location,
                site=site,
                department=business,
                posted_date=_parse_date(date_str),
            )
            job.compute_hash()
            jobs.append(job)

        return jobs

    @staticmethod
    def _extract_req_id(url: str) -> str:
        m = re.search(r"(REQ-\d+)", url, re.IGNORECASE)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_row_chunks(anchor, title: str) -> List[str]:
        row = anchor.find_parent(["tr", "li"])
        if row is None:
            row = anchor.find_parent("div")
        if row is None:
            return []

        cells = row.find_all(["td", "div", "span"], recursive=True)
        chunks: List[str] = []
        for c in cells:
            txt = c.get_text(" ", strip=True)
            if not txt or txt == title or len(txt) > 120 or txt in chunks:
                continue
            chunks.append(txt)
        return chunks


# --- helpers ---------------------------------------------------------------

def _set_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["page"] = [str(page)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _url_slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1][:80]


_DATE_RE = re.compile(
    r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})\b"
    r"|"
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)


def _parse_date(raw: str) -> dt_date | None:
    if not raw:
        return None
    from dateutil.parser import parse as dateparse

    m = _DATE_RE.search(raw)
    if not m:
        return None
    try:
        return dateparse(m.group(0)).date()
    except (ValueError, OverflowError):
        return None
