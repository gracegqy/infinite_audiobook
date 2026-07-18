from pipeline import textproc


def test_normalize_ws_unwraps_hard_wraps():
    # probe 1b: hard line-wraps inside a paragraph must become single spaces
    wrapped = "During the whole of a dull,\ndark, and soundless day\nin the autumn"
    assert textproc.normalize_ws(wrapped) == \
        "During the whole of a dull, dark, and soundless day in the autumn"


def test_split_paragraphs_blank_line_segmentation_and_unwrap():
    text = "First para line one\nline two.\n\n\nSecond para.\n\nx"
    paras = textproc.split_paragraphs(text)
    assert paras == ["First para line one line two.", "Second para.", "x"]


def test_split_paragraphs_min_chars_drops_chrome():
    text = "Categories\n\n" + "A real paragraph long enough to keep around here."
    assert textproc.split_paragraphs(text, min_chars=40) == \
        ["A real paragraph long enough to keep around here."]


def test_dedup_key_ignores_case_and_whitespace():
    a = textproc.dedup_key("The  Monkey's Paw", "It was  a dark night.\nOutside,")
    b = textproc.dedup_key("the monkey's paw", "It was a dark night. Outside,")
    assert a == b and len(a) == 40


def test_dedup_key_differs_on_text():
    base = "Same Title"
    assert textproc.dedup_key(base, "text one") != textproc.dedup_key(base, "text two")


def test_story_id_format():
    key = textproc.dedup_key("The Willows", "some text")
    sid = textproc.story_id(key, "The Willows")
    assert sid == f"{key[:12]}-the-willows"


def test_story_id_handles_cjk_titles():
    key = textproc.dedup_key("聊斋志异", "some text")
    sid = textproc.story_id(key, "聊斋志异")
    assert sid.startswith(key[:12] + "-") and sid.endswith("-story")


def test_story_length_problem_bounds():
    assert textproc.story_length_problem("x" * 5000, 1500, 120_000) is None
    assert "too short" in textproc.story_length_problem("x" * 100, 1500, 120_000)
    # gate-run lesson: a 550KB Poe collection volume must be rejected fast
    assert "too long" in textproc.story_length_problem("x" * 550_000, 1500, 120_000)


def test_strip_gutenberg_markers():
    raw = ("junk header\n*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
           "the story body\n*** END OF THE PROJECT GUTENBERG EBOOK FOO ***\nlicense")
    body, found = textproc.strip_gutenberg(raw)
    assert found and body == "the story body"


def test_strip_gutenberg_missing_markers_returns_all():
    body, found = textproc.strip_gutenberg("no markers here")
    assert not found and body == "no markers here"
