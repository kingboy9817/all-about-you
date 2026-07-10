# tests/test_run_guide.py
"""Plan 4 — Guide / Gate 3 helpers: submit transition, follow-up tracker,
outcome recording, outcome-rate metric."""
from datetime import date

import pytest

from run import mark_submitted, followups_due, record_outcome, build_pipeline
from store import load_opportunity, save_opportunity


def _record(tmp, slug, status="drafted", **extra):
    fm = {"id": slug, "org": extra.pop("org", "Acme"), "title": extra.pop("title", "Role"),
          "status": status, **extra}
    path = str(tmp / f"{slug}.md")
    save_opportunity(path, fm, "body text")
    return path


# --- mark_submitted (Gate 3 transition) ---

def test_mark_submitted_sets_status_date_and_followup(tmp_path):
    path = _record(tmp_path, "a")
    fm = mark_submitted(path, when=date(2026, 6, 12))
    assert fm["status"] == "submitted"
    assert fm["date_submitted"] == "2026-06-12"
    assert fm["next_followup"] == "2026-06-19"
    on_disk, body = load_opportunity(path)
    assert on_disk["status"] == "submitted"
    assert body.strip() == "body text"


def test_mark_submitted_custom_followup_days(tmp_path):
    path = _record(tmp_path, "a")
    fm = mark_submitted(path, when=date(2026, 6, 12), followup_days=3)
    assert fm["next_followup"] == "2026-06-15"


def test_mark_submitted_fails_closed_from_other_statuses(tmp_path):
    path = _record(tmp_path, "a", status="shortlisted")
    with pytest.raises(ValueError):
        mark_submitted(path)


def test_mark_submitted_backfills_already_submitted(tmp_path):
    path = _record(tmp_path, "a", status="submitted", date_submitted="2026-06-11")
    fm = mark_submitted(path, when=date(2026, 6, 11))
    assert fm["date_submitted"] == "2026-06-11"
    assert fm["next_followup"] == "2026-06-18"


# --- followups_due ---

def test_followups_due_returns_due_sorted_and_skips_rest(tmp_path):
    _record(tmp_path, "later", status="submitted",
            date_submitted="2026-06-10", next_followup="2026-06-30")
    _record(tmp_path, "due2", status="submitted",
            date_submitted="2026-06-05", next_followup="2026-06-12")
    _record(tmp_path, "due1", status="submitted",
            date_submitted="2026-06-01", next_followup="2026-06-08")
    _record(tmp_path, "notsub", status="drafted", next_followup="2026-06-01")
    due = followups_due(tmp_path, today=date(2026, 6, 12))
    assert [r["id"] for r in due] == ["due1", "due2"]
    assert due[0]["org"] == "Acme" and due[0]["path"].endswith("due1.md")


def test_followups_due_empty_dir(tmp_path):
    assert followups_due(tmp_path, today=date(2026, 6, 12)) == []


# --- set_followup (re-arm after a nudge was sent) ---

def test_set_followup_rearms_submitted_record(tmp_path):
    from run import set_followup
    path = _record(tmp_path, "a", status="submitted",
                   date_submitted="2026-06-11", next_followup="2026-06-12")
    fm = set_followup(path, when=date(2026, 6, 19))
    assert fm["next_followup"] == "2026-06-19"
    assert fm["date_submitted"] == "2026-06-11"   # untouched


def test_set_followup_fails_closed_off_submitted(tmp_path):
    from run import set_followup
    path = _record(tmp_path, "a", status="drafted")
    with pytest.raises(ValueError):
        set_followup(path, when=date(2026, 6, 19))


# --- record_outcome ---

def test_record_outcome_reply(tmp_path):
    path = _record(tmp_path, "a", status="submitted",
                   date_submitted="2026-06-11", next_followup="2026-06-18")
    fm = record_outcome(path, "reply", when=date(2026, 6, 14))
    assert fm["status"] == "replied"
    assert fm["outcome"] == "reply"
    assert fm["date_outcome"] == "2026-06-14"
    assert "next_followup" not in fm


def test_record_outcome_ghost_closes(tmp_path):
    path = _record(tmp_path, "a", status="submitted")
    fm = record_outcome(path, "ghost", when=date(2026, 7, 1))
    assert fm["status"] == "closed"
    assert fm["outcome"] == "ghost"


def test_record_outcome_can_chain_next_followup(tmp_path):
    path = _record(tmp_path, "a", status="submitted")
    fm = record_outcome(path, "reply", when=date(2026, 6, 14), next_followup_days=5)
    assert fm["next_followup"] == "2026-06-19"


def test_record_outcome_fails_closed(tmp_path):
    path = _record(tmp_path, "a", status="submitted")
    with pytest.raises(ValueError):
        record_outcome(path, "won-the-lottery")
    path2 = _record(tmp_path, "b", status="drafted")
    with pytest.raises(ValueError):
        record_outcome(path2, "reply")


def test_record_outcome_allows_progression(tmp_path):
    path = _record(tmp_path, "a", status="submitted")
    record_outcome(path, "reply", when=date(2026, 6, 14))
    fm = record_outcome(path, "interview", when=date(2026, 6, 20))
    assert fm["status"] == "interview"


# --- pipeline board: outcome rate + follow-ups section ---

def test_build_pipeline_outcome_rate_and_followups(tmp_path):
    _record(tmp_path, "sub", status="submitted", org="Northwind Labs", title="Sales",
            date_submitted="2026-06-11", next_followup="2026-06-12")
    _record(tmp_path, "rep", status="replied", org="Acme", title="VA",
            date_submitted="2026-06-01", outcome="reply")
    _record(tmp_path, "still-drafting", status="drafted")
    md = build_pipeline(tmp_path, today=date(2026, 6, 12))
    assert "Outcome rate" in md
    assert "1/2 (50%)" in md
    assert "## Follow-ups" in md
    assert "Northwind Labs — Sales" in md and "DUE" in md


def test_build_pipeline_no_submissions_dash_rate(tmp_path):
    _record(tmp_path, "d", status="drafted")
    md = build_pipeline(tmp_path, today=date(2026, 6, 12))
    assert "Outcome rate" in md
    assert "_Nothing awaiting follow-up._" in md
