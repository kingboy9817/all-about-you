# provider/fake_provider.py
"""In-memory ProfileProvider for tests; also documents the contract shape."""
from provider.profile_provider import ProfileProvider

DEFAULT_LENS = {
    "compass": "Build across infrastructure, tools, and LLMs.",
    "goals": [{"id": "llm-infra", "summary": "Senior infra/LLM roles", "priority": 5}],
    "hard_filters": {"allowed_locations": ["Singapore", "SEA"], "remote_ok": True,
                     "comp_floor": 8000, "exclude": ["gambling"]},
    "soft_weights": {},
    "tier_thresholds": {"deep": 0.75, "light": 0.5},
    "eligibility": {"work_auth": ["freedonia"], "languages": ["english", "elvish-basic"]},
    "voice": "Direct, concrete, no fluff.",
}


class FakeProvider(ProfileProvider):
    def __init__(self, lens=None, evidence=None):
        self._lens = dict(lens) if lens is not None else dict(DEFAULT_LENS)
        self._evidence = list(evidence) if evidence else []
        self.proposed = []

    def search_evidence(self, query):
        return list(self._evidence)

    def get_lens(self):
        return dict(self._lens)

    def propose_kb_change(self, change):
        self.proposed.append(change)
