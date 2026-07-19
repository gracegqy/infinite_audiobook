"""App server (DESIGN §1 + §6, Phase 4): FastAPI serving the REST API, story
audio with HTTP range support (probe-5-proven mechanism — Starlette FileResponse
answers Range with 206, asserted in tests), and the built React PWA as static
files. Binds the Mac's Tailscale interface only via scripts/serve.sh — never
0.0.0.0 (negative spec §10).

State lives in the pipeline's SQLite + data/library/ — this server owns no
second copy. iOS rules (§6, binding): the /ended endpoint clears the progress
row AND marks the story read, so end-of-file is never stored as a resume point;
progress saves are the client's job every ~5 s / on pause / visibility-change.
"""
import json
import subprocess
import sys

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline import config, db
from pipeline.models import OffsetsManifest, StoryMeta

FRONTEND_DIST = config.ROOT / "app" / "frontend" / "dist"

STORY_LIST_SQL = """
SELECT s.id, s.title, s.author, s.year, s.status, s.language, s.source_class,
       s.source_url, s.license_class, s.tts_engine, s.voice, s.duration_s,
       s.paragraph_count, s.created_at, s.ready_at, s.failure_note,
       s.curation_evidence_json,
       p.position_s, r.score AS rating
FROM stories s
LEFT JOIN progress p ON p.story_id = s.id
LEFT JOIN ratings  r ON r.story_id = s.id
ORDER BY s.created_at, s.id
"""


def default_rerender_runner(story_id: str, voice: str) -> None:
    """Spawn the $0 background re-render (AMENDMENT_04 D3) — detached, logged,
    never blocking playback of the existing audio."""
    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    log = (config.INTERIM_DIR / f"rerender_{story_id}.log").open("ab")
    subprocess.Popen(
        [sys.executable, "-m", "pipeline.retry", story_id, "--voice", voice],
        cwd=config.ROOT, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True)


def create_app(db_path=None, library_dir=None, samples_dir=None,
               rerender_runner=default_rerender_runner) -> FastAPI:
    """App factory — paths and the re-render runner are injectable so tests run
    against a temp DB/library and never spawn a real render."""
    library_dir = library_dir or config.LIBRARY_DIR
    samples_dir = samples_dir or config.VOICE_SAMPLES_DIR
    app = FastAPI(title="horror_readaloud")
    db.connect(db_path).close()  # schema + default channel, once

    def conn():
        # one fresh connection per request (schema skipped): SQLite objects
        # are thread-bound and uvicorn dispatches across threads; WAL keeps
        # cross-process reads/writes with the pipeline safe
        return db.connect(db_path, init=False)

    def story_or_404(c, sid: str):
        row = c.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no story {sid}")
        return row

    # ---- library ----

    @app.get("/api/stories")
    def list_stories():
        c = conn()
        out = []
        for r in c.execute(STORY_LIST_SQL):
            d = dict(r)
            d["evidence"] = json.loads(d.pop("curation_evidence_json") or "[]")
            out.append(d)
        return {"stories": out, "queue_depth": config.QUEUE_DEPTH}

    @app.get("/api/stories/{sid}")
    def story_detail(sid: str):
        c = conn()
        row = story_or_404(c, sid)
        d = dict(row)
        d["evidence"] = json.loads(d.pop("curation_evidence_json") or "[]")
        story_dir = library_dir / sid
        # files exist only from text_ready/ready on — null over crash
        d["paragraphs"] = None
        d["offsets"] = None
        txt = story_dir / "story.txt"
        if txt.exists():
            d["paragraphs"] = txt.read_text().split("\n\n")
        off = story_dir / "offsets.json"
        if off.exists():
            try:
                d["offsets"] = json.loads(
                    OffsetsManifest.decode(off.read_text()).encode())
            except (json.JSONDecodeError, TypeError) as e:
                d["offsets_error"] = f"unreadable offsets.json: {e}"
        meta = story_dir / "meta.json"
        if meta.exists():
            try:
                StoryMeta.decode(meta.read_text())
            except (json.JSONDecodeError, TypeError) as e:
                d["meta_error"] = f"unreadable meta.json: {e}"
        d["bookmarks"] = [dict(b) for b in c.execute(
            "SELECT id, position_s, note, created_at FROM bookmarks "
            "WHERE story_id=? ORDER BY position_s", (sid,))]
        return d

    @app.get("/api/stories/{sid}/audio")
    def story_audio(sid: str):
        c = conn()
        story_or_404(c, sid)
        path = library_dir / sid / "audio.m4a"
        if not path.exists():
            raise HTTPException(404, f"no audio for {sid}")
        return FileResponse(path, media_type="audio/mp4")

    # ---- progress (iOS rules §6) ----

    @app.get("/api/progress/{sid}")
    def get_progress(sid: str):
        c = conn()
        story_or_404(c, sid)
        row = c.execute("SELECT position_s, updated_at FROM progress "
                        "WHERE story_id=?", (sid,)).fetchone()
        return {"position_s": row["position_s"] if row else None,
                "updated_at": row["updated_at"] if row else None}

    @app.put("/api/progress/{sid}")
    def put_progress(sid: str, position_s: float = Body(embed=True)):
        c = conn()
        row = story_or_404(c, sid)
        if row["status"] in ("read", "skipped"):
            # a late keepalive save racing the /ended (or /skip) call must not
            # resurrect a resume point on finished history — the Entry-10
            # "resumed at end-of-file" symptom, via a request race
            return {"position_s": None, "stored": False}
        pos = max(0.0, float(position_s))
        # defensive server-side copy of iOS rule 2: never persist a position at
        # (or past) end-of-file — a finished story "resumed" at its end looks
        # like broken playback (probe 5, Entry 10). The client's `ended`
        # handler is primary; this clamp catches anything that slips through.
        if row["duration_s"]:
            pos = min(pos, max(0.0, row["duration_s"] - 1.0))
        c.execute("INSERT INTO progress(story_id, position_s, updated_at) "
                  "VALUES(?,?,datetime('now')) ON CONFLICT(story_id) DO UPDATE "
                  "SET position_s=excluded.position_s, "
                  "updated_at=excluded.updated_at", (sid, pos))
        if row["status"] == "ready":
            c.execute("UPDATE stories SET status='in_progress' WHERE id=?", (sid,))
        c.commit()
        return {"position_s": pos}

    @app.post("/api/stories/{sid}/ended")
    def story_ended(sid: str):
        """iOS rule 2 (binding): on `ended`, clear the progress row + mark
        read — end-of-file is never a resume point."""
        c = conn()
        story_or_404(c, sid)
        c.execute("DELETE FROM progress WHERE story_id=?", (sid,))
        c.execute("UPDATE stories SET status='read' WHERE id=?", (sid,))
        c.commit()
        return {"status": "read"}

    @app.post("/api/stories/{sid}/skip")
    def story_skip(sid: str):
        """AMENDMENT_02: skip is permanent history (never re-proposed). Mid-
        render skips abort synthesis via the pipeline's should_abort poll.
        Replenishment trigger arrives with the Phase 5 worker."""
        c = conn()
        row = story_or_404(c, sid)
        if row["status"] == "read":
            raise HTTPException(409, "story already read — not skippable")
        c.execute("DELETE FROM progress WHERE story_id=?", (sid,))
        c.execute("UPDATE stories SET status='skipped' WHERE id=?", (sid,))
        c.commit()
        return {"status": "skipped"}

    # ---- ratings + bookmarks ----

    @app.put("/api/ratings/{sid}")
    def put_rating(sid: str, score: int = Body(embed=True)):
        c = conn()
        story_or_404(c, sid)
        if not 1 <= int(score) <= 5:
            raise HTTPException(422, "score must be 1..5")
        c.execute("INSERT INTO ratings(story_id, score, rated_at) "
                  "VALUES(?,?,datetime('now')) ON CONFLICT(story_id) DO UPDATE "
                  "SET score=excluded.score, rated_at=excluded.rated_at",
                  (sid, int(score)))
        c.commit()
        return {"score": int(score)}

    @app.post("/api/stories/{sid}/bookmarks")
    def add_bookmark(sid: str, position_s: float = Body(embed=True),
                     note: str | None = Body(default=None, embed=True)):
        c = conn()
        story_or_404(c, sid)
        cur = c.execute("INSERT INTO bookmarks(story_id, position_s, note) "
                        "VALUES(?,?,?)", (sid, max(0.0, float(position_s)), note))
        c.commit()
        return {"id": cur.lastrowid}

    @app.delete("/api/bookmarks/{bid}")
    def delete_bookmark(bid: int):
        c = conn()
        cur = c.execute("DELETE FROM bookmarks WHERE id=?", (bid,))
        c.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"no bookmark {bid}")
        return {"deleted": bid}

    # ---- voices (AMENDMENT_04 D: gallery + picker + explicit re-render) ----

    @app.get("/api/voices")
    def voices():
        return {"languages": {
            lang: [{"voice": v,
                    "default": v == config.TTS_BY_LANGUAGE[lang][1],
                    "sample_url": (f"/api/voices/{v}/sample"
                                   if (samples_dir / f"{v}.m4a").exists()
                                   else None)}
                   for v in vs]
            for lang, vs in config.VOICE_OPTIONS.items()}}

    @app.get("/api/voices/{voice}/sample")
    def voice_sample(voice: str):
        # gallery voices only — the whitelist doubles as a traversal guard
        if not any(voice in vs for vs in config.VOICE_OPTIONS.values()):
            raise HTTPException(404, f"unknown voice {voice}")
        path = samples_dir / f"{voice}.m4a"
        if not path.exists():
            raise HTTPException(404,
                                f"sample for {voice} not rendered yet "
                                "(scripts/render_voice_samples.py)")
        return FileResponse(path, media_type="audio/mp4")

    @app.post("/api/stories/{sid}/voice")
    def set_voice(sid: str, voice: str = Body(embed=True)):
        c = conn()
        row = story_or_404(c, sid)
        if voice not in config.VOICE_OPTIONS.get(row["language"], []):
            raise HTTPException(422,
                                f"voice {voice} not offered for language "
                                f"{row['language']}")
        if row["status"] == "text_ready":
            # queue-window picker: chosen BEFORE synthesis; the render (worker
            # or retry) honors the stored voice
            c.execute("UPDATE stories SET voice=? WHERE id=?", (voice, sid))
            c.commit()
            return {"voice": voice, "rerender": False}
        if row["status"] in ("ready", "in_progress", "read"):
            if voice == row["voice"]:
                return {"voice": voice, "rerender": False}
            rerender_runner(sid, voice)
            return {"voice": voice, "rerender": True}
        raise HTTPException(409,
                            f"story is {row['status']} — voice applies at "
                            "text_ready or after")

    # ---- PWA static (mounted last so /api keeps precedence) ----

    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True),
                  name="frontend")

    return app


app = create_app()
