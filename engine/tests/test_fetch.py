# tests/test_fetch.py — deterministic Lane-A2 fetchers (fetch.py)
import yaml

import fetch
from fetch import (title_matches, location_matches, strip_html,
                   fetch_greenhouse, fetch_lever, fetch_ashby,
                   fetch_smartrecruiters, fetch_workable,
                   fetch_mycareersfuture, fetch_registry)

FLT = {"title_any": ["ai enablement", "forward deployed", "solutions engineer"],
       "location_any": ["singapore", "remote", "apac"]}


# --- matching helpers ---------------------------------------------------

def test_title_matches_word_boundary_not_substring():
    assert title_matches("AI Enablement Lead", ["ai enablement"])
    assert not title_matches("Maintenance Engineer", ["ai"])
    assert title_matches("Head of AI", ["ai"])


def test_title_matches_phrase_across_hyphens_and_case():
    assert title_matches("Forward-Deployed Engineer", ["forward deployed"])
    assert title_matches("FORWARD DEPLOYED ENGINEER, APAC", ["forward deployed"])
    assert not title_matches("Backward Deployed", ["forward deployed"])


def test_title_matches_empty_keywords_keeps_all():
    assert title_matches("Anything", [])
    assert title_matches("Anything", None)


def test_location_matches():
    assert location_matches("Singapore", FLT["location_any"])
    assert location_matches("Remote - APAC", FLT["location_any"])
    assert not location_matches("New York City, NY", FLT["location_any"])
    assert location_matches("", FLT["location_any"])      # unknown → keep (gates decide later)
    assert location_matches(None, FLT["location_any"])
    assert location_matches("Anywhere", [])               # no filter configured → keep


def test_strip_html_unescapes_then_strips():
    # Greenhouse ships escaped HTML in `content`
    assert strip_html("&lt;p&gt;Do &amp;amp; teach&lt;/p&gt;") == "Do & teach"
    assert strip_html("<div><b>no</b> tags</div>") == "no tags"


# --- per-ATS fetchers (fake http; shapes mirror live API responses) -----

def _http_from(routes):
    """Fake http: first route whose key is a substring of the URL wins."""
    calls = []

    def http(url, method="GET", payload=None, timeout=30):
        calls.append(url)
        for k, v in routes.items():
            if k in url:
                return v(url, payload) if callable(v) else v
        raise AssertionError(f"unexpected url {url}")

    http.calls = calls
    return http


GH_LIST = {"jobs": [
    {"id": 1, "absolute_url": "https://gh.io/1", "title": "Forward Deployed Engineer",
     "location": {"name": "Singapore"}, "company_name": "Acme"},
    {"id": 2, "absolute_url": "https://gh.io/2", "title": "Accountant",
     "location": {"name": "Singapore"}},
    {"id": 3, "absolute_url": "https://gh.io/3", "title": "Solutions Engineer",
     "location": {"name": "New York City, NY"}},
]}


def test_fetch_greenhouse_filters_and_hydrates_kept_only():
    http = _http_from({"/jobs/1": {"content": "&lt;p&gt;Deploy AI&lt;/p&gt;"},
                       "/boards/acme/jobs": GH_LIST})
    cands, stats = fetch_greenhouse("acme", "Acme", FLT, http=http)
    assert stats == {"fetched": 3, "kept": 1}
    assert len(cands) == 1
    c = cands[0]
    assert c["source"] == "greenhouse:acme"
    assert c["url"] == "https://gh.io/1"
    assert c["org"] == "Acme"
    assert "Deploy AI" in c["description"]
    assert "Location: Singapore" in c["description"]
    # only the kept job was hydrated: list + 1 detail = 2 calls
    assert len(http.calls) == 2


def test_fetch_lever_uses_plain_description_no_hydration():
    http = _http_from({"api.lever.co": [
        {"text": "AI Enablement Manager", "hostedUrl": "https://lv.io/a",
         "categories": {"location": "Remote"}, "descriptionPlain": "Teach teams AI."},
        {"text": "Chef", "hostedUrl": "https://lv.io/b",
         "categories": {"location": "Remote"}, "descriptionPlain": "Cook."},
    ]})
    cands, stats = fetch_lever("acme", "Acme", FLT, http=http)
    assert stats == {"fetched": 2, "kept": 1}
    assert cands[0]["title"] == "AI Enablement Manager"
    assert "Teach teams AI." in cands[0]["description"]
    assert len(http.calls) == 1


def test_fetch_ashby_drops_unlisted_and_reads_location_fields():
    http = _http_from({"ashbyhq.com": {"jobs": [
        {"title": "Forward Deployed Engineer", "isListed": True, "isRemote": False,
         "location": "Singapore", "secondaryLocations": [], "jobUrl": "https://ab.io/1",
         "descriptionPlain": "Embed with customers."},
        {"title": "Forward Deployed Engineer", "isListed": False, "isRemote": False,
         "location": "Singapore", "secondaryLocations": [], "jobUrl": "https://ab.io/2",
         "descriptionPlain": "hidden"},
        {"title": "Solutions Engineer", "isListed": True, "isRemote": True,
         "location": "San Francisco", "secondaryLocations": [], "jobUrl": "https://ab.io/3",
         "descriptionHtml": "<p>Remote role</p>"},
    ]}})
    cands, stats = fetch_ashby("acme", "Acme", FLT, http=http)
    # job 2 unlisted; job 3 kept because isRemote makes location "remote"-matched
    assert stats == {"fetched": 3, "kept": 2}
    assert "Embed with customers." in cands[0]["description"]
    assert "Remote role" in cands[1]["description"]


def test_fetch_smartrecruiters_paginates_and_hydrates():
    page1 = {"totalFound": 2, "content": [
        {"id": "11", "name": "AI Enablement Lead", "ref": "https://sr.api/postings/11",
         "location": {"fullLocation": "Singapore, , Singapore", "remote": False}},
        {"id": "12", "name": "Driver", "ref": "https://sr.api/postings/12",
         "location": {"fullLocation": "Jakarta, , Indonesia", "remote": False}},
    ]}

    def list_route(url, payload):
        return page1 if "offset=0" in url else {"totalFound": 2, "content": []}

    http = _http_from({"postings/11": {"jobAd": {"sections": {
                           "jobDescription": {"title": "Job Description",
                                              "text": "<p>Drive AI adoption</p>"}}}},
                       "postings?": list_route})
    cands, stats = fetch_smartrecruiters("Acme", "Acme", FLT, http=http)
    assert stats == {"fetched": 2, "kept": 1}
    c = cands[0]
    assert c["source"] == "smartrecruiters:Acme"
    assert c["url"] == "https://jobs.smartrecruiters.com/Acme/11"
    assert "Drive AI adoption" in c["description"]


def test_fetch_workable_builds_urls_and_hydrates():
    def jobs_route(url, payload):
        if url.endswith("/jobs"):  # POST list
            return {"total": 1, "results": [
                {"title": "Solutions Engineer", "shortcode": "SE1",
                 "location": {"city": "", "country": "United States"},
                 "remote": True}]}
        return {"description": "<p>Help customers ship AI</p>"}  # GET detail

    http = _http_from({"workable.com": jobs_route})
    cands, stats = fetch_workable("acme", "Acme", FLT, http=http)
    assert stats == {"fetched": 1, "kept": 1}
    c = cands[0]
    assert c["url"] == "https://apply.workable.com/acme/j/SE1/"
    assert "Help customers ship AI" in c["description"]


MCF_RESULT = {"results": [{
    "uuid": "abc123", "title": "AI Enablement Manager",
    "postedCompany": {"name": "GRABTAXI HOLDINGS PTE. LTD."},
    "salary": {"minimum": 8000, "maximum": 12000, "type": {"salaryType": "Monthly"}},
    "address": {"isOverseas": False},
    "metadata": {"jobDetailsUrl": "https://www.mycareersfuture.gov.sg/job/x-abc123",
                 "newPostingDate": "2026-07-02"},
}]}


def test_fetch_mycareersfuture_salary_url_and_hydration():
    http = _http_from({"/v2/jobs/abc123": {"description": "<p>Coach bankers on GenAI</p>"},
                       "/v2/search": MCF_RESULT})
    cands, stats = fetch_mycareersfuture(["AI enablement"], FLT, http=http)
    assert stats == {"fetched": 1, "kept": 1}
    c = cands[0]
    assert c["source"] == "mycareersfuture"
    assert c["url"] == "https://www.mycareersfuture.gov.sg/job/x-abc123"
    assert c["org"] == "GRABTAXI HOLDINGS PTE. LTD."
    assert "8000" in c["description"] and "12000" in c["description"]
    assert "Coach bankers on GenAI" in c["description"]


def test_fetch_mycareersfuture_dedupes_across_queries():
    http = _http_from({"/v2/jobs/abc123": {"description": "d"},
                       "/v2/search": MCF_RESULT})
    cands, stats = fetch_mycareersfuture(["AI enablement", "GenAI"], FLT, http=http)
    assert stats == {"fetched": 2, "kept": 1}
    assert len(cands) == 1


# --- registry orchestration ---------------------------------------------

def _write_registry(tmp_path, reg):
    p = tmp_path / "ats.yaml"
    p.write_text(yaml.safe_dump(reg))
    return str(p)


REG = {
    "filters": FLT,
    "boards": [
        {"org": "Acme", "ats": "greenhouse", "token": "acme"},
        {"org": "Beta", "ats": "lever", "token": "beta"},
    ],
    "mycareersfuture": {"queries": ["AI enablement"]},
    "keyed": {"adzuna": {"country": "sg", "queries": ["AI enablement"]},
              "jooble": {"location": "Singapore", "queries": ["AI enablement"]}},
}


def test_fetch_registry_reports_per_source_and_isolates_errors(tmp_path):
    def boom(url, payload):
        raise RuntimeError("board offline")

    http = _http_from({"greenhouse.io": boom,
                       "api.lever.co": [
                           {"text": "AI Enablement Manager", "hostedUrl": "https://lv.io/a",
                            "categories": {"location": "Remote"}, "descriptionPlain": "d"}],
                       "/v2/jobs/abc123": {"description": "d"},
                       "/v2/search": MCF_RESULT})
    out = fetch_registry(_write_registry(tmp_path, REG), api_keys={}, http=http)
    r = out["report"]
    assert "board offline" in r["greenhouse:acme"]["error"]
    assert r["lever:beta"] == {"fetched": 1, "kept": 1}
    assert r["mycareersfuture"] == {"fetched": 1, "kept": 1}
    # keyed lanes skipped without keys — reported, never silent
    assert r["adzuna"]["skipped"] == "no key"
    assert r["jooble"]["skipped"] == "no key"
    assert len(out["candidates"]) == 2  # lever + mcf; greenhouse errored


def test_fetch_registry_per_board_filter_override(tmp_path):
    reg = {"filters": FLT,
           "boards": [{"org": "Beta", "ats": "lever", "token": "beta",
                       "title_any": ["chef"]}]}
    http = _http_from({"api.lever.co": [
        {"text": "Chef", "hostedUrl": "https://lv.io/b",
         "categories": {"location": "Remote"}, "descriptionPlain": "Cook."}]})
    out = fetch_registry(_write_registry(tmp_path, reg), http=http)
    assert out["report"]["lever:beta"]["kept"] == 1


def test_fetch_registry_keyed_adzuna_and_jooble_run_with_keys(tmp_path):
    def adzuna_route(url, payload):
        return {"results": [{"title": "AI Enablement Lead", "redirect_url": "https://adz.io/1",
                             "company": {"display_name": "Acme"},
                             "location": {"display_name": "Singapore"},
                             "description": "Lead adoption."}]}

    def jooble_route(url, payload):
        return {"jobs": [{"title": "Forward Deployed Engineer", "link": "https://jb.io/1",
                          "company": "Beta", "location": "Singapore",
                          "snippet": "Embed on site."}]}

    reg = {"filters": FLT, "boards": [],
           "keyed": {"adzuna": {"country": "sg", "queries": ["AI enablement"]},
                     "jooble": {"location": "Singapore", "queries": ["forward deployed"]}}}
    http = _http_from({"adzuna.com": adzuna_route, "jooble.org": jooble_route})
    out = fetch_registry(_write_registry(tmp_path, reg),
                         api_keys={"adzuna_app_id": "i", "adzuna_key": "k",
                                   "jooble_key": "j"},
                         http=http)
    assert out["report"]["adzuna"] == {"fetched": 1, "kept": 1}
    assert out["report"]["jooble"] == {"fetched": 1, "kept": 1}
    srcs = {c["source"] for c in out["candidates"]}
    assert srcs == {"adzuna", "jooble"}


def test_candidates_satisfy_discover_contract(tmp_path):
    http = _http_from({"api.lever.co": [
        {"text": "AI Enablement Manager", "hostedUrl": "https://lv.io/a",
         "categories": {"location": "Remote"}, "descriptionPlain": "d"}]})
    reg = {"filters": FLT,
           "boards": [{"org": "Beta", "ats": "lever", "token": "beta"}]}
    out = fetch_registry(_write_registry(tmp_path, reg), http=http)
    c = out["candidates"][0]
    assert set(c) >= {"source", "url", "org", "title", "description"}
    for k in ("source", "url", "org", "title", "description"):
        assert isinstance(c[k], str) and c[k]
