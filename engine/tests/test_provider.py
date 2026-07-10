# tests/test_provider.py
from provider.profile_provider import ProfileProvider
from provider.fake_provider import FakeProvider


def test_fake_provider_satisfies_contract():
    assert isinstance(FakeProvider(), ProfileProvider)


def test_get_lens_returns_hard_filters():
    lens = FakeProvider().get_lens()
    assert "hard_filters" in lens
    assert "allowed_locations" in lens["hard_filters"]


def test_propose_kb_change_is_recorded_not_applied():
    p = FakeProvider()
    p.propose_kb_change({"target": "lens.md", "after": "new pref"})
    assert len(p.proposed) == 1
    assert p.proposed[0]["target"] == "lens.md"


def test_search_evidence_returns_list():
    p = FakeProvider(evidence=[{"text": "Built X"}])
    assert p.search_evidence("infra") == [{"text": "Built X"}]
