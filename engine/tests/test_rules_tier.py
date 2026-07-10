# tests/test_rules_tier.py
from rules import assign_tier

TH = {"deep": 0.75, "light": 0.5}


def test_low_score_either_axis_is_skip():
    assert assign_tier(0.9, 0.3, TH, matched_priority_goal=True) == "skip"
    assert assign_tier(0.4, 0.9, TH, matched_priority_goal=True) == "skip"


def test_high_both_with_priority_goal_is_deep():
    assert assign_tier(0.8, 0.85, TH, matched_priority_goal=True) == "deep"


def test_high_both_without_priority_goal_is_light():
    assert assign_tier(0.8, 0.85, TH, matched_priority_goal=False) == "light"


def test_mid_scores_are_light():
    assert assign_tier(0.6, 0.6, TH, matched_priority_goal=True) == "light"
