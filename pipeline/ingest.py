"""Orchestrator: one curator candidate → a complete library entry.
Status walk (DESIGN §3): queued → fetching → text_ready → ready, or failed with
failure_note — failures never wedge the loop, rows are never deleted.

Tagging is NON-fatal: tags are the Phase 6 enhancement, synthesis is the
expensive part — a tag-call failure logs a warning and the story proceeds
untagged (re-taggable later via tag.run_tagging)."""
import datetime
import json
import re
import urllib.parse

from . import config, db, fetch, synthesize, tag, textproc
from .models import OffsetsManifest, StoryMeta


class DuplicateStory(Exception):
    pass


def paragraph_floor(source_class: str) -> int:
    """HTML-derived sources keep the chrome-stripping floor; plain-text sources
    keep every paragraph (Yellow Wallpaper lesson)."""
    return config.MIN_PARAGRAPH_CHARS if source_class in config.HTML_SOURCE_CLASSES else 0


def _fetch_clean(candidate: dict) -> tuple[list[str], str, str]:
    """fetch + clean + validate → (paragraphs, canonical_text, source_url)."""
    raw, source_url = fetch.fetch_candidate(candidate)
    paragraphs = textproc.split_paragraphs(raw, paragraph_floor(candidate["source_class"]))
    text = "\n\n".join(paragraphs)
    problem = textproc.story_length_problem(
        text, config.MIN_STORY_CHARS, config.MAX_STORY_CHARS)
    if problem:
        raise fetch.FetchError(problem)
    return paragraphs, text, source_url


def _finalize(conn, sid: str, key: str, candidate: dict, language: str,
              paragraphs: list[str], text: str, source_url: str,
              voice_override: str | None = None) -> None:
    """Everything after the stories row exists: files, tags, audio, ready."""
    title = candidate["title"]
    author = candidate.get("author")

    story_dir = config.LIBRARY_DIR / sid
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "story.txt").write_text(text)
    db.set_status(conn, sid, "text_ready")
    print(f"[ingest] {sid}: text_ready ({len(paragraphs)} paras, {len(text)} chars)")

    try:
        tag.run_tagging(conn, sid, title, author, language, text)
    except Exception as e:
        print(f"[ingest] WARNING: tagging failed ({e}) — continuing untagged")

    if voice_override is None:
        # honor a queue-window voice pick (AMENDMENT_04 D1) made after this
        # row hit text_ready — re-read at the last moment before synthesis
        r = conn.execute("SELECT voice FROM stories WHERE id=?", (sid,)).fetchone()
        voice_override = stored_voice_override(r["voice"] if r else None, language)
    # the gallery voice this render is committed to; language default when None
    render_target = voice_override or config.TTS_BY_LANGUAGE.get(
        language, config.FALLBACK_TTS)[1]

    def abort_meanwhile():
        row = conn.execute("SELECT status, voice FROM stories WHERE id=?",
                           (sid,)).fetchone()
        if row is None or row["status"] in ("skipped", "read"):
            return True
        # AMENDMENT_05 C6: a NEW gallery voice stored mid-render aborts this
        # render; the picker spawns a fresh one with the chosen voice. Compares
        # gallery voices only, so an engine fallback (voice "onyx") never
        # self-aborts a legitimate degrade render.
        picked = stored_voice_override(row["voice"], language)
        return picked is not None and picked != render_target

    engine, voice, sr, durations = synthesize.synthesize_story(
        paragraphs, language, story_dir / "audio.m4a",
        voice_override=voice_override, should_abort=abort_meanwhile)
    offsets = OffsetsManifest(
        engine=engine, voice=voice, sample_rate=sr,
        paragraphs=textproc.build_offsets(paragraphs, durations))
    (story_dir / "offsets.json").write_text(offsets.encode())

    meta = StoryMeta(
        id=sid, dedup_key=key,
        title=title, source_class=candidate["source_class"],
        source_url=source_url, license_class=candidate["license_class"],
        language=language, author=author, year=candidate.get("year"),
        curation_evidence=candidate.get("evidence", []),
        tts_engine=engine, voice=voice,
        duration_s=round(sum(durations), 2), paragraph_count=len(paragraphs),
        created_at=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"))
    (story_dir / "meta.json").write_text(meta.encode())

    conn.execute(
        "UPDATE stories SET tts_engine=?, voice=?, duration_s=?, paragraph_count=? "
        "WHERE id=?",
        (engine, voice, meta.duration_s, meta.paragraph_count, sid))
    db.set_status(conn, sid, "ready")
    print(f"[ingest] {sid}: READY — {meta.duration_s / 60:.1f} min, {engine}/{voice}")


def ingest_candidate(conn, candidate: dict, channel) -> str:
    """Fresh candidate → library entry. Returns story_id.
    Raises DuplicateStory if the dedup key is already history."""
    language = candidate.get("language") or channel["language"]
    title = candidate["title"]

    sid = None
    try:
        paragraphs, text, source_url = _fetch_clean(candidate)
        key = textproc.dedup_key(title, text)
        if key in db.known_dedup_keys(conn):
            raise DuplicateStory(title)
        sid = textproc.story_id(key, title)

        author = candidate.get("author")
        year = candidate.get("year")
        conn.execute(
            "INSERT INTO stories(id, channel_id, dedup_key, title, author, "
            "author_present, year, year_present, source_class, source_url, "
            "license_class, language, curation_evidence_json, status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'fetching')",
            (sid, channel["id"], key, title, author, int(bool(author)),
             year, int(year is not None), candidate["source_class"], source_url,
             candidate["license_class"], language,
             json.dumps(candidate.get("evidence", []), ensure_ascii=False)))
        conn.commit()

        _finalize(conn, sid, key, candidate, language, paragraphs, text, source_url)
        return sid
    except DuplicateStory:
        raise
    except synthesize.AbortRender as e:
        print(f"[ingest] {sid}: render aborted ({e}) — status stays as marked")
        raise
    except Exception as e:
        if sid:
            db.set_status(conn, sid, "failed", failure_note=str(e)[:500])
        else:
            record_provisional(conn, candidate, channel, "failed", str(e)[:500])
        raise


def record_provisional(conn, candidate: dict, channel, status: str,
                       note: str | None = None) -> str:
    """Enter a candidate into history WITHOUT fetched text: rejected candidates
    (bad fetch, wrong length — gate-run lesson: the 550KB Poe collection would
    be re-proposed forever otherwise) and Grace's pre-extraction read/skip marks
    (AMENDMENT_04 B). Uses a provisional dedup key since no clean text exists."""
    import hashlib
    title = candidate["title"]
    basis = f"provisional|{textproc.normalize_ws(title).lower()}|" \
            f"{candidate.get('source_class', '')}:{candidate.get('source_ref', '')}"
    key = hashlib.sha1(basis.encode()).hexdigest()
    sid = textproc.story_id(key, title)
    conn.execute(
        "INSERT OR IGNORE INTO stories(id, channel_id, dedup_key, title, author, "
        "author_present, year, year_present, source_class, source_url, "
        "license_class, language, curation_evidence_json, status, failure_note) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, channel["id"], key, title,
         candidate.get("author"), int(bool(candidate.get("author"))),
         candidate.get("year"), int(candidate.get("year") is not None),
         candidate.get("source_class") or "other",
         f"{candidate.get('source_class', 'other')}:{candidate.get('source_ref', '')}",
         candidate.get("license_class") or "modern_private",
         candidate.get("language") or channel["language"],
         json.dumps(candidate.get("evidence", []), ensure_ascii=False),
         status, note))
    conn.commit()
    return sid


def candidate_from_row(row) -> dict:
    """Reconstruct a curator candidate from a stories row (everything needed is
    stored — provenance rule pays off). source_ref is derived from source_url."""
    sc = row["source_class"]
    if sc == "gutenberg":
        m = re.search(r"\d+", row["source_url"])
        ref = m.group() if m else ""
    elif sc == "creepypasta":
        ref = urllib.parse.unquote(
            row["source_url"].rsplit("/wiki/", 1)[-1]).replace("_", " ")
    else:
        ref = row["source_url"]
    return {"title": row["title"], "author": row["author"], "year": row["year"],
            "source_class": sc, "source_ref": ref,
            "license_class": row["license_class"], "language": row["language"],
            "evidence": json.loads(row["curation_evidence_json"] or "[]")}


def stored_voice_override(voice: str | None, language: str) -> str | None:
    """A voice already chosen on the row (queue-window picker on a text_ready
    story, AMENDMENT_04 D, or a prior render's voice) is honored on retry —
    but only gallery (primary-engine) voices qualify: a stored fallback voice
    like "onyx" must not silently re-route a $0 retry onto paid OpenAI."""
    return voice if voice in config.VOICE_OPTIONS.get(language, []) else None


def retry_story(conn, sid: str, voice_override: str | None = None) -> str:
    """Re-run fetch→clean→tag→synthesize for an existing (typically failed)
    story row, updating it in place — no new curation spend. Also the voice
    re-render path (AMENDMENT_04 D): retry --voice <v> on a ready story. The
    dedup key is recomputed (clean rules may have changed) and updated on the
    same row."""
    row = conn.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise ValueError(f"no story {sid}")
    voice_override = voice_override or stored_voice_override(
        row["voice"], row["language"])
    candidate = candidate_from_row(row)
    try:
        db.set_status(conn, sid, "fetching")
        paragraphs, text, source_url = _fetch_clean(candidate)
        key = textproc.dedup_key(row["title"], text)
        dup = conn.execute("SELECT id FROM stories WHERE dedup_key=? AND id<>?",
                           (key, sid)).fetchone()
        if dup:
            raise fetch.FetchError(
                f"re-cleaned text duplicates existing story {dup['id']}")
        conn.execute("UPDATE stories SET dedup_key=?, source_url=? WHERE id=?",
                     (key, source_url, sid))
        conn.commit()
        _finalize(conn, sid, key, candidate, row["language"], paragraphs, text,
                  source_url, voice_override=voice_override)
        if row["status"] == "read":
            # a voice re-render of a finished story must NOT resurrect it as
            # unread — _finalize's walk ends at 'ready', so restore history
            db.set_status(conn, sid, "read")
        return sid
    except synthesize.AbortRender:
        raise
    except Exception as e:
        db.set_status(conn, sid, "failed", failure_note=str(e)[:500])
        raise
