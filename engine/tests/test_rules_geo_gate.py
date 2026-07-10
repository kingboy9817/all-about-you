# tests/test_rules_geo_gate.py
"""Plan 7 — applicant-eligibility gate. The verify stage reports facts
(geo_scope, language_req); geo_gate makes the call. Fail closed:
unknowns route to needs_review, never auto-pass."""
from rules import geo_gate, PASS, SKIP, NEEDS_REVIEW

ELIGIBILITY = {
    "work_auth": ["freedonia"],
    "languages": ["english", "elvish-basic"],
}


def verified(**kw):
    base = {"geo_scope": "global", "language_req": None}
    base.update(kw)
    return base


# --- geo scope ---

def test_global_passes():
    assert geo_gate(verified(), ELIGIBILITY).status == PASS


def test_restriction_matching_work_auth_passes():
    r = geo_gate(verified(geo_scope=["freedonia"]), ELIGIBILITY)
    assert r.status == PASS


def test_restriction_outside_work_auth_skips():
    r = geo_gate(verified(geo_scope=["sylvania"]), ELIGIBILITY)
    assert r.status == SKIP
    assert any("sylvania" in reason for reason in r.reasons)


def test_geo_scope_string_token_accepted():
    assert geo_gate(verified(geo_scope="sylvania"), ELIGIBILITY).status == SKIP
    assert geo_gate(verified(geo_scope="freedonia"), ELIGIBILITY).status == PASS


def test_geo_scope_case_insensitive():
    r = geo_gate(verified(geo_scope=["Freedonia"]), {"work_auth": ["FREEDONIA"]})
    assert r.status == PASS


def test_unknown_geo_scope_needs_review():
    for unknown in ("unknown", None):
        r = geo_gate(verified(geo_scope=unknown), ELIGIBILITY)
        assert r.status == NEEDS_REVIEW
        assert any("unverified" in reason for reason in r.reasons)


def test_multi_region_restriction_passes_on_any_match():
    r = geo_gate(verified(geo_scope=["sylvania", "freedonia"]), ELIGIBILITY)
    assert r.status == PASS


# --- fail closed on missing lens data ---

def test_missing_work_auth_needs_review():
    for elig in ({}, {"work_auth": []}, None):
        r = geo_gate(verified(geo_scope=["sylvania"]), elig)
        assert r.status == NEEDS_REVIEW


def test_missing_work_auth_blocks_even_global():
    # without owner data the gate cannot vouch; never auto-pass
    assert geo_gate(verified(), {}).status == NEEDS_REVIEW


# --- language requirement ---

def test_no_language_requirement_passes():
    assert geo_gate(verified(language_req=[]), ELIGIBILITY).status == PASS


def test_owned_language_passes():
    assert geo_gate(verified(language_req=["english"]), ELIGIBILITY).status == PASS


def test_unowned_language_skips():
    r = geo_gate(verified(language_req=["klingon"]), ELIGIBILITY)
    assert r.status == SKIP
    assert any("klingon" in reason for reason in r.reasons)


def test_basic_only_language_needs_review_not_pass():
    r = geo_gate(verified(language_req=["elvish"]), ELIGIBILITY)
    assert r.status == NEEDS_REVIEW
    assert any("elvish" in reason for reason in r.reasons)


def test_any_partial_level_routes_to_review_not_skip():
    # level names are owner vocabulary ('-intermediate', '-n2', ...); the gate
    # only distinguishes full proficiency (bare token) from partial (suffixed)
    elig = {"work_auth": ["freedonia"], "languages": ["dwarvish-intermediate"]}
    r = geo_gate(verified(language_req=["dwarvish"]), elig)
    assert r.status == NEEDS_REVIEW
    assert any("dwarvish" in reason for reason in r.reasons)


def test_one_satisfied_language_among_alternatives_is_not_enough():
    # requirements are conjunctive: every required language must be satisfied
    r = geo_gate(verified(language_req=["english", "klingon"]), ELIGIBILITY)
    assert r.status == SKIP


# --- precedence: hard skip beats review ---

def test_skip_beats_needs_review():
    r = geo_gate(verified(geo_scope="unknown", language_req=["klingon"]), ELIGIBILITY)
    assert r.status == SKIP
