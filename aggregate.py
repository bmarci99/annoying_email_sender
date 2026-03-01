from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from helpers import get_output_run_dir


REQ_RE = re.compile(r"\bREQ-\d+\b")
APPLY_RE = re.compile(r"\(https?://[^)]+myworkdayjobs\.com[^)]+\)")
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Simple "Field\nValue" blocks often appear near the bottom
FIELD_RE = re.compile(r"^(Division|Business Unit|Location|Site|Functional Area|Job Type|Employment Type)\s*\n(.+)$", re.MULTILINE)

# Date line often appears as: "Feb 26, 2026"
DATE_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b")

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

@dataclass
class JobRecord:
    req_id: str
    title: str
    posted_date: str
    country: str
    location: str
    site: str
    division: str
    business_unit: str
    functional_area: str
    job_type: str
    employment_type: str
    apply_url: str
    details_url: str
    summary: str
    content_hash: str
    job_folder: str

def extract_first(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return m.group(0) if m else ""

def extract_title(text: str) -> str:
    m = TITLE_RE.search(text)
    return (m.group(1).strip() if m else "").strip()

def extract_apply_url(text: str) -> str:
    # markdownify shows: [Apply to Job](https://...)
    m = re.search(r"\[Apply to Job\]\((https?://[^)]+)\)", text)
    return m.group(1).strip() if m else ""

def extract_summary(text: str, max_chars: int = 400) -> str:
    # Try to capture Summary section
    m = re.search(r"###\s+Summary\s+(.+?)(?:###\s+About the Role|###\s+About|##\s+|$)", text, flags=re.S)
    if not m:
        return ""
    s = re.sub(r"\s+", " ", m.group(1)).strip()
    return s[:max_chars]

def parse_fields(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {
        "Division": "",
        "Business Unit": "",
        "Location": "",
        "Site": "",
        "Functional Area": "",
        "Job Type": "",
        "Employment Type": "",
    }
    for k, v in FIELD_RE.findall(text):
        out[k] = v.strip()
    return out

def load_meta(job_dir: Path) -> Dict[str, str]:
    meta_path = job_dir / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}

def load_markdown(job_dir: Path) -> str:
    md_path = job_dir / "extracted.md"
    if md_path.exists():
        return md_path.read_text(encoding="utf-8", errors="ignore")
    # fallback if you still have details.html only: skip
    return ""

def build_record(job_dir: Path) -> Optional[JobRecord]:
    md = load_markdown(job_dir)
    if not md.strip():
        return None

    meta = load_meta(job_dir)
    details_url = meta.get("details_url", "")

    req_id = extract_first(REQ_RE, md)
    title = extract_title(md) or meta.get("title", "")

    posted_date = extract_first(DATE_RE, md)
    fields = parse_fields(md)

    apply_url = extract_apply_url(md)

    summary = extract_summary(md)

    # prefer structured fields, fallback to meta
    country = fields.get("Location", "") or meta.get("location", "")
    location = fields.get("Location", "") or meta.get("location", "")
    site = fields.get("Site", "") or meta.get("site", "")
    division = fields.get("Division", "") or meta.get("business", "")
    business_unit = fields.get("Business Unit", "")
    functional_area = fields.get("Functional Area", "")
    job_type = fields.get("Job Type", "")
    employment_type = fields.get("Employment Type", "")

    content_hash = sha1(md)

    return JobRecord(
        req_id=req_id,
        title=title,
        posted_date=posted_date,
        country=country,
        location=location,
        site=site,
        division=division,
        business_unit=business_unit,
        functional_area=functional_area,
        job_type=job_type,
        employment_type=employment_type,
        apply_url=apply_url,
        details_url=details_url,
        summary=summary,
        content_hash=content_hash,
        job_folder=job_dir.name,
    )

def find_latest_previous_run(outputs_dir: Path, current_run: Path) -> Optional[Path]:
    runs = sorted([p for p in outputs_dir.iterdir() if p.is_dir() and p.name != current_run.name])
    return runs[-1] if runs else None

def load_master_json(run_dir: Path) -> Dict[str, JobRecord]:
    p = run_dir / "jobs_master.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out: Dict[str, JobRecord] = {}
    for row in data:
        out[row["req_id"]] = JobRecord(**row)
    return out

def write_outputs(run_dir: Path, records: List[JobRecord]) -> None:
    # JSON
    (run_dir / "jobs_master.json").write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # CSV
    csv_path = run_dir / "jobs_master.csv"
    cols = list(asdict(records[0]).keys()) if records else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow(asdict(r))

    # Markdown digest
    md_lines = [f"# Jobs digest ({run_dir.name})", ""]
    for r in sorted(records, key=lambda x: (x.country, x.site, x.title)):
        md_lines += [
            f"## {r.title}",
            f"- **REQ:** {r.req_id}",
            f"- **Posted:** {r.posted_date}",
            f"- **Location:** {r.location} | **Site:** {r.site}",
            f"- **Division:** {r.division} | **Business Unit:** {r.business_unit}",
            f"- **Functional Area:** {r.functional_area}",
            f"- **Type:** {r.job_type} | **Employment:** {r.employment_type}",
            f"- **Apply:** {r.apply_url}" if r.apply_url else "- **Apply:**",
            f"- **Details:** {r.details_url}",
        ]
        if r.summary:
            md_lines += [f"- **Summary:** {r.summary}"]
        md_lines.append("")

    (run_dir / "jobs_master.md").write_text("\n".join(md_lines), encoding="utf-8")

def write_diff(run_dir: Path, prev_dir: Optional[Path]) -> None:
    current = load_master_json(run_dir)
    prev = load_master_json(prev_dir) if prev_dir else {}

    new_ids = sorted(set(current) - set(prev))
    removed_ids = sorted(set(prev) - set(current))

    changed_ids = sorted(
        rid for rid in set(current) & set(prev)
        if current[rid].content_hash != prev[rid].content_hash
    )

    diff = {
        "run": run_dir.name,
        "prev_run": prev_dir.name if prev_dir else None,
        "new": new_ids,
        "removed": removed_ids,
        "changed": changed_ids,
    }
    (run_dir / "diff.json").write_text(json.dumps(diff, indent=2), encoding="utf-8")

    # Human-readable
    lines = [f"# Diff ({run_dir.name})", ""]
    lines.append(f"Prev run: {prev_dir.name if prev_dir else '(none)'}")
    lines.append("")
    lines.append(f"## New ({len(new_ids)})")
    for rid in new_ids:
        r = current[rid]
        lines.append(f"- {r.title} ({rid}) — {r.site} — {r.apply_url or r.details_url}")
    lines.append("")
    lines.append(f"## Removed ({len(removed_ids)})")
    for rid in removed_ids:
        r = prev[rid]
        lines.append(f"- {r.title} ({rid}) — {r.site}")
    lines.append("")
    lines.append(f"## Changed ({len(changed_ids)})")
    for rid in changed_ids:
        r = current[rid]
        lines.append(f"- {r.title} ({rid}) — {r.site} — {r.apply_url or r.details_url}")
    lines.append("")

    (run_dir / "diff.md").write_text("\n".join(lines), encoding="utf-8")

    # Notification payload (short)
    notify_lines = []
    if new_ids:
        notify_lines.append(f"New jobs ({len(new_ids)}):")
        for rid in new_ids[:10]:
            r = current[rid]
            notify_lines.append(f"- {r.title} ({rid}) — {r.site}")
    if changed_ids:
        notify_lines.append(f"\nUpdated jobs ({len(changed_ids)}):")
        for rid in changed_ids[:10]:
            r = current[rid]
            notify_lines.append(f"- {r.title} ({rid}) — {r.site}")
    if not notify_lines:
        notify_lines = ["No new or updated jobs."]

    (run_dir / "notify.txt").write_text("\n".join(notify_lines) + "\n", encoding="utf-8")

def main():
    outputs_dir = Path("outputs")
    run_dir = get_output_run_dir(outputs_dir)

    records: List[JobRecord] = []
    for job_dir in sorted(run_dir.glob("JOB_*")):
        rec = build_record(job_dir)
        if rec and rec.req_id:
            records.append(rec)

    write_outputs(run_dir, records)

    prev = find_latest_previous_run(outputs_dir, run_dir)
    write_diff(run_dir, prev)

    print(f"Aggregated {len(records)} jobs in {run_dir}")
    print(f"Wrote: jobs_master.csv, jobs_master.md, diff.md/json, notify.txt")

if __name__ == "__main__":
    main()