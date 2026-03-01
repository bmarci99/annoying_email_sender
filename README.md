<p align="center">
  <img src="misc/me_rn.gif" width="300" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-blue" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-brightgreen?logo=githubactions" />
  <img src="https://img.shields.io/badge/Scheduler-Weekly-orange" />
  <img src="https://img.shields.io/badge/Status-Production-success" />
</p>

## 👀 What This Does

Every week it:

* Scrapes some careers
* Gets job detail pages
* Converts HTML → Markdown
* Builds a nicely formatted HTML digest
* Sends an email

---

## Locations Monitored
Currently watching: 🇨🇭 🇩🇪 🇱🇺 🇲🇹🇶🇦🇨🇾

---

## Stack

* Python
* `uv` for dependency management
* `httpx`
* `markdownify`
* GitHub Actions (weekly scheduler)
* Gmail SMTP (App Password)

---

## How It Works

```text
main.py
 ├─ fetch listings
 ├─ create job folders
 ├─ convert HTML → markdown
 ├─ render HTML digest
 └─ (optional) send email
```


---

## Run It Locally

Install dependencies:

```
uv sync
```

Run without email:

```
uv run python main.py
```

Run + email yourself:

```
uv run python main.py --send-email
```

---

## Weekly Automation

---

## Possible Upgrades


* Only notify on new REQ IDs
* Keyword filters (AI, SAP, Data, etc.)
* Highlight new jobs
* Send to Slack/Telegram
* Track trends over time

---
