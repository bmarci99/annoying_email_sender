from __future__ import annotations

from typing import Dict, List, Set

from ..models import Job


def render_markdown(
    jobs: List[Job], *, new_ids: Set[str] | None = None, date: str = ""
) -> str:
    """Render a Markdown digest grouped by employer → location."""
    new_ids = new_ids or set()
    lines: List[str] = []

    lines.append(f"# Swiss Jobs Tracker — {date}")
    lines.append("")
    lines.append(f"**{len(jobs)}** total tracked · **{len(new_ids)}** new")
    lines.append("")

    grouped = _group_by_employer(jobs)

    for employer, emp_jobs in sorted(grouped.items()):
        badge_count = sum(1 for j in emp_jobs if j.id in new_ids)
        new_badge = f" (+{badge_count} new)" if badge_count else ""
        lines.append(f"## {employer.upper()}{new_badge}")
        lines.append("")

        by_location = _group_by(emp_jobs, "location")
        for loc, loc_jobs in sorted(by_location.items()):
            lines.append(f"### {loc or 'Unknown'}")
            lines.append("")
            for j in sorted(loc_jobs, key=lambda x: x.title):
                flag = " 🆕" if j.id in new_ids else ""
                deadline = f" ⏰ {j.deadline}" if j.deadline else ""
                posted = f" ({j.posted_date})" if j.posted_date else ""
                dept = f" — {j.department}" if j.department else ""
                lines.append(f"- [{j.title}]({j.url}){dept}{posted}{deadline}{flag}")
            lines.append("")

    lines.append("---")
    lines.append(f"_Generated {date} by [Swiss Jobs Tracker](https://github.com/)_")
    return "\n".join(lines)


def _group_by_employer(jobs: List[Job]) -> Dict[str, List[Job]]:
    groups: Dict[str, List[Job]] = {}
    for j in jobs:
        groups.setdefault(j.employer, []).append(j)
    return groups


def _group_by(jobs: List[Job], attr: str) -> Dict[str, List[Job]]:
    groups: Dict[str, List[Job]] = {}
    for j in jobs:
        key = getattr(j, attr, "") or ""
        groups.setdefault(key, []).append(j)
    return groups
