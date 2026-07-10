# tests/test_rules_filters.py
from datetime import date
from rules import passes_hard_filters, PASS, SKIP, NEEDS_REVIEW

FILTERS = {"allowed_locations": ["Singapore", "SEA"], "remote_ok": True,
           "comp_floor": 8000, "exclude": ["gambling"]}
TODAY = date(2026, 6, 5)


def opp(**extracted):
    return {"org": "Acme", "title": "Infra Engineer", "extracted": extracted}


def test_remote_role_passes_location():
    r = passes_hard_filters(opp(location="Remote", remote=True, comp=12000), FILTERS, TODAY)
    assert r.status == PASS


def test_allowed_location_passes():
    r = passes_hard_filters(opp(location="Singapore", remote=False, comp=12000), FILTERS, TODAY)
    assert r.status == PASS


def test_disallowed_onsite_location_skips():
    r = passes_hard_filters(opp(location="Lagos", remote=False, comp=12000), FILTERS, TODAY)
    assert r.status == SKIP
    assert any("location" in reason for reason in r.reasons)


def test_unknown_location_needs_review_not_pass():
    r = passes_hard_filters(opp(location=None, remote=False, comp=12000), FILTERS, TODAY)
    assert r.status == NEEDS_REVIEW


def test_comp_below_floor_skips():
    r = passes_hard_filters(opp(location="Remote", remote=True, comp=5000), FILTERS, TODAY)
    assert r.status == SKIP


def test_comp_unknown_with_floor_needs_review():
    r = passes_hard_filters(opp(location="Remote", remote=True, comp=None), FILTERS, TODAY)
    assert r.status == NEEDS_REVIEW


def test_excluded_industry_in_title_skips():
    o = {"org": "BigBet", "title": "Gambling Platform Engineer", "extracted": {"location": "Remote", "remote": True, "comp": 12000}}
    r = passes_hard_filters(o, FILTERS, TODAY)
    assert r.status == SKIP


def test_passed_deadline_skips():
    r = passes_hard_filters(opp(location="Remote", remote=True, comp=12000, deadline="2026-01-01"), FILTERS, TODAY)
    assert r.status == SKIP


def test_skip_wins_over_needs_review():
    # unknown comp (needs_review) + disallowed location (skip) -> skip
    r = passes_hard_filters(opp(location="Lagos", remote=False, comp=None), FILTERS, TODAY)
    assert r.status == SKIP
