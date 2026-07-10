# tests/test_run_reflect.py
"""Reflection loop helpers: feedback parsing + golden-set drift guard (spec §7)."""
from datetime import date
from pathlib import Path

import pytest

from run import (read_feedback, record_feedback, load_golden_cases,
                 run_golden_cases)

REPO = Path(__file__).resolve().parent.parent


# --- read_feedback ---

def test_read_feedback_roundtrips_record_feedback(tmp_path):
    fb = tmp_path / "feedback.md"
    record_feedback(str(fb), "opp-a", "triage", "approve", "credible + automatable",
                    when=date(2026, 6, 6))
    record_feedback(str(fb), "opp-b", "draft", "accept", "approved after edits",
                    when=date(2026, 6, 9))
    rows = read_feedback(str(fb))
    assert rows == [
        {"date": "2026-06-06", "opportunity_id": "opp-a", "gate": "triage",
         "decision": "approve", "reason": "credible + automatable"},
        {"date": "2026-06-09", "opportunity_id": "opp-b", "gate": "draft",
         "decision": "accept", "reason": "approved after edits"},
    ]


def test_read_feedback_missing_file_is_empty(tmp_path):
    assert read_feedback(str(tmp_path / "nope.md")) == []


def test_read_feedback_keeps_pipes_inside_reason(tmp_path):
    fb = tmp_path / "feedback.md"
    record_feedback(str(fb), "opp-a", "triage", "reject", "low pay | live hours",
                    when=date(2026, 6, 6))
    assert read_feedback(str(fb))[0]["reason"] == "low pay | live hours"


def test_read_feedback_parses_the_real_log():
    pytest.skip("feedback.md is intentionally excluded from the public skeleton")
    rows = read_feedback(str(REPO / "feedback.md"))
    assert len(rows) >= 10
    assert all(r["gate"] in ("triage", "draft", "submit", "reflect", "outcome") for r in rows)


# --- load_golden_cases ---

CASES_MD = """# eval/cases.md

```yaml
as_of: 2026-06-11
lens_baseline:
  hard_filters: {allowed_locations: [], remote_ok: true, comp_floor: null, exclude: [gambling]}
  tier_thresholds: {deep: 0.75, light: 0.5}
cases:
  - id: remote-deep
    org: Acme
    title: Data Entry
    extracted: {location: Remote, remote: true, comp: null, deadline: null}
    capability_score: 0.85
    intent_score: 0.82
    matched_priority_goal: true
    expected: {filter_result: pass, tier: deep, status: shortlisted}
```
"""


def test_load_golden_cases_parses_yaml_block(tmp_path):
    p = tmp_path / "cases.md"
    p.write_text(CASES_MD, encoding="utf-8")
    golden = load_golden_cases(str(p))
    assert golden["as_of"] == date(2026, 6, 11)
    assert golden["lens_baseline"]["hard_filters"]["remote_ok"] is True
    assert golden["cases"][0]["id"] == "remote-deep"


def test_load_golden_cases_missing_or_blockless(tmp_path):
    assert load_golden_cases(str(tmp_path / "nope.md")) == {}
    p = tmp_path / "empty.md"
    p.write_text("# no yaml here\n", encoding="utf-8")
    assert load_golden_cases(str(p)) == {}


# --- run_golden_cases ---

def _golden(**case_overrides):
    case = {
        "id": "remote-deep", "org": "Acme", "title": "Data Entry",
        "extracted": {"location": "Remote", "remote": True, "geo_scope": "global",
                      "comp": None, "deadline": None,
                      "liveness": {"status": "open", "checked_at": "2026-06-11"}},
        "capability_score": 0.85, "intent_score": 0.82,
        "matched_priority_goal": True,
        "expected": {"filter_result": "pass", "tier": "deep",
                     "status": "shortlisted"},
    }
    case.update(case_overrides)
    return {
        "as_of": date(2026, 6, 11),
        "lens_baseline": {
            "hard_filters": {"allowed_locations": [], "remote_ok": True,
                             "comp_floor": None, "exclude": ["gambling"]},
            "tier_thresholds": {"deep": 0.75, "light": 0.5},
            "eligibility": {"work_auth": ["freedonia"], "languages": ["english"]},
        },
        "cases": [case],
    }


def test_run_golden_cases_passes_on_baseline():
    report = run_golden_cases(_golden())
    assert report["passed"] == 1 and report["failed"] == 0
    assert report["results"][0]["ok"] is True


def test_run_golden_cases_flags_regression_under_proposed_lens():
    proposed = {"hard_filters": {"allowed_locations": [], "remote_ok": False},
                "tier_thresholds": {"deep": 0.75, "light": 0.5}}
    report = run_golden_cases(_golden(), lens=proposed)
    assert report["failed"] == 1
    r = report["results"][0]
    assert r["ok"] is False
    assert r["expected"]["filter_result"] == "pass"
    assert r["got"]["filter_result"] == "skip"


def test_run_golden_cases_legitimacy_fails_closed():
    golden = _golden(org="RecruitLytic Hires", org_count=4,
                     capability_score=0.8, intent_score=0.72,
                     matched_priority_goal=True,
                     expected={"filter_result": "pass", "tier": "light",
                               "status": "needs_review"})
    report = run_golden_cases(golden)
    assert report["failed"] == 0


def test_run_golden_cases_respects_as_of_for_deadlines():
    golden = _golden()
    golden["cases"][0]["extracted"]["deadline"] = date(2026, 1, 1)
    golden["cases"][0]["expected"] = {"filter_result": "skip",
                                      "tier": "skip", "status": "rejected"}
    assert run_golden_cases(golden)["failed"] == 0


def test_run_golden_cases_compares_only_expected_keys():
    golden = _golden(expected={"filter_result": "pass"})
    report = run_golden_cases(golden)
    assert report["failed"] == 0
    assert report["results"][0]["got"] == {"filter_result": "pass"}


# --- the real golden set ---

def test_real_eval_cases_all_green_on_baseline():
    pytest.skip("eval/cases.md is intentionally excluded from the public skeleton")
    golden = load_golden_cases(str(REPO / "eval" / "cases.md"))
    assert len(golden.get("cases", [])) >= 10
    report = run_golden_cases(golden)
    bad = [r for r in report["results"] if not r["ok"]]
    assert not bad, f"golden regressions: {bad}"
