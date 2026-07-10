# provider/profile_provider.py
"""The only interface between the engine and any personal data source."""
from abc import ABC, abstractmethod


class ProfileProvider(ABC):
    @abstractmethod
    def search_evidence(self, query):
        """Return a list of evidence snippets relevant to `query`."""

    @abstractmethod
    def get_lens(self):
        """Return the lens dict: compass, goals, hard_filters, soft_weights,
        tier_thresholds, voice."""

    @abstractmethod
    def propose_kb_change(self, change):
        """Propose an owner-approved change to the KB. `change` targets ANY
        Engine-1 file (lens, experience, contact, ...). NEVER a direct edit."""
