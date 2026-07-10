# tests/test_run_inbox.py
import glob
from datetime import date
from run import ingest_inbox
from store import save_opportunity, load_opportunity

TODAY = date(2026, 6, 6)


def test_ingest_inbox_promotes_and_clears(tmp_path):
    inbox = tmp_path / "_inbox"; inbox.mkdir()
    opps = tmp_path / "opps"; opps.mkdir()
    save_opportunity(str(inbox / "paste1.md"),
                     {"source": "manual:linkedin", "url": "https://linkedin.com/jobs/1",
                      "org": "Acme", "title": "Remote VA"}, "Pasted JD text")
    written = ingest_inbox(inbox, opps, today=TODAY)
    assert len(written) == 1
    assert glob.glob(str(inbox / "*.md")) == []      # inbox cleared
    files = glob.glob(str(opps / "*.md"))
    assert len(files) == 1
    fm, body = load_opportunity(files[0])
    assert fm["source"] == "manual:linkedin"
    assert fm["status"] == "discovered"
    assert "Pasted JD text" in body


def test_ingest_inbox_missing_dir_returns_empty(tmp_path):
    assert ingest_inbox(tmp_path / "nope", tmp_path / "opps") == []
