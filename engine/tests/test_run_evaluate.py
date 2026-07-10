# tests/test_run_evaluate.py
from datetime import date
from run import evaluate

LENS = {"hard_filters": {"allowed_locations": [], "remote_ok": True,
                         "comp_floor": None, "exclude": ["gambling"]},
        "tier_thresholds": {"deep": 0.75, "light": 0.5},
        "eligibility": {"work_auth": ["freedonia"], "languages": ["english"]}}
TODAY = date(2026, 6, 6)


def test_evaluate_skips_non_remote():
    opp = {"org": "A", "title": "t", "extracted": {"remote": False, "location": "Paris"}}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["filter_result"] == "skip"
    assert out["status"] == "rejected"
    assert out["tier"] == "skip"


def test_evaluate_deep_when_priority_goal_matched():
    opp = {"org": "A", "title": "t",
           "extracted": {"remote": True, "geo_scope": "global",
                         "liveness": {"status": "open", "checked_at": "2026-06-06"}},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["filter_result"] == "pass"
    assert out["tier"] == "deep"
    assert out["status"] == "shortlisted"


def test_evaluate_light_when_no_priority_goal():
    opp = {"org": "A", "title": "t",
           "extracted": {"remote": True, "geo_scope": "global",
                         "liveness": {"status": "open", "checked_at": "2026-06-06"}},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": False}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["tier"] == "light"
    assert out["status"] == "shortlisted"


def test_evaluate_unscored_survivor_left_for_agent():
    opp = {"org": "A", "title": "t", "extracted": {"remote": True}}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["filter_result"] == "pass"
    assert out["status"] == "discovered"


def test_evaluate_needs_review_when_fields_unknown():
    opp = {"org": "A", "title": "t", "extracted": {}}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["filter_result"] == "needs_review"
    assert out["status"] == "needs_review"


def test_evaluate_legit_flagged_shortlist_routes_to_needs_review():
    opp = {"org": "RecruitLytic Hires", "title": "Data Entry", "extracted": {"remote": True, "geo_scope": "global"},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY, org_counts={"RecruitLytic Hires": 4})
    assert out["filter_result"] == "pass"
    assert out["tier"] == "deep"            # would have been shortlisted...
    assert out["status"] == "needs_review"  # ...but legitimacy flags route it to human review
    assert out["legitimacy"] == "suspect"
    assert any("generic-recruiter" in x for x in out["flags"])


def test_evaluate_clean_shortlist_is_unverified_not_suspect():
    opp = {"org": "Bendigo Advertiser", "title": "Data Entry",
           "extracted": {"remote": True, "geo_scope": "global",
                         "liveness": {"status": "open", "checked_at": "2026-06-06"}},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY, org_counts={"Bendigo Advertiser": 1})
    assert out["status"] == "shortlisted"
    assert out["legitimacy"] == "unverified"


def test_evaluate_geo_mismatch_rejected_despite_good_scores():
    opp = {"org": "A", "title": "t",
           "extracted": {"remote": True, "geo_scope": ["sylvania"]},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["status"] == "rejected"
    assert any("sylvania" in f for f in out["flags"])


def test_evaluate_unverified_geo_parks_in_needs_review_never_shortlists():
    opp = {"org": "A", "title": "t", "extracted": {"remote": True},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY)
    assert out["status"] == "needs_review"
    assert any("unverified" in f for f in out["flags"])


def test_evaluate_prior_suspect_org_variant_routes_to_review():
    opp = {"org": "Re-cruit-Lytic", "title": "Entry Level Admin",
           "extracted": {"remote": True, "geo_scope": "global"},
           "capability_score": 0.9, "intent_score": 0.8, "matched_priority_goal": True}
    out = evaluate(opp, LENS, today=TODAY, suspect_orgs={"RecruitLytic Hires"})
    assert out["status"] == "needs_review"
    assert out["legitimacy"] == "suspect"
