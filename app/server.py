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
import sqlite3
import subprocess
import sys

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline import config, curate, db, renderjob, sources, taste, worker
from pipeline.models import OffsetsManifest, StoryMeta

# Settings copy for the curation modes. Kept beside the API rather than in the
# frontend so the cost figures and the coverage answer have ONE source — the
# Entry-29 UI hardcoded its two descriptions in JSX and they went stale the
# moment a third mode existed.
CURATION_MODE_LABELS = {
    "free": ("free — $0", "Builds the pool from every free source covering "
             "this channel, ranked by each source's own reputation metadata. "
             "No model call at all, and references come from the sources as "
             "fields so they are never guessed wrong. What it lacks is taste: "
             "within a source's recognised set the ordering is arbitrary, so "
             "expect obscure work beside the canon. Because there is no model "
             "call, this mode CANNOT use your ratings — nothing here reads "
             "the taste profile."),
    "free_llm": ("free sources + AI picks — ~$0.03", "Same free sources, but "
                 "the model chooses from the shortlist they produce. It picks "
                 "by index, so it cannot invent a reference — and with no web "
                 "search a batch costs a few cents. It cannot reach beyond the "
                 "sources listed below. Your ratings steer the picks (Trends)."),
    "llm": ("AI web search — ~$0.75", "Paid curation with web search: the only "
            "mode that can reach beyond the free sources, verifying reputation "
            "against named lists it finds live. Its weak point is the "
            "reference, which it can still get wrong, and cost scales with "
            "batch size (3 searches per candidate). Your ratings steer the "
            "search and the picks (Trends)."),
}


def curation_mode_info(conn) -> list[dict]:
    """Per-mode label/description plus, for the free modes, which registered
    sources cover the ACTIVE channel and which do not and why.

    Coverage needs a channel, but Settings must render WITHOUT one — it is where
    you would go to fix a broken install, so a missing active channel has to
    degrade to "modes without coverage" rather than 500 the whole screen."""
    try:
        channel = db.active_channel(conn)
    except Exception:
        channel = None
    if channel is None:
        return [{"mode": m, "available": True, "sources": [],
                 "label": CURATION_MODE_LABELS.get(m, (m, ""))[0],
                 "description": CURATION_MODE_LABELS.get(m, (m, ""))[1]}
                for m in db.CURATION_MODES]

    covering, skipped = sources.for_channel(channel)
    src_info = ([{"name": s.name, "covers": True, "reason": s.covers(channel)[1]}
                 for s in covering]
                + [{"name": s.name, "covers": False, "reason": why}
                   for s, why in skipped])
    out = []
    for mode in db.CURATION_MODES:
        label, desc = CURATION_MODE_LABELS.get(mode, (mode, ""))
        entry = {"mode": mode, "label": label, "description": desc}
        if mode in ("free", "free_llm"):
            entry["sources"] = src_info
            entry["available"] = bool(covering)
        else:
            entry["available"] = True
        out.append(entry)
    return out

FRONTEND_DIST = config.ROOT / "app" / "frontend" / "dist"

STORY_LIST_SQL = """
SELECT s.id, s.title, s.author, s.year, s.status, s.language, s.source_class,
       s.source_url, s.license_class, s.tts_engine, s.voice, s.duration_s,
       s.paragraph_count, s.created_at, s.ready_at, s.failure_note,
       s.curation_evidence_json,
       p.position_s, p.updated_at AS progress_updated_at, r.score AS rating
FROM stories s
LEFT JOIN progress p ON p.story_id = s.id
LEFT JOIN ratings  r ON r.story_id = s.id
ORDER BY s.rowid
"""  # acquisition order = queue + autoplay order (db.ACQUISITION_ORDER)


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

    def _mark_read(sid: str):
        c = conn()
        story_or_404(c, sid)
        c.execute("DELETE FROM progress WHERE story_id=?", (sid,))
        c.execute("UPDATE stories SET status='read' WHERE id=?", (sid,))
        c.commit()
        return {"status": "read"}

    @app.post("/api/stories/{sid}/ended")
    def story_ended(sid: str):
        """iOS rule 2 (binding): on `ended`, clear the progress row + mark
        read — end-of-file is never a resume point."""
        return _mark_read(sid)

    @app.post("/api/stories/{sid}/read")
    def story_read(sid: str):
        """AMENDMENT_05 C3: 'already read' from the skip menu — same semantics
        as ended, distinct intent (read ≠ dislike for Phase 6 adaptation)."""
        return _mark_read(sid)

    @app.post("/api/stories/{sid}/unskip")
    def story_unskip(sid: str):
        """AMENDMENT_05 C4 (misclick recovery): Grace's explicit revoke.
        Status is re-derived from artifacts, not remembered — the record on
        disk is the truth."""
        c = conn()
        row = story_or_404(c, sid)
        if row["status"] != "skipped":
            raise HTTPException(409, f"story is {row['status']}, not skipped")
        if (library_dir / sid / "audio.m4a").exists():
            new = "ready"
        elif (library_dir / sid / "story.txt").exists():
            new = "text_ready"
        else:
            new = "failed"  # never fetched (provisional row) — retryable
        c.execute("UPDATE stories SET status=?, failure_note=? WHERE id=?",
                  (new, "unskipped, needs refetch" if new == "failed" else None,
                   sid))
        c.commit()
        return {"status": new}

    @app.post("/api/stories/{sid}/skip")
    def story_skip(sid: str):
        """AMENDMENT_02: skip is permanent history (never re-proposed). Mid-
        render skips abort synthesis via the pipeline's checkpoint poll.
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

    @app.delete("/api/ratings/{sid}")
    def delete_rating(sid: str):
        """Misclick recovery for ratings (Grace, 2026-07-18, item 3)."""
        c = conn()
        story_or_404(c, sid)
        c.execute("DELETE FROM ratings WHERE story_id=?", (sid,))
        c.commit()
        return {"score": None}

    # ---- taste / trends (Phase 6, DESIGN §8) ----

    @app.get("/api/taste")
    def get_taste():
        """The Trends screen. Returns `taste.summary` for the ACTIVE channel,
        plus the profile text verbatim — the screen shows the same string the
        curation prompt is given, so 'what does the pipeline think I like' and
        'what was the model told' can never drift apart.

        `applies_to_curation` is stated because it is genuinely conditional:
        `free` mode makes no model call, so it has nowhere to put a profile.
        A trends screen that implied otherwise would be lying about the
        listener's ratings changing anything.
        """
        c = conn()
        try:
            channel = db.active_channel(c)
            channel_id, channel_name = channel["id"], channel["name"]
        except Exception:
            # Settings-style degradation (Entry 33): a broken channel must not
            # take out the screen that explains the library.
            channel_id, channel_name = None, None
        mode = db.effective_curation_mode(c)
        out = taste.summary(c, channel_id)
        out["channel"] = channel_name
        out["curation_mode"] = mode
        out["applies_to_curation"] = mode in ("free_llm", "llm")
        return out

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
            # queue-window picker (AMENDMENT_05 C6): store the choice, then
            # kick a render. If a render is already in flight it aborts at the
            # next paragraph on the voice mismatch (pipeline checkpoint) and
            # this fresh one takes over with the chosen voice.
            c.execute("UPDATE stories SET voice=? WHERE id=?", (voice, sid))
            c.commit()
            if voice != row["voice"]:
                rerender_runner(sid, voice)
            return {"voice": voice, "rerender": voice != row["voice"]}
        if row["status"] in ("ready", "in_progress", "read"):
            if voice == row["voice"]:
                return {"voice": voice, "rerender": False}
            rerender_runner(sid, voice)
            return {"voice": voice, "rerender": True}
        raise HTTPException(409,
                            f"story is {row['status']} — voice applies at "
                            "text_ready or after")

    # ---- channels (R12 / AMENDMENT_01: criteria editable in the UI) ----

    CHANNEL_FIELDS = ("name", "genre", "language", "era", "extra_criteria")
    CHANNEL_LIST_FIELDS = ("topics", "exclusions")  # stored as *_json

    def _channel_dict(c, row) -> dict:
        d = {k: row[k] for k in ("id", "name", "genre", "language", "era",
                                 "extra_criteria")}
        d["is_active"] = bool(row["is_active"])
        for f in CHANNEL_LIST_FIELDS:
            d[f] = curate.channel_list_field(row, f"{f}_json")
        d["unread"] = worker.unread_count(c, row["id"])
        return d

    @app.get("/api/channels")
    def list_channels():
        c = conn()
        return {"channels": [_channel_dict(c, r) for r in c.execute(
            "SELECT * FROM channels ORDER BY id")],
            "queue_depth": config.QUEUE_DEPTH,
            "languages": sorted(config.VOICE_OPTIONS)}

    def _validate(language: str | None, name: str | None):
        if language is not None and language not in config.VOICE_OPTIONS:
            raise HTTPException(
                422, f"language {language} has no TTS config "
                     f"(available: {sorted(config.VOICE_OPTIONS)})")
        if name is not None and not name.strip():
            raise HTTPException(422, "channel name cannot be empty")

    @app.post("/api/channels")
    def create_channel(body: dict = Body(...)):
        c = conn()
        _validate(body.get("language", "en"), body.get("name"))
        cols = {"name": body["name"].strip(),
                "genre": body.get("genre"),
                "language": body.get("language", "en"),
                "era": body.get("era"),
                "extra_criteria": body.get("extra_criteria"),
                "topics_json": json.dumps(body.get("topics") or []),
                "exclusions_json": json.dumps(body.get("exclusions") or [])}
        try:
            cur = c.execute(
                f"INSERT INTO channels({','.join(cols)}) "
                f"VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, f"channel {body['name']!r} already exists")
        c.commit()
        row = c.execute("SELECT * FROM channels WHERE id=?",
                        (cur.lastrowid,)).fetchone()
        return _channel_dict(c, row)

    @app.put("/api/channels/{cid}")
    def update_channel(cid: int, body: dict = Body(...)):
        c = conn()
        row = c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no channel {cid}")
        _validate(body.get("language"), body.get("name"))
        sets, args = [], []
        for f in CHANNEL_FIELDS:
            if f in body:
                sets.append(f"{f}=?")
                args.append(body[f].strip() if f == "name" else body[f])
        for f in CHANNEL_LIST_FIELDS:
            if f in body:
                sets.append(f"{f}_json=?")
                args.append(json.dumps(body[f] or []))
        if sets:
            sets.append("updated_at=datetime('now')")
            try:
                c.execute(f"UPDATE channels SET {','.join(sets)} WHERE id=?",
                          (*args, cid))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "another channel already has that name")
            c.commit()
        return _channel_dict(
            c, c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone())

    @app.post("/api/channels/{cid}/activate")
    def activate_channel(cid: int):
        """Switching channels re-targets replenishment (DESIGN §7). Other
        channels' unread stories stay in the library but stop counting toward
        the queue — nothing is deleted."""
        c = conn()
        if c.execute("SELECT 1 FROM channels WHERE id=?", (cid,)).fetchone() is None:
            raise HTTPException(404, f"no channel {cid}")
        c.execute("UPDATE channels SET is_active=(id=?)", (cid,))
        c.commit()
        return _channel_dict(
            c, c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone())

    # ---- render jobs (AMENDMENT_06: progress bar + pause/cancel) ----

    @app.get("/api/renders")
    def list_renders():
        """Active renders, newest walk state. Dead-process rows are reaped by
        renderjob.active(), so a bar on screen always means a live render."""
        c = conn()
        return {"renders": [j.as_dict() for j in renderjob.active(c)],
                "poll_ms": 2000}

    def _control(sid: str, control: str, expect_active: bool = True):
        c = conn()
        story_or_404(c, sid)
        job = renderjob.get(c, sid)
        if job is None or not renderjob.pid_alive(job.pid) or \
                job.state not in ("running", "paused"):
            raise HTTPException(409, f"no render in flight for {sid}")
        if expect_active:
            renderjob.set_control(c, sid, control)
        return renderjob.get(c, sid).as_dict()

    @app.post("/api/renders/{sid}/pause")
    def pause_render(sid: str):
        """Holds the render at the next paragraph boundary — the process stays
        alive with the TTS model loaded, so resume is immediate. Work already
        rendered is kept in memory; nothing is written until the last
        paragraph, so a pause costs nothing but time."""
        return _control(sid, "pause")

    @app.post("/api/renders/{sid}/resume")
    def resume_render(sid: str):
        return _control(sid, "run")

    @app.post("/api/renders/{sid}/cancel")
    def cancel_render(sid: str):
        """Stops the render and puts the story back exactly as it was — the
        existing audio is untouched (the m4a is written only after the final
        paragraph) and the pre-render status is restored by the pipeline."""
        return _control(sid, "cancel")

    # ---- settings (AMENDMENT_05 A, BINDING) ----

    @app.get("/api/settings")
    def get_settings():
        c = conn()
        # R14 quality notice: skip-rate over the most recent decided stories.
        # Never auto-switches anything — it only prompts Grace toward the
        # model setting (DESIGN §5 policy).
        recent = [r["status"] for r in c.execute(
            "SELECT status FROM stories "
            "WHERE status IN ('read','skipped','ready','in_progress') "
            "ORDER BY rowid DESC LIMIT 10")]  # most recent decisions
        skip_rate = (recent.count("skipped") / len(recent)) if recent else 0.0
        return {
            "curation_model": db.effective_curation_model(c),
            "curation_model_options": sorted(config.MODEL_PRICING),
            # Entry 29/32: how the pool is built. Grace's choice, never
            # automatic. The mode descriptions and the free-source coverage
            # come from the pipeline, not the frontend, so a channel that no
            # free source covers says so HERE rather than failing later at
            # build time (AMENDMENT_01: nothing outside the channel row assumes
            # horror).
            "curation_mode": db.effective_curation_mode(c),
            "curation_mode_options": list(db.CURATION_MODES),
            "curation_modes": curation_mode_info(c),
            "default_voices": {lang: db.effective_voice(c, lang)
                               for lang in config.VOICE_OPTIONS},
            "quality_notice": (
                f"{int(skip_rate * 100)}% of the last {len(recent)} stories "
                "were skipped — consider changing the curation model below."
                if skip_rate >= 0.5 and len(recent) >= 5 else None),
        }

    @app.put("/api/settings")
    def put_settings(curation_model: str | None = Body(default=None, embed=True),
                     curation_mode: str | None = Body(default=None, embed=True),
                     default_voices: dict[str, str] | None = Body(default=None,
                                                                  embed=True)):
        c = conn()
        if curation_mode is not None:
            if curation_mode not in db.CURATION_MODES:
                raise HTTPException(
                    422, f"unknown curation_mode {curation_mode} "
                         f"(expected one of {list(db.CURATION_MODES)})")
            db.set_setting(c, "curation_mode", curation_mode)
        if curation_model is not None:
            if curation_model not in config.MODEL_PRICING:
                raise HTTPException(422, f"unknown model {curation_model}")
            db.set_setting(c, "curation_model", curation_model)
        for lang, v in (default_voices or {}).items():
            if v not in config.VOICE_OPTIONS.get(lang, []):
                raise HTTPException(422, f"voice {v} not offered for {lang}")
            db.set_setting(c, f"default_voice.{lang}", v)
        return get_settings()

    # ---- PWA static (mounted last so /api keeps precedence) ----

    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True),
                  name="frontend")

    return app


app = create_app()
