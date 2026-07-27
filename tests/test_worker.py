"""Phase 5 replenishment worker (DESIGN §7).

Pure logic (shortfall, eligibility) takes its state as parameters. The cycle
tests inject fetch and render so nothing hits the network or Kokoro — what is
under test is the DECISION: how many to acquire, in what order, what stops it,
and that nothing ever repeats.
"""
import json

import pytest

from pipeline import config, db, fetch, ingest, pool, worker


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path / "interim")
    return db.connect(tmp_path / "app.db")


def add_run(conn, titles, channel_id=1):
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, candidates_json) "
        "VALUES(?,'m',?)",
        (channel_id, json.dumps([
            {"title": t, "author": "A", "source_class": "gutenberg",
             "source_ref": str(i), "license_class": "pd", "language": "en",
             "evidence": ["listed"]} for i, t in enumerate(titles)])))
    conn.commit()


def add_story(conn, sid, title, status, channel_id=1):
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_ref, source_url, license_class, language, status) "
        "VALUES(?,?,?,?,'gutenberg','1','https://example.org/x','pd','en',?)",
        (sid, channel_id, f"k-{sid}", title, status))
    conn.commit()


@pytest.fixture()
def fake_pipeline(monkeypatch):
    """Fetch returns three paragraphs per candidate; render just flips the row
    to ready. Keeps the cycle honest about DB transitions without synthesis."""
    monkeypatch.setattr(
        ingest, "_fetch_clean",
        lambda c: ([f"{c['title']} one.", "Two.", "Three."],
                   f"{c['title']} one.\n\nTwo.\n\nThree.",
                   f"https://example.org/{c['source_ref']}"))
    monkeypatch.setattr(ingest.tag, "run_tagging",
                        lambda *a, **k: None)

    rendered = []

    def fake_render(conn, sid, voice_override=None):
        rendered.append(sid)
        conn.execute("UPDATE stories SET status='ready', duration_s=60.0 "
                     "WHERE id=?", (sid,))
        conn.commit()
        return sid

    monkeypatch.setattr(ingest, "render_ready_story", fake_render)
    return rendered


# ---- pure logic ----

def test_unread_shortfall():
    assert worker.unread_shortfall(0, 3) == 3
    assert worker.unread_shortfall(2, 3) == 1
    assert worker.unread_shortfall(3, 3) == 0
    assert worker.unread_shortfall(5, 3) == 0  # over-full never goes negative


def test_needs_replenishment_boundary():
    assert worker.needs_replenishment(2, 3)
    assert not worker.needs_replenishment(3, 3)


def test_eligible_drops_what_cannot_be_attempted():
    cands = [{"title": "a", "source_class": "gutenberg", "source_ref": "42"},
             {"title": "b", "source_class": "reddit", "source_ref": "x"},
             {"title": "c", "source_class": "creepypasta", "source_ref": "Page"},
             {"title": "d", "source_class": "gutenberg", "source_ref": "unknown"},
             {"title": "e", "source_class": "creepypasta", "source_ref": ""}]
    assert [c["title"] for c in worker.eligible(cands, fetch.ENABLED_SOURCE_CLASSES)] \
        == ["a", "c"]  # b: no fetcher · d/e: no usable reference


# ---- counting ----

def test_unread_counts_only_acquired_but_unstarted(conn):
    add_story(conn, "s1", "T1", "text_ready")
    add_story(conn, "s2", "T2", "ready")
    add_story(conn, "s3", "T3", "in_progress")  # started
    add_story(conn, "s4", "T4", "read")
    add_story(conn, "s5", "T5", "skipped")
    add_story(conn, "s6", "T6", "failed")
    assert worker.unread_count(conn, 1) == 2


def test_unread_is_per_channel(conn):
    conn.execute("INSERT INTO channels(id, name, language) VALUES(2,'sf','en')")
    conn.commit()
    add_story(conn, "s1", "T1", "ready", channel_id=1)
    add_story(conn, "s2", "T2", "ready", channel_id=2)
    assert worker.unread_count(conn, 1) == 1
    assert worker.unread_count(conn, 2) == 1


# ---- the cycle ----

def test_cycle_heals_an_empty_queue_to_depth(conn, fake_pipeline):
    add_run(conn, ["One", "Two", "Three", "Four", "Five"])
    out = worker.cycle(conn, log=lambda *a: None)
    assert out["before"] == 0
    assert out["after"] == config.QUEUE_DEPTH
    assert len(out["acquired"]) == config.QUEUE_DEPTH  # exactly the shortfall
    assert fake_pipeline == out["acquired"]            # rendered in that order


def test_cycle_tops_up_only_the_shortfall(conn, fake_pipeline):
    add_story(conn, "have1", "Have One", "ready")
    add_story(conn, "have2", "Have Two", "ready")
    add_run(conn, ["One", "Two", "Three"])
    out = worker.cycle(conn, log=lambda *a: None)
    assert len(out["acquired"]) == 1
    assert out["after"] == 3


def test_cycle_is_a_noop_when_the_queue_is_healthy(conn, fake_pipeline):
    for i in range(3):
        add_story(conn, f"s{i}", f"T{i}", "ready")
    add_run(conn, ["One", "Two"])
    out = worker.cycle(conn, log=lambda *a: None)
    assert out["acquired"] == [] and out["rendered"] == []


def test_reading_stories_reopens_the_shortfall(conn, fake_pipeline):
    """TASKS Phase 5 gate: mark 2 read → one cycle returns to depth."""
    add_run(conn, ["One", "Two", "Three", "Four", "Five", "Six"])
    worker.cycle(conn, log=lambda *a: None)
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM stories WHERE status='ready' ORDER BY created_at")]
    for sid in ids[:2]:
        conn.execute("UPDATE stories SET status='read' WHERE id=?", (sid,))
    conn.commit()
    assert worker.unread_count(conn, 1) == 1

    out = worker.cycle(conn, log=lambda *a: None)
    assert out["after"] == config.QUEUE_DEPTH
    assert len(out["acquired"]) == 2


def test_no_title_ever_repeats_across_cycles(conn, fake_pipeline):
    """All-time dedup (R6): read and skipped stories are still history."""
    add_run(conn, ["One", "Two", "Three", "Four", "Five", "Six"])
    worker.cycle(conn, log=lambda *a: None)
    conn.execute("UPDATE stories SET status='read'")
    conn.commit()
    worker.cycle(conn, log=lambda *a: None)
    conn.execute("UPDATE stories SET status='skipped'")
    conn.commit()
    worker.cycle(conn, log=lambda *a: None)
    titles = [r["title"] for r in conn.execute("SELECT title FROM stories")]
    assert len(titles) == len(set(titles)) == 6


def test_pool_exhaustion_ends_the_cycle_without_spending(conn, fake_pipeline,
                                                        monkeypatch):
    """An empty pool is a message, never a silent paid curation call."""
    monkeypatch.setattr(
        ingest, "curate", None, raising=False)  # any curation use would explode
    add_run(conn, ["Only One"])
    logs = []
    out = worker.cycle(conn, log=logs.append)
    assert len(out["acquired"]) == 1
    assert out["after"] == 1  # short of depth, and that is fine
    assert any("pool exhausted" in m for m in logs)
    assert any("--build-pool" in m for m in logs)


def test_a_failing_candidate_does_not_wedge_the_queue(conn, fake_pipeline,
                                                      monkeypatch):
    real = ingest._fetch_clean

    def flaky(c):
        if c["title"] == "Two":
            raise fetch.FetchError("404")
        return real(c)

    monkeypatch.setattr(ingest, "_fetch_clean", flaky)
    add_run(conn, ["One", "Two", "Three", "Four"])
    out = worker.cycle(conn, log=lambda *a: None)
    assert out["after"] == config.QUEUE_DEPTH
    assert "Two" in out["skipped"]
    # its SOURCE is recorded as dead, so that reference is never retried...
    assert pool.ref_key("gutenberg", "1") in pool.failed_refs(conn)
    assert pool.pool_candidates(conn) == []
    # ...but the story stays available to a batch offering a working reference
    assert "Two" not in db.known_titles(conn)


def test_acquire_only_leaves_stories_queue_visible_unrendered(conn, fake_pipeline):
    """DESIGN §7: stories reach the queue at text_ready, before render cost."""
    add_run(conn, ["One", "Two", "Three"])
    out = worker.cycle(conn, log=lambda *a: None, acquire_only=True)
    assert len(out["acquired"]) == 3
    assert out["rendered"] == [] and fake_pipeline == []
    statuses = {r["status"] for r in conn.execute("SELECT status FROM stories")}
    assert statuses == {"text_ready"}
    assert worker.pending_renders(conn, 1) == out["acquired"]


def test_skip_between_acquire_and_render_costs_no_render(conn, fake_pipeline):
    add_run(conn, ["One", "Two", "Three"])
    worker.cycle(conn, log=lambda *a: None, acquire_only=True)
    victim = worker.pending_renders(conn, 1)[1]
    conn.execute("UPDATE stories SET status='skipped' WHERE id=?", (victim,))
    conn.commit()
    worker.cycle(conn, log=lambda *a: None)
    assert victim not in fake_pipeline  # never rendered


def test_worker_targets_the_active_channel_only(conn, fake_pipeline):
    """Switching channels re-targets replenishment (DESIGN §7)."""
    conn.execute("INSERT INTO channels(id, name, language, is_active) "
                 "VALUES(2,'sf','en',0)")
    conn.commit()
    add_run(conn, ["Horror One", "Horror Two", "Horror Three"], channel_id=1)
    add_run(conn, ["SF One", "SF Two", "SF Three"], channel_id=2)

    worker.cycle(conn, log=lambda *a: None)
    assert {r["title"] for r in conn.execute("SELECT title FROM stories")} \
        == {"Horror One", "Horror Two", "Horror Three"}

    conn.execute("UPDATE channels SET is_active=(id=2)")
    conn.commit()
    out = worker.cycle(conn, log=lambda *a: None)
    assert out["channel"] == "sf"
    assert {r["title"] for r in conn.execute(
        "SELECT title FROM stories WHERE channel_id=2")} \
        == {"SF One", "SF Two", "SF Three"}


# ---- reference vs. story failures (Entry 24) ----

def test_unfetchable_reference_is_skipped_without_a_history_row(conn, fake_pipeline):
    """A curator metadata gap must not blacklist a real story forever."""
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, candidates_json) "
        "VALUES(1,'m',?)",
        (json.dumps([
            {"title": "Erich Zann", "source_class": "gutenberg",
             "source_ref": "unknown", "license_class": "pd", "language": "en"},
            {"title": "Good One", "source_class": "gutenberg",
             "source_ref": "42", "license_class": "pd", "language": "en"}]),))
    conn.commit()
    out = worker.cycle(conn, log=lambda *a: None)
    assert out["acquired"] and "Erich Zann" not in db.known_titles(conn)
    # still offered by the pool, so a later batch with a real id can get it
    assert any(c["title"] == "Erich Zann" for c in pool.pool_candidates(conn))


def test_a_failed_ref_is_never_retried_but_its_title_stays_available(conn):
    """Entry-16 lesson kept (no re-proposing the 550 KB collection ebook) with
    the Entry-24 fix (the story itself is not lost)."""
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_ref, source_url, license_class, language, status, failure_note) "
        "VALUES('s1',1,'k1','The Yellow Sign','gutenberg','8492',"
        "'gutenberg:8492','pd','en','failed','collection volume')")
    conn.commit()
    add_run(conn, [])
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, candidates_json) "
        "VALUES(1,'m',?)",
        (json.dumps([
            {"title": "The Yellow Sign", "source_class": "gutenberg",
             "source_ref": "8492", "license_class": "pd", "language": "en"},
            {"title": "The Yellow Sign", "source_class": "gutenberg",
             "source_ref": "6883", "license_class": "pd", "language": "en"}]),))
    conn.commit()

    refs = [c["source_ref"] for c in pool.pool_candidates(conn)]
    assert "8492" not in refs   # the dead reference is never retried
    assert "6883" in refs       # a standalone edition of the same story is fine
    assert "The Yellow Sign" not in db.known_titles(conn)
