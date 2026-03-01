# send_email.py
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from helpers import get_output_run_dir


def main():
    run_dir = get_output_run_dir("outputs")
    html_path = run_dir / "weekly_report.html"

    if not html_path.exists():
        raise FileNotFoundError(f"Missing {html_path}")

    html = html_path.read_text(encoding="utf-8")

    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("GMAIL_TO", sender)

    msg = EmailMessage()
    msg["Subject"] = f"Novartis Jobs Digest — {run_dir.name}"
    msg["From"] = sender
    msg["To"] = recipient

    msg.set_content("Your email client does not support HTML. Please view the report on GitHub.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print("Email sent.")


if __name__ == "__main__":
    main()