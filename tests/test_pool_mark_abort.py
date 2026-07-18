import json

import numpy as np
import pytest

from pipeline import db, ingest, mark, pool, synthesize


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


def _seed_run(conn, titles, run_note="r1"):
    cands = [{"title": t, "author": "A", "source_class": "gutenberg",
              "source_ref": "1", "license_class": "pd", "evidence": [run_note]}
             for t in titles]
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, "
        "candidates_json) VALUES(1,'m',1.0,0,?)",
        (json.dumps(cands),))
    conn.commit()


def test_pool_excludes_consumed_and_dedups_across_runs(conn):
    _seed_run(conn, ["Alpha", "Beta", "Gamma"], "old")
    _seed_run(conn, ["Beta", "Delta"], "new")
    # Alpha already has a stories row (any status counts as consumed)
    ingest.record_provisional(conn, {"title": "Alpha"},
                              db.active_channel(conn), "read")
    titles = [c["title"] for c in pool.pool_candidates(conn)]
    assert "Alpha" not in titles
    assert titles.count("Beta") == 1  # deduped across runs, newest run first
    assert set(titles) == {"Beta", "Delta", "Gamma"}


def test_pool_skips_unparsed_failure_rows(conn):
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, "
        "candidates_json) VALUES(1,'m',1.0,0,?)",
        (json.dumps({"unparsed": "garbage"}),))
    conn.commit()
    assert pool.pool_candidates(conn) == []


def test_mark_read_pool_candidate_never_fetched(conn):
    _seed_run(conn, ["The Willows"])
    msg = mark.mark(conn, "read", "willows")
    assert "read" in msg
    assert "The Willows" in db.known_titles(conn)
    assert pool.pool_candidates(conn) == []  # consumed without any fetch
    row = conn.execute(
        "SELECT * FROM stories WHERE title='The Willows'").fetchone()
    assert row["status"] == "read"


def test_mark_skip_existing_row_flips_status(conn):
    sid = ingest.record_provisional(conn, {"title": "Carmilla"},
                                    db.active_channel(conn), "failed", "x")
    msg = mark.mark(conn, "skip", "carmilla")
    assert sid in msg
    row = conn.execute("SELECT status FROM stories WHERE id=?", (sid,)).fetchone()
    assert row["status"] == "skipped"


def test_mark_unknown_title_creates_provisional_row(conn):
    mark.mark(conn, "read", "Some Story I Read Years Ago")
    assert "Some Story I Read Years Ago" in db.known_titles(conn)


def test_abort_render_between_paragraphs_no_fallback(monkeypatch, tmp_path):
    calls = []

    class FakeEngine:
        name = "fake"

        def __init__(self, language, voice):
            self.voice = voice

        def render(self, p):
            calls.append(p)
            return np.zeros(2400, dtype=np.float32), 24000

    from pipeline import config
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path)
    monkeypatch.setitem(synthesize.ENGINES, "kokoro", FakeEngine)
    monkeypatch.setitem(synthesize.ENGINES, "openai", FakeEngine)

    aborted = iter([False, True])  # abort before the second paragraph
    with pytest.raises(synthesize.AbortRender):
        synthesize.synthesize_story(["one", "two", "three"], "en",
                                    tmp_path / "out.m4a",
                                    should_abort=lambda: next(aborted))
    assert calls == ["one"]  # second render never started, no fallback restart


def test_voice_override_reaches_engine(monkeypatch, tmp_path):
    seen = {}

    class FakeEngine:
        name = "fake"

        def __init__(self, language, voice):
            seen["voice"] = voice

        def render(self, p):
            return np.zeros(2400, dtype=np.float32), 24000

    from pipeline import config
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path)
    monkeypatch.setitem(synthesize.ENGINES, "kokoro", FakeEngine)
    engine, voice, sr, durations = synthesize.synthesize_story(
        ["hello"], "en", tmp_path / "out.m4a", voice_override="am_michael")
    assert seen["voice"] == "am_michael" and voice == "am_michael"
    assert len(durations) == 1 and sr == 24000
