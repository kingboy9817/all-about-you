# tests/test_screen.py
from store import save_opportunity, load_opportunity
from provider.fake_provider import FakeProvider
from run import screen_opportunity
from datetime import date

TODAY = date(2026, 6, 5)


def test_screen_skips_disallowed_onsite_location(tmp_path):
    p = tmp_path / "o.md"
    save_opportunity(str(p), {"id": "x", "org": "Acme", "title": "Infra",
                              "extracted": {"location": "Lagos", "remote": False, "comp": 12000}}, "jd")
    fm, _ = load_opportunity(str(p))
    result = screen_opportunity(fm, FakeProvider(), today=TODAY)
    assert result.status == "skip"


def test_screen_passes_remote_in_budget(tmp_path):
    p = tmp_path / "o.md"
    save_opportunity(str(p), {"id": "y", "org": "Acme", "title": "Infra",
                              "extracted": {"location": "Remote", "remote": True, "comp": 12000}}, "jd")
    fm, _ = load_opportunity(str(p))
    result = screen_opportunity(fm, FakeProvider(), today=TODAY)
    assert result.status == "pass"
