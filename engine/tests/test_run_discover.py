# tests/test_run_discover.py
import glob
from datetime import date
from run import discover_write
from store import load_opportunity

TODAY = date(2026, 6, 6)


def test_discover_write_creates_files_and_dedupes(tmp_path):
    cands = [
        {"source": "remoteok", "url": "https://x.com/a", "org": "Acme", "title": "Data entry"},
        {"source": "remoteok", "url": "https://x.com/a", "org": "Acme", "title": "Data entry"},
        {"source": "hn", "url": "https://y.com/b", "org": "Beta", "title": "Copywriter"},
    ]
    summary = discover_write(cands, tmp_path, today=TODAY)
    assert len(summary["written"]) == 2
    assert len(summary["skipped"]) == 1
    assert len(glob.glob(str(tmp_path / "*.md"))) == 2
    fm, _ = load_opportunity(glob.glob(str(tmp_path / "*.md"))[0])
    assert fm["status"] == "discovered"
    assert fm["date_found"] == "2026-06-06"
    assert fm["opportunity_type"] == "job"


def test_discover_write_dedupes_against_existing_files(tmp_path):
    cand = [{"source": "x", "url": "https://x.com/a", "org": "Acme", "title": "T"}]
    discover_write(cand, tmp_path, today=TODAY)
    summary = discover_write(cand, tmp_path, today=TODAY)
    assert summary["written"] == []
    assert len(summary["skipped"]) == 1


def test_per_source_counts(tmp_path):
    cands = [{"source": "hn", "url": "u1", "title": "a"},
             {"source": "hn", "url": "u2", "title": "b"}]
    summary = discover_write(cands, tmp_path, today=TODAY)
    assert summary["per_source"]["hn"]["written"] == 2
