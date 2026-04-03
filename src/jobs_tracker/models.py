from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, HttpUrl


Employer = Literal["novartis", "sandoz", "roche", "bis", "ecb"]


class Job(BaseModel):
    """Canonical job record shared by every ingester."""

    id: str                                   # e.g. "novartis:REQ-12345"
    employer: Employer
    title: str
    url: HttpUrl
    apply_url: Optional[HttpUrl] = None

    location: str = ""                        # country or region
    site: str = ""                            # office / campus
    department: str = ""                      # business unit / division

    posted_date: Optional[date] = None
    deadline: Optional[date] = None           # BIS / ECB have these
    employment_type: str = ""                 # Full-time / Part-time / Internship

    summary: Optional[str] = None             # max ~400 chars
    first_seen: datetime = datetime.now(timezone.utc)
    content_hash: str = ""

    def compute_hash(self) -> str:
        """SHA-1 over the stable identity fields."""
        blob = f"{self.id}|{self.title}|{self.location}|{self.site}|{self.department}|{self.employment_type}"
        self.content_hash = hashlib.sha1(blob.encode()).hexdigest()[:12]
        return self.content_hash
