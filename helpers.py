# helpers.py
from __future__ import annotations

import csv, re, httpx, json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class JobRow:
    title: str
    business: str
    location: str
    site: str
    date_posted: str
    details_url: str


def get_output_run_dir(
    base_dir: str | Path = "outputs",
    *,
    tz: str = "Europe/Berlin",
    now: Optional[datetime] = None,
) -> Path:
    """
    Returns outputs/YYYY-MM-WW where WW is ISO week number (01-53).
    """
    now = now or datetime.now(ZoneInfo(tz))
    iso_year, iso_week, _ = now.isocalendar()
    month = now.strftime("%m")
    return Path(base_dir) / f"{iso_year}-{month}-{iso_week:02d}"


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


_slug_re = re.compile(r"[^a-zA-Z0-9_-]+")


def slugify(s: str, max_len: int = 80) -> str:
    s = s.strip().lower().replace(" ", "-")
    s = _slug_re.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:max_len] if len(s) > max_len else s


def _set_or_replace_query_param(url: str, key: str, value: str) -> str:
    """
    Returns url with query param key set to value (replacing any existing key).
    Preserves all other params (including repeated ones like country[]).
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs[key] = [value]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _parse_results_page(html: str, base_url: str = "https://www.novartis.com") -> List[JobRow]:
    soup = BeautifulSoup(html, "html.parser")

    # all job detail links
    links = soup.select('a[href^="/careers/career-search/job/details/"]')

    rows: List[JobRow] = []
    seen = set()

    for a in links:
        href = a.get("href") or ""
        title = a.get_text(strip=True)
        if not href or not title:
            continue

        details_url = href if href.startswith("http") else f"{base_url}{href}"
        if details_url in seen:
            continue
        seen.add(details_url)

        # Find nearest "row" container: try common patterns first
        row = a.find_parent(["tr", "li"])
        if row is None:
            # fallback: div-based listings
            row = a.find_parent("div")
        if row is None:
            continue

        # Extract "cell-ish" chunks: table cells or divs that look like columns
        cells = row.find_all(["td", "div", "span"], recursive=True)

        # Collect distinct visible chunks in order
        chunks: List[str] = []
        for c in cells:
            txt = c.get_text(" ", strip=True)
            if not txt:
                continue
            # avoid duplicates and huge blobs
            if txt in chunks:
                continue
            if len(txt) > 120:
                continue
            chunks.append(txt)

        # Remove title chunk(s)
        chunks = [c for c in chunks if c != title]

        # Heuristic: pick the first 4 “column values” after title
        business = chunks[0] if len(chunks) > 0 else ""
        location = chunks[1] if len(chunks) > 1 else ""
        site = chunks[2] if len(chunks) > 2 else ""
        date_posted = chunks[3] if len(chunks) > 3 else ""

        rows.append(
            JobRow(
                title=title,
                business=business,
                location=location,
                site=site,
                date_posted=date_posted,
                details_url=details_url,
            )
        )

    return rows


def fetch_all_jobs_from_novartis(
    careers_url: str,
    *,
    timeout_s: float = 30.0,
    max_pages: int = 200,
    debug: bool = False,
) -> List[JobRow]:
    """
    Paginates novartis.com/careers/career-search by adding/overwriting the `page` param.

    Stops when a page returns zero jobs.
    """
    jobs: List[JobRow] = []

    with httpx.Client(timeout=timeout_s, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    }) as client:
        for page in range(max_pages):
            url = _set_or_replace_query_param(careers_url, "page", str(page))
            r = client.get(url)
            if debug:
                print("GET", r.status_code, url)
            r.raise_for_status()

            page_jobs = _parse_results_page(r.text)
            if debug:
                print(f"  parsed {len(page_jobs)} jobs on page {page}")

            if not page_jobs:
                break

            jobs.extend(page_jobs)

    # De-dup by details_url
    uniq: Dict[str, JobRow] = {j.details_url: j for j in jobs}
    return list(uniq.values())


def save_jobs_to_csv(
    jobs: Iterable[JobRow],
    out_dir: str | Path,
    filename: str = "novartis_jobs.csv",
) -> Path:
    out_path = ensure_dir(Path(out_dir)) / filename

    jobs_list = list(jobs)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "business", "location", "site", "datePosted", "details_url"])
        for j in jobs_list:
            w.writerow([j.title, j.business, j.location, j.site, j.date_posted, j.details_url])

    print(f"Saved {len(jobs_list)} jobs → {out_path}")
    return out_path

def materialize_job_folders(
    jobs: Sequence[JobRow],
    run_dir: str | Path,
    *,
    write_index_csv: bool = True,
    download_details_html: bool = True,
    timeout_s: float = 30.0,
) -> List[Path]:
    """
    Creates:
      outputs/YYYY-MM-WW/
        jobs_index.csv (optional)
        JOB_0001_<slug>/
          meta.json
          details_url.txt
          details.html (optional)

    Returns list of created job folder paths.
    """
    run_dir = ensure_dir(Path(run_dir))
    created: List[Path] = []

    # Optional index CSV mapping JOB_xxx -> details_url
    if write_index_csv:
        idx_path = run_dir / "jobs_index.csv"
        with open(idx_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["job_folder", "title", "details_url"])
            for i, j in enumerate(jobs, start=1):
                folder_name = f"JOB_{i:04d}_{slugify(j.title)}"
                w.writerow([folder_name, j.title, j.details_url])

    client = httpx.Client(timeout=timeout_s, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    }) if download_details_html else None

    try:
        for i, j in enumerate(jobs, start=1):
            folder = ensure_dir(run_dir / f"JOB_{i:04d}_{slugify(j.title)}")

            # Write minimal metadata (good handoff for crawl4ai)
            meta = {
                "title": j.title,
                "business": j.business,
                "location": j.location,
                "site": j.site,
                "datePosted": j.date_posted,
                "details_url": j.details_url,
            }
            (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            (folder / "details_url.txt").write_text(j.details_url + "\n", encoding="utf-8")

            html_path = folder / "details.html"

            if download_details_html:
                if not html_path.exists():  # don't re-fetch if already there
                    r = client.get(j.details_url)
                    r.raise_for_status()
                    html_path.write_text(r.text, encoding="utf-8")

            created.append(folder)
    finally:
        if client is not None:
            client.close()

    print(f"Created {len(created)} job folders → {run_dir}")
    return created