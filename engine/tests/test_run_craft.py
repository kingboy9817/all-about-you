# tests/test_run_craft.py
from datetime import date
from run import choose_deliverable, build_pipeline, record_feedback
from store import save_opportunity


# --- choose_deliverable: deterministic shape selection ---

def test_explicit_deliverable_field_wins():
    assert choose_deliverable({"deliverable": "gig_proposal",
                               "source": "remoteok"}) == "gig_proposal"
    assert choose_deliverable({"deliverable": "cv_cover",
                               "url": "https://upwork.com/jobs/x"}) == "cv_cover"


def test_job_board_source_defaults_to_cv_cover():
    assert choose_deliverable({"source": "remoteok"}) == "cv_cover"
    assert choose_deliverable({"source": "remotive"}) == "cv_cover"


def test_marketplace_url_defaults_to_gig_proposal():
    assert choose_deliverable(
        {"source": "manual-paste", "url": "https://www.upwork.com/jobs/abc"}
    ) == "gig_proposal"
    assert choose_deliverable({"source": "fiverr"}) == "gig_proposal"


def test_unknown_or_bad_override_falls_back_to_cv_cover():
    assert choose_deliverable({}) == "cv_cover"
    assert choose_deliverable({"deliverable": "nonsense",
                               "source": "remoteok"}) == "cv_cover"


# --- draft acceptance metric surfaces in the pipeline ---

def test_pipeline_shows_drafted_board_and_draft_acceptance(tmp_path):
    save_opportunity(str(tmp_path / "a.md"),
                     {"id": "a", "org": "Acme", "title": "VA", "status": "drafted",
                      "tier": "deep"}, "")
    fb = tmp_path / "feedback.md"
    when = date(2026, 6, 9)
    record_feedback(str(fb), "a", "draft", "accept", "clean", when=when)
    record_feedback(str(fb), "b", "draft", "edit", "tightened intro", when=when)
    record_feedback(str(fb), "c", "draft", "reject", "off voice", when=when)
    # a triage row must NOT count toward draft acceptance
    record_feedback(str(fb), "d", "triage", "approve", "", when=when)

    md = build_pipeline(tmp_path, str(fb))
    assert "**drafted**: 1" in md
    assert "Draft acceptance" in md
    assert "1/3 (33%)" in md


def test_pipeline_draft_acceptance_dash_when_no_draft_rows(tmp_path):
    save_opportunity(str(tmp_path / "a.md"),
                     {"id": "a", "org": "O", "title": "T", "status": "shortlisted"}, "")
    md = build_pipeline(tmp_path, None)
    assert "Draft acceptance" in md
    assert "Draft acceptance** (accepted / draft decisions): —" in md
