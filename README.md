<p align="center">
  <img src="misc/me_rn.gif" width="300" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-blue" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-brightgreen?logo=githubactions" />
  <img src="https://img.shields.io/badge/Scheduler-Daily-orange" />
  <img src="https://img.shields.io/badge/Status-Production-success" />
  <img src="https://img.shields.io/badge/Employers-5-blueviolet" />
</p>

# Swiss Jobs Tracker

Automated daily job monitoring for top Swiss and European employers. Tracks new postings at **Novartis**, **Sandoz**, **Roche**, **BIS**, and **ECB**, delivering HTML/Markdown digests via email and a GitHub Pages archive.

## Architecture

```
config.yaml -> INGEST (5 scrapers) -> DIFF (history) -> RENDER (HTML/MD/JSON) -> DELIVER (email + archive)
```

## Employers

| Employer | Strategy | Region |
|----------|----------|--------|
| **Novartis** | HTML scraping (paginated) | Switzerland |
| **Sandoz** | HTML scraping (Drupal CMS) | Switzerland |
| **Roche** | Workday JSON API + fallback HTML | Switzerland |
| **BIS** | RSS feed | Basel |
| **ECB** | HTML scraping | Frankfurt (all) |

## Quick Start

```bash
# Install (requires uv)
uv sync

# Run pipeline (no email)
uv run python -m jobs_tracker

# Run with email delivery
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
uv run python -m jobs_tracker --send-email
```

## Configuration

Edit `config.yaml` to enable/disable employers, adjust scraping limits, set history rolling window (default: 30 days), and configure output paths.

## Outputs

| File | Description |
|------|-------------|
| `outputs/digest.html` | Styled HTML email digest |
| `outputs/digest.md` | Markdown summary |
| `outputs/digest.json` | Machine-readable full data |
| `outputs/history.json` | Rolling job history for diff |
| `outputs/run_stats.json` | Pipeline execution stats |
| `docs/` | GitHub Pages archive site |

## GitHub Actions

- **Daily** (Mon-Fri 07:00 CET) - scrape, diff, email if changes, commit archive
- **Weekly** (Monday 08:00 CET) - full scan with forced email

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GMAIL_ADDRESS` | Sender Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `GMAIL_TO` | Recipient email (defaults to sender) |

## Tests

```bash
uv run pytest
```

## Project Structure

```
src/jobs_tracker/
  main.py              # pipeline orchestrator
  models.py            # Pydantic Job model
  ingest/              # 5 employer scrapers
  render/              # HTML, Markdown, archive site
  delivery/            # Gmail SMTP
  util/                # http client, history, logging
```
