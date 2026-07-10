# tests/test_rules_dedupe.py
from rules import dedupe_key


def test_same_url_different_case_and_slash_is_same_key():
    a = {"url": "https://Example.com/jobs/123/"}
    b = {"url": "https://example.com/jobs/123"}
    assert dedupe_key(a) == dedupe_key(b)


def test_different_url_is_different_key():
    a = {"url": "https://example.com/jobs/123"}
    b = {"url": "https://example.com/jobs/999"}
    assert dedupe_key(a) != dedupe_key(b)


def test_falls_back_to_org_and_title_when_no_url():
    a = {"org": "Acme", "title": "Infra Engineer"}
    b = {"org": "Acme", "title": "Infra Engineer"}
    assert dedupe_key(a) == dedupe_key(b)
