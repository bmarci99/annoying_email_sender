from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..util.logging import setup_logger

logger, _ = setup_logger()

_INDEX_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Swiss Jobs Tracker — Archive</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 720px; margin: 40px auto; padding: 0 20px; color: #1a1a1a;
    }}
    h1 {{ color: #0066cc; }}
    ul {{ list-style: none; padding: 0; }}
    li {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
    a {{ color: #0066cc; text-decoration: none; font-weight: 500; }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ color: #888; font-size: 13px; margin-left: 8px; }}
  </style>
</head>
<body>
  <h1>🇨🇭 Swiss Jobs Tracker — Archive</h1>
  <p>Daily digests tracking Novartis · Sandoz · Roche · BIS · ECB</p>
  <ul>
{entries}
  </ul>
  <hr/>
  <p style="font-size: 12px; color: #888;">
    Updated {updated} · <a href="feed.xml">RSS Feed</a>
  </p>
</body>
</html>
"""

_RSS_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Swiss Jobs Tracker</title>
    <description>Daily job digests from top Swiss employers</description>
    <link>https://github.com</link>
    <lastBuildDate>{build_date}</lastBuildDate>
{items}
  </channel>
</rss>
"""


def build_site(html: str, date: str, archive_dir: str) -> None:
    """
    Build a simple static archive site.

    - archive_dir/YYYY-MM-DD.html  — daily snapshot
    - archive_dir/index.html       — listing page
    - archive_dir/feed.xml         — RSS feed
    """
    root = Path(archive_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Write daily page
    daily_path = root / f"{date}.html"
    daily_path.write_text(html, encoding="utf-8")
    logger.info(f"Archive page → {daily_path}")

    # Discover all daily pages (sorted newest first)
    pages = sorted(root.glob("????-??-??.html"), reverse=True)

    # Build index
    entries_html = []
    for p in pages[:90]:  # keep last ~3 months in index
        d = p.stem
        entries_html.append(f'    <li><a href="{p.name}">{d}</a></li>')

    index_html = _INDEX_TEMPLATE.format(
        entries="\n".join(entries_html),
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    (root / "index.html").write_text(index_html, encoding="utf-8")

    # Build RSS
    items: List[str] = []
    for p in pages[:20]:
        d = p.stem
        items.append(
            f"    <item>\n"
            f"      <title>Swiss Jobs Digest — {d}</title>\n"
            f"      <link>{p.name}</link>\n"
            f"      <pubDate>{d}</pubDate>\n"
            f"    </item>"
        )
    rss = _RSS_TEMPLATE.format(
        build_date=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        items="\n".join(items),
    )
    (root / "feed.xml").write_text(rss, encoding="utf-8")
