# tests/test_render_pdf.py
import pytest
from weasyprint import HTML

from render_pdf import (build_html, render_pdf, render_cv_html, render_ats_html,
                        _rich, _plain, _is_structured)
from store import save_opportunity


def _cv_fixture(**over):
    """Synthetic structured cv_cover draft (no personal data) for the editorial
    template. Exercises chips, highlight/bold markup, and a current entry."""
    cv = {
        "deliverable": "cv_cover",
        "name": "Test Person",
        "tagline": "Role Tagline",
        "contact": {"email": "t@example.com", "phone": "123",
                    "base": "City", "linkedin": "x"},
        "sidebar": [
            {"heading": "Education",
             "items": [{"title": "Degree", "meta": "School · 2020"}]},
            {"heading": "Tooling", "chips": ["Excel · SPSS", "Python"]},
        ],
        "profile": "A short profile with a ==metric== and **bold**.",
        "sections": [
            {"heading": "Experience", "note": "Remote", "entries": [
                {"role": "Role A", "org": "Org A", "date": "2024 – present",
                 "current": True, "summary": "Did things with ==99%== accuracy.",
                 "bullets": ["Bullet one", "Bullet **two**"]},
            ]},
        ],
    }
    cv.update(over)
    return cv


# --- build_html: pure markdown -> HTML, no system libs needed ---

def test_build_html_converts_markdown_body():
    html = build_html({"deliverable": "cv_cover"}, "# Alex\n\nData entry pro.")
    assert "<h1>Alex</h1>" in html
    assert "<p>Data entry pro.</p>" in html
    assert html.lstrip().startswith("<!DOCTYPE html>")


def test_build_html_tags_body_class_by_deliverable():
    cv = build_html({"deliverable": "cv_cover"}, "x")
    gig = build_html({"deliverable": "gig_proposal"}, "x")
    assert "class='cv-cover'" in cv
    assert "class='gig-proposal'" in gig


def test_build_html_defaults_to_cv_cover_when_unset():
    assert "class='cv-cover'" in build_html({}, "x")


# --- render_pdf: end-to-end through WeasyPrint ---

def test_render_pdf_writes_a_real_pdf(tmp_path):
    draft = tmp_path / "acme-va-abc123.md"
    save_opportunity(str(draft),
                     {"opp_id": "acme-va-abc123", "deliverable": "cv_cover",
                      "org": "Acme", "title": "VA"},
                     "# Alex Rivera\n\n## Summary\n\nRemote data-entry specialist.")
    out = render_pdf(str(draft))

    assert out.endswith(".pdf")
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_render_pdf_honors_explicit_out_path(tmp_path):
    draft = tmp_path / "d.md"
    save_opportunity(str(draft), {"deliverable": "gig_proposal"},
                     "# Proposal\n\nHello.")
    out = tmp_path / "custom.pdf"
    returned = render_pdf(str(draft), str(out))
    assert returned == str(out)
    assert out.exists() and out.read_bytes().startswith(b"%PDF")


# --- structured editorial template: regressions for bugs found in the live run ---

def test_rich_filter_converts_markup_and_escapes_html():
    out = str(_rich("a ==hi== and **bold** and <script>"))
    assert "<mark>hi</mark>" in out
    assert "<strong>bold</strong>" in out
    assert "&lt;script&gt;" in out and "<script>" not in out  # no HTML injection


def test_chips_render_as_line_breaks_not_literal_tags():
    # regression: chips were literal "<br>" in YAML and showed escaped on the page
    html = render_cv_html(_cv_fixture())
    assert "Excel · SPSS<br>Python" in html
    assert "&lt;br&gt;" not in html


def test_highlight_and_bold_applied_no_leaked_tokens():
    html = render_cv_html(_cv_fixture())
    assert "<mark>metric</mark>" in html and "<mark>99%</mark>" in html
    assert "<strong>bold</strong>" in html and "<strong>two</strong>" in html
    assert "==" not in html  # no leaked highlight markers


def test_running_footer_css_present():
    # regression: footer was clipped when @page had no bottom margin
    html = render_cv_html(_cv_fixture())
    assert "@bottom-left" in html and "@bottom-right" in html
    assert "margin: 13mm 0 11mm 0" in html  # bottom margin reserves the footer band


def test_continuation_pages_have_a_top_margin():
    # regression: with @page top margin 0, an entry that broke to page 2+ hugged the
    # very top edge (no header band there to supply spacing). Continuation pages now
    # carry a top margin; page 1 opts out because .head supplies its own top space.
    css = render_cv_html(_cv_fixture()).split("</style>", 1)[0]
    assert "margin: 13mm 0 11mm 0" in css       # base: top margin on every page
    assert "@page:first" in css                 # page 1 ...
    assert "margin-top: 0" in css               # ... zeroes it (header supplies spacing)


def test_entries_and_blocks_avoid_breaking_across_pages():
    # regression: an entry header was stranded at a page foot with its body on the
    # next page; sidebar block heading split from its chips.
    html = render_cv_html(_cv_fixture())
    body = html.split("</style>", 1)[1]
    assert body.count("break-inside") == 0  # the rule lives in CSS, not inlined
    css = html.split("</style>", 1)[0]
    assert css.count("break-inside: avoid") >= 2  # .entry and .blk both guarded


def test_is_structured_routes_only_structured_cv_cover():
    assert _is_structured(_cv_fixture()) is True
    assert _is_structured({"deliverable": "cv_cover"}) is False          # no sections
    assert _is_structured({"deliverable": "gig_proposal",
                           "sections": [1]}) is False                    # wrong shape


def test_structured_cv_paginates_without_a_blank_page():
    # regression: a flex two-column body bumped the whole block to page 2,
    # leaving page 1 blank. A minimal CV must be exactly one page; adding a
    # cover letter adds exactly one more.
    base = _cv_fixture()
    one = len(HTML(string=render_cv_html(base)).render().pages)
    assert one == 1, f"minimal CV should be 1 page, got {one}"
    withcl = dict(base, cover_letter="Dear Team,\n\nHello there.\n\nRegards,\n\nName")
    assert len(HTML(string=render_cv_html(withcl)).render().pages) == 2


# --- ATS-safe single-column variant (resume-parser legibility) ---

def test_plain_filter_strips_markup_markers():
    assert _plain("a ==hi== and **bold**") == "a hi and bold"
    assert _plain(None) == ""


def test_ats_html_is_single_column_no_letterspacing():
    # the whole point: parsers scramble two-column + letter-spaced layouts
    html = render_ats_html(_cv_fixture())
    assert "letter-spacing:" not in html        # no spaced-out "E x p e r i e n c e" (CSS prop)
    assert "display: table" not in html         # no two-column table
    assert 'class="aside"' not in html and 'class="grid"' not in html


def test_ats_html_has_canonical_headings_in_reading_order():
    html = render_ats_html(_cv_fixture())
    for h in ("<h2>Summary</h2>", "<h2>Skills</h2>", "<h2>Experience</h2>",
              "<h2>Education</h2>"):
        assert h in html
    # name must linearize before Experience (parsers read top-to-bottom)
    assert html.index("Test Person") < html.index("<h2>Experience</h2>")


def test_ats_html_strips_inline_markup_no_mark_tags():
    html = render_ats_html(_cv_fixture())
    assert "<mark>" not in html and "==" not in html   # plain text, not highlighted
    assert "metric" in html and "99%" in html          # content survives, markers gone


def test_render_pdf_emits_ats_variant(tmp_path):
    draft = tmp_path / "acme-fde-abc123.md"
    save_opportunity(str(draft), dict(_cv_fixture(opp_id="acme-fde-abc123")), "")
    render_pdf(str(draft))
    ats = tmp_path / "acme-fde-abc123-ats.pdf"
    assert ats.exists() and ats.read_bytes().startswith(b"%PDF")


# --- split_cover: CV and cover letter as two separate PDFs ---

def test_cover_only_renders_just_the_cover_no_cv_body():
    cv = _cv_fixture(cover_letter="Dear Team,\n\nHello there.\n\nRegards,\n\nName")
    html = render_cv_html(cv, cover_only=True)
    assert "cover-body" in html and "Hello there." in html
    assert 'class="grid"' not in html        # CV two-column body dropped
    assert 'class="head"' not in html         # top contact band dropped
    # standalone cover is a single page (no leading blank from page-break-before)
    assert len(HTML(string=html).render().pages) == 1


def test_cv_only_drops_the_cover_letter():
    cv = _cv_fixture(cover_letter="Dear Team,\n\nHello.\n\nRegards,\n\nName")
    html = render_cv_html(cv, cv_only=True)
    assert 'class="grid"' in html             # CV body present
    assert '<section class="cover">' not in html  # cover letter dropped
    assert "Hello." not in html
    assert len(HTML(string=html).render().pages) == 1


def test_split_cover_writes_two_pdfs(tmp_path):
    draft = tmp_path / "acme-fde-abc123.md"
    save_opportunity(str(draft), dict(_cv_fixture(
        opp_id="acme-fde-abc123", split_cover=True,
        cover_letter="Dear Team,\n\nHello.\n\nRegards,\n\nName")), "")
    out = render_pdf(str(draft))

    cover = tmp_path / "acme-fde-abc123-cover.pdf"
    assert open(out, "rb").read().startswith(b"%PDF")
    assert cover.exists() and cover.read_bytes().startswith(b"%PDF")
