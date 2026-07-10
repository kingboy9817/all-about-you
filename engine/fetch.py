# fetch.py
"""Deterministic Lane-A2 fetchers: pull whole ATS boards / national-board
searches as JSON, prefilter by the registry's title+location keywords, and emit
discover-contract candidates {source, url, org, title, description}.

Driven by `sources/ats.yaml` (the token registry). The agent never hand-parses
these boards — it calls `fetch_registry(...)` and passes the candidates to
`run.discover_write`. Every source's fetched/kept counts (and any error) are
reported — a failed or thin source is visible, never silently empty.

Filtering here is inclusion-only volume control: dropping a candidate is safe
because it never reaches the pipeline, and keeping extra is safe because the
deterministic gates (hard filters, geo, liveness) reject later. Unknown
location ⇒ keep (fail toward the gates, not toward silence)."""
import html as _html
import json
import re
import urllib.request

import yaml

UA = "all-about-you-radar/1.0 (job-search agent; contact via repo)"
TIMEOUT = 30


def http_json(url, method="GET", payload=None, timeout=TIMEOUT):
    """GET/POST a JSON endpoint. The single network chokepoint (injectable)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def strip_html(s):
    """HTML (possibly entity-escaped, per Greenhouse) → readable plain text."""
    s = _html.unescape(s or "")
    s = re.sub(r"</(?:p|div|li|ul|ol|h[1-6]|tr)\s*>|<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)  # entities inside once-escaped HTML (Greenhouse)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def title_matches(title, keywords):
    """True if any keyword phrase appears in the title on word boundaries.
    Phrase gaps tolerate hyphens/punctuation ('Forward-Deployed'). Empty
    keyword list means no title filter."""
    if not keywords:
        return True
    t = title or ""
    for kw in keywords:
        pat = r"\b" + r"[\W_]+".join(re.escape(w) for w in kw.split()) + r"\b"
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def location_matches(location, needles):
    """Substring match against any needle. No needles, or unknown location ⇒
    keep (the geo gate decides eligibility later, deterministically)."""
    if not needles or not location:
        return True
    loc = location.lower()
    return any(n.lower() in loc for n in needles)


def _keep(title, location, flt):
    return (title_matches(title, flt.get("title_any"))
            and location_matches(location, flt.get("location_any")))


def _cand(source, url, org, title, description, location=None, extra=()):
    lines = [f"Location: {location}"] if location else []
    lines += [x for x in extra if x]
    body = "\n".join(lines)
    if description:
        body = f"{body}\n\n{description}" if body else description
    return {"source": source, "url": url or "", "org": org or "",
            "title": title or "", "description": body}


# --- per-ATS fetchers ----------------------------------------------------
# Each returns (candidates, {"fetched": N, "kept": K}). Detail pages are
# hydrated only for kept jobs, to keep whole-board fetches cheap.

def fetch_greenhouse(token, org, flt, http=http_json):
    base = f"https://boards-api.greenhouse.io/v1/boards/{token}"
    jobs = http(f"{base}/jobs").get("jobs", [])
    cands = []
    for j in jobs:
        loc = (j.get("location") or {}).get("name", "")
        if not _keep(j.get("title"), loc, flt):
            continue
        detail = http(f"{base}/jobs/{j['id']}")
        cands.append(_cand(f"greenhouse:{token}", j.get("absolute_url"),
                           j.get("company_name") or org, j.get("title"),
                           strip_html(detail.get("content", "")), location=loc))
    return cands, {"fetched": len(jobs), "kept": len(cands)}


def fetch_lever(token, org, flt, http=http_json):
    jobs = http(f"https://api.lever.co/v0/postings/{token}?mode=json")
    cands = []
    for j in jobs:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        if not _keep(j.get("text"), loc, flt):
            continue
        desc = j.get("descriptionPlain") or strip_html(j.get("description", ""))
        cands.append(_cand(f"lever:{token}", j.get("hostedUrl"), org,
                           j.get("text"), desc, location=loc))
    return cands, {"fetched": len(jobs), "kept": len(cands)}


def fetch_ashby(token, org, flt, http=http_json):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
    jobs = http(url).get("jobs", [])
    cands = []
    for j in jobs:
        if not j.get("isListed", True):
            continue
        locs = [j.get("location") or ""] + [
            (s or {}).get("location", "") for s in j.get("secondaryLocations") or []]
        if j.get("isRemote"):
            locs.append("Remote")
        loc = "; ".join(x for x in locs if x)
        if not _keep(j.get("title"), loc, flt):
            continue
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", ""))
        comp = (j.get("compensation") or {}).get("compensationTierSummary")
        cands.append(_cand(f"ashby:{token}", j.get("jobUrl"), org, j.get("title"),
                           desc, location=loc,
                           extra=[f"Compensation: {comp}" if comp else ""]))
    fetched = len(jobs)
    return cands, {"fetched": fetched, "kept": len(cands)}


def fetch_smartrecruiters(token, org, flt, http=http_json):
    base = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    items, offset = [], 0
    while True:
        page = http(f"{base}?limit=100&offset={offset}")
        content = page.get("content", [])
        if not content:
            break
        items += content
        offset += len(content)
        if offset >= int(page.get("totalFound") or 0):
            break
    cands = []
    for j in items:
        locd = j.get("location") or {}
        loc = locd.get("fullLocation") or ", ".join(
            x for x in [locd.get("city"), locd.get("country")] if x)
        if locd.get("remote"):
            loc = f"{loc}; Remote" if loc else "Remote"
        if not _keep(j.get("name"), loc, flt):
            continue
        desc = ""
        if j.get("ref"):
            sections = (http(j["ref"]).get("jobAd") or {}).get("sections") or {}
            desc = "\n\n".join(strip_html(s.get("text", ""))
                               for s in sections.values() if isinstance(s, dict))
        cands.append(_cand(f"smartrecruiters:{token}",
                           f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
                           (j.get("company") or {}).get("name") or org,
                           j.get("name"), desc, location=loc))
    return cands, {"fetched": len(items), "kept": len(cands)}


def fetch_workable(token, org, flt, http=http_json):
    base = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    items, token_page, pages = [], None, 0
    while pages < 20:
        payload = {"query": "", "location": []}
        if token_page:
            payload["token"] = token_page
        page = http(base, method="POST", payload=payload)
        items += page.get("results", [])
        token_page = page.get("nextPage")
        pages += 1
        if not token_page:
            break
    cands = []
    for j in items:
        locd = j.get("location") or {}
        loc = ", ".join(x for x in [locd.get("city"), locd.get("country")] if x)
        if j.get("remote"):
            loc = f"{loc}; Remote" if loc else "Remote"
        if not _keep(j.get("title"), loc, flt):
            continue
        detail = http(f"{base}/{j['shortcode']}")
        cands.append(_cand(f"workable:{token}",
                           f"https://apply.workable.com/{token}/j/{j['shortcode']}/",
                           org, j.get("title"),
                           strip_html(detail.get("description", "")), location=loc))
    return cands, {"fetched": len(items), "kept": len(cands)}


def fetch_mycareersfuture(queries, flt, limit=100, http=http_json):
    """SG national board. POST search per query; dedupe by uuid across queries;
    hydrate kept jobs for the full JD. Location is Singapore by construction."""
    # Region-specific example source: MyCareersFuture assumes Singapore-centric
    # listings and currency. Swap or remove this source for other regions.
    seen, cands, fetched = set(), [], 0
    for q in queries or []:
        data = http(f"https://api.mycareersfuture.gov.sg/v2/search?limit={limit}&page=0",
                    method="POST", payload={"search": q, "sessionId": ""})
        for j in data.get("results", []):
            fetched += 1  # raw rows, so cross-query dedup shows in the report
            uuid = j.get("uuid")
            if not uuid or uuid in seen:
                continue
            seen.add(uuid)
            if not title_matches(j.get("title"), flt.get("title_any")):
                continue
            meta = j.get("metadata") or {}
            sal = j.get("salary") or {}
            sal_line = ""
            if sal.get("minimum") or sal.get("maximum"):
                stype = (sal.get("type") or {}).get("salaryType", "Monthly")
                sal_line = (f"Compensation: {sal.get('minimum')}-{sal.get('maximum')} "
                            f"SGD {stype}")
            addr = j.get("address") or {}
            loc = (addr.get("overseasCountry") or "Overseas"
                   if addr.get("isOverseas") else "Singapore")
            detail = http(f"https://api.mycareersfuture.gov.sg/v2/jobs/{uuid}")
            url = (meta.get("jobDetailsUrl")
                   or f"https://www.mycareersfuture.gov.sg/job/{uuid}")
            posted = (f"Posted: {meta.get('newPostingDate')}"
                      if meta.get("newPostingDate") else "")
            cands.append(_cand("mycareersfuture", url,
                               (j.get("postedCompany") or {}).get("name"),
                               j.get("title"),
                               strip_html(detail.get("description", "")),
                               location=loc, extra=[sal_line, posted]))
    return cands, {"fetched": fetched, "kept": len(cands)}


# --- keyed aggregators (Lane B; run only when keys are present) ----------

def fetch_adzuna(cfg, app_id, app_key, flt, http=http_json):
    country = cfg.get("country", "sg")
    cands, fetched, seen = [], 0, set()
    for q in cfg.get("queries", []):
        url = (f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
               f"?app_id={app_id}&app_key={app_key}"
               f"&what={urllib.request.quote(q)}&results_per_page=50")
        for j in http(url).get("results", []):
            u = j.get("redirect_url", "")
            if u in seen:
                continue
            seen.add(u)
            fetched += 1
            loc = (j.get("location") or {}).get("display_name", "")
            if not _keep(j.get("title"), loc, flt):
                continue
            sal = ""
            if j.get("salary_min") or j.get("salary_max"):
                sal = f"Compensation: {j.get('salary_min')}-{j.get('salary_max')} (Adzuna est.)"
            cands.append(_cand("adzuna", u, (j.get("company") or {}).get("display_name"),
                               j.get("title"), j.get("description", ""),
                               location=loc, extra=[sal]))
    return cands, {"fetched": fetched, "kept": len(cands)}


def fetch_jooble(cfg, key, flt, http=http_json):
    cands, fetched, seen = [], 0, set()
    for q in cfg.get("queries", []):
        data = http(f"https://jooble.org/api/{key}", method="POST",
                    payload={"keywords": q, "location": cfg.get("location", "")})
        for j in data.get("jobs", []):
            u = j.get("link", "")
            if u in seen:
                continue
            seen.add(u)
            fetched += 1
            if not _keep(j.get("title"), j.get("location"), flt):
                continue
            cands.append(_cand("jooble", u, j.get("company"), j.get("title"),
                               strip_html(j.get("snippet", "")),
                               location=j.get("location")))
    return cands, {"fetched": fetched, "kept": len(cands)}


# --- registry orchestration ----------------------------------------------

FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever,
            "ashby": fetch_ashby, "smartrecruiters": fetch_smartrecruiters,
            "workable": fetch_workable}


def _board_flt(reg_filters, entry):
    """Per-board keys override the registry-wide filters."""
    flt = dict(reg_filters or {})
    for k in ("title_any", "location_any"):
        if k in entry:
            flt[k] = entry[k]
    return flt


def fetch_registry(registry_path, api_keys=None, http=http_json):
    """Fetch every board/search in the registry. Errors are isolated per
    source and reported; keyed lanes without keys are reported as skipped.
    Returns {"candidates": [...], "report": {source: stats}}."""
    with open(registry_path, encoding="utf-8") as f:
        reg = yaml.safe_load(f) or {}
    flt = reg.get("filters") or {}
    api_keys = api_keys or {}
    candidates, report = [], {}

    for entry in reg.get("boards", []):
        source = f"{entry['ats']}:{entry['token']}"
        try:
            cands, stats = FETCHERS[entry["ats"]](
                entry["token"], entry.get("org"), _board_flt(flt, entry), http=http)
            candidates += cands
            report[source] = stats
        except Exception as e:  # fail visible, keep the run alive
            report[source] = {"fetched": 0, "kept": 0, "error": str(e)}

    mcf = reg.get("mycareersfuture")
    if mcf:
        try:
            cands, stats = fetch_mycareersfuture(
                mcf.get("queries", []), _board_flt(flt, mcf),
                limit=mcf.get("limit", 100), http=http)
            candidates += cands
            report["mycareersfuture"] = stats
        except Exception as e:
            report["mycareersfuture"] = {"fetched": 0, "kept": 0, "error": str(e)}

    keyed = reg.get("keyed") or {}
    if "adzuna" in keyed:
        if api_keys.get("adzuna_app_id") and api_keys.get("adzuna_key"):
            try:
                cands, stats = fetch_adzuna(keyed["adzuna"], api_keys["adzuna_app_id"],
                                            api_keys["adzuna_key"],
                                            _board_flt(flt, keyed["adzuna"]), http=http)
                candidates += cands
                report["adzuna"] = stats
            except Exception as e:
                report["adzuna"] = {"fetched": 0, "kept": 0, "error": str(e)}
        else:
            report["adzuna"] = {"skipped": "no key"}
    if "jooble" in keyed:
        if api_keys.get("jooble_key"):
            try:
                cands, stats = fetch_jooble(keyed["jooble"], api_keys["jooble_key"],
                                            _board_flt(flt, keyed["jooble"]), http=http)
                candidates += cands
                report["jooble"] = stats
            except Exception as e:
                report["jooble"] = {"fetched": 0, "kept": 0, "error": str(e)}
        else:
            report["jooble"] = {"skipped": "no key"}

    return {"candidates": candidates, "report": report}
