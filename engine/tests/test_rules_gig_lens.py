# tests/test_rules_gig_lens.py
from rules import passes_hard_filters

GIG = {"allowed_locations": [], "remote_ok": True, "comp_floor": None, "exclude": ["gambling"]}


def test_remote_gig_passes_with_no_comp_floor():
    opp = {"org": "Acme", "title": "Data entry",
           "extracted": {"remote": True, "location": "Remote", "comp": None}}
    assert passes_hard_filters(opp, GIG).status == "pass"


def test_non_remote_gig_is_skipped():
    opp = {"org": "Acme", "title": "Data entry",
           "extracted": {"remote": False, "location": "Berlin", "comp": 99999}}
    assert passes_hard_filters(opp, GIG).status == "skip"


def test_excluded_term_skips():
    opp = {"org": "BetCo", "title": "Gambling site data entry",
           "extracted": {"remote": True}}
    assert passes_hard_filters(opp, GIG).status == "skip"


def test_unknown_remote_and_location_needs_review():
    opp = {"org": "Acme", "title": "Mystery gig", "extracted": {}}
    assert passes_hard_filters(opp, GIG).status == "needs_review"
