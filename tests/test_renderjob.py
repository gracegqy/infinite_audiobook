"""AMENDMENT_06: render progress + pause/cancel.

Pure logic (progress fraction, control→action, staleness) is tested without a
DB; the pause loop takes its sleep injected so nothing here waits on real time;
the cancel path is tested end-to-end through ingest.retry_story with a fake
engine, because the thing that actually matters is that a cancel leaves the
story exactly as it was."""
import numpy as np
import pytest

from fastapi.testclient import TestClient

from app.server import create_app
from pipeline import db, ingest, renderjob, synthesize


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def _insert(conn, sid, status, voice="af_heart"):
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, language, status, voice, duration_s, "
        "paragraph_count) VALUES(?,1,?,?,'gutenberg','https://example.org/x',"
        "'pd','en',?,?,60.0,3)",
        (sid, f"k-{sid}", f"T {sid}", status, voice))
    conn.commit()


# ---- pure logic ----

def test_progress_fraction_clamps_and_divides():
    assert renderjob.progress_fraction("synthesizing", 0, 4) == 0.0
    assert renderjob.progress_fraction("synthesizing", 2, 4) == 0.5
    assert renderjob.progress_fraction("synthesizing", 9, 4) == 1.0


def test_progress_fraction_is_none_when_not_measurable():
    # fetch is one HTTP GET of a whole story — an indeterminate bar is honest
    assert renderjob.progress_fraction("fetching", 0, None) is None
    assert renderjob.progress_fraction("tagging", 0, 12) is None
    assert renderjob.progress_fraction("encoding", 12, 12) is None
    assert renderjob.progress_fraction("synthesizing", 1, 0) is None


def test_action_for_control():
    assert renderjob.action_for("run") == "continue"
    assert renderjob.action_for("pause") == "wait"
    assert renderjob.action_for("cancel") == "cancel"


def test_is_stale_only_for_dead_active_jobs():
    assert renderjob.is_stale("running", pid_alive=False)
    assert renderjob.is_stale("paused", pid_alive=False)
    assert not renderjob.is_stale("running", pid_alive=True)
    assert not renderjob.is_stale("done", pid_alive=False)


def test_job_roundtrip():
    job = renderjob.RenderJob(
        story_id="sid", phase="synthesizing", control="run", state="running",
        paragraphs_done=3, paragraphs_total=12, voice="am_adam", pid=42,
        started_at="2026-07-27 10:00:00", updated_at="2026-07-27 10:01:00")
    assert renderjob.RenderJob.decode(job.encode()) == job


# ---- pause loop (clock injected) ----

def test_await_control_blocks_until_resumed(conn):
    _insert(conn, "sid-p", "ready")
    renderjob.open_job(conn, "sid-p")
    renderjob.set_control(conn, "sid-p", "pause")

    slept = []

    def sleep(s):
        slept.append(s)
        if len(slept) == 3:  # Grace hits resume after three polls
            renderjob.set_control(conn, "sid-p", "run")

    assert renderjob.await_control(conn, "sid-p", sleep=sleep) == "continue"
    assert len(slept) == 3
    # 'paused' is written once, not on every poll
    assert renderjob.get(conn, "sid-p").state == "paused"


def test_await_control_returns_cancel(conn):
    _insert(conn, "sid-c", "ready")
    renderjob.open_job(conn, "sid-c")
    renderjob.set_control(conn, "sid-c", "cancel")
    assert renderjob.await_control(conn, "sid-c", sleep=lambda s: None) == "cancel"


def test_reopening_clears_a_stale_cancel(conn):
    # a cancel left on the row must never kill the NEXT render
    _insert(conn, "sid-r", "ready")
    renderjob.open_job(conn, "sid-r")
    renderjob.set_control(conn, "sid-r", "cancel")
    renderjob.open_job(conn, "sid-r")
    assert renderjob.get(conn, "sid-r").control == "run"
    assert renderjob.get(conn, "sid-r").state == "running"


def test_active_reaps_dead_process_rows(conn):
    _insert(conn, "sid-dead", "ready")
    renderjob.open_job(conn, "sid-dead", pid=999999)  # not a live pid
    assert renderjob.active(conn) == []
    assert renderjob.get(conn, "sid-dead").state == "failed"


# ---- cancel through the real pipeline path ----

def _fake_engine_env(monkeypatch, tmp_path, on_render=None):
    calls = []

    class FakeEngine:
        name = "fake"

        def __init__(self, language, voice):
            self.voice = voice

        def render(self, p):
            calls.append(p)
            if on_render:
                on_render(len(calls))
            return np.zeros(2400, dtype=np.float32), 24000

    from pipeline import config
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path / "interim")
    monkeypatch.setattr(config, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setitem(synthesize.ENGINES, "kokoro", FakeEngine)
    monkeypatch.setitem(synthesize.ENGINES, "openai", FakeEngine)
    monkeypatch.setattr(
        ingest, "_fetch_clean",
        lambda cand: (["One.", "Two.", "Three."], "One.\n\nTwo.\n\nThree.",
                      "https://example.org/x"))
    return calls


def test_cancel_restores_prior_status_and_keeps_audio(monkeypatch, tmp_path, conn):
    """The whole point of cancel: the story is left exactly as it was. This is
    the Entry-21 stranding bug pre-empted — a cancelled re-render used to leave
    the row at 'fetching' and need a hand repair."""
    _insert(conn, "sid-x", "in_progress", voice="af_heart")
    calls = _fake_engine_env(
        monkeypatch, tmp_path,
        # Grace hits cancel while paragraph 1 is rendering
        on_render=lambda n: renderjob.set_control(conn, "sid-x", "cancel")
        if n == 1 else None)

    story_dir = tmp_path / "library" / "sid-x"
    story_dir.mkdir(parents=True)
    (story_dir / "audio.m4a").write_bytes(b"OLD-AUDIO")

    with pytest.raises(synthesize.AbortRender):
        ingest.retry_story(conn, "sid-x", voice_override="am_adam")

    assert calls == ["One."]  # stopped at the next paragraph boundary
    row = conn.execute("SELECT status, voice FROM stories WHERE id='sid-x'"
                       ).fetchone()
    assert row["status"] == "in_progress"   # restored, not stranded at 'fetching'
    assert row["voice"] == "af_heart"       # the new voice never landed
    assert (story_dir / "audio.m4a").read_bytes() == b"OLD-AUDIO"
    assert renderjob.get(conn, "sid-x").state == "cancelled"


def test_completed_render_marks_job_done_and_reports_full_progress(
        monkeypatch, tmp_path, conn):
    _insert(conn, "sid-ok", "ready", voice="af_heart")
    _fake_engine_env(monkeypatch, tmp_path)
    ingest.retry_story(conn, "sid-ok", voice_override="am_adam")
    job = renderjob.get(conn, "sid-ok")
    assert job.state == "done"
    assert (job.paragraphs_done, job.paragraphs_total) == (3, 3)
    assert renderjob.active(conn) == []


def test_automatic_skip_abort_does_not_restore_status(monkeypatch, tmp_path, conn):
    """AMENDMENT_04 C is unchanged by 06: a mid-render SKIP keeps the story
    skipped — only Grace's explicit cancel restores the prior status."""
    _insert(conn, "sid-s", "ready", voice="af_heart")
    _fake_engine_env(
        monkeypatch, tmp_path,
        on_render=lambda n: conn.execute(
            "UPDATE stories SET status='skipped' WHERE id='sid-s'").connection.commit()
        if n == 1 else None)
    with pytest.raises(synthesize.AbortRender):
        ingest.retry_story(conn, "sid-s", voice_override="am_adam")
    assert conn.execute("SELECT status FROM stories WHERE id='sid-s'"
                        ).fetchone()["status"] == "skipped"


# ---- API ----

@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "app.db"
    c = db.connect(db_path)
    _insert(c, "sid-api", "ready")
    app = create_app(db_path=db_path, library_dir=tmp_path / "library",
                     samples_dir=tmp_path / "samples",
                     rerender_runner=lambda sid, voice: None)
    return TestClient(app), c


def test_renders_endpoint_lists_live_job(client):
    tc, c = client
    assert tc.get("/api/renders").json()["renders"] == []
    renderjob.open_job(c, "sid-api", phase="synthesizing")
    renderjob.set_progress(c, "sid-api", 2, 8)
    (job,) = tc.get("/api/renders").json()["renders"]
    assert job["story_id"] == "sid-api"
    assert job["fraction"] == 0.25
    assert job["active"] is True


def test_pause_resume_cancel_set_control(client):
    tc, c = client
    renderjob.open_job(c, "sid-api", phase="synthesizing")
    assert tc.post("/api/renders/sid-api/pause").json()["control"] == "pause"
    assert tc.post("/api/renders/sid-api/resume").json()["control"] == "run"
    assert tc.post("/api/renders/sid-api/cancel").json()["control"] == "cancel"


def test_control_409s_when_no_render_in_flight(client):
    tc, _ = client
    assert tc.post("/api/renders/sid-api/pause").status_code == 409


def test_control_404s_for_unknown_story(client):
    tc, _ = client
    assert tc.post("/api/renders/nope/pause").status_code == 404
