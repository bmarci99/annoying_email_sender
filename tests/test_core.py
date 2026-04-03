"""Tests for models, history utilities, and renderers."""
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from jobs_tracker.models import Job
from jobs_tracker.util.history import (
    diff_jobs,
    load_history,
    prune_history,
    record_jobs,
    save_history,
)
from jobs_tracker.render.digest_md import render_markdown
from jobs_tracker.render.digest_html import render_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_job(**overrides) -> Job:
    defaults = dict(
        id="novartis:REQ-001",
        employer="novartis",
        title="Data Scientist",
        url="https://example.com/jobs/001",
        location="Basel, Switzerland",
        site="Campus",
        department="Data Science",
        posted_date=date(2024, 6, 1),
    )
    defaults.update(overrides)
    j = Job(**defaults)
    j.compute_hash()
    return j


@pytest.fixture
def sample_jobs():
    return [
        _make_job(),
        _make_job(id="roche:JR-002", employer="roche", title="ML Engineer",
                  url="https://example.com/jobs/002", location="Zurich"),
        _make_job(id="bis:jr100001", employer="bis", title="Economist",
                  url="https://example.com/jobs/003", location="Basel"),
    ]


@pytest.fixture
def tmp_history(tmp_path):
    return tmp_path / "history.json"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestJob:
    def test_create_minimal(self):
        j = _make_job()
        assert j.employer == "novartis"
        assert j.content_hash  # not empty after compute_hash

    def test_hash_deterministic(self):
        a = _make_job()
        b = _make_job()
        assert a.content_hash == b.content_hash

    def test_hash_changes_on_title(self):
        a = _make_job()
        b = _make_job(title="Different Title")
        assert a.content_hash != b.content_hash


# ---------------------------------------------------------------------------
# History tests
# ---------------------------------------------------------------------------

class TestHistory:
    def test_load_empty(self, tmp_history):
        h = load_history(tmp_history)
        assert h == {"items": []}

    def test_round_trip(self, tmp_history):
        data = {"items": [{"id": "x", "first_seen": "2024-01-01T00:00:00+00:00"}]}
        save_history(tmp_history, data)
        h = load_history(tmp_history)
        assert len(h["items"]) == 1
        assert h["items"][0]["id"] == "x"

    def test_diff_new_jobs(self):
        history = {"items": []}
        current = [{"id": "a", "content_hash": "abc"}]
        new, changed, removed = diff_jobs(current, history)
        assert len(new) == 1
        assert len(changed) == 0
        assert len(removed) == 0

    def test_diff_changed_jobs(self):
        history = {"items": [{"id": "a", "content_hash": "old"}]}
        current = [{"id": "a", "content_hash": "new"}]
        new, changed, removed = diff_jobs(current, history)
        assert len(new) == 0
        assert len(changed) == 1

    def test_diff_removed_jobs(self):
        history = {"items": [{"id": "a", "content_hash": "abc"}]}
        current = []
        new, changed, removed = diff_jobs(current, history)
        assert len(removed) == 1

    def test_record_upsert(self):
        history = {"items": [{"id": "a", "title": "Old", "first_seen": "2024-01-01"}]}
        jobs = [{"id": "a", "title": "New", "first_seen": "2024-06-01"}]
        h = record_jobs(history, jobs)
        assert h["items"][0]["title"] == "New"
        assert h["items"][0]["first_seen"] == "2024-01-01"  # preserved

    def test_prune(self):
        old = (datetime(2020, 1, 1, tzinfo=timezone.utc)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        history = {"items": [
            {"id": "old", "first_seen": old},
            {"id": "new", "first_seen": recent},
        ]}
        h = prune_history(history, rolling_days=30)
        assert len(h["items"]) == 1
        assert h["items"][0]["id"] == "new"


# ---------------------------------------------------------------------------
# Render tests
# ---------------------------------------------------------------------------

class TestRender:
    def test_markdown_output(self, sample_jobs):
        md = render_markdown(sample_jobs, new_ids={"novartis:REQ-001"}, date="2024-06-15")
        assert "Data Scientist" in md
        assert "2024-06-15" in md
        assert "🆕" in md  # new badge

    def test_html_output(self, sample_jobs):
        html = render_html(sample_jobs, new_ids={"roche:JR-002"}, date="2024-06-15")
        assert "<html" in html
        assert "ML Engineer" in html
        assert "2024-06-15" in html
