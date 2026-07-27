"""SQLite schema (DESIGN §3, frozen v1.0) + connection helper. WAL mode; the
stories table is append-only all-time history — rows are never deleted (R6)."""
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0,
  genre TEXT,
  language TEXT NOT NULL DEFAULT 'en',
  topics_json TEXT,
  era TEXT,
  exclusions_json TEXT,
  extra_criteria TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stories(
  id TEXT PRIMARY KEY,
  channel_id INTEGER REFERENCES channels(id),
  dedup_key TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  author TEXT,
  author_present INTEGER NOT NULL DEFAULT 0,
  year INTEGER,
  year_present INTEGER NOT NULL DEFAULT 0,
  source_class TEXT NOT NULL,
  source_ref TEXT,
  source_url TEXT NOT NULL,
  license_class TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en',
  curation_evidence_json TEXT,
  status TEXT NOT NULL CHECK(status IN
    ('queued','fetching','text_ready','ready','in_progress','read','skipped','failed')),
  tts_engine TEXT,
  voice TEXT,
  duration_s REAL,
  paragraph_count INTEGER,
  failure_note TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  ready_at TEXT
);

CREATE TABLE IF NOT EXISTS tags(
  story_id TEXT NOT NULL REFERENCES stories(id),
  kind TEXT NOT NULL,
  value_verbatim TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  PRIMARY KEY(story_id, kind, value_norm)
);

CREATE TABLE IF NOT EXISTS progress(
  story_id TEXT PRIMARY KEY REFERENCES stories(id),
  position_s REAL NOT NULL,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookmarks(
  id INTEGER PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  position_s REAL NOT NULL,
  note TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ratings(
  story_id TEXT PRIMARY KEY REFERENCES stories(id),
  score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
  rated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS curation_runs(
  id INTEGER PRIMARY KEY,
  channel_id INTEGER REFERENCES channels(id),
  model TEXT NOT NULL,
  cost_usd REAL,
  searches INTEGER,
  candidates_json TEXT,
  taste_profile_text TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

-- AMENDMENT_05 A (BINDING 2026-07-18): one key-value row per setting.
-- Keys: curation_model (R14) · default_voice.<language> (voice half of
-- TTS_BY_LANGUAGE; the engine never changes via settings).
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- AMENDMENT_06 (BINDING 2026-07-27): render progress + pause/cancel control.
-- One row per story, rewritten on each new render. The pipeline writes
-- phase/progress and reads `control`; the server writes `control` and reads
-- progress (WAL makes the cross-process traffic safe). `restore_status` is the
-- status a cancel must put back — without it a cancelled re-render strands the
-- row mid-walk (the Entry-21 Damned Thing symptom, hand-repaired then).
CREATE TABLE IF NOT EXISTS render_jobs(
  story_id TEXT PRIMARY KEY REFERENCES stories(id),
  pid INTEGER,
  phase TEXT NOT NULL CHECK(phase IN
    ('fetching','tagging','synthesizing','encoding')),
  paragraphs_done INTEGER NOT NULL DEFAULT 0,
  paragraphs_total INTEGER,
  control TEXT NOT NULL DEFAULT 'run' CHECK(control IN ('run','pause','cancel')),
  state TEXT NOT NULL DEFAULT 'running' CHECK(state IN
    ('running','paused','done','cancelled','failed')),
  voice TEXT,
  restore_status TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""

# Default row = the horror brief. Nothing outside this row says "horror"
# (AMENDMENT_01).
DEFAULT_CHANNEL = dict(
    name="horror",
    is_active=1,
    genre="horror",
    language="en",
    extra_criteria=("Highly-reputed short horror fiction: public-domain classics "
                    "(gothic, cosmic, ghost) and modern web horror (creepypasta; "
                    "NoSleep once its fetcher exists). Reputation must be checkable — "
                    "named lists, essays, awards, ratings."),
)


def connect(db_path=None, init=True) -> sqlite3.Connection:
    """init=False skips schema creation + default-channel seeding — for
    callers opening many short-lived connections (the app server does one
    init=True at startup, then init=False per request)."""
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if not init:
        return conn
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM channels LIMIT 1").fetchone():
        cols = ", ".join(DEFAULT_CHANNEL)
        qs = ", ".join("?" * len(DEFAULT_CHANNEL))
        conn.execute(f"INSERT INTO channels({cols}) VALUES({qs})",
                     tuple(DEFAULT_CHANNEL.values()))
        conn.commit()
    _migrate_source_ref(conn)
    return conn


def _migrate_source_ref(conn):
    """AMENDMENT_05 B (BINDING 2026-07-18): stories.source_ref stored
    explicitly. One-time ALTER + backfill from source_url on pre-amendment
    rows (the reverse parse lives on only here, for that backfill)."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(stories)")]
    if "source_ref" in cols:
        return
    conn.execute("ALTER TABLE stories ADD COLUMN source_ref TEXT")
    from . import ingest  # deferred: ingest imports db
    for row in conn.execute(
            "SELECT id, source_class, source_url, title FROM stories").fetchall():
        conn.execute("UPDATE stories SET source_ref=? WHERE id=?",
                     (ingest.legacy_source_ref(row), row["id"]))
    conn.commit()


def get_setting(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO settings(key, value, updated_at) "
        "VALUES(?,?,datetime('now')) ON CONFLICT(key) DO UPDATE "
        "SET value=excluded.value, updated_at=excluded.updated_at", (key, value))
    conn.commit()


def effective_curation_model(conn) -> str:
    """R14: Grace-selected model or the config constant — the single copy of
    this precedence (curate stage + settings UI both read it)."""
    return get_setting(conn, "curation_model", config.CURATION_MODEL)


def effective_voice(conn, language: str) -> str | None:
    """AMENDMENT_05 A: per-language default voice override (gallery voices
    only), else the TTS_BY_LANGUAGE default. None for unknown languages."""
    v = get_setting(conn, f"default_voice.{language}")
    if v and v in config.VOICE_OPTIONS.get(language, []):
        return v
    engine_voice = config.TTS_BY_LANGUAGE.get(language)
    return engine_voice[1] if engine_voice else None


def active_channel(conn) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM channels WHERE is_active=1").fetchone()
    if row is None:
        raise RuntimeError("no active channel")
    return row


def known_dedup_keys(conn) -> set[str]:
    return {r["dedup_key"] for r in conn.execute("SELECT dedup_key FROM stories")}


def known_titles(conn) -> list[str]:
    return [r["title"] for r in
            conn.execute("SELECT title FROM stories ORDER BY created_at")]


def set_status(conn, story_id: str, status: str, failure_note: str | None = None):
    conn.execute(
        "UPDATE stories SET status=?, failure_note=?, "
        "ready_at=CASE WHEN ?='ready' THEN datetime('now') ELSE ready_at END "
        "WHERE id=?",
        (status, failure_note, status, story_id))
    conn.commit()
