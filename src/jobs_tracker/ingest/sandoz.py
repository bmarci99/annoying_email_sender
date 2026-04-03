from __future__ import annotations

import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, List

from ..models import Job
from ..util.http import fetch_with_retry, make_client
from .base import BaseIngester

logger = logging.getLogger("jobs_tracker")

# Sandoz CMS JSON:API endpoint for the job search view.
_CMS_BASE = "https://sandoz-com.cms.sandoz.com"
_JOBS_ENDPOINT = f"{_CMS_BASE}/jsonapi/views/job_search/job_search"
# Internal taxonomy ID for Switzerland in the Sandoz CMS.
_SWITZERLAND_TID = "986"
_ITEMS_PER_PAGE = 10
_DETAIL_BASE = "https://www.sandoz.com/careers/career-search/job-details"


class SandozIngester(BaseIngester):
    """
    Fetches Sandoz Switzerland jobs from the Drupal JSON:API views endpoint.
    The career site at sandoz.com is a Next.js SPA backed by a Drupal CMS.
    This ingester calls the public CMS API directly, filtering by country=CH.
    """

    name = "sandoz"

    def fetch(self) -> List[Job]:
        max_pages = self.cfg.get("max_pages", 50)
        client = make_client(self.http_cfg)
        jobs: List[Job] = []

        try:
            for page in range(max_pages):
                params = {
                    "page": str(page),
                    "views-filter[field_job_functional_area]": "All",
                    "views-filter[field_job_country]": _SWITZERLAND_TID,
                    "views-filter[field_job_alt_country_1]": "",
                    "views-filter[field_job_posted_date][min]": "",
                    "views-filter[field_job_posted_date][max]": "",
                }
                r = fetch_with_retry(client, _JOBS_ENDPOINT, params=params)
                data = r.json()

                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    job = self._parse_item(item)
                    if job:
                        jobs.append(job)

                total = data.get("meta", {}).get("count", 0)
                fetched = (page + 1) * _ITEMS_PER_PAGE
                logger.debug(
                    f"sandoz page {page}: {len(items)} items (total={total})"
                )
                if fetched >= total:
                    break
        finally:
            client.close()

        return jobs

    @staticmethod
    def _parse_item(item: Dict[str, Any]) -> Job | None:
        attrs = item.get("attributes", {})
        req_id = attrs.get("field_job_id", "")
        title = attrs.get("title", "")
        if not req_id or not title:
            return None

        slug = (attrs.get("path") or {}).get("alias", "").strip("/")
        detail_url = f"{_DETAIL_BASE}/{req_id}//{slug}" if slug else f"{_DETAIL_BASE}/{req_id}"
        posted = _parse_date(attrs.get("field_date"))

        job = Job(
            id=f"sandoz:{req_id}",
            employer="sandoz",
            title=title,
            url=detail_url,
            location="Switzerland",
            site=attrs.get("field_job_work_location", ""),
            department=attrs.get("field_job_business_unit", ""),
            employment_type=_emp_type(attrs),
            posted_date=posted,
        )
        job.compute_hash()
        return job


def _parse_date(raw: str | None) -> dt_date | None:
    if not raw:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return dt_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _emp_type(attrs: Dict[str, Any]) -> str:
    parts = []
    if attrs.get("field_job_employment_type"):
        parts.append(attrs["field_job_employment_type"])
    if attrs.get("field_job_type"):
        parts.append(attrs["field_job_type"])
    return ", ".join(parts) if parts else ""
