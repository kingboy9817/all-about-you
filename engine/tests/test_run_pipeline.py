# tests/test_run_pipeline.py
from datetime import date
from run import build_pipeline, record_feedback
from store import save_opportunity


def _opp(tmp, slug, **kw):
    fm = {"id": slug, "org": kw.get("org", "O"), "title": kw.get("title", "T"),
          "status": kw.get("status", "discovered"), "tier": kw.get("tier"),
          "capability_score": kw.get("cap"), "intent_score": kw.get("intent"),
          "flags": kw.get("flags", [])}
    save_opportunity(str(tmp / f"{slug}.md"), fm, "")


def test_build_pipeline_lists_board_and_shortlist(tmp_path):
    _opp(tmp_path, "a", status="shortlisted", tier="deep", cap=0.9, intent=0.8,
         org="Acme", title="VA")
    _opp(tmp_path, "b", status="rejected", tier="skip")
    md = build_pipeline(tmp_path)
    assert "## Board" in md
    assert "**shortlisted**: 1" in md
    assert "Acme — VA" in md
    assert "Triage precision" in md


def test_record_and_score_triage_precision(tmp_path):
    fb = tmp_path / "feedback.md"
    record_feedback(str(fb), "a", "triage", "approve", "good", when=date(2026, 6, 6))
    record_feedback(str(fb), "b", "triage", "reject", "low pay", when=date(2026, 6, 6))
    md = build_pipeline(tmp_path, feedback_path=str(fb))
    assert "1/2 (50%)" in md
