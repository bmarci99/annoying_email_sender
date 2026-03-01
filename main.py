# main.py
from __future__ import annotations

import argparse

from helpers import (
    fetch_all_jobs_from_novartis,
    get_output_run_dir,
    save_jobs_to_csv,
    materialize_job_folders,
)

CAREERS_URL = (
    "https://www.novartis.com/careers/career-search"
    "?search_api_fulltext="
    "&country%5B%5D=LOC_AT"
    "&country%5B%5D=LOC_CY"
    "&country%5B%5D=LOC_DE"
    "&country%5B%5D=LOC_LU"
    "&country%5B%5D=LOC_MT"
    "&country%5B%5D=LOC_QA"
    "&country%5B%5D=LOC_CH"
    "&field_job_posted_date=All"
    "&op=Submit"
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--send-email", action="store_true", help="Send email (default off)")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    jobs = fetch_all_jobs_from_novartis(CAREERS_URL, debug=args.debug)
    run_dir = get_output_run_dir("outputs")

    save_jobs_to_csv(jobs, run_dir, "novartis_selected_countries.csv")
    materialize_job_folders(jobs, run_dir, download_details_html=True)

    # HTML -> MD
    from html_to_md_runner import main as html_to_md
    html_to_md(str(run_dir))

    # MD/meta -> nice HTML digest
    from render_report import main as render_report
    render_report()

    if args.send_email:
        from send_email import main as send_email
        send_email()


if __name__ == "__main__":
    main()