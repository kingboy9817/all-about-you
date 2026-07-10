# tests/test_draft_lint.py
from draft_lint import (find_tells, find_truncations, summary, prose_blocks,
                        prose_text, EM_DASH)

D = EM_DASH


def _tells(flags):
    return {f["tell"] for f in flags}


def _em(flags):
    return [f for f in flags if f["tell"] == "em_dash"]


def test_clean_text_has_no_flags():
    clean = ("I build AI tools and coach teams to adopt them. Across five years "
             "my throughline held: make the technical land for the people who need it.")
    assert find_tells(clean) == []
    assert summary(clean) == "clean — no AI tics flagged"


# --- em-dash: <=1 unit per PARAGRAPH; a parenthetical pair is one allowed unit ---

def test_single_em_dash_per_paragraph_ok():
    assert not _em(find_tells(f"I built it {D} fast. Then I shipped it clean."))


def test_parenthetical_pair_in_one_sentence_is_allowed():
    # X — aside — Y is two dashes doing a pair of commas' job: one unit, allowed
    assert not _em(find_tells(f"I built the tool {D} a report compiler {D} in a week."))


def test_two_separate_dashes_in_one_paragraph_flags():
    flags = _em(find_tells(f"I built it {D} fast. Then I shipped it {D} clean."))
    assert flags and flags[0]["paragraphs"] == 1


def test_pair_plus_another_dash_in_same_paragraph_flags():
    # one sentence holds the pair, another sentence adds a lone dash -> 2 units
    assert _em(find_tells(f"I built it {D} a compiler {D} fast. It shipped {D} clean."))


def test_three_dash_chain_in_one_sentence_flags():
    assert _em(find_tells(f"a {D} b {D} c {D} d, all in one breath."))


def test_em_dash_budget_is_per_paragraph_not_per_doc():
    # one unit in each of two paragraphs is fine — the budget does not span the doc
    text = f"First para has one {D} dash here.\n\nSecond para has one {D} dash too."
    assert not _em(find_tells(text))


def test_en_dash_and_hyphen_not_flagged_as_em_dash():
    text = "Worked 2024–2025 on a multi-agent project with non-technical teams. " * 3
    assert not _em(find_tells(text))


# --- "x not y" family ---

def test_flags_x_not_y_constructions():
    for bad in ["I do both, not just one half", "the building and the adoption, "
                "not one without the other", "it's not luck but skill",
                "not only fast but also cheap"]:
        assert "x_not_y" in _tells(find_tells(bad)), bad


# --- cliché list: short, high-precision, excludes the owner's vocabulary ---

def test_flags_high_signal_cliches():
    flags = find_tells("Let me delve into the rich tapestry of this multifaceted realm of work.")
    words = {f["word"] for f in flags if f["tell"] == "cliche"}
    assert {"delve", "tapestry", "multifaceted", "realm of"} <= words


def test_owner_vocabulary_is_not_flagged():
    # regression guard (2026-06-19): words the owner genuinely uses
    text = ("We leverage a seamless, robust system. Furthermore, moreover, we utilize "
            "a comprehensive agent harness. It's a testament to a pivotal effort at the "
            "forefront, which I spearheaded and which fosters and elevates the work.")
    assert not any(f["tell"] == "cliche" for f in find_tells(text))


def test_cliche_match_is_whole_word():
    assert not any(f.get("word") == "realm of" for f in find_tells("overwhelmed"))
    assert not any(f.get("word") == "delve" for f in find_tells("delved deeply"))


# --- structured-draft prose extraction ---

def test_prose_blocks_extracts_chunks_excludes_chips():
    meta = {
        "profile": "Profile here.",
        "tagline": "ignored",
        "sidebar": [{"heading": "Skills", "chips": [f"Excel {D} SPSS"]}],  # chips excluded
        "sections": [{"entries": [{"summary": "Summary one.", "bullets": ["b1", "b2"]}]}],
        "cover_letter": "Para A.\n\nPara B.",
    }
    blocks = prose_blocks(meta)
    assert blocks == ["Profile here.", "Summary one.", "b1", "b2", "Para A.", "Para B."]


def test_prose_text_keeps_each_chunk_a_separate_paragraph():
    # one dash in the profile and one in a bullet must NOT combine to bust the budget
    meta = {"profile": f"Built it {D} fast.",
            "sections": [{"entries": [{"summary": "", "bullets": [f"Shipped it {D} clean."]}]}]}
    assert not _em(find_tells(prose_text(meta)))


# --- find_truncations: the YAML parser's blind spots (render-breaking) ---

def _meta(bullets):
    return {"sections": [{"entries": [{"summary": "", "bullets": bullets}]}]}


def test_unquoted_hash_in_raw_is_flagged_as_comment_truncation():
    # the live 2026-06-19 bug: ' #1' makes YAML drop the rest of the bullet
    raw = ("sections:\n  - entries:\n      - bullets:\n"
           "          - Built it and ranked #1 on Google ==fast== within 60 days.\n")
    flags = find_truncations({}, raw)
    assert any(f["tell"] == "yaml_comment_truncation" for f in flags)


def test_quoting_the_value_clears_the_comment_flag():
    raw = ("          - 'Built it and ranked #1 on Google ==fast== within 60 days.'\n")
    assert not [f for f in find_truncations({}, raw)
                if f["tell"] == "yaml_comment_truncation"]


def test_folded_scalar_body_with_hash_is_not_flagged():
    # a '>' folded summary's continuation lines are not value-introducers, and '#'
    # inside a block scalar is literal anyway — must not false-positive
    raw = ("      - summary: >\n"
           "          We ranked #1 and held it; this is prose, not a comment.\n")
    assert not [f for f in find_truncations({}, raw)
                if f["tell"] == "yaml_comment_truncation"]


def test_bullet_parsed_as_dict_is_flagged():
    # '- Label: detail' parses to a dict, not a string bullet (the ': '-swap bug)
    flags = find_truncations(_meta([{"Label": "detail"}]), "")
    assert any(f["tell"] == "yaml_bullet_not_string" for f in flags)


def test_unbalanced_highlight_is_flagged():
    flags = find_truncations(_meta(["Built it and ==recommended by ChatGPT and ranked"]), "")
    assert any(f["tell"] == "unbalanced_highlight" for f in flags)


def test_balanced_highlight_and_plain_string_bullets_are_clean():
    raw = "          - Built it and ranked No.1 on Google within 60 days.\n"
    meta = _meta(["A ==balanced== highlight.", "A plain bullet."])
    assert find_truncations(meta, raw) == []
