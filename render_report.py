# render_report.py
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List
from helpers import get_output_run_dir

REQ_RE = re.compile(r"\bREQ-\d+\b")


def extract_req(md: str) -> str:
    m = REQ_RE.search(md)
    return m.group(0) if m else ""


def extract_title(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def extract_apply(md: str) -> str:
    m = re.search(r"\[Apply to Job\]\((https?://[^)]+)\)", md)
    return m.group(1) if m else ""


def extract_posted(md: str) -> str:
    m = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b", md)
    return m.group(0) if m else ""


def safe(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def main():
    run_dir = get_output_run_dir("outputs")
    job_dirs = sorted(run_dir.glob("JOB_*"))

    jobs: List[Dict[str, str]] = []
    for jd in job_dirs:
        md_path = jd / "extracted.md"
        meta_path = jd / "meta.json"
        if not md_path.exists():
            continue

        md = md_path.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(md)
        req = extract_req(md)
        apply_url = extract_apply(md)
        posted = extract_posted(md)

        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        jobs.append({
            "req": req,
            "title": title or meta.get("title", ""),
            "posted": posted or meta.get("datePosted", ""),
            "country": meta.get("location", ""),
            "site": meta.get("site", ""),
            "details_url": meta.get("details_url", ""),
            "apply_url": apply_url,
            "folder": jd.name,
        })

    # group by country then site
    groups: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for j in jobs:
        country = j["country"] or "Unknown"
        site = j["site"] or "Unknown"
        groups.setdefault(country, {}).setdefault(site, []).append(j)

    # sort inside groups
    for country in groups:
        for site in groups[country]:
            groups[country][site].sort(key=lambda x: (x["title"], x["req"]))

    title = f"Novartis Jobs Digest — {run_dir.name}"
    html_parts = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'/>",
        f"<title>{safe(title)}</title>",
        """
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
          h1 { font-size: 20px; margin: 0 0 12px; }
          .meta { color: #555; margin-bottom: 18px; }
          h2 { font-size: 16px; margin-top: 20px; border-top: 1px solid #eee; padding-top: 14px; }
          h3 { font-size: 14px; margin: 14px 0 8px; color: #333; }
          table { width: 100%; border-collapse: collapse; }
          th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
          th { background: #fafafa; font-weight: 600; }
          a { color: #0b57d0; text-decoration: none; }
          a:hover { text-decoration: underline; }
          .pill { display: inline-block; padding: 2px 8px; border: 1px solid #ddd; border-radius: 999px; font-size: 12px; color: #444; margin-right: 6px; }
          .small { color: #666; font-size: 12px; }
        </style>
        """,
        "</head><body>",
        f"<h1>{safe(title)}</h1>",
        "<div class='meta'>Weekly listing for selected countries. Click <b>Apply</b> to open Workday.</div>",
    ]

    for country in sorted(groups.keys()):
        html_parts.append(f"<h2>{safe(country)}</h2>")
        for site in sorted(groups[country].keys()):
            html_parts.append(f"<h3>{safe(site)}</h3>")
            html_parts.append("<table>")
            html_parts.append("<tr><th>Title</th><th>REQ</th><th>Posted</th><th>Links</th></tr>")
            for j in groups[country][site]:
                links = []
                if j["apply_url"]:
                    links.append(f"<a href='{safe(j['apply_url'])}'>Apply</a>")
                if j["details_url"]:
                    links.append(f"<a href='{safe(j['details_url'])}'>Details</a>")
                link_html = " | ".join(links) if links else ""
                html_parts.append(
                    "<tr>"
                    f"<td>{safe(j['title'])}</td>"
                    f"<td><span class='pill'>{safe(j['req'])}</span></td>"
                    f"<td class='small'>{safe(j['posted'])}</td>"
                    f"<td>{link_html}</td>"
                    "</tr>"
                )
            html_parts.append("</table>")

    html_parts.append("</body></html>")
    out_path = run_dir / "weekly_report.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()