# tests/test_allaboutme_provider.py
import json
import subprocess
from types import SimpleNamespace

import pytest
from provider.allaboutme_provider import AllAboutMeProvider
from provider.profile_provider import ProfileProvider


def _fake_qmd(stdout="", returncode=0, raises=None):
    """A stand-in for subprocess.run that records argv and returns/raises a canned result."""
    def run(cmd, *args, **kwargs):
        run.calls.append(cmd)
        if raises is not None:
            raise raises
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")
    run.calls = []
    return run


def _qmd_json(*files, score=0.9):
    """Build a `qmd --json` stdout payload (the real shape) for the given qmd:// URLs."""
    return json.dumps([{"docid": f"#{i}", "score": score, "file": f,
                        "title": "t", "snippet": "s"} for i, f in enumerate(files)])


def _make_kb(tmp_path):
    kb = tmp_path / "kb"
    (kb / "goals").mkdir(parents=True)
    (kb / "experience").mkdir()
    (kb / "lens.md").write_text(
        "# Lens\n\n```yaml\n"
        "hard_filters:\n  allowed_locations: []\n  remote_ok: true\n"
        "  comp_floor: null\n  exclude: [gambling]\n"
        "soft_weights:\n  automatable: 3\n"
        "tier_thresholds: {deep: 0.75, light: 0.5}\n"
        "eligibility:\n  work_auth: [freedonia]\n  languages: [english, elvish-basic]\n```\n",
        encoding="utf-8")
    (kb / "compass.md").write_text("Side income via automatable remote gigs.", encoding="utf-8")
    (kb / "voice.md").write_text("Direct and concrete.", encoding="utf-8")
    (kb / "goals" / "g1.md").write_text(
        "---\nid: side-income\ntype: goal\nsummary: Recurring automatable side income\n"
        "priority: 5\nstatus: active\n---\n\nbody", encoding="utf-8")
    (kb / "experience" / "e1.md").write_text(
        "---\nid: northwind-labs\ntype: experience\n---\n\nBuilt AI workflows and automations.",
        encoding="utf-8")
    return kb


def _config(tmp_path, kb, qmd_collection=None, qmd_command=None):
    lines = [f"all_about_me_path: {kb}", "api_keys:", "  adzuna_key: abc"]
    if qmd_collection is not None:
        lines.append(f"qmd_collection: {qmd_collection}")
    if qmd_command is not None:
        lines.append(f"qmd_command: {qmd_command}")
    cfg = tmp_path / "provider.local.yaml"
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(cfg)


def test_provider_is_a_profile_provider(tmp_path):
    kb = _make_kb(tmp_path)
    assert isinstance(AllAboutMeProvider(_config(tmp_path, kb)), ProfileProvider)


def test_get_lens_parses_machine_block_and_files(tmp_path):
    kb = _make_kb(tmp_path)
    lens = AllAboutMeProvider(_config(tmp_path, kb)).get_lens()
    assert lens["hard_filters"]["comp_floor"] is None
    assert lens["hard_filters"]["remote_ok"] is True
    assert lens["soft_weights"]["automatable"] == 3
    assert lens["tier_thresholds"]["deep"] == 0.75
    assert "automatable remote gigs" in lens["compass"]
    assert lens["goals"][0]["priority"] == 5
    assert lens["api_keys"]["adzuna_key"] == "abc"
    assert lens["eligibility"]["work_auth"] == ["freedonia"]
    assert lens["eligibility"]["languages"] == ["english", "elvish-basic"]


def test_get_lens_missing_eligibility_block_yields_empty_dict(tmp_path):
    kb = _make_kb(tmp_path)
    (kb / "lens.md").write_text(
        "# Lens\n\n```yaml\nhard_filters:\n  remote_ok: true\n```\n", encoding="utf-8")
    lens = AllAboutMeProvider(_config(tmp_path, kb)).get_lens()
    assert lens["eligibility"] == {}  # geo_gate fails closed on this


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="all_about_me_path"):
        AllAboutMeProvider(str(tmp_path / "nonexistent.yaml"))


def test_search_evidence_finds_matching_files(tmp_path):
    kb = _make_kb(tmp_path)
    p = AllAboutMeProvider(_config(tmp_path, kb))
    hits = p.search_evidence("automation workflows")
    assert any("Built AI workflows" in h["text"] for h in hits)
    assert all("source" in h for h in hits)


def test_search_evidence_returns_empty_on_no_match(tmp_path):
    kb = _make_kb(tmp_path)
    p = AllAboutMeProvider(_config(tmp_path, kb))
    assert p.search_evidence("xyzzy nonexistent") == []


def test_propose_kb_change_writes_to_inbox_not_kb(tmp_path):
    kb = _make_kb(tmp_path)
    p = AllAboutMeProvider(_config(tmp_path, kb))
    out = p.propose_kb_change({"target": "lens.md", "after": "new pref", "rationale": "why"})
    from pathlib import Path
    assert Path(out).exists()
    assert (kb / "lens-proposals").is_dir()
    assert "new pref" in Path(out).read_text(encoding="utf-8")
    assert "new pref" not in (kb / "lens.md").read_text(encoding="utf-8")


# --- qmd-accelerated search_evidence (spec 2026-06-18) -----------------------

def test_qmd_used_when_configured(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    (kb / "projects").mkdir()
    (kb / "projects" / "p1.md").write_text("Shipped a billing automation.", encoding="utf-8")
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/experience/e1.md", "qmd://me/projects/p1.md"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me", qmd_command="search"))
    hits = p.search_evidence("automation")
    # ranked, in qmd's order, content read from disk
    assert [h["source"] for h in hits] == ["experience/e1.md", "projects/p1.md"]
    assert any("Built AI workflows" in h["text"] for h in hits)
    assert any("billing automation" in h["text"] for h in hits)
    # correct command shape
    argv = fake.calls[0]
    assert argv[0] == "qmd" and "search" in argv
    assert "--collection" in argv and "me" in argv and "--json" in argv


def test_qmd_default_command_is_query(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/experience/e1.md"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))  # no qmd_command
    p.search_evidence("anything")
    assert "query" in fake.calls[0]  # semantic default (expansion + rerank), matches deep_search


def test_qmd_command_override_is_used(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/experience/e1.md"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me", qmd_command="vsearch"))
    p.search_evidence("anything")
    assert "vsearch" in fake.calls[0]
    assert "search" not in fake.calls[0]


def test_qmd_results_filtered_to_evidence_dirs(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json(
        "qmd://me/compass.md", "qmd://me/goals/g1.md", "qmd://me/experience/e1.md"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    hits = p.search_evidence("anything")
    assert [h["source"] for h in hits] == ["experience/e1.md"]


def test_qmd_handles_comma_in_path_and_skips_malformed_rows(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    (kb / "skills").mkdir()
    (kb / "skills" / "a,b.md").write_text("comma skill", encoding="utf-8")
    stdout = json.dumps([
        {"docid": "#a", "score": 0.9, "file": "qmd://me/skills/a,b.md"},  # comma in filename
        {"docid": "#b", "score": 0.8},                                    # missing 'file'
        None,                                                             # malformed row
        {"docid": "#c", "score": 0.7, "file": "qmd://me/experience/e1.md"},
    ])
    fake = _fake_qmd(stdout=stdout)
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    hits = p._qmd_evidence("anything")
    assert [h["source"] for h in hits] == ["skills/a,b.md", "experience/e1.md"]
    assert any("comma skill" in h["text"] for h in hits)


def test_qmd_traversal_path_yields_no_hit(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/../../../etc/passwd"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert p._qmd_evidence("anything") == []


def test_qmd_traversal_via_evidence_prefix_is_blocked(monkeypatch, tmp_path):
    # First segment is a valid evidence dir, but '..' still climbs out of the KB.
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/experience/../../../etc/passwd"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert p._qmd_evidence("anything") == []


def test_qmd_directory_hit_does_not_crash(monkeypatch, tmp_path):
    # A hit that resolves to a directory must be skipped, not raise IsADirectoryError.
    kb = _make_kb(tmp_path)
    (kb / "skills").mkdir()
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/skills"))  # 'skills' is a directory
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    # qmd yields nothing usable -> falls back to glob, which finds e1
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_leading_dash_query_is_sanitized(monkeypatch, tmp_path):
    # A JD-derived query that starts like a flag must not be parsed by qmd as one.
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout=_qmd_json("qmd://me/experience/e1.md"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    p.search_evidence("--collection evil")
    argv = fake.calls[0]
    assert argv[2] == "collection evil"   # leading dashes stripped before reaching qmd
    assert not argv[2].startswith("-")


def test_qmd_empty_query_after_sanitize_does_not_invoke_qmd(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(raises=AssertionError("qmd must not be called for an empty query"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert p._qmd_evidence("---") == []
    assert fake.calls == []


def test_qmd_fallback_when_binary_missing(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(raises=FileNotFoundError("qmd"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation workflows"))


def test_qmd_fallback_on_nonzero_exit(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout="boom", returncode=1)
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_fallback_on_timeout(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(raises=subprocess.TimeoutExpired(cmd="qmd", timeout=30))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_fallback_on_malformed_json(monkeypatch, tmp_path):
    # Garbage stdout (json.loads raises ValueError) must fall back, not crash.
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout="not json {{{", returncode=0)
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_fallback_on_decode_error(monkeypatch, tmp_path):
    # A UnicodeDecodeError (a ValueError subclass) must be caught -> glob fallback.
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(raises=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_empty_result_falls_back_to_glob(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(stdout="[]", returncode=0)
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me"))
    assert any("Built AI workflows" in h["text"] for h in p.search_evidence("automation"))


def test_qmd_not_invoked_when_collection_absent(monkeypatch, tmp_path):
    kb = _make_kb(tmp_path)
    fake = _fake_qmd(raises=AssertionError("qmd must not be called"))
    monkeypatch.setattr("provider.allaboutme_provider.subprocess.run", fake)
    p = AllAboutMeProvider(_config(tmp_path, kb))  # no qmd_collection
    hits = p.search_evidence("automation workflows")
    assert any("Built AI workflows" in h["text"] for h in hits)
    assert fake.calls == []


def test_invalid_qmd_command_raises(tmp_path):
    kb = _make_kb(tmp_path)
    with pytest.raises(RuntimeError, match="qmd_command"):
        AllAboutMeProvider(_config(tmp_path, kb, qmd_collection="me", qmd_command="rm -rf /"))
