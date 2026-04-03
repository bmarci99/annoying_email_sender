from __future__ import annotations

from datetime import date as dt_date, timedelta
from pathlib import Path
from typing import Dict, List, Set

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import Job


_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html(
    jobs: List[Job],
    *,
    new_ids: Set[str] | None = None,
    date: str = "",
) -> str:
    """Render a full HTML digest using Jinja2 template."""
    new_ids = new_ids or set()

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("email.html")

    grouped = _group_by_employer(jobs)
    today = dt_date.today()
    deadline_soon = today + timedelta(days=7)

    return tmpl.render(
        date=date,
        total=len(jobs),
        new_count=len(new_ids),
        grouped=grouped,
        new_ids=new_ids,
        deadline_soon=deadline_soon,
    )


def _group_by_employer(jobs: List[Job]) -> Dict[str, Dict[str, List[Job]]]:
    """employer → location → [jobs] (sorted)."""
    result: Dict[str, Dict[str, List[Job]]] = {}
    for j in jobs:
        by_loc = result.setdefault(j.employer, {})
        by_loc.setdefault(j.location or "Unknown", []).append(j)
    # sort jobs inside each group
    for emp in result:
        for loc in result[emp]:
            result[emp][loc].sort(key=lambda x: x.title)
    return result
