# tests/test_rules_legitimacy.py
from rules import legitimacy_flags, normalize_org


def test_normalize_org_strips_punctuation_case_and_spaces():
    assert normalize_org("Re-cruit-Lytic") == "recruitlytic"
    assert normalize_org("RecruitLytic  Hires!") == "recruitlytichires"
    assert normalize_org(None) == ""


def test_prior_suspect_org_variant_is_flagged():
    # the real 2026-06-12 leak: hyphenated respelling dodged the suspect verdict
    f = legitimacy_flags({"org": "Re-cruit-Lytic", "title": "Entry Level Admin"},
                         suspect_orgs={"RecruitLytic Hires"})
    assert any("prior suspect" in x for x in f)


def test_suspect_match_requires_substantial_overlap():
    # short normalized names must not substring-match longer unrelated ones
    f = legitimacy_flags({"org": "Acme", "title": "X"},
                         suspect_orgs={"Acme Global Staffing Partners"})
    assert not any("prior suspect" in x for x in f)
    f2 = legitimacy_flags({"org": "Beta Co", "title": "X"}, suspect_orgs={"Gamma LLC"})
    assert not any("prior suspect" in x for x in f2)


def test_flags_generic_recruiter_name():
    f = legitimacy_flags({"org": "RecruitLytic Hires", "title": "Data Entry"})
    assert any("generic-recruiter" in x for x in f)


def test_flags_duplicate_postings():
    f = legitimacy_flags({"org": "RecruitLytic Hires", "title": "X"},
                         org_counts={"RecruitLytic Hires": 4})
    assert any("near-identical" in x for x in f)


def test_flags_scam_phrase_in_text():
    f = legitimacy_flags({"org": "Acme Co", "title": "Typist"},
                         text="Pay a registration fee, then contact us on Telegram")
    assert any("scam-phrase" in x for x in f)


def test_clean_posting_no_flags():
    f = legitimacy_flags({"org": "Bendigo Advertiser", "title": "Data Entry Specialist"},
                         org_counts={"Bendigo Advertiser": 1},
                         text="Remote data entry into spreadsheets, part-time option.")
    assert f == []
