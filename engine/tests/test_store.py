# tests/test_store.py
from store import load_opportunity, save_opportunity


def test_round_trips_frontmatter_and_body(tmp_path):
    p = tmp_path / "acme.md"
    fm = {"id": "acme-infra", "status": "discovered",
          "extracted": {"remote": True, "comp": 12000}}
    save_opportunity(str(p), fm, "JD body here")

    loaded_fm, body = load_opportunity(str(p))
    assert loaded_fm["id"] == "acme-infra"
    assert loaded_fm["extracted"]["remote"] is True
    assert loaded_fm["extracted"]["comp"] == 12000
    assert "JD body here" in body


def test_load_handles_file_without_frontmatter(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("just text, no frontmatter", encoding="utf-8")
    fm, body = load_opportunity(str(p))
    assert fm == {}
    assert "just text" in body
