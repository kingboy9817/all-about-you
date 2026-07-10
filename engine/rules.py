# rules.py
"""Deterministic gates: dedup, hard filters, tiering. Pure functions only."""
import hashlib


def dedupe_key(opp):
    """Stable 16-char key. Normalizes URL; falls back to org|title."""
    url = (opp.get("url") or "").strip().lower().rstrip("/")
    basis = url or f"{opp.get('org', '')}|{opp.get('title', '')}".lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


from dataclasses import dataclass, field
from datetime import date

PASS, SKIP, NEEDS_REVIEW = "pass", "skip", "needs_review"


@dataclass
class FilterResult:
    status: str
    reasons: list = field(default_factory=list)


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def passes_hard_filters(opp, hard_filters, today=None):
    """Deterministic deal-breaker gate. Fail closed on unknown required fields."""
    today = today or date.today()
    extracted = opp.get("extracted", {}) or {}
    statuses, reasons = [], []

    # --- location ---
    allowed = [a.lower() for a in hard_filters.get("allowed_locations", [])]
    loc = extracted.get("location")
    if hard_filters.get("remote_ok", False) and extracted.get("remote") is True:
        pass  # remote satisfies location
    elif loc is None:
        statuses.append(NEEDS_REVIEW); reasons.append("location unknown")
    elif any(a in loc.lower() for a in allowed):
        pass
    else:
        statuses.append(SKIP); reasons.append(f"location not allowed: {loc}")

    # --- comp floor ---
    floor = hard_filters.get("comp_floor")
    if floor is not None:
        comp = extracted.get("comp")
        if comp is None:
            statuses.append(NEEDS_REVIEW); reasons.append("comp unknown, floor set")
        elif comp < floor:
            statuses.append(SKIP); reasons.append(f"comp {comp} below floor {floor}")

    # --- exclusions ---
    haystack = " ".join(str(x) for x in [
        opp.get("org", ""), opp.get("title", ""), loc or "", extracted.get("industry", "")
    ]).lower()
    for term in hard_filters.get("exclude", []):
        if term.lower() in haystack:
            statuses.append(SKIP); reasons.append(f"excluded term: {term}")

    # --- deadline ---
    deadline = _as_date(extracted.get("deadline"))
    if deadline is not None and deadline < today:
        statuses.append(SKIP); reasons.append(f"deadline passed: {deadline}")

    if SKIP in statuses:
        return FilterResult(SKIP, reasons)
    if NEEDS_REVIEW in statuses:
        return FilterResult(NEEDS_REVIEW, reasons)
    return FilterResult(PASS, reasons)


def geo_gate(verified, eligibility):
    """Applicant-eligibility gate on verify-stage facts (Plan 7).

    verified: facts the verify agent extracted from the listing detail page —
      geo_scope: 'global' | 'unknown'/None | token(s) naming the restricted
        country/region (str or list), e.g. ['us'], 'philippines'
      language_req: required working languages (list), or None/[] if unstated
    eligibility: lens block via the provider — work_auth: [tokens],
      languages: [tokens], with '<lang>-basic' marking partial proficiency.

    Fail closed: unknown geo, or a missing/empty work_auth block, routes to
    needs_review — the gate never vouches without owner data. An explicit
    restriction or unmet language requirement is a hard skip.
    """
    eligibility = eligibility or {}
    work_auth = [w.lower() for w in eligibility.get("work_auth") or []]
    languages = [l.lower() for l in eligibility.get("languages") or []]
    statuses, reasons = [], []

    geo = verified.get("geo_scope")
    if not work_auth:
        statuses.append(NEEDS_REVIEW); reasons.append("lens eligibility.work_auth missing")
    elif geo is None or geo == "unknown":
        statuses.append(NEEDS_REVIEW); reasons.append("eligibility unverified")
    elif geo != "global":
        tokens = [geo] if isinstance(geo, str) else list(geo)
        tokens = [t.lower() for t in tokens]
        if not any(t in work_auth for t in tokens):
            statuses.append(SKIP)
            reasons.append(f"restricted to {', '.join(tokens)} — outside work auth")

    for req in verified.get("language_req") or []:
        req = req.lower()
        if req in languages:
            continue
        partial = next((l for l in languages if l.startswith(f"{req}-")), None)
        if partial:
            level = partial.split("-", 1)[1]
            statuses.append(NEEDS_REVIEW); reasons.append(f"only {level} {req}")
        else:
            statuses.append(SKIP); reasons.append(f"requires {req}")

    if SKIP in statuses:
        return FilterResult(SKIP, reasons)
    if NEEDS_REVIEW in statuses:
        return FilterResult(NEEDS_REVIEW, reasons)
    return FilterResult(PASS, reasons)


LIVENESS_OPEN = {"open", "active", "live", "listed", "published", "accepting", "reopen", "re-open"}
LIVENESS_CLOSED = {"closed", "expired", "filled", "deleted", "removed",
                   "inactive", "draft", "unlisted", "withdrawn", "paused"}


def liveness_gate(liveness, today=None, max_age_days=14):
    """Listing-liveness gate — the deal-breaker that the posting is still OPEN.

    Distinct from geo_gate (which gates the *applicant's* eligibility): this gates
    the *listing*. A record cannot become a presented application unless liveness is
    a VERIFIED-open fact. Fail closed: missing / unknown / stale-check verification
    routes to needs_review; an explicit closed status or a past expiry is a hard skip.

    liveness: facts the verify stage FETCHED from the source (never self-asserted) —
      status: source status string — open/active/live/listed/published/accepting vs
        closed/expired/filled/deleted/... ; None or an unrecognized value => unverified.
      expiry_date: the listing's close/expiry date (ISO str | date) or None.
      checked_at: when liveness was last fetched (ISO str | date) or None.
    max_age_days: a verification older than this counts as unverified (forces a
      re-ping at craft / submit time — listings close between triage and apply).
    """
    today = today or date.today()
    liveness = liveness or {}
    statuses, reasons = [], []

    status = (liveness.get("status") or "").strip().lower()
    expiry = _as_date(liveness.get("expiry_date"))
    checked = _as_date(liveness.get("checked_at"))

    # 1) explicit dead signals -> hard skip
    if status in LIVENESS_CLOSED:
        statuses.append(SKIP); reasons.append(f"listing not open: {status}")
    if expiry is not None and expiry < today:
        statuses.append(SKIP); reasons.append(f"listing expired {expiry.isoformat()}")

    # 2) verification must exist, be fresh, and read as open -> else fail closed
    if checked is None:
        statuses.append(NEEDS_REVIEW); reasons.append("liveness unverified (never checked)")
    elif (today - checked).days > max_age_days:
        statuses.append(NEEDS_REVIEW)
        reasons.append(f"liveness check stale ({checked.isoformat()}, >{max_age_days}d) — re-ping")
    elif status not in LIVENESS_OPEN and status not in LIVENESS_CLOSED:
        reasons.append(f"liveness unverified: status {status!r}" if status
                       else "liveness unverified (no status)")
        statuses.append(NEEDS_REVIEW)

    if SKIP in statuses:
        return FilterResult(SKIP, reasons)
    if NEEDS_REVIEW in statuses:
        return FilterResult(NEEDS_REVIEW, reasons)
    return FilterResult(PASS, reasons)


import re as _re

_RECRUITER_PAT = _re.compile(
    r"\b(hires|staffing|recruit\w*|talent|agency|outsourc\w*|solutions|consultanc\w*)\b", _re.I)
_SCAM_PHRASES = [
    "wire transfer", "upfront payment", "pay a fee", "pay a deposit", "registration fee",
    "processing fee", "buy your own equipment", "buy equipment", "gift card",
    "no experience needed", "telegram", "whatsapp",
]


def normalize_org(org):
    """Canonical form for org matching: lowercase alphanumerics only.
    'Re-cruit-Lytic' and 'RecruitLytic' normalize identically."""
    return _re.sub(r"[^a-z0-9]", "", (org or "").lower())


_MIN_SUSPECT_OVERLAP = 8  # normalized chars; below this, containment is too noisy


def _matches_suspect(org, suspect_orgs):
    n = normalize_org(org)
    if not n:
        return None
    for s in suspect_orgs or []:
        ns = normalize_org(s)
        if n == ns or (min(len(n), len(ns)) >= _MIN_SUSPECT_OVERLAP
                       and (n in ns or ns in n)):
            return s
    return None


def legitimacy_flags(opp, org_counts=None, text="", suspect_orgs=None):
    """Deterministic scam / low-quality smell detection. Returns a list of flag
    strings (empty = no smells found). Pure: pass org_counts (org -> count in the
    current batch) for duplicate-posting detection, text for the posting body, and
    suspect_orgs (org names with a prior suspect/scam verdict) for variant matching."""
    flags = []
    org = opp.get("org") or ""
    prior = _matches_suspect(org, suspect_orgs)
    if prior:
        flags.append(f"org matches prior suspect verdict: {prior}")
    if org_counts and org and org_counts.get(org, 0) >= 3:
        flags.append(f"org posted {org_counts[org]} near-identical roles")
    if _RECRUITER_PAT.search(org):
        flags.append("generic-recruiter name")
    hay = " ".join(str(x) for x in [
        org, opp.get("title", ""),
        (opp.get("extracted", {}) or {}).get("comp", ""), text,
    ]).lower()
    for ph in _SCAM_PHRASES:
        if ph in hay:
            flags.append(f"scam-phrase: {ph}")
    return flags


def assign_tier(capability, intent, thresholds, matched_priority_goal=False):
    """Map two-sided fit scores to a tier. Assumes hard filters already passed."""
    deep = thresholds.get("deep", 0.75)
    light = thresholds.get("light", 0.5)
    if capability < light or intent < light:
        return "skip"
    if capability >= deep and intent >= deep and matched_priority_goal:
        return "deep"
    return "light"


# --- Plan 8: programmatic fit scoring (pure; fed by LLM-extracted atoms) ---

DEFAULT_SCORING = {
    "mode_factor": {"explanatory": 1.0, "mixed": 0.5, "transactional": 0.1},
    "persuasion_load_ref": 0.4,
    "caveat_threshold_K": 12,   # forgiving: a few honest caveats shouldn't tank a can-do fit
    "caveat_hard_skip": 8,
    # CAPABILITY = can-do: caveats (can I do it?) + in-domain, MINUS a transactional-style penalty.
    # Peak-strength (persuasion) is NOT scored here — it earns DEEP via matched_priority_goal + intent.
    "career_capability": {"w_caveat": 0.7, "w_in_domain": 0.3, "w_trans": 0.5},
    "career_intent": {
        "comp_tier": {"unknown": 0.45, "below_wake": 0.2, "wake": 0.4, "look": 0.7, "apply_hard": 1.0},
        "in_domain": 0.1, "core_align": 0.15, "inbound": 0.1, "face_to_face": 0.05,
    },
}

DEFAULT_COMP_TIERS = {"wake": 8000, "look": 11000, "apply_hard": 18000}


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def comp_tier_of(comp_sgd_month, lens):
    """Map a monthly-SGD comp figure to a career tier label using the lens tiers."""
    tiers = ((lens or {}).get("lanes", {}).get("career", {})
             .get("comp_tiers_sgd_month")) or DEFAULT_COMP_TIERS
    if comp_sgd_month is None:
        return "unknown"        # unstated comp != known-low; scored neutral, not near-zero
    c = float(comp_sgd_month)
    if c >= tiers.get("apply_hard", 18000):
        return "apply_hard"
    if c >= tiers.get("look", 11000):
        return "look"
    if c >= tiers.get("wake", 8000):
        return "wake"
    return "below_wake"


def _scoring(lens):
    """lens.scoring merged over DEFAULT_SCORING (one level deep for nested dicts)."""
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_SCORING.items()}
    for k, v in ((lens or {}).get("scoring") or {}).items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return s


def score_fit(fit_inputs, lens):
    """Pure fit scorer (Plan 8). The LLM emits the atoms in ``fit_inputs``; this turns
    them into capability/intent deterministically. Returns {capability, intent, breakdown}.

    career atoms: lane, core_responsibilities[{text, persuasion(bool), mode}],
      fit_caveats[str], in_domain(bool), inbound(bool), comp_sgd_month(num|None),
      anti_fit(bool), face_to_face(bool).
    side_gig atoms: lane, automatable_fraction(0..1), recurring, async_no_meetings,
      non_distracting (bools).
    """
    fi = fit_inputs or {}
    s = _scoring(lens)
    light = ((lens or {}).get("tier_thresholds") or {}).get("light", 0.5)

    lane = fi.get("lane") or (
        "side_gig" if (fi.get("automatable_fraction") is not None
                       and not fi.get("core_responsibilities")) else "career")

    if lane == "side_gig":
        cap = clamp01(fi.get("automatable_fraction") or 0.0)
        flags = [bool(fi.get("recurring")), bool(fi.get("async_no_meetings")),
                 bool(fi.get("non_distracting", True))]
        intent = clamp01(sum(1 for f in flags if f) / len(flags))
        return {"capability": round(cap, 3), "intent": round(intent, 3),
                "breakdown": {"lane": "side_gig", "automatable_fraction": cap}}

    # career lane
    mode_factor = s["mode_factor"]
    default_mode = mode_factor.get("mixed", 0.5)
    resp = fi.get("core_responsibilities") or []
    pers = [r for r in resp if r.get("persuasion")]
    load = (len(pers) / len(resp)) if resp else 0.0
    mode_avg = (sum(mode_factor.get(r.get("mode"), default_mode) for r in pers) / len(pers)
                if pers else 0.0)
    load_ref = s.get("persuasion_load_ref") or 0.4
    load_credit = min(1.0, load / load_ref)
    core_align = mode_avg * load_credit                          # +ve strength signal (used in intent)
    transactional = load_credit * max(0.0, 1.0 - 2.0 * mode_avg)  # >0 only for transactional-leaning persuasion

    caveats = len(fi.get("fit_caveats") or [])
    K = s.get("caveat_threshold_K") or 12
    caveat_penalty = min(1.0, caveats / K)
    in_domain = 1.0 if fi.get("in_domain") else 0.0

    cc = s["career_capability"]
    # CAPABILITY = can-do: few caveats + in-domain, minus a transactional-style penalty.
    # Peak-strength/persuasion is NOT here — it earns DEEP via matched_priority_goal + intent.
    cap = clamp01(cc["w_caveat"] * (1.0 - caveat_penalty)
                  + cc["w_in_domain"] * in_domain
                  - cc.get("w_trans", 0.5) * transactional)
    hard = s.get("caveat_hard_skip")
    auto_skip = bool((hard and caveats >= hard) or fi.get("anti_fit"))
    if auto_skip:                       # comp NEVER buys fit
        cap = min(cap, light - 0.01)

    ci = s["career_intent"]
    tier_label = comp_tier_of(fi.get("comp_sgd_month"), lens)
    intent = clamp01(ci["comp_tier"].get(tier_label, 0.2)
                     + ci["in_domain"] * in_domain
                     + ci["core_align"] * core_align
                     + (ci["inbound"] if fi.get("inbound") else 0.0)
                     + (ci["face_to_face"] if fi.get("face_to_face") else 0.0))
    if tier_label == "unknown":   # deep requires REAL comp; unstated comp caps the role at light
        deep_th = ((lens or {}).get("tier_thresholds") or {}).get("deep", 0.75)
        intent = min(intent, deep_th - 0.01)

    return {"capability": round(cap, 3), "intent": round(intent, 3),
            "breakdown": {"lane": "career", "persuasion_load": round(load, 2),
                          "mode_avg": round(mode_avg, 2), "core_align": round(core_align, 2),
                          "transactional_penalty": round(cc.get("w_trans", 0.5) * transactional, 2),
                          "caveats": caveats, "caveat_penalty": round(caveat_penalty, 2),
                          "in_domain": bool(in_domain), "comp_tier": tier_label,
                          "auto_skip": auto_skip}}
