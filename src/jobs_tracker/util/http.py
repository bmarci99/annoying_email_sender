from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("jobs_tracker")

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def make_client(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    timeout_s: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
) -> httpx.Client:
    """Build an httpx.Client with shared defaults from config."""
    cfg = cfg or {}
    timeout = cfg.get("timeout_s", timeout_s)
    ua = cfg.get("user_agent", _DEFAULT_UA)
    h = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}
    if headers:
        h.update(headers)
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=h)


def fetch_with_retry(
    client: httpx.Client,
    url: str,
    *,
    method: str = "GET",
    max_retries: int = 3,
    backoff: float = 1.0,
    **kwargs: Any,
) -> httpx.Response:
    """GET/POST with exponential backoff on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code in (429, 502, 503, 504):
                wait = backoff * (2 ** attempt)
                logger.warning(f"HTTP {r.status_code} from {url}, retry in {wait:.1f}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            wait = backoff * (2 ** attempt)
            logger.warning(f"Request error ({exc}), retry {attempt + 1}/{max_retries} in {wait:.1f}s")
            time.sleep(wait)
    raise last_exc or RuntimeError(f"Failed after {max_retries} retries: {url}")
