# html_to_md_runner.py
from __future__ import annotations

import sys
from pathlib import Path
from markdownify import markdownify as md


def main(run_dir: str) -> None:
    run_path = Path(run_dir)
    ok = 0
    for jd in sorted(run_path.glob("JOB_*")):
        html_path = jd / "details.html"
        out_path = jd / "extracted.md"

        if not html_path.exists():
            continue
        if out_path.exists() and out_path.stat().st_size > 0:
            continue

        html = html_path.read_text(encoding="utf-8", errors="ignore")
        out_path.write_text(md(html) + "\n", encoding="utf-8")
        ok += 1

    print(f"Converted {ok} jobs → markdown in {run_dir}")


if __name__ == "__main__":
    main(sys.argv[1])