<p align="center">
  <img src="misc/me_rn.gif" width="260" />
</p>

<h1 align="center">🇨🇭 Swiss Jobs Tracker</h1>

<p align="center">
  <strong>Automated weekly career monitoring for top Swiss &amp; European employers</strong><br/>
  <sub>Scrapes · Diffs · Renders · Delivers — while you sleep</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" />
  <img src="https://img.shields.io/badge/schedule-Monday_08%3A00_CET-FF6F00?style=for-the-badge&logo=clockify&logoColor=white" />
  <img src="https://img.shields.io/badge/status-production-2E7D32?style=for-the-badge" />
</p>

<p align="center">
  <a href="https://bmarci99.github.io/annoying_email_sender/">📄 Live Archive</a> ·
  <a href="#quick-start">🚀 Quick Start</a> ·
  <a href="#how-it-works">⚙️ How It Works</a>
</p>

---

## What Is This?

Every Monday morning, this pipeline wakes up, scrapes career pages at **5 major employers**, compares against last week's results, and sends a styled email digest + publishes an archive page. Zero manual effort.

### Tracked Employers

<table>
  <tr>
    <td align="center"><strong>💊 Novartis</strong><br/><sub>HTML scraping · paginated</sub><br/><code>Switzerland</code></td>
    <td align="center"><strong>💊 Sandoz</strong><br/><sub>Drupal JSON API</sub><br/><code>Switzerland</code></td>
    <td align="center"><strong>🧬 Roche</strong><br/><sub>Workday API + HTML fallback</sub><br/><code>Switzerland</code></td>
    <td align="center"><strong>🏦 BIS</strong><br/><sub>RSS feed</sub><br/><code>Basel</code></td>
    <td align="center"><strong>🏛️ ECB</strong><br/><sub>HTML scraping</sub><br/><code>Frankfurt</code></td>
  </tr>
</table>

---

## How It Works

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐     ┌────────────────────┐
│  config.yaml │ ──▶ │  INGEST       │ ──▶ │  DIFF        │ ──▶ │  RENDER + DELIVER  │
│              │     │  5 scrapers   │     │  vs history  │     │  HTML · MD · JSON  │
│              │     │  (parallel)   │     │  new/removed │     │  email · GH Pages  │
└─────────────┘     └───────────────┘     └──────────────┘     └────────────────────┘
```

**Key features:**
- 🔄 **30-day rolling history** — detects new & removed postings automatically
- 📧 **Email digest** — styled HTML email via Gmail SMTP, only when there are changes
- 🌐 **GitHub Pages archive** — browsable history + RSS feed
- ⚡ **Fast & resilient** — async HTTP with retries, backoff, and per-scraper error isolation
- 🛠️ **Fully configurable** — toggle employers, limits, output formats via `config.yaml`

---

## Quick Start

```bash
# 1. Install (requires uv)
uv sync

# 2. Run the pipeline
uv run python -m jobs_tracker

# 3. (Optional) Run with email delivery
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
uv run python -m jobs_tracker --send-email
```

---

## Outputs

| File | What |
|:-----|:-----|
| `outputs/digest.html` | 📨 Styled email-ready digest |
| `outputs/digest.md` | 📝 Markdown summary |
| `outputs/digest.json` | 🔗 Machine-readable full data |
| `outputs/history.json` | 🗂️ Rolling 30-day job history |
| `outputs/run_stats.json` | 📊 Pipeline execution stats |
| `docs/` | 🌐 GitHub Pages archive site |

---

## CI / CD

Fully automated via **GitHub Actions** — no human in the loop.

| Workflow | Schedule | What it does |
|:---------|:---------|:-------------|
| **Weekly Full Scan** | Monday 08:00 CET | Scrape → diff → email → commit archive |

<details>
<summary><strong>Required Secrets</strong></summary>

| Secret | Description |
|:-------|:------------|
| `GMAIL_ADDRESS` | Sender Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `GMAIL_TO` | Recipient email (defaults to sender) |

</details>

---

## Project Structure

```
src/jobs_tracker/
  ├── main.py           # pipeline orchestrator
  ├── models.py         # Pydantic Job model
  ├── ingest/           # 5 employer scrapers
  ├── render/           # HTML, Markdown, archive site
  ├── delivery/         # Gmail SMTP sender
  └── util/             # http client, history, logging
```

## Tests

```bash
uv run pytest
```

---

<p align="center">
  <sub>Built with 🐍 Python · Automated with GitHub Actions · Delivered to your inbox</sub>
</p>
