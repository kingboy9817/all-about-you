# templates/ — Craft render templates

`render_pdf.py` turns a **structured `cv_cover` draft** (rich frontmatter) into a
PDF via `cv.html` (Jinja2 + WeasyPrint). Rendering is deterministic code, not an
agent step — the Craft agent (`prompts/craft.md`) produces the draft data; this
turns it into the same PDF every time. There is **no PDF-creation prompt** by design.

## Structured `cv_cover` frontmatter

```yaml
deliverable: cv_cover
name: ...            # serif display name
tagline: ...         # mono caps subtitle
ref: ...             # tiny kicker label
contact: {email, phone, base, linkedin}
sidebar:             # list of blocks
  - {heading, items: [{title, meta}]}     # titled items, OR
  - {heading, chips: ["a · b", "c"]}      # one chip per line (a YAML LIST)
profile: ...         # serif lead paragraph
sections:
  - heading: ...
    note: ...         # right-aligned label
    entries:
      - {role, org, date, summary, bullets: [...], current: true}
cover_letter: |       # markdown -> page 2
  ...
```

Inline markup in any string: `==text==` → highlight, `**text**` → bold. The `rich`
filter HTML-escapes data first, so draft content can never inject tags.

## Gotchas — bugs we already hit; do not reintroduce

1. **Two-column = CSS `table`, never `flex`.** A flex container won't fragment across
   pages, so once content passed one page the whole block jumped to page 2, leaving
   page 1 blank. `display: table` + `table-cell` paginate. (test: `test_structured_cv_paginates_without_a_blank_page`)
2. **Keep a bottom `@page` margin for the footer.** With `margin: 0` the running
   footer had no margin band and was clipped at the page edge. (test: `test_running_footer_css_present`)
3. **Keep a CV to ~1 page.** The table won't split *below the header*: if header +
   content exceed one page, the whole table jumps to the next page (blank first
   page). Tighten spacing / trim content so the CV fits one page, cover on page 2.
4. **Chips are a YAML list**, joined with `<br>` in the template — never embed a
   literal `<br>` in the data; the `rich` filter escapes it to visible `&lt;br&gt;`.
   (test: `test_chips_render_as_line_breaks_not_literal_tags`)
5. **Jinja: use `blk['items']`, not `blk.items`** — the latter resolves to the dict's
   built-in `.items()` method and explodes.
6. **Folded YAML scalars (`>`) join lines with a space** — don't split a hyphenated
   word across source lines (`behavioural-\n  insights` renders as "behavioural-
   insights"). Keep hyphenated words on one line.
7. **Keep blocks unbroken across pages — it's the renderer's job, not the drafter's.**
   `.entry` and `.blk` carry `break-inside: avoid` so an experience entry never has its
   role header stranded at a page foot with its body on the next page, and a sidebar
   block never splits its heading from its chips. A block that doesn't fit moves whole
   to the next page. Don't try to control page breaks by hand-trimming draft content —
   the rule fires automatically on every render. (Caveat: an entry taller than the
   printable area still breaks — WeasyPrint degrades gracefully — so keep any single
   entry under ~one page.) (test: `test_entries_and_blocks_avoid_breaking_across_pages`)
8. **Continuation pages need a top margin; page 1 doesn't.** The `@page` top margin was
   `0` because page 1's top spacing comes from the `.head` band — but page 2+ have no
   header, so content broke flush against the top edge. Fix: base `@page { margin: 13mm
   0 11mm 0 }` for breathing room on every page, and `@page:first { margin-top: 0 }` so
   page 1 isn't double-spaced (which would risk pushing content to a third page). Don't
   "fix" a top-hugging entry by hand-inserting blank lines in the draft — the margin is
   the renderer's job. (test: `test_continuation_pages_have_a_top_margin`)
9. **Two-column editorial PDFs do not survive resume parsers — always ship a single-column
   ATS variant too.** ATS / AI screeners (e.g. Greenhouse, which Stripe uses) read only the
   *parsed text*: they linearize left-to-right, top-to-bottom, so the two-column grid
   interleaves the skills rail into the experience, and CSS `letter-spacing` splits a heading
   into `E x p e r i e n c e` and a keyword like `Forward Deployed` into spaced letters that
   **fail keyword matching**. So `render_pdf` always *also* emits `<slug>-ats.pdf` from
   `render_ats_html` + `templates/cv_ats.html`: single column, system font, canonical headings
   (Summary/Skills/Experience/Education), no `letter-spacing`, plain text (markup stripped via
   the `plain` filter). Upload the `-ats.pdf` to portals; use the editorial two-column for
   human / warm-intro. Keyword coverage is a *content* job — put JD terms in the structured
   draft (profile/skills), not the template. Sharpens gotcha #5: `blk['items']` is safe only
   when the key is known to exist (cv.html guards it behind `{% if blk.chips %}…{% else %}`);
   iterating *all* sidebar blocks (as cv_ats.html does) needs `blk.get('items')`, else an
   `items`-less block resolves to the dict's `.items` method (truthy, uniterable) and explodes.
   (tests: `test_ats_html_*`, `test_render_pdf_emits_ats_variant`)

## How layout guarantees are preserved (the pattern)

Layout fidelity is a **guarantee**, so it lives in deterministic code, not agent
judgment (see the root `CLAUDE.md` principle 3). Each fix we land has three layers so it
survives future re-crafts and future agents: (1) the CSS rule in `cv.html`, (2) a
regression test in `tests/test_render_pdf.py` that fails if the rule is stripped, and
(3) a numbered gotcha here explaining *why*, so no one reintroduces the bug. Add a new
layout instinct the same way — rule + test + gotcha — never as a one-off manual tweak to
a draft.
