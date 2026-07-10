# draft_lint.py
"""Deterministic AI-tic linter for application drafts.

WHY THIS IS CODE, NOT A PROMPT CHECKLIST: the voice.md "AI tells" rules used to
live only as prose in `voice.md` + `prompts/craft.md`'s QC list — the
*agent-judgment* bucket, which by CLAUDE.md principle 3 is measured-not-
guaranteed: it fired only if the drafting agent remembered, and on 2026-06-19 a
re-craft sailed through with 29 em-dashes. These tics are *mechanically*
checkable, so they belong in the deterministic, unit-tested bucket — here.
`find_tells()` SURFACES flags; it does NOT block (a flag is a prompt to look).

EM-DASH RULE, calibrated to the owner (2026-06-19): 0 is NOT the goal — he writes
with em-dashes as moderators (they do a comma's job). The unit is the PARAGRAPH,
and the budget is **one em-dash "unit" per paragraph**, where a unit is either:
  • a single em-dash, OR
  • a parenthetical PAIR — two em-dashes in one sentence: "X — aside — Y".
So a paragraph may carry one lone dash OR one pair, but NOT two separate dashes,
and NOT a 3+ dash chain in a sentence. Cliché list excludes his own vocabulary
(leverage / seamless / furthermore / harness / … — see test_owner_vocabulary).
"""
import re

EM_DASH = "—"  # — (NOT the en-dash – used in date ranges like 2024–2025)

_NOT_PATTERNS = [
    r"\bnot just\b",
    r"\bisn't just\b",
    r"\bnot only\b",
    r"\bnot\s+\w+[,]?\s+but\b",        # "not X but Y" / "not X, but Y"
    r"\bnot\s+\w+\s+without\b",         # "not one without the other"
]

# Short, high-precision AI-cliché list — NONE of the owner's genuine vocabulary
# (see module docstring). Low severity: advisory.
_CLICHES = [
    "delve", "tapestry", "multifaceted", "underscore", "boasts",
    "ever-evolving", "in today's", "it's important to note",
    "it's worth noting", "navigating the", "realm of",
]

# A line that INTRODUCES a YAML value: a "- " bullet or a "key: " scalar.
_SCALAR_RE = re.compile(r"^\s*(?:-\s+|[A-Za-z_][\w-]*:\s+)(?P<val>\S.*)$")


def _plain_scalar_has_comment(val):
    """True if `val` is an UNQUOTED YAML plain scalar carrying a ' #' — which YAML
    reads as the start of a comment and silently DROPS everything after it (and any
    closing '==' with it). Quoted/block/flow/anchor values are immune, so skip them."""
    v = val.rstrip()
    if not v or v[0] in "'\"|>&*[{#":
        return False
    return bool(re.search(r"\s#", v))


def _paragraphs(text):
    """Blank-line-delimited blocks. For a structured draft, feed prose via
    `prose_text(meta)`, which joins each field/bullet with a blank line so every
    chunk is its own paragraph."""
    return [p for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def _sentences(paragraph):
    """Whitespace-collapsed sentence split, so a sentence wrapped across folded
    YAML-scalar lines is still counted as one sentence."""
    norm = re.sub(r"\s+", " ", paragraph or "")
    return [s for s in re.split(r"(?<=[.!?])\s+", norm) if s]


def _paragraph_em_exceeds(paragraph, max_units):
    """A paragraph is over budget if it holds more than `max_units` em-dash units
    (a single dash, or a 2-dash parenthetical pair = 1 unit each) OR any sentence
    has a 3+ em-dash chain."""
    units = 0
    for s in _sentences(paragraph):
        d = s.count(EM_DASH)
        if d == 0:
            continue
        if d >= 3:
            return True            # dash-chain in one sentence
        units += 1                 # d == 1 (lone) or d == 2 (pair) -> one unit
    return units > max_units


def find_tells(text, max_em_dash_units_per_paragraph=1):
    """Return a list of flag dicts for AI/voice tics in `text`. Em-dash use is
    judged per paragraph (see `_paragraph_em_exceeds`); `count` is the doc total
    (informational), `paragraphs` is how many paragraphs are over budget."""
    text = text or ""
    flags = []

    over = [p for p in _paragraphs(text)
            if _paragraph_em_exceeds(p, max_em_dash_units_per_paragraph)]
    if over:
        flags.append({"tell": "em_dash", "severity": "high",
                      "count": text.count(EM_DASH), "paragraphs": len(over),
                      "examples": [_trim(p) for p in over[:3]],
                      "fix": "≤1 em-dash unit per paragraph — one lone dash OR one "
                             "'X — aside — Y' pair; split the paragraph or use commas"})

    for pat in _NOT_PATTERNS:
        hits = list(re.finditer(pat, text, flags=re.I))
        if hits:
            flags.append({"tell": "x_not_y", "severity": "medium", "count": len(hits),
                          "pattern": pat, "examples": [_ctx(text, m) for m in hits[:3]],
                          "fix": "voice.md: no 'x not y' constructions — state it straight"})

    for w in _CLICHES:
        pat = r"\b" + re.escape(w) + r"\b"
        c = len(re.findall(pat, text, flags=re.I))
        if c:
            flags.append({"tell": "cliche", "severity": "low", "word": w, "count": c,
                          "fix": "2026 AI-detector flag — swap for a plain, specific word"})

    return flags


def find_truncations(meta, raw):
    """Flag content the YAML parser DROPS or MANGLES *before the renderer sees it* —
    the blind spot of the prose linter, which only ever inspects the already-parsed
    (already-truncated) value and so reports "clean" on a half-eaten bullet. Three
    failure modes seen live, all high-severity because they silently ship broken text:

      • yaml_comment_truncation — an unquoted ' #' cuts the value at the hash
        (2026-06-19: a bullet's '… ranked #1 on Google ==…==' shipped to a real
        application as '… ranked', losing half the sentence and its closing '=='
        highlight). Scanned from the raw frontmatter, since the parsed value is the
        already-truncated one.
      • yaml_bullet_not_string — '- Label: detail' parses as a dict, not a string
        bullet (the 2026-06-19 ': '-swap regression).
      • unbalanced_highlight — an odd count of '==' in a parsed value: a half-open
        highlight, usually the downstream symptom of a truncation (or a typo).

    `raw` is the frontmatter text; `meta` its parsed form. Flags shaped like
    `find_tells()` so `_fmt()`/`summary()` render them uniformly."""
    flags = []
    for sec in meta.get("sections") or []:
        for e in sec.get("entries") or []:
            for b in e.get("bullets") or []:
                if not isinstance(b, str):
                    flags.append({"tell": "yaml_bullet_not_string", "severity": "high",
                                  "count": 1, "examples": [_trim(repr(b))],
                                  "fix": f"bullet parsed as {type(b).__name__}, not text — "
                                         "an unquoted ': ' makes a YAML dict; quote the bullet"})
    for blk in prose_blocks(meta):
        if blk.count("==") % 2:
            flags.append({"tell": "unbalanced_highlight", "severity": "high",
                          "count": blk.count("=="), "examples": [_trim(blk)],
                          "fix": "odd number of '==' — a half-open highlight, often a "
                                 "YAML-truncated value; close it or quote the scalar"})
    for ln in (raw or "").splitlines():
        m = _SCALAR_RE.match(ln)
        if m and _plain_scalar_has_comment(m.group("val")):
            flags.append({"tell": "yaml_comment_truncation", "severity": "high",
                          "count": 1, "examples": [_trim(ln.strip())],
                          "fix": "unquoted ' #' starts a YAML comment — text after it is "
                                 "DROPPED before render; single-quote the whole value"})
    return flags


def prose_blocks(meta):
    """Extract the prose chunks (paragraphs) of a structured cv_cover draft:
    profile, each experience summary + bullet, and each cover-letter paragraph.
    Chips/labels are excluded (they're fragments, not prose)."""
    blocks = []
    if meta.get("profile"):
        blocks.append(str(meta["profile"]))
    for sec in meta.get("sections") or []:
        for e in sec.get("entries") or []:
            if e.get("summary"):
                blocks.append(str(e["summary"]))
            blocks.extend(str(b) for b in (e.get("bullets") or []))  # str(): a YAML
            # mis-parse ("- Label: detail" -> dict) shouldn't crash the linter
    cl = meta.get("cover_letter")
    if cl:
        blocks.extend(p for p in re.split(r"\n\s*\n", str(cl)) if p.strip())
    return blocks


def prose_text(meta):
    """Structured draft -> one text with each prose chunk as its own paragraph
    (blank-line separated), ready for `find_tells`."""
    return "\n\n".join(prose_blocks(meta))


def _trim(s, n=80):
    s = " ".join((s or "").split())
    return (s[:n] + "…") if len(s) > n else s


def _ctx(text, m, width=28):
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return "…" + " ".join(text[a:b].split()) + "…"


def _fmt(flags, clean="clean — no AI tics flagged", label="TICS"):
    if not flags:
        return clean
    parts = [f"{f.get('word') or f['tell']}×{f.get('count', 1)}[{f['severity'][0]}]"
             for f in flags]
    return f"{label}: " + ", ".join(parts)


def summary(text, **kw):
    """One-line human summary for the Craft QC step / CLI."""
    return _fmt(find_tells(text, **kw))


if __name__ == "__main__":  # quick CLI: python draft_lint.py <draft.md ...>
    import sys
    try:
        from store import load_opportunity
    except Exception:
        load_opportunity = None
    for path in sys.argv[1:]:
        if load_opportunity:
            meta, _ = load_opportunity(path)
            if meta.get("deliverable") == "cv_cover" and meta.get("sections"):
                with open(path, encoding="utf-8") as fh:
                    src = fh.read()
                fm = src.split("---", 2)[1] if src.startswith("---") else src
                trunc = find_truncations(meta, fm)
                if trunc:  # render-breaking: louder than a tic
                    print(f"{path}: ⚠ YAML DROPS CONTENT — {_fmt(trunc, label='RENDER')}")
                print(f"{path}: {summary(prose_text(meta))}")
                continue
        with open(path, encoding="utf-8") as fh:
            print(f"{path}: {summary(fh.read())}")
