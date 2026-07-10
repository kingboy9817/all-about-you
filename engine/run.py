# run.py
"""Thin orchestrator + deterministic helpers. The agent (Claude Code) does the
fuzzy steps (search/extract/score); these functions enforce the guarantees."""
import glob
import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from rules import (passes_hard_filters, assign_tier, dedupe_key, legitimacy_flags,
                   geo_gate, liveness_gate, score_fit, PASS, SKIP, NEEDS_REVIEW)
from store import load_opportunity, save_opportunity


def screen_opportunity(opp, provider, today=None):
    """Run the deterministic hard-filter gate using the provider's lens."""
    lens = provider.get_lens()
    return passes_hard_filters(opp, lens.get("hard_filters", {}), today=today)


def make_slug(opp):
    """Stable, unique, readable slug: org-title words + 6 chars of the dedupe key."""
    basis = " ".join(x for x in [opp.get("org"), opp.get("title")] if x) \
        or opp.get("url") or "opportunity"
    words = re.sub(r"[^a-z0-9]+", "-", basis.lower()).strip("-")[:50] or "opportunity"
    return f"{words}-{dedupe_key(opp)[:6]}"


def discover_write(candidates, opps_dir, today=None):
    """Dedup candidates (by URL/org+title key, incl. against existing files) and
    write one markdown record each (status: discovered). Returns a summary dict
    with per-source counts. Lane-agnostic: 'source' is just a string."""
    today = today or date.today()
    opps_dir = Path(opps_dir)
    opps_dir.mkdir(parents=True, exist_ok=True)
    seen = set()
    for fp in glob.glob(str(opps_dir / "*.md")):
        fm, _ = load_opportunity(fp)
        if fm.get("dedupe_key"):
            seen.add(fm["dedupe_key"])
    written, skipped, per_source = [], [], {}
    for c in candidates:
        key = dedupe_key(c)
        src = c.get("source", "unknown")
        per_source.setdefault(src, {"written": 0, "skipped": 0})
        if key in seen:
            skipped.append(key)
            per_source[src]["skipped"] += 1
            continue
        seen.add(key)
        slug = make_slug(c)
        fm = {
            "id": slug,
            "opportunity_type": "job",
            "source": src,
            "url": c.get("url"),
            "org": c.get("org"),
            "title": c.get("title"),
            "status": "discovered",
            "dedupe_key": key,
            "extracted": {},
            "flags": [],
            "date_found": today.isoformat(),
        }
        save_opportunity(str(opps_dir / f"{slug}.md"), fm, c.get("description", ""))
        written.append(slug)
        per_source[src]["written"] += 1
    return {"written": written, "skipped": skipped, "per_source": per_source}


def ingest_inbox(inbox_dir, opps_dir, today=None):
    """Promote manual-paste drops (markdown w/ frontmatter) into normal
    opportunity records via discover_write, then clear the inbox. Returns the
    slugs written. The agent fills each inbox file's frontmatter + body first."""
    inbox_dir = Path(inbox_dir)
    if not inbox_dir.is_dir():
        return []
    files = sorted(glob.glob(str(inbox_dir / "*.md")))
    candidates = []
    for fp in files:
        fm, body = load_opportunity(fp)
        c = dict(fm)
        c["description"] = body
        c.setdefault("source", "manual-paste")
        candidates.append(c)
    summary = discover_write(candidates, opps_dir, today=today)
    for fp in files:
        Path(fp).unlink()
    return summary["written"]


def suspect_org_names(opps_dir):
    """Org names carrying a prior suspect/scam legitimacy verdict, for variant
    matching in legitimacy_flags (Plan 7: 'Re-cruit-Lytic' vs 'RecruitLytic')."""
    names = set()
    for fp in sorted(glob.glob(str(Path(opps_dir) / "*.md"))):
        fm, _ = load_opportunity(fp)
        if fm.get("legitimacy") in ("suspect", "scam") and fm.get("org"):
            names.add(fm["org"])
    return names


def evaluate(opp, lens, today=None, org_counts=None, text="", suspect_orgs=None):
    """Apply the deterministic gates to an opp the agent has already extracted
    (+ scored, for survivors). Sets filter_result, tier, status, legitimacy;
    appends filter + legitimacy reasons to flags. Expects (when scored):
    capability_score, intent_score, matched_priority_goal. org_counts (org ->
    batch count), text (posting body) and suspect_orgs (prior suspect verdicts,
    see suspect_org_names) feed the legitimacy check. A legitimacy-flagged opp
    is routed to needs_review instead of auto-shortlisting (fail closed).

    Liveness/Plan-7 guarantee: a record can only become `shortlisted` by clearing
    BOTH geo_gate (applicant eligibility: extracted.geo_scope / language_req vs the
    lens eligibility block) AND liveness_gate (the listing is verified-OPEN:
    extracted.liveness {status, expiry_date, checked_at}). Either gate's unknown
    parks the record in needs_review (fail closed); an explicit closed/mismatch is
    rejected outright. Returns the updated opp dict (does not write)."""
    opp = dict(opp)
    fr = passes_hard_filters(opp, lens.get("hard_filters", {}), today=today)
    opp["filter_result"] = fr.status
    legit = legitimacy_flags(opp, org_counts=org_counts, text=text,
                             suspect_orgs=suspect_orgs)
    opp["flags"] = list(opp.get("flags", [])) + list(fr.reasons) + legit
    opp["legitimacy"] = "suspect" if legit else "unverified"
    if fr.status == SKIP:
        opp["tier"] = "skip"
        opp["status"] = "rejected"
        return opp
    cap, intent = opp.get("capability_score"), opp.get("intent_score")
    if (cap is None or intent is None) and opp.get("fit_inputs") is not None:
        sf = score_fit(opp["fit_inputs"], lens)   # Plan 8: programmatic score from LLM atoms
        cap = opp["capability_score"] = sf["capability"]
        intent = opp["intent_score"] = sf["intent"]
        opp["fit_breakdown"] = sf["breakdown"]
    if cap is None or intent is None:
        # survivor not yet scored: leave for the agent's scoring pass
        opp["status"] = "needs_review" if fr.status == NEEDS_REVIEW else "discovered"
        return opp
    tier = assign_tier(cap, intent, lens.get("tier_thresholds", {}),
                       matched_priority_goal=bool(opp.get("matched_priority_goal")))
    opp["tier"] = tier
    if fr.status == NEEDS_REVIEW:
        opp["status"] = "needs_review"
    elif tier == "skip":
        opp["status"] = "rejected"
    elif legit:
        opp["status"] = "needs_review"   # legitimacy-flagged -> human review, not auto-shortlist
    else:
        extracted = opp.get("extracted", {}) or {}
        gg = geo_gate({"geo_scope": extracted.get("geo_scope"),
                       "language_req": extracted.get("language_req")},
                      lens.get("eligibility", {}))
        lg = liveness_gate(extracted.get("liveness"), today=today)   # listing must be verified-OPEN
        opp["flags"] = list(opp["flags"]) + list(gg.reasons) + list(lg.reasons)
        gates = (gg.status, lg.status)
        if SKIP in gates:
            opp["status"] = "rejected"
        elif NEEDS_REVIEW in gates:
            opp["status"] = "needs_review"  # awaiting verify stage / human look
        else:
            opp["status"] = "shortlisted"
    return opp


MARKETPLACE_SOURCES = {"upwork", "fiverr", "contra", "freelancer", "guru",
                       "peopleperhour", "toptal"}
MARKETPLACE_HOSTS = ("upwork.com", "fiverr.com", "contra.com", "freelancer.com",
                     "guru.com", "peopleperhour.com", "toptal.com")


def choose_deliverable(opp):
    """Pick the application deliverable shape for an opportunity.

    An explicit ``deliverable`` field wins; otherwise default by source/url —
    marketplace gig platforms -> ``gig_proposal``, everything else -> ``cv_cover``.
    Deterministic so the choice is auditable and the agent can't drift it."""
    explicit = opp.get("deliverable")
    if explicit in ("cv_cover", "gig_proposal"):
        return explicit
    src = (opp.get("source") or "").lower()
    url = (opp.get("url") or "").lower()
    if src in MARKETPLACE_SOURCES or any(h in url for h in MARKETPLACE_HOSTS):
        return "gig_proposal"
    return "cv_cover"


def record_feedback(feedback_path, opportunity_id, gate, decision, reason="", when=None):
    """Append one decision to feedback.md (append-only learning log)."""
    when = when or date.today()
    p = Path(feedback_path)
    if not p.exists():
        p.write_text("# feedback.md — append-only decision log\n\n"
                     "| date | opportunity_id | gate | decision | reason |\n"
                     "|---|---|---|---|---|\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"| {when.isoformat()} | {opportunity_id} | {gate} | {decision} | {reason} |\n")


FOLLOWUP_DAYS = 7

OUTCOMES = {"reply": "replied", "interview": "interview", "offer": "offer",
            "ghost": "closed", "closed": "closed"}


def mark_submitted(record_path, when=None, followup_days=FOLLOWUP_DAYS):
    """Gate-3 state transition: drafted -> submitted, stamping date_submitted
    and a next_followup nudge. Re-running on an already-submitted record just
    (re)stamps the dates — that's the backfill path for manual submissions.
    Any other status raises (fail closed: never submit what wasn't drafted)."""
    fm, body = load_opportunity(record_path)
    if fm.get("status") not in ("drafted", "submitted"):
        raise ValueError(f"cannot submit from status {fm.get('status')!r}")
    when = when or date.today()
    fm["status"] = "submitted"
    fm["date_submitted"] = when.isoformat()
    fm["next_followup"] = (when + timedelta(days=followup_days)).isoformat()
    save_opportunity(record_path, fm, body)
    return fm


def followups_due(opps_dir, today=None):
    """Submitted records whose next_followup is due (<= today), oldest first.
    The agent drafts the nudge; the owner sends it — never auto-send."""
    today = today or date.today()
    due = []
    for fp in sorted(glob.glob(str(Path(opps_dir) / "*.md"))):
        fm, _ = load_opportunity(fp)
        nf = fm.get("next_followup")
        if fm.get("status") == "submitted" and nf \
                and date.fromisoformat(str(nf)) <= today:
            due.append({"path": fp, "id": fm.get("id"), "org": fm.get("org"),
                        "title": fm.get("title"),
                        "date_submitted": fm.get("date_submitted"),
                        "next_followup": str(nf)})
    due.sort(key=lambda r: r["next_followup"])
    return due


def set_followup(record_path, when):
    """Re-arm the follow-up nudge on a submitted record (after a follow-up was
    sent with no response yet). Leaves date_submitted untouched; only valid on
    submitted records (fail closed)."""
    fm, body = load_opportunity(record_path)
    if fm.get("status") != "submitted":
        raise ValueError(f"cannot re-arm follow-up from status {fm.get('status')!r}")
    fm["next_followup"] = when.isoformat()
    save_opportunity(record_path, fm, body)
    return fm


def record_outcome(record_path, outcome, when=None, next_followup_days=None):
    """Record the slow ground-truth signal: outcome -> status transition
    (reply->replied, interview, offer, ghost/closed->closed). Only valid from
    submitted/replied/interview/offer; unknown outcomes raise (fail closed).
    Clears the follow-up nudge unless next_followup_days chains a new one."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}; one of {sorted(OUTCOMES)}")
    fm, body = load_opportunity(record_path)
    if fm.get("status") not in ("submitted", "replied", "interview", "offer"):
        raise ValueError(f"cannot record outcome from status {fm.get('status')!r}")
    when = when or date.today()
    fm["outcome"] = outcome
    fm["status"] = OUTCOMES[outcome]
    fm["date_outcome"] = when.isoformat()
    if next_followup_days:
        fm["next_followup"] = (when + timedelta(days=next_followup_days)).isoformat()
    else:
        fm.pop("next_followup", None)
    save_opportunity(record_path, fm, body)
    return fm


def read_feedback(feedback_path):
    """Parse feedback.md back into row dicts (date, opportunity_id, gate,
    decision, reason). Inverse of record_feedback; missing file -> []."""
    p = Path(feedback_path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        cells = line.split("|")
        if len(cells) < 7:
            continue
        first = cells[1].strip()
        if first == "date" or not first.strip("-"):
            continue
        rows.append({"date": first,
                     "opportunity_id": cells[2].strip(),
                     "gate": cells[3].strip(),
                     "decision": cells[4].strip(),
                     "reason": "|".join(cells[5:-1]).strip()})
    return rows


def _gate_rate(feedback_path, gate, good):
    rows = [r for r in read_feedback(feedback_path) if r["gate"] == gate]
    if not rows:
        return None
    n = sum(1 for r in rows if r["decision"] == good)
    return f"{n}/{len(rows)} ({round(100 * n / len(rows))}%)"


def _triage_precision(feedback_path):
    return _gate_rate(feedback_path, "triage", "approve")


def _draft_acceptance(feedback_path):
    """Gate-2 health: of draft decisions, the share accepted clean (not edited /
    rejected)."""
    return _gate_rate(feedback_path, "draft", "accept")


def load_golden_cases(path):
    """eval/cases.md -> {as_of, lens_baseline, cases} from its ```yaml block
    (same machine-readable-block convention as lens.md). {} when absent."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    m = re.search(r"```yaml\s*\n(.*?)\n```", text, re.DOTALL)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


_CASE_CONTROL_KEYS = ("expected", "note", "org_count", "text")


def run_golden_cases(golden, lens=None):
    """Drift guard for lens changes (spec §7.3): re-run evaluate() on each
    golden case — agent scores frozen in the case, deterministic gates live —
    and diff the verdict against the case's expected values. lens defaults to
    the baseline frozen in cases.md; pass a proposed lens to preview which
    cases a change would flip. Only the keys named in expected are compared."""
    lens = lens if lens is not None else golden.get("lens_baseline", {})
    today = golden.get("as_of")
    results = []
    for case in golden.get("cases", []):
        opp = {k: v for k, v in case.items() if k not in _CASE_CONTROL_KEYS}
        org_counts = {case["org"]: case["org_count"]} if case.get("org_count") else None
        verdict = evaluate(opp, lens, today=today, org_counts=org_counts,
                           text=case.get("text", ""))
        expected = case.get("expected", {})
        got = {k: verdict.get(k) for k in expected}
        results.append({"id": case.get("id"), "ok": got == expected,
                        "expected": expected, "got": got})
    failed = sum(1 for r in results if not r["ok"])
    return {"passed": len(results) - failed, "failed": failed, "results": results}


WILDCARD_FLAG = "exploration wildcard — off-lens on purpose"


def _iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def select_wildcards(opps_dir, k=2, week=None):
    """Exploration quota (spec §15): resurface up to k off-lens rejects as
    labeled wildcards for triage, so the reflect loop can detect an
    over-narrowed lens. Pool: rejected records the lens screened out
    (filter_result skip or tier skip), never legitimacy-suspect, and never
    previously surfaced (each record gets at most one wildcard shot — no
    nagging). Deterministic: candidates ranked by sha1(id:week) so a large
    pool rotates fairly. Tags + saves the chosen records, returns them.
    Wildcards are surfaced-only — triage still decides; nothing auto-advances."""
    week = week or _iso_week(date.today())
    pool = []
    for fp in sorted(glob.glob(str(Path(opps_dir) / "*.md"))):
        fm, body = load_opportunity(fp)
        if fm.get("status") != "rejected" or fm.get("legitimacy") == "suspect":
            continue
        if fm.get("filter_result") != "skip" and fm.get("tier") != "skip":
            continue
        if fm.get("wildcard"):
            continue
        pool.append((fp, fm, body))
    pool.sort(key=lambda t: hashlib.sha1(f"{t[1].get('id')}:{week}".encode()).hexdigest())
    chosen = []
    for fp, fm, body in pool[:k]:
        fm["wildcard"] = True
        fm["wildcard_week"] = week
        fm["flags"] = list(fm.get("flags", [])) + [WILDCARD_FLAG]
        save_opportunity(fp, fm, body)
        chosen.append(fm)
    return chosen


def _outcome_rate(rows):
    """Slow north star: responses (reply/interview/offer) per submitted
    application. Denominator = ever submitted (has date_submitted), so closed
    and ghosted records still count as attempts."""
    apps = [fm for fm in rows if fm.get("date_submitted")]
    if not apps:
        return None
    n = sum(1 for fm in apps
            if fm.get("outcome") in ("reply", "interview", "offer")
            or fm.get("status") in ("replied", "interview", "offer"))
    return f"{n}/{len(apps)} ({round(100 * n / len(apps))}%)"


def build_pipeline(opps_dir, feedback_path=None, today=None):
    """Generate pipeline.md: status board + tier-ranked shortlist + follow-up
    queue + the 3 metrics. Pure read over opportunity files; never edits them."""
    today = today or date.today()
    opps_dir = Path(opps_dir)
    rows = [load_opportunity(fp)[0] for fp in sorted(glob.glob(str(opps_dir / "*.md")))]
    by_status = {}
    for fm in rows:
        by_status[fm.get("status", "?")] = by_status.get(fm.get("status", "?"), 0) + 1

    out = ["# pipeline.md — GENERATED, do not edit\n", "## Board\n"]
    for st in ["discovered", "needs_review", "shortlisted", "rejected",
               "drafting", "drafted", "submitted", "replied", "interview",
               "offer", "closed"]:
        if by_status.get(st):
            out.append(f"- **{st}**: {by_status[st]}")

    out.append("\n## Shortlist (tier-ranked)\n")
    short = [fm for fm in rows if fm.get("status") in ("shortlisted", "needs_review")]
    order = {"deep": 0, "light": 1, None: 2, "skip": 3}
    short.sort(key=lambda f: (order.get(f.get("tier"), 2), -(f.get("capability_score") or 0)))
    if short:
        out.append("| tier | cap | intent | org — title | flags |")
        out.append("|---|---|---|---|---|")
        for fm in short:
            out.append(f"| {fm.get('tier', '—')} | {fm.get('capability_score', '—')} | "
                       f"{fm.get('intent_score', '—')} | {fm.get('org', '?')} — "
                       f"{fm.get('title', '?')} | {', '.join(fm.get('flags', []) or [])} |")
    else:
        out.append("_Nothing shortlisted yet._")

    wild = [fm for fm in rows if fm.get("wildcard")
            and fm.get("status") == "rejected"
            and fm.get("wildcard_week") == _iso_week(today)]
    if wild:
        out.append("\n## Wildcards (exploration quota — off-lens on purpose)\n")
        for fm in wild:
            reasons = [f for f in fm.get("flags", []) if f != WILDCARD_FLAG]
            out.append(f"- {fm.get('org', '?')} — {fm.get('title', '?')} "
                       f"({', '.join(reasons) or 'off-lens'})")

    out.append("\n## Follow-ups\n")
    subs = [fm for fm in rows if fm.get("status") == "submitted"]
    subs.sort(key=lambda f: str(f.get("next_followup") or "9999"))
    if subs:
        for fm in subs:
            nf = fm.get("next_followup")
            due = nf and date.fromisoformat(str(nf)) <= today
            out.append(f"- {fm.get('org', '?')} — {fm.get('title', '?')}: "
                       f"submitted {fm.get('date_submitted', '?')}, follow up "
                       f"{nf or 'unscheduled'}{' **← DUE**' if due else ''}")
    else:
        out.append("_Nothing awaiting follow-up._")

    prec = _triage_precision(feedback_path) if feedback_path else None
    acc = _draft_acceptance(feedback_path) if feedback_path else None
    rate = _outcome_rate(rows)
    out.append("\n## Metrics\n")
    out.append(f"- **Triage precision** (approved / triage decisions): "
               f"{prec if prec is not None else '—'}")
    out.append(f"- **Draft acceptance** (accepted / draft decisions): "
               f"{acc if acc is not None else '—'}")
    out.append(f"- **Outcome rate** (responses / submitted applications): "
               f"{rate if rate is not None else '—'}")
    return "\n".join(out) + "\n"
