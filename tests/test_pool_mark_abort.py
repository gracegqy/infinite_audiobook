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

    def checkpoint(done, total):
        if done == 1:  # abort before the second paragraph
            raise synthesize.AbortRender("skipped")

    with pytest.raises(synthesize.AbortRender):
        synthesize.synthesize_story(["one", "two", "three"], "en",
                                    tmp_path / "out.m4a", checkpoint=checkpoint)
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


def test_stored_voice_override_gallery_only():
    # queue-window pick (gallery voice) is honored on retry...
    assert ingest.stored_voice_override("am_michael", "en") == "am_michael"
    # ...but a stored OpenAI-fallback voice must NOT re-route a $0 retry onto
    # the paid engine, and NULL/foreign-language voices pass through as None
    assert ingest.stored_voice_override("onyx", "en") is None
    assert ingest.stored_voice_override(None, "en") is None
    assert ingest.stored_voice_override("af_heart", "zh") is None


def _fake_render_env(monkeypatch, tmp_path):
    """Patch fetch + engines so retry_story runs without network or Kokoro."""
    class FakeEngine:
        name = "fake"

        def __init__(self, language, voice):
            self.voice = voice

        def render(self, p):
            return np.zeros(2400, dtype=np.float32), 24000

    from pipeline import config
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path / "interim")
    monkeypatch.setattr(config, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setitem(synthesize.ENGINES, "kokoro", FakeEngine)
    monkeypatch.setattr(
        ingest, "_fetch_clean",
        lambda cand: (["Para one.", "Para two."], "Para one.\n\nPara two.",
                      "https://example.org/x"))


def _insert_story(conn, sid, status, voice=None):
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, language, status, voice) "
        "VALUES(?,1,?,?, 'gutenberg','https://example.org/x','pd','en',?,?)",
        (sid, f"k-{sid}", f"T {sid}", status, voice))
    conn.commit()


def test_rerender_of_read_story_stays_read(monkeypatch, tmp_path, conn):
    # voice re-render (AMENDMENT_04 D3) must not resurrect finished history
    _fake_render_env(monkeypatch, tmp_path)
    _insert_story(conn, "sid-read", "read")
    ingest.retry_story(conn, "sid-read", voice_override="af_bella")
    row = conn.execute("SELECT status, voice FROM stories WHERE id='sid-read'").fetchone()
    assert row["status"] == "read"
    assert row["voice"] == "af_bella"


def test_retry_of_failed_story_ends_ready(monkeypatch, tmp_path, conn):
    _fake_render_env(monkeypatch, tmp_path)
    _insert_story(conn, "sid-fail", "failed")
    ingest.retry_story(conn, "sid-fail")
    assert conn.execute("SELECT status FROM stories WHERE id='sid-fail'")\
        .fetchone()["status"] == "ready"


def test_finalize_rereads_queue_window_voice_pick(monkeypatch, tmp_path, conn):
    # pick stored on the row after text_ready (queue-window picker) is honored
    # even when the caller passed no explicit override
    _fake_render_env(monkeypatch, tmp_path)
    _insert_story(conn, "sid-pick", "text_ready", voice="bm_george")
    ingest.retry_story(conn, "sid-pick")
    row = conn.execute("SELECT status, voice FROM stories WHERE id='sid-pick'").fetchone()
    assert row["status"] == "ready"
    assert row["voice"] == "bm_george"


def test_voice_change_mid_render_aborts(monkeypatch, tmp_path, conn):
    # AMENDMENT_05 C6: storing a different gallery voice mid-render aborts at
    # the next paragraph; a stored FALLBACK voice (engine degrade) never does
    calls = []

    class FakeEngine:
        name = "fake"

        def __init__(self, language, voice):
            self.voice = voice

        def render(self, p):
            calls.append(p)
            # simulate Grace picking a new voice after paragraph one renders
            if len(calls) == 1:
                conn.execute("UPDATE stories SET voice='bm_george' "
                             "WHERE id='sid-mid'")
                conn.commit()
            return np.zeros(2400, dtype=np.float32), 24000

    from pipeline import config
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path / "interim")
    monkeypatch.setattr(config, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setitem(synthesize.ENGINES, "kokoro", FakeEngine)
    monkeypatch.setattr(
        ingest, "_fetch_clean",
        lambda cand: (["One.", "Two.", "Three."], "One.\n\nTwo.\n\nThree.",
                      "https://example.org/x"))
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, language, status) VALUES('sid-mid',1,"
        "'k-mid','T mid','gutenberg','https://example.org/x','pd','en','failed')")
    conn.commit()
    with pytest.raises(synthesize.AbortRender):
        ingest.retry_story(conn, "sid-mid")
    assert calls == ["One."]  # second paragraph never rendered
    assert conn.execute("SELECT voice FROM stories WHERE id='sid-mid'")\
        .fetchone()["voice"] == "bm_george"  # the pick survives for the re-run


def test_explicit_voice_retry_does_not_self_abort(monkeypatch, tmp_path, conn):
    # Entry-21 regression: retry --voice X must not abort against the row's
    # stale OLD voice (it only updates at finalize)
    _fake_render_env(monkeypatch, tmp_path)
    _insert_story(conn, "sid-stale", "ready", voice="af_heart")
    ingest.retry_story(conn, "sid-stale", voice_override="bf_emma")
    row = conn.execute(
        "SELECT status, voice FROM stories WHERE id='sid-stale'").fetchone()
    assert row["status"] == "ready"
    assert row["voice"] == "bf_emma"


def test_rerender_of_in_progress_story_stays_in_progress(monkeypatch, tmp_path, conn):
    _fake_render_env(monkeypatch, tmp_path)
    _insert_story(conn, "sid-prog", "in_progress", voice="af_heart")
    ingest.retry_story(conn, "sid-prog", voice_override="am_adam")
    assert conn.execute("SELECT status FROM stories WHERE id='sid-prog'")\
        .fetchone()["status"] == "in_progress"


def test_settings_default_voice_reaches_render(monkeypatch, tmp_path, conn):
    # AMENDMENT_05 A: per-language default voice applies when nothing else set
    _fake_render_env(monkeypatch, tmp_path)
    db.set_setting(conn, "default_voice.en", "bm_george")
    _insert_story(conn, "sid-dflt", "failed")
    ingest.retry_story(conn, "sid-dflt")
    assert conn.execute("SELECT voice FROM stories WHERE id='sid-dflt'")\
        .fetchone()["voice"] == "bm_george"


def test_source_ref_stored_and_used(conn):
    from pipeline import ingest as ing
    sid = ing.record_provisional(
        conn, {"title": "Ref Test", "source_class": "gutenberg",
               "source_ref": "1234", "license_class": "pd"},
        db.active_channel(conn), "skipped")
    row = conn.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
    assert row["source_ref"] == "1234"
    assert ing.candidate_from_row(row)["source_ref"] == "1234"
