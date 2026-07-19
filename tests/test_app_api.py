"""Phase 4 API tests: range serving (the probe-5 mechanism), progress + the
binding iOS ended/skip semantics, ratings/bookmarks round-trips, voice picker
transitions (AMENDMENT_04 D). Runs on a temp DB + temp library; the re-render
runner is injected so no test spawns a real render."""
import json

import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from pipeline import db

AUDIO_BYTES = bytes(range(256)) * 4  # fake m4a — range math doesn't care


@pytest.fixture()
def env(tmp_path):
    db_path = tmp_path / "app.db"
    library = tmp_path / "library"
    samples = tmp_path / "voice_samples"
    conn = db.connect(db_path)

    def add_story(sid, status, duration=100.0, language="en", voice="af_heart"):
        conn.execute(
            "INSERT INTO stories(id, channel_id, dedup_key, title, author, "
            "source_class, source_url, license_class, language, status, "
            "tts_engine, voice, duration_s, paragraph_count) "
            "VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, f"key-{sid}", f"Title {sid}", "Author", "gutenberg",
             "https://example.org", "pd", language, status,
             "kokoro" if status in ("ready", "in_progress", "read") else None,
             voice if status in ("ready", "in_progress", "read") else None,
             duration if status in ("ready", "in_progress", "read") else None,
             3))
        conn.commit()
        d = library / sid
        d.mkdir(parents=True)
        if status in ("text_ready", "ready", "in_progress", "read"):
            (d / "story.txt").write_text("Para one.\n\nPara two.\n\nPara three.")
        if status in ("ready", "in_progress", "read"):
            (d / "audio.m4a").write_bytes(AUDIO_BYTES)
            (d / "offsets.json").write_text(json.dumps(
                {"version": 1, "engine": "kokoro", "voice": voice,
                 "sample_rate": 24000,
                 "paragraphs": [
                     {"i": 0, "char_start": 0, "char_end": 9,
                      "t_start_s": 0.0, "t_end_s": 30.0},
                     {"i": 1, "char_start": 11, "char_end": 20,
                      "t_start_s": 30.0, "t_end_s": 60.0},
                     {"i": 2, "char_start": 22, "char_end": 33,
                      "t_start_s": 60.0, "t_end_s": 100.0}]}))
        return sid

    add_story("s1-ready", "ready")
    add_story("s2-text", "text_ready")
    rerenders = []
    app = create_app(db_path=db_path, library_dir=library, samples_dir=samples,
                     rerender_runner=lambda sid, v: rerenders.append((sid, v)))
    client = TestClient(app)
    return type("Env", (), dict(client=client, conn=conn, add=add_story,
                                rerenders=rerenders, samples=samples))


def status_of(env, sid):
    return env.conn.execute("SELECT status FROM stories WHERE id=?",
                            (sid,)).fetchone()["status"]


# ---- library + audio ----

def test_list_stories(env):
    r = env.client.get("/api/stories")
    assert r.status_code == 200
    body = r.json()
    assert body["queue_depth"] == 3
    by_id = {s["id"]: s for s in body["stories"]}
    assert by_id["s1-ready"]["status"] == "ready"
    assert by_id["s1-ready"]["duration_s"] == 100.0
    assert by_id["s2-text"]["voice"] is None


def test_detail_has_text_offsets_bookmarks(env):
    r = env.client.get("/api/stories/s1-ready")
    assert r.status_code == 200
    d = r.json()
    assert d["paragraphs"] == ["Para one.", "Para two.", "Para three."]
    assert len(d["offsets"]["paragraphs"]) == 3
    assert d["bookmarks"] == []


def test_detail_text_ready_has_no_offsets(env):
    d = env.client.get("/api/stories/s2-text").json()
    assert d["paragraphs"] is not None
    assert d["offsets"] is None


def test_missing_story_404(env):
    assert env.client.get("/api/stories/nope").status_code == 404
    assert env.client.get("/api/stories/nope/audio").status_code == 404


def test_audio_full_and_range(env):
    r = env.client.get("/api/stories/s1-ready/audio")
    assert r.status_code == 200
    assert r.content == AUDIO_BYTES
    # the probe-5 mechanism: iOS seeking requires 206 partial content
    r = env.client.get("/api/stories/s1-ready/audio",
                       headers={"Range": "bytes=100-199"})
    assert r.status_code == 206
    assert r.content == AUDIO_BYTES[100:200]
    assert r.headers["content-range"] == f"bytes 100-199/{len(AUDIO_BYTES)}"


def test_audio_404_before_ready(env):
    assert env.client.get("/api/stories/s2-text/audio").status_code == 404


# ---- progress + iOS rules ----

def test_progress_roundtrip_and_in_progress_transition(env):
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] is None
    r = env.client.put("/api/progress/s1-ready", json={"position_s": 42.5})
    assert r.json()["position_s"] == 42.5
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] == 42.5
    assert status_of(env, "s1-ready") == "in_progress"


def test_progress_clamps_negative_and_past_end(env):
    r = env.client.put("/api/progress/s1-ready", json={"position_s": -3})
    assert r.json()["position_s"] == 0.0
    # never persist end-of-file as a resume point (iOS rule 2, Entry 10)
    r = env.client.put("/api/progress/s1-ready", json={"position_s": 100.0})
    assert r.json()["position_s"] == 99.0


def test_ended_clears_progress_and_marks_read(env):
    env.client.put("/api/progress/s1-ready", json={"position_s": 90})
    r = env.client.post("/api/stories/s1-ready/ended")
    assert r.json()["status"] == "read"
    assert status_of(env, "s1-ready") == "read"
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] is None


def test_skip_is_permanent_and_clears_progress(env):
    env.client.put("/api/progress/s1-ready", json={"position_s": 10})
    assert env.client.post("/api/stories/s1-ready/skip").json()["status"] == "skipped"
    assert status_of(env, "s1-ready") == "skipped"
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] is None
    # a read story is history, not skippable
    env.add("s3-read", "read")
    assert env.client.post("/api/stories/s3-read/skip").status_code == 409


# ---- ratings + bookmarks ----

def test_rating_upsert_and_bounds(env):
    assert env.client.put("/api/ratings/s1-ready", json={"score": 4}).status_code == 200
    assert env.client.put("/api/ratings/s1-ready", json={"score": 2}).status_code == 200
    row = env.conn.execute("SELECT score FROM ratings WHERE story_id='s1-ready'").fetchone()
    assert row["score"] == 2
    assert env.client.put("/api/ratings/s1-ready", json={"score": 6}).status_code == 422
    assert env.client.put("/api/ratings/s1-ready", json={"score": 0}).status_code == 422


def test_bookmarks_crud(env):
    bid = env.client.post("/api/stories/s1-ready/bookmarks",
                          json={"position_s": 33.3, "note": "creepy bit"}).json()["id"]
    marks = env.client.get("/api/stories/s1-ready").json()["bookmarks"]
    assert [(m["position_s"], m["note"]) for m in marks] == [(33.3, "creepy bit")]
    assert env.client.delete(f"/api/bookmarks/{bid}").status_code == 200
    assert env.client.get("/api/stories/s1-ready").json()["bookmarks"] == []
    assert env.client.delete(f"/api/bookmarks/{bid}").status_code == 404


# ---- voices (AMENDMENT_04 D) ----

def test_voices_listing_marks_default_and_missing_samples(env):
    langs = env.client.get("/api/voices").json()["languages"]
    en = {v["voice"]: v for v in langs["en"]}
    assert en["af_heart"]["default"] is True
    assert en["af_bella"]["default"] is False
    assert en["af_heart"]["sample_url"] is None  # not rendered in this env


def test_voice_sample_served_when_rendered(env):
    env.samples.mkdir(parents=True)
    (env.samples / "af_bella.m4a").write_bytes(b"sample")
    assert env.client.get("/api/voices/af_bella/sample").content == b"sample"
    assert env.client.get("/api/voices/af_heart/sample").status_code == 404
    assert env.client.get("/api/voices/..%2Fescape/sample").status_code == 404


def test_voice_pick_on_text_ready_stores_and_spawns_render(env):
    # AMENDMENT_05 C6: the pick kicks a render; an in-flight one aborts on the
    # voice mismatch pipeline-side and this fresh one takes over
    r = env.client.post("/api/stories/s2-text/voice", json={"voice": "am_michael"})
    assert r.json() == {"voice": "am_michael", "rerender": True}
    row = env.conn.execute("SELECT voice FROM stories WHERE id='s2-text'").fetchone()
    assert row["voice"] == "am_michael"
    assert env.rerenders == [("s2-text", "am_michael")]


def test_read_endpoint_marks_read_and_clears_progress(env):
    env.client.put("/api/progress/s1-ready", json={"position_s": 10})
    r = env.client.post("/api/stories/s1-ready/read")
    assert r.json()["status"] == "read"
    assert status_of(env, "s1-ready") == "read"
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] is None


def test_progress_save_noop_on_read_story(env):
    # late keepalive save racing /ended must not resurrect a resume point
    env.client.post("/api/stories/s1-ready/ended")
    r = env.client.put("/api/progress/s1-ready", json={"position_s": 95})
    assert r.json() == {"position_s": None, "stored": False}
    assert env.client.get("/api/progress/s1-ready").json()["position_s"] is None


def test_unskip_restores_status_from_artifacts(env):
    # ready story (audio on disk) -> skipped -> unskip -> ready again
    env.client.post("/api/stories/s1-ready/skip")
    assert env.client.post("/api/stories/s1-ready/unskip").json()["status"] == "ready"
    # text-only story -> text_ready
    env.client.post("/api/stories/s2-text/skip")
    assert env.client.post("/api/stories/s2-text/unskip").json()["status"] == "text_ready"
    # provisional row with no artifacts -> failed (retryable), note set
    env.add("s5-prov", "queued")
    import shutil
    shutil.rmtree(env.samples.parent / "library" / "s5-prov")
    env.client.post("/api/stories/s5-prov/skip")
    assert env.client.post("/api/stories/s5-prov/unskip").json()["status"] == "failed"
    # unskip of a non-skipped story is a 409
    assert env.client.post("/api/stories/s1-ready/unskip").status_code == 409


def test_voice_change_on_ready_triggers_rerender(env):
    r = env.client.post("/api/stories/s1-ready/voice", json={"voice": "bf_emma"})
    assert r.json() == {"voice": "bf_emma", "rerender": True}
    assert env.rerenders == [("s1-ready", "bf_emma")]
    # same voice again is a no-op, not a render
    env.rerenders.clear()
    env.conn.execute("UPDATE stories SET voice='bf_emma' WHERE id='s1-ready'")
    env.conn.commit()
    r = env.client.post("/api/stories/s1-ready/voice", json={"voice": "bf_emma"})
    assert r.json()["rerender"] is False
    assert env.rerenders == []


def test_voice_rejected_for_wrong_language_or_status(env):
    assert env.client.post("/api/stories/s1-ready/voice",
                           json={"voice": "zh-CN-YunxiNeural"}).status_code == 422
    env.add("s4-failed", "failed")
    assert env.client.post("/api/stories/s4-failed/voice",
                           json={"voice": "af_bella"}).status_code == 409


# ---- AMENDMENT_05 A/B + rating clear ----

def test_settings_roundtrip_and_validation(env):
    s = env.client.get("/api/settings").json()
    assert s["curation_model"] == "claude-sonnet-5"  # config default
    assert s["default_voices"]["en"] == "af_heart"
    assert s["quality_notice"] is None  # too few decided stories
    s = env.client.put("/api/settings", json={
        "curation_model": "claude-haiku-4-5-20251001",
        "default_voices": {"en": "bf_emma"}}).json()
    assert s["curation_model"] == "claude-haiku-4-5-20251001"
    assert s["default_voices"]["en"] == "bf_emma"
    assert env.client.put("/api/settings",
                          json={"curation_model": "gpt-99"}).status_code == 422
    assert env.client.put("/api/settings",
                          json={"default_voices": {"en": "onyx"}}).status_code == 422


def test_quality_notice_on_high_skip_rate(env):
    for i in range(4):
        env.add(f"s-skip{i}", "ready")
        env.client.post(f"/api/stories/s-skip{i}/skip")
    env.add("s-ok", "ready")
    notice = env.client.get("/api/settings").json()["quality_notice"]
    assert notice is not None and "skipped" in notice


def test_clear_rating(env):
    env.client.put("/api/ratings/s1-ready", json={"score": 5})
    assert env.client.delete("/api/ratings/s1-ready").json()["score"] is None
    assert env.conn.execute(
        "SELECT 1 FROM ratings WHERE story_id='s1-ready'").fetchone() is None
