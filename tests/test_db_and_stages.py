import json

import pytest

from pipeline import curate, db, tag


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


def test_schema_creates_and_seeds_default_channel(conn):
    ch = db.active_channel(conn)
    assert ch["name"] == "horror" and ch["language"] == "en"
    tables = {r["name"] for r in
              conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"channels", "stories", "tags", "progress", "bookmarks", "ratings",
            "curation_runs"} <= tables


def _insert_story(conn, sid="k1-title", key="k1", status="ready", title="T"):
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, status) VALUES(?,1,?,?,'gutenberg','u','pd',?)",
        (sid, key, title, status))
    conn.commit()


def test_dedup_key_unique_enforced(conn):
    _insert_story(conn)
    with pytest.raises(Exception):
        _insert_story(conn, sid="other-id")


def test_status_check_constraint(conn):
    with pytest.raises(Exception):
        _insert_story(conn, status="bogus")


def test_set_status_records_ready_at_and_failure_note(conn):
    _insert_story(conn, status="fetching")
    db.set_status(conn, "k1-title", "failed", failure_note="boom")
    row = conn.execute("SELECT * FROM stories WHERE id='k1-title'").fetchone()
    assert row["status"] == "failed" and row["failure_note"] == "boom"
    assert row["ready_at"] is None
    db.set_status(conn, "k1-title", "ready")
    row = conn.execute("SELECT * FROM stories WHERE id='k1-title'").fetchone()
    assert row["status"] == "ready" and row["ready_at"] is not None


def test_known_titles_and_keys(conn):
    _insert_story(conn, sid="a-x", key="ka", title="Alpha")
    _insert_story(conn, sid="b-x", key="kb", title="Beta")
    assert db.known_dedup_keys(conn) == {"ka", "kb"}
    assert db.known_titles(conn) == ["Alpha", "Beta"]


# ---- curation prompt/parse (pure halves of the stage) ----

def test_curation_prompt_carries_exclusions_and_criteria(conn):
    ch = db.active_channel(conn)
    p = curate.build_prompt(ch, ["The Willows", "Carmilla"], batch=8)
    assert "- The Willows" in p and "- Carmilla" in p
    assert "horror" in p and "en" in p


def test_parse_candidates_from_fenced_json():
    payload = [{"title": "T", "author": "A", "year": 1907,
                "source_class": "gutenberg", "source_ref": "11438",
                "license_class": "pd", "evidence": ["a list"], "unverified": []}]
    text = f"Here are picks:\n```json\n{json.dumps(payload)}\n```"
    assert curate.parse_candidates(text) == payload


def test_parse_candidates_rejects_missing_fields():
    with pytest.raises(ValueError):
        curate.parse_candidates('[{"title": "X"}]')


# ---- ingest pure halves ----

def test_paragraph_floor_only_for_html_sources():
    from pipeline import config, ingest
    assert ingest.paragraph_floor("creepypasta") == config.MIN_PARAGRAPH_CHARS
    assert ingest.paragraph_floor("nosleep") == config.MIN_PARAGRAPH_CHARS
    assert ingest.paragraph_floor("gutenberg") == 0   # Yellow Wallpaper lesson
    assert ingest.paragraph_floor("local_import") == 0


def test_candidate_from_row_derives_source_ref(conn):
    from pipeline import ingest
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, author, year, "
        "source_class, source_url, license_class, language, "
        "curation_evidence_json, status) "
        "VALUES('g-x',1,'kg','G','A',1901,'gutenberg',"
        "'https://www.gutenberg.org/cache/epub/1952/pg1952.txt','pd','en',"
        "'[\"ev\"]','failed')")
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, language, status) "
        "VALUES('c-x',1,'kc','C','creepypasta',"
        "'https://creepypasta.fandom.com/wiki/Candle_Cove','modern_private',"
        "'en','failed')")
    conn.commit()
    g = ingest.candidate_from_row(
        conn.execute("SELECT * FROM stories WHERE id='g-x'").fetchone())
    assert g["source_ref"] == "1952" and g["evidence"] == ["ev"] and g["year"] == 1901
    c = ingest.candidate_from_row(
        conn.execute("SELECT * FROM stories WHERE id='c-x'").fetchone())
    assert c["source_ref"] == "Candle Cove"


def test_html_text_parser_skips_chrome_and_breaks_paragraphs():
    from pipeline.fetch import _HtmlText
    p = _HtmlText()
    p.feed("<p>First para.</p><table><tr><td>chrome</td></tr></table>"
           "<p>Second <b>bold</b> para.</p><style>.x{}</style>")
    text = "".join(p.parts)
    assert "First para." in text and "Second bold para." in text
    assert "chrome" not in text and ".x{}" not in text
    assert p.skip == 0  # balanced skip-depth after nested skip tags


def test_html_text_parser_decodes_entities_exactly_once():
    from pipeline.fetch import _HtmlText
    p = _HtmlText()
    p.feed("<p>Tom &amp;amp; Jerry</p>")  # page shows literal "&amp; Jerry"
    assert "Tom &amp; Jerry" in "".join(p.parts)


def test_rejected_candidate_enters_history(conn, monkeypatch):
    from pipeline import fetch, ingest
    monkeypatch.setattr(fetch, "fetch_candidate",
                        lambda c: (_ for _ in ()).throw(
                            fetch.FetchError("cleaned text too long")))
    cand = {"title": "The Complete Works", "source_class": "gutenberg",
            "source_ref": "2148", "license_class": "pd", "evidence": []}
    ch = db.active_channel(conn)
    with pytest.raises(fetch.FetchError):
        ingest.ingest_candidate(conn, cand, ch)
    # the doomed pick is now history: excluded from future curation batches
    assert "The Complete Works" in db.known_titles(conn)
    row = conn.execute("SELECT * FROM stories WHERE title='The Complete Works'"
                       ).fetchone()
    assert row["status"] == "failed" and "too long" in row["failure_note"]


# ---- tag normalization (pure half) ----

def test_tag_rows_controlled_vocab_and_verbatim():
    rows = tag.tag_rows("sid", {"era": "19th century", "origin": "Western",
                                "subgenre": ["Gothic", "weirdcore"],
                                "themes": ["isolation", "Isolation"]},
                        author="A. Blackwood", language="en")
    by_kind = {}
    for _, kind, verbatim, norm in rows:
        by_kind.setdefault(kind, []).append((verbatim, norm))
    assert by_kind["era"] == [("19th century", "19th-century")]
    assert by_kind["origin"] == [("Western", "western")]
    assert by_kind["subgenre"] == [("Gothic", "gothic")]  # off-vocab dropped
    assert by_kind["theme"] == [("isolation", "isolation")]  # deduped on norm
    assert by_kind["author"] == [("A. Blackwood", "a. blackwood")]
    assert by_kind["language"] == [("en", "en")]
