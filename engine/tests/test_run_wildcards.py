# tests/test_run_wildcards.py
"""Plan 5 — exploration quota: deterministic wildcard selection (spec §15)."""
from datetime import date

from run import select_wildcards, build_pipeline
from store import load_opportunity, save_opportunity

WEEK = "2026-W24"


def _reject(tmp, slug, filter_result="skip", tier="skip", legitimacy="unverified",
            status="rejected", **extra):
    fm = {"id": slug, "org": extra.pop("org", slug.title()), "title": "Role",
          "status": status, "filter_result": filter_result, "tier": tier,
          "legitimacy": legitimacy, "flags": extra.pop("flags", []), **extra}
    save_opportunity(str(tmp / f"{slug}.md"), fm, "")


def test_select_wildcards_picks_caps_and_tags(tmp_path):
    for s in ("alpha", "beta", "gamma"):
        _reject(tmp_path, s)
    chosen = select_wildcards(tmp_path, k=2, week=WEEK)
    assert len(chosen) == 2
    for fm in chosen:
        assert fm["wildcard"] is True
        assert fm["wildcard_week"] == WEEK
        assert any("wildcard" in f for f in fm["flags"])
    on_disk, _ = load_opportunity(str(tmp_path / f"{chosen[0]['id']}.md"))
    assert on_disk["wildcard"] is True


def test_select_wildcards_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    for d in (a, b):
        for s in ("alpha", "beta", "gamma", "delta"):
            _reject(d, s)
    ids_a = [fm["id"] for fm in select_wildcards(a, k=2, week=WEEK)]
    ids_b = [fm["id"] for fm in select_wildcards(b, k=2, week=WEEK)]
    assert ids_a == ids_b


def test_select_wildcards_excludes_suspect_and_non_rejects(tmp_path):
    _reject(tmp_path, "scammy", legitimacy="suspect")
    _reject(tmp_path, "live-one", status="shortlisted")
    _reject(tmp_path, "passed-fit", filter_result="pass", tier="light")
    _reject(tmp_path, "fair-game")
    chosen = select_wildcards(tmp_path, k=3, week=WEEK)
    assert [fm["id"] for fm in chosen] == ["fair-game"]


def test_select_wildcards_surfaces_each_record_at_most_once(tmp_path):
    _reject(tmp_path, "alpha")
    _reject(tmp_path, "beta")
    first = select_wildcards(tmp_path, k=2, week=WEEK)
    assert len(first) == 2
    again = select_wildcards(tmp_path, k=2, week="2026-W25")
    assert again == []   # already surfaced once; never re-nag


def test_select_wildcards_empty_pool(tmp_path):
    assert select_wildcards(tmp_path, k=2, week=WEEK) == []


def test_build_pipeline_shows_current_week_wildcards(tmp_path):
    _reject(tmp_path, "alpha", org="OffLens Co")
    select_wildcards(tmp_path, k=1, week="2026-W24")
    md = build_pipeline(tmp_path, today=date(2026, 6, 12))   # ISO week 24
    assert "## Wildcards" in md
    assert "OffLens Co" in md
    # a different week's board no longer shows it
    md_later = build_pipeline(tmp_path, today=date(2026, 6, 22))   # week 26
    assert "OffLens Co" not in md_later
