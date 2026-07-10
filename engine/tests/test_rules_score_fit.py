# tests/test_rules_score_fit.py
"""Plan 8: pure fit scorer. Atoms in -> deterministic capability/intent out."""
from rules import score_fit, comp_tier_of, clamp01, assign_tier

LENS = {
    "tier_thresholds": {"deep": 0.75, "light": 0.5},
    "lanes": {"career": {"comp_tiers_sgd_month": {"wake": 8000, "look": 11000, "apply_hard": 18000}}},
    "scoring": {
        "mode_factor": {"explanatory": 1.0, "mixed": 0.5, "transactional": 0.1},
        "persuasion_load_ref": 0.4,
        "caveat_threshold_K": 12,
        "caveat_hard_skip": 8,
        "career_capability": {"w_caveat": 0.7, "w_in_domain": 0.3, "w_trans": 0.5},
        "career_intent": {
            "comp_tier": {"unknown": 0.45, "below_wake": 0.2, "wake": 0.4, "look": 0.7, "apply_hard": 1.0},
            "in_domain": 0.1, "core_align": 0.15, "inbound": 0.1, "face_to_face": 0.05,
        },
    },
}
LIGHT, DEEP = 0.5, 0.75


def _tier(fi):
    sf = score_fit(fi, LENS)
    return sf, assign_tier(sf["capability"], sf["intent"], LENS["tier_thresholds"],
                           matched_priority_goal=fi.get("_mpg", False))


def test_clamp01():
    assert clamp01(-3) == 0.0 and clamp01(0.5) == 0.5 and clamp01(9) == 1.0


def test_comp_tier_of():
    assert comp_tier_of(None, LENS) == "unknown"
    assert comp_tier_of(7000, LENS) == "below_wake"
    assert comp_tier_of(9000, LENS) == "wake"
    assert comp_tier_of(12000, LENS) == "look"
    assert comp_tier_of(20000, LENS) == "apply_hard"


def test_fde_explanatory_in_domain_is_deep_eligible():
    fi = {
        "lane": "career", "in_domain": True, "comp_sgd_month": 14000, "face_to_face": True,
        "core_responsibilities": [
            {"persuasion": True, "mode": "explanatory"},
            {"persuasion": True, "mode": "explanatory"},
            {"persuasion": True, "mode": "explanatory"},
            {"persuasion": False, "mode": None},
            {"persuasion": False, "mode": None},
        ],
        "fit_caveats": ["no enterprise martech", "ai-orchestration self-assessed"],
        "_mpg": True,
    }
    sf, tier = _tier(fi)
    assert sf["capability"] >= DEEP, sf
    assert sf["intent"] >= DEEP, sf
    assert tier == "deep"


def test_transactional_sdr_skips_despite_in_domain_and_comp():
    fi = {
        "lane": "career", "in_domain": True, "comp_sgd_month": 12000,
        "core_responsibilities": [
            {"persuasion": True, "mode": "transactional"},
            {"persuasion": True, "mode": "transactional"},
            {"persuasion": True, "mode": "transactional"},
            {"persuasion": True, "mode": "transactional"},
        ],
        "fit_caveats": ["no SDR exp", "consultative not transactional", "no cadence track record",
                        "competes vs career SDRs"],
    }
    sf, tier = _tier(fi)
    assert sf["capability"] < LIGHT, sf
    assert tier == "skip"


def test_principal_swe_auto_skips_even_at_top_comp():
    fi = {
        "lane": "career", "in_domain": True, "comp_sgd_month": 25000,  # apply_hard
        "core_responsibilities": [
            {"persuasion": False, "mode": None},
            {"persuasion": False, "mode": None},
            {"persuasion": True, "mode": "mixed"},
            {"persuasion": False, "mode": None},
        ],
        "fit_caveats": ["a", "b", "c", "d", "e", "f", "g", "h"],  # >= caveat_hard_skip (8)
    }
    sf, tier = _tier(fi)
    assert sf["breakdown"]["auto_skip"] is True
    assert sf["capability"] < LIGHT, sf   # comp never buys fit
    assert tier == "skip"


def test_anti_fit_auto_skips():
    fi = {
        "lane": "career", "in_domain": False, "comp_sgd_month": 20000, "anti_fit": True,
        "core_responsibilities": [{"persuasion": True, "mode": "explanatory"}],
        "fit_caveats": ["no domain background"],
    }
    sf, _ = _tier(fi)
    assert sf["capability"] < LIGHT, sf


def test_side_gig_uses_automatability():
    fi = {"lane": "side_gig", "automatable_fraction": 0.85, "recurring": True,
          "async_no_meetings": True, "non_distracting": True, "_mpg": True}
    sf, tier = _tier(fi)
    assert sf["capability"] == 0.85
    assert sf["intent"] == 1.0
    assert tier == "deep"


def test_defaults_used_when_lens_lacks_scoring_block():
    # bare lens (only thresholds) must still score via DEFAULT_SCORING / DEFAULT_COMP_TIERS
    bare = {"tier_thresholds": {"deep": 0.75, "light": 0.5}}
    fi = {"lane": "side_gig", "automatable_fraction": 0.9, "recurring": True,
          "async_no_meetings": True, "non_distracting": True}
    sf = score_fit(fi, bare)
    assert sf["capability"] == 0.9 and sf["intent"] == 1.0


def test_can_do_nonpersuasion_role_surfaces_light_not_skip():
    # copy-editor archetype: no persuasion, but in-domain + few caveats = clearly can-do.
    # Capability should be high; tier caps at light (no priority-goal match), never skip.
    fi = {
        "lane": "career", "in_domain": True, "comp_sgd_month": 20000, "anti_fit": False,
        "core_responsibilities": [
            {"persuasion": False, "mode": None},
            {"persuasion": False, "mode": None},
            {"persuasion": False, "mode": None},
        ],
        "fit_caveats": ["no dedicated editorial role", "no portfolio", "editing not core function"],
        "_mpg": False,  # not a priority-archetype match -> light ceiling
    }
    sf, tier = _tier(fi)
    assert sf["capability"] >= LIGHT, sf   # can-do
    assert tier == "light"                 # surfaced, not skipped, not deep


def test_transactional_skips_even_at_top_comp():
    # comp can't rescue a transactional-mode role: capability penalty gates it to skip.
    fi = {
        "lane": "career", "in_domain": True, "comp_sgd_month": 30000,  # apply_hard
        "core_responsibilities": [
            {"persuasion": True, "mode": "transactional"},
            {"persuasion": True, "mode": "transactional"},
            {"persuasion": True, "mode": "transactional"},
        ],
        "fit_caveats": ["no quota outbound exp", "transactional not my style", "no cadence tooling"],
    }
    sf, tier = _tier(fi)
    assert sf["capability"] < LIGHT, sf
    assert tier == "skip"
