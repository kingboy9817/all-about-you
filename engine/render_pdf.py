# render_pdf.py
"""Render a draft markdown file to PDF via WeasyPrint.

Deterministic wrapper: the Craft agent writes ``drafts/<slug>/<slug>.md`` (frontmatter +
markdown body); this turns it into ``drafts/<slug>/<slug>.pdf`` with a clean default
template chosen by deliverable type (``cv_cover`` | ``gig_proposal``). Template
fidelity is intentionally minimal for v1 — iterate later.
"""
import html as _html
import re
from pathlib import Path

import markdown as _md
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from store import load_opportunity

_TEMPLATES = Path(__file__).parent / "templates"

BASE_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 19pt; margin: 0 0 2pt; }
h2 { font-size: 12pt; margin: 14pt 0 4pt; padding-bottom: 2pt;
     border-bottom: 1px solid #ccc; text-transform: uppercase;
     letter-spacing: 0.04em; }
h3 { font-size: 11pt; margin: 8pt 0 2pt; }
p, ul, ol { margin: 0 0 6pt; }
ul, ol { padding-left: 18px; }
li { margin: 0 0 2pt; }
a { color: inherit; text-decoration: none; }
"""

CV_CSS = """
body.cv-cover h1 { color: #111; }
"""

PROPOSAL_CSS = """
body.gig-proposal { font-size: 11pt; }
body.gig-proposal h1 { font-size: 16pt; }
body.gig-proposal h2 { text-transform: none; letter-spacing: 0; }
"""


def _css_for(deliverable):
    extra = PROPOSAL_CSS if deliverable == "gig_proposal" else CV_CSS
    return BASE_CSS + extra


def build_html(meta, body_md):
    """Pure markdown-body -> standalone HTML string. No system libs required,
    so this is unit-testable without WeasyPrint installed. The body gets a class
    of the deliverable type (``cv-cover`` | ``gig-proposal``) for CSS hooks."""
    deliverable = meta.get("deliverable") or "cv_cover"
    if deliverable not in ("cv_cover", "gig_proposal"):
        deliverable = "cv_cover"
    body_html = _md.markdown(body_md or "", extensions=["extra", "sane_lists"])
    css = _css_for(deliverable)
    title = " — ".join(x for x in (meta.get("org"), meta.get("title")) if x)
    return (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{css}</style></head>"
        f"<body class='{deliverable.replace('_', '-')}'>{body_html}</body></html>"
    )


def _rich(s):
    """Tiny inline markup for template strings: ``**bold**`` -> <strong>,
    ``==hl==`` -> <mark>. HTML-escapes first, so source data can't inject tags."""
    if s is None:
        return Markup("")
    out = _html.escape(str(s))
    out = re.sub(r"==(.+?)==", r"<mark>\1</mark>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return Markup(out)


def _plain(s):
    """ATS variant of ``_rich``: strip the inline markup markers (``==hl==``,
    ``**bold**``) to plain text — no <mark>/<strong> styling. Returned as a plain
    str so Jinja autoescape still neutralizes any HTML in the source data."""
    if s is None:
        return ""
    out = re.sub(r"==(.+?)==", r"\1", str(s))
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    return out


def _jinja():
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["rich"] = _rich
    env.filters["plain"] = _plain
    return env


def render_cv_html(meta, cover_only=False, cv_only=False):
    """Render a structured cv_cover draft (rich frontmatter) through the editorial
    Jinja template. The cover-letter markdown is converted to HTML here.

    ``cv_only`` drops the cover letter (CV pages only). ``cover_only`` drops the CV
    body (header + two-column grid) and renders just the cover letter as a standalone
    document — together these let ``split_cover`` emit the CV and the cover as two PDFs."""
    ctx = dict(meta)
    ctx["cover_only"] = cover_only
    cl = None if cv_only else meta.get("cover_letter")
    ctx["cover_letter_html"] = _md.markdown(cl, extensions=["extra"]) if cl else ""
    return _jinja().get_template("cv.html").render(**ctx)


def render_ats_html(meta):
    """Render an ATS-safe single-column CV from the same structured ``meta``.

    The editorial ``cv.html`` is a two-column, letter-spaced design built for human
    eyes — but resume parsers read left-to-right top-to-bottom and choke on it: the
    columns interleave and letter-spacing splits ``Experience`` into ``E x p ...``,
    breaking keyword + heading detection. This variant is single-column, system-font,
    canonical-heading, plain-text (CV only, no cover) — the file to upload to an
    ATS / Greenhouse portal. Same data, parser-legible."""
    return _jinja().get_template("cv_ats.html").render(**meta)


def _is_structured(meta):
    """A cv_cover draft with structured sections renders via the template; anything
    else (gig_proposal, plain markdown drafts) falls back to build_html."""
    return meta.get("deliverable") == "cv_cover" and bool(meta.get("sections"))


def render_pdf(draft_path, out_path=None):
    """Render ``draft_path`` (markdown w/ frontmatter) to a PDF. Returns the
    output path. Defaults to the draft's stem with a ``.pdf`` suffix."""
    from weasyprint import HTML  # lazy: keeps build_html unit-testable w/o system libs

    meta, body = load_opportunity(draft_path)
    out_path = out_path or str(Path(draft_path).with_suffix(".pdf"))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Always emit an ATS-safe single-column CV alongside the editorial one, so the
    # owner has a parser-legible file to upload to ATS / Greenhouse portals.
    if _is_structured(meta):
        ats_path = str(Path(out_path).with_name(Path(out_path).stem + "-ats.pdf"))
        HTML(string=render_ats_html(meta)).write_pdf(ats_path)

    # split_cover: emit the CV and the cover letter as two separate PDFs
    # (<stem>.pdf + <stem>-cover.pdf) from one source draft.
    if _is_structured(meta) and meta.get("split_cover") and meta.get("cover_letter"):
        HTML(string=render_cv_html(meta, cv_only=True)).write_pdf(out_path)
        cover_path = str(Path(out_path).with_name(Path(out_path).stem + "-cover.pdf"))
        HTML(string=render_cv_html(meta, cover_only=True)).write_pdf(cover_path)
        return out_path

    html_str = render_cv_html(meta) if _is_structured(meta) else build_html(meta, body)
    HTML(string=html_str).write_pdf(out_path)
    return out_path
