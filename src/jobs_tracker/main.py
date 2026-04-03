from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .ingest.base import BaseIngester
from .ingest.bis import BISIngester
from .ingest.ecb import ECBIngester
from .ingest.novartis import NovartisIngester
from .ingest.roche import RocheIngester
from .ingest.sandoz import SandozIngester
from .models import Job
from .render.digest_html import render_html
from .render.digest_md import render_markdown
from .render.site_builder import build_site
from .delivery.email_sender import send_digest_email
from .util.history import (
    diff_jobs,
    load_history,
    prune_history,
    record_jobs,
    save_history,
)
from .util.logging import section, setup_logger

logger, console = setup_logger()


INGESTERS: Dict[str, type[BaseIngester]] = {
    "novartis": NovartisIngester,
    "sandoz": SandozIngester,
    "roche": RocheIngester,
    "bis": BISIngester,
    "ecb": ECBIngester,
}


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def run_pipeline(cfg: Dict[str, Any], *, send_email: bool = False) -> Dict[str, Any]:
    """
    Full pipeline: ingest → diff → render → deliver.
    Returns run stats dict.
    """
    t0 = time.monotonic()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # --- 1. Ingest ---
    section(console, "INGEST")
    http_cfg = cfg.get("http", {})
    all_jobs: List[Job] = []

    for name, klass in INGESTERS.items():
        employer_cfg = cfg.get("employers", {}).get(name, {})
        if not employer_cfg.get("enabled", True):
            logger.info(f"[dim]{name}[/dim]: disabled, skipping")
            continue

        ingester = klass(employer_cfg, http_cfg)
        jobs = ingester.safe_fetch()
        all_jobs.extend(jobs)

    logger.info(f"Total scraped: [bold]{len(all_jobs)}[/bold] jobs from {len(INGESTERS)} employers")

    # --- 2. Diff against history ---
    section(console, "DIFF")
    hist_path = cfg.get("history", {}).get("path", "outputs/history.json")
    rolling_days = cfg.get("history", {}).get("rolling_days", 30)
    history = load_history(hist_path)
    history = prune_history(history, rolling_days)

    current_dicts = [j.model_dump(mode="json") for j in all_jobs]
    new_jobs, changed_jobs, removed_jobs = diff_jobs(current_dicts, history)

    logger.info(
        f"[green]+{len(new_jobs)} new[/green] · "
        f"[yellow]~{len(changed_jobs)} changed[/yellow] · "
        f"[red]-{len(removed_jobs)} removed[/red] · "
        f"{len(all_jobs)} total"
    )

    # --- 3. Update history ---
    history = record_jobs(history, current_dicts)
    save_history(hist_path, history)

    # --- 4. Render ---
    section(console, "RENDER")
    out_dir = Path(cfg.get("output", {}).get("dir", "outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    digest_data = {
        "date": today,
        "total": len(all_jobs),
        "new": len(new_jobs),
        "changed": len(changed_jobs),
        "removed": len(removed_jobs),
        "jobs": current_dicts,
        "new_jobs": new_jobs,
        "removed_jobs": removed_jobs,
    }
    (out_dir / "digest.json").write_text(
        json.dumps(digest_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Markdown
    md_text = render_markdown(all_jobs, new_ids={j["id"] for j in new_jobs}, date=today)
    (out_dir / "digest.md").write_text(md_text, encoding="utf-8")

    # HTML
    html_text = render_html(all_jobs, new_ids={j["id"] for j in new_jobs}, date=today)
    (out_dir / "digest.html").write_text(html_text, encoding="utf-8")

    logger.info(f"Outputs → {out_dir}/")

    # --- 5. Archive (GitHub Pages) ---
    if cfg.get("output", {}).get("archive", True):
        section(console, "ARCHIVE")
        archive_dir = cfg.get("output", {}).get("archive_dir", "docs")
        build_site(html_text, today, archive_dir)
        logger.info(f"Archive → {archive_dir}/")

    # --- 6. Email ---
    has_changes = len(new_jobs) > 0 or len(changed_jobs) > 0
    send_on_empty = cfg.get("email", {}).get("send_on_empty", False)

    if send_email and (has_changes or send_on_empty):
        section(console, "EMAIL")
        subject_prefix = cfg.get("email", {}).get("subject_prefix", "Swiss Jobs Tracker")
        send_digest_email(html_text, subject=f"{subject_prefix} — {today}")
        logger.info("[green]Email sent[/green]")
    elif send_email:
        logger.info("No new jobs — skipping email")

    # --- 7. Run stats ---
    elapsed = time.monotonic() - t0
    stats = {
        "date": today,
        "elapsed_s": round(elapsed, 1),
        "total_jobs": len(all_jobs),
        "new_jobs": len(new_jobs),
        "changed_jobs": len(changed_jobs),
        "removed_jobs": len(removed_jobs),
        "per_employer": {
            name: sum(1 for j in all_jobs if j.employer == name)
            for name in INGESTERS
        },
    }
    (out_dir / "run_stats.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8"
    )

    section(console, "DONE")
    logger.info(f"Completed in {elapsed:.1f}s")
    return stats


def cli():
    p = argparse.ArgumentParser(description="Swiss Jobs Tracker")
    p.add_argument("--send-email", action="store_true", help="Send digest email")
    p.add_argument("--config", default="config.yaml", help="Config file path")
    args = p.parse_args()

    cfg = load_config(args.config)
    run_pipeline(cfg, send_email=args.send_email)


if __name__ == "__main__":
    cli()
