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


def connect(db_path=None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM channels LIMIT 1").fetchone():
        cols = ", ".join(DEFAULT_CHANNEL)
        qs = ", ".join("?" * len(DEFAULT_CHANNEL))
        conn.execute(f"INSERT INTO channels({cols}) VALUES({qs})",
                     tuple(DEFAULT_CHANNEL.values()))
        conn.commit()
    return conn


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
