# tests/test_rules_liveness_gate.py
"""Listing-liveness gate. Distinct from geo_gate (applicant eligibility): this
gates the *listing* — is it still OPEN? The verify stage FETCHES the facts
(status / expiry_date / checked_at) from the source; liveness_gate makes the call.
Fail closed: missing / unknown / stale-check verification routes to needs_review,
never auto-pass; an explicit closed status or a past expiry is a hard skip.

Regression target: a closed MyCareersFuture listing (expired 20 days before
ingest) sailed to a full crafted package because `stale: false` was *asserted*
at ingest, never verified. This gate makes liveness a verified fact with a gate."""
from datetime import date
from rules import liveness_gate, PASS, SKIP, NEEDS_REVIEW

TODAY = date(2026, 6, 20)


def live(**kw):
    # an OPEN listing, verified two days ago, no expiry
    base = {"status": "open", "expiry_date": None, "checked_at": "2026-06-18"}
    base.update(kw)
    return base


# --- the happy path ---

def test_open_freshly_checked_passes():
    assert liveness_gate(live(), today=TODAY).status == PASS


def test_future_expiry_passes():
    assert liveness_gate(live(expiry_date="2026-12-31"), today=TODAY).status == PASS


def test_reopen_status_passes():
    assert liveness_gate(live(status="re-open"), today=TODAY).status == PASS


def test_status_case_insensitive():
    assert liveness_gate(live(status="Open"), today=TODAY).status == PASS
    assert liveness_gate(live(status="CLOSED"), today=TODAY).status == SKIP


def test_date_objects_accepted():
    r = liveness_gate(live(checked_at=date(2026, 6, 19), expiry_date=date(2026, 12, 1)), today=TODAY)
    assert r.status == PASS


# --- explicit dead signals: hard skip ---

def test_closed_statuses_skip():
    for s in ("closed", "expired", "filled", "deleted", "withdrawn", "inactive"):
        r = liveness_gate(live(status=s), today=TODAY)
        assert r.status == SKIP, s
        assert any("not open" in reason for reason in r.reasons)


def test_past_expiry_skips():
    r = liveness_gate(live(expiry_date="2026-05-30"), today=TODAY)
    assert r.status == SKIP
    assert any("expired" in reason and "2026-05-30" in reason for reason in r.reasons)


def test_past_expiry_overrides_open_status():
    # the exact Prudential failure: status read 'open' but it had already expired
    r = liveness_gate(live(status="open", expiry_date="2026-05-30"), today=TODAY)
    assert r.status == SKIP


# --- fail closed: unverified / unknown / stale check ---

def test_never_checked_needs_review_even_if_open():
    r = liveness_gate(live(checked_at=None), today=TODAY)
    assert r.status == NEEDS_REVIEW
    assert any("unverified" in reason for reason in r.reasons)


def test_unknown_status_needs_review():
    for s in ("unknown", None, ""):
        r = liveness_gate(live(status=s), today=TODAY)
        assert r.status == NEEDS_REVIEW, repr(s)
        assert any("unverified" in reason for reason in r.reasons)


def test_empty_or_missing_liveness_fails_closed():
    assert liveness_gate({}, today=TODAY).status == NEEDS_REVIEW
    assert liveness_gate(None, today=TODAY).status == NEEDS_REVIEW


def test_stale_check_needs_review():
    # checked too long ago -> can't vouch; force a re-ping
    r = liveness_gate(live(checked_at="2026-05-01"), today=TODAY)
    assert r.status == NEEDS_REVIEW
    assert any("stale" in reason and "re-ping" in reason for reason in r.reasons)


def test_custom_max_age_days():
    ten_days = live(checked_at="2026-06-10")          # 10 days old
    assert liveness_gate(ten_days, today=TODAY, max_age_days=14).status == PASS
    assert liveness_gate(ten_days, today=TODAY, max_age_days=5).status == NEEDS_REVIEW


# --- precedence: a definite skip beats a fail-closed review ---

def test_skip_beats_needs_review():
    # closed AND never checked -> the definite signal (closed) wins
    r = liveness_gate(live(status="closed", checked_at=None), today=TODAY)
    assert r.status == SKIP
