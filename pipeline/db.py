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
  -- millisecond precision, not datetime('now'): acquisition order IS the queue
  -- and the autoplay order (DESIGN §7), and the worker acquires several
  -- stories inside one second. Writers pass this explicitly (NOW_MS) so
  -- existing DBs get the precision too — a DEFAULT would only reach new ones.
  created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
  ready_at TEXT
);

CREATE TABLE IF NOT EXISTS tags(
  story_id TEXT NOT NULL REFERENCES stories(id),
  kind TEXT NOT NULL,
  value_verbatim TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  PRIMARY KEY(story_id, kind, value_norm)
);

-- Manual taste steering (Phase 6, Grace's request Entry 35). Overrides sit ON
-- TOP of the computed aggregation and always win, because they are a stated
-- preference rather than inferred evidence. score NULL = suppress this tag from
-- the profile; a row with no matching computed tag is one Grace added herself.
-- Deleting the ROW reverts that tag to automatic.
CREATE TABLE IF NOT EXISTS taste_overrides(
  kind TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  score REAL,
  updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(kind, value_norm)
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
  created_at TEXT DEFAULT (datetime('now')),
  -- Token breakdown (Entry 28). Without these, "why did that batch cost $1.55?"
  -- can only be back-solved from the total, which is how the cache-read lever
  -- stayed invisible for two batches. Recorded so the next cost question is
  -- answered from data.
  input_tokens INTEGER,
  output_tokens INTEGER,
  cache_read_tokens INTEGER,
  cache_write_tokens INTEGER
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
    _migrate_curation_tokens(conn)
    _migrate_tag_value_norm(conn)
    return conn


def _migrate_curation_tokens(conn):
    """Entry 28: per-run token counts on curation_runs. Pre-migration rows keep
    NULL — the totals they recorded are still true, the breakdown just wasn't
    captured, and backfilling it would be inventing numbers."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(curation_runs)")}
    for col in ("input_tokens", "output_tokens", "cache_read_tokens",
                "cache_write_tokens"):
        if col not in cols:
            conn.execute(f"ALTER TABLE curation_runs ADD COLUMN {col} INTEGER")
    conn.commit()


def _migrate_tag_value_norm(conn):
    """Phase 6: re-derive uncontrolled tags' value_norm with the canonical
    normalizer (tag.free_value_norm).

    Rows written before that normalization existed kept spaces, so the SAME
    theme could sit in the table twice — "unreliable narrator" on one story and
    "unreliable-narrator" on another. Phase 6 aggregates on (kind, value_norm),
    which would have scored one theme as two, each with half its evidence.

    `author` is deliberately untouched: its value_norm is a lowercased name and
    spaces belong in it (tag.tag_rows). Only kinds the tagger free-texts are
    re-derived. UPDATE OR IGNORE + delete-the-leftover handles the case where a
    story already carries both spellings, since (story_id, kind, value_norm) is
    the primary key and the merge would otherwise raise.
    """
    stale = conn.execute(
        "SELECT rowid, kind, value_verbatim, value_norm FROM tags "
        "WHERE kind NOT IN ('author') AND value_norm LIKE '% %'").fetchall()
    if not stale:
        return
    from . import tag  # deferred: tag imports config, not db — no cycle either way
    fixed = 0
    for row in stale:
        new = tag.free_value_norm(row["value_verbatim"] or row["value_norm"])
        if new == row["value_norm"]:
            continue
        cur = conn.execute(
            "UPDATE OR IGNORE tags SET value_norm=? WHERE rowid=?",
            (new, row["rowid"]))
        if cur.rowcount == 0:  # that (story, kind, value_norm) already exists
            conn.execute("DELETE FROM tags WHERE rowid=?", (row["rowid"],))
        fixed += 1
    conn.commit()
    if fixed:
        print(f"[db] normalized {fixed} tag value_norm rows (Phase 6 migration)")


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


# Millisecond `now` on every stories INSERT — timestamps that can tell two
# acquisitions apart. Ordering does NOT depend on it (see ACQUISITION_ORDER).
NOW_MS = "strftime('%Y-%m-%d %H:%M:%f','now')"

# Acquisition order — the queue order, the autoplay order, and the worker's
# render order (DESIGN §7). The single copy of this ORDER BY.
#
# rowid, not created_at: the queue is a SEQUENCE, and a wall clock at any
# resolution ties when the worker acquires several stories quickly (it did, at
# both second and millisecond precision). SQLite's rowid is monotonic per
# insert, and `stories` is append-only all-time history (R6 — rows are never
# deleted), so no rowid is ever reused.
ACQUISITION_ORDER = "rowid"


def get_setting(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO settings(key, value, updated_at) "
        "VALUES(?,?,datetime('now')) ON CONFLICT(key) DO UPDATE "
        "SET value=excluded.value, updated_at=excluded.updated_at", (key, value))
    conn.commit()


# How the pool gets built (Entry 29, extended Entry 32). Grace's choice, never
# automatic. Cost figures are per batch of ~12 on 2026-07-28 pricing.
#
#   free     — every free source covering the channel (pipeline/sources.py),
#              ranked heuristically. $0, no model call at all.
#   free_llm — same free sources, but the model PICKS from the supplied list.
#              ~$0.03: no web search, and it cannot invent a reference because
#              it only chooses indices from candidates the pipeline found.
#   llm      — paid curation with web search. ~$0.75. The only mode that can
#              reach beyond the registered free sources.
CURATION_MODES = ("free", "free_llm", "llm")
# "catalog" was the Entry-29 name for what is now `free`, back when Gutenberg
# was the only free source. Mapped rather than migrated so an existing setting
# keeps working and means the same thing (Gutenberg still covers that channel).
CURATION_MODE_ALIASES = {"catalog": "free"}
DEFAULT_CURATION_MODE = "llm"


def effective_curation_mode(conn) -> str:
    """Grace's curation-mode setting, defaulting to the paid LLM path so this
    never silently changes what an existing install does."""
    mode = get_setting(conn, "curation_mode", DEFAULT_CURATION_MODE)
    mode = CURATION_MODE_ALIASES.get(mode, mode)
    return mode if mode in CURATION_MODES else DEFAULT_CURATION_MODE


def record_curation_run(conn, channel_id: int, model: str, cost_usd: float,
                        searches: int, candidates_json: str,
                        in_tok: int = 0, out_tok: int = 0,
                        cache_read: int = 0, cache_write: int = 0,
                        taste_profile_text: str | None = None) -> int:
    """The single copy of the R11 ledger write. Every pool build lands here —
    paid, free, and aborted alike — so 'what has curation cost' is always one
    query and a free build can never be mistaken for a missing row.

    `taste_profile_text` is the Phase-6 profile the run was actually given (""
    when none). Storing the profile ON the run is what makes the gate's
    before/after diff auditable later: the candidate list and the preferences
    that produced it stay in the same row (DESIGN §8)."""
    run_id = conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, "
        "candidates_json, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens, taste_profile_text) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (channel_id, model, round(cost_usd, 4), searches, candidates_json,
         in_tok, out_tok, cache_read, cache_write,
         taste_profile_text)).lastrowid
    conn.commit()
    return run_id


def update_curation_candidates(conn, run_id: int, candidates_json: str):
    conn.execute("UPDATE curation_runs SET candidates_json=? WHERE id=?",
                 (candidates_json, run_id))
    conn.commit()


def effective_curation_model(conn) -> str:
    """R14: Grace-selected model or the config constant — the single copy of
    this precedence (curate stage + settings UI both read it)."""
    return get_setting(conn, "curation_model", config.CURATION_MODEL)


# ---- settings-backed knobs (Entry 37) ----
# Each of these is the SINGLE copy of "what is this knob actually set to".
# Everything else — the worker loop, the budget check, the Settings screen —
# asks here rather than reading config, so there is exactly one place where a
# stored value beats a default, and a bad stored value can never crash a run.

def effective_worker_interval_s(conn) -> int:
    """Seconds between replenishment cycles. Re-read every cycle so a change in
    Settings applies on the next tick. Clamped at WORKER_INTERVAL_MIN_S: a
    hand-typed "10" would otherwise make the loop hot."""
    raw = get_setting(conn, "worker_interval_s")
    try:
        return max(config.WORKER_INTERVAL_MIN_S, int(float(raw)))
    except (TypeError, ValueError):
        return config.DEFAULT_WORKER_INTERVAL_S


def effective_backup_interval_s(conn) -> int:
    """Seconds between automatic DB snapshots taken by the running worker.
    0 disables them (the manual `python -m pipeline.backup` always works)."""
    raw = get_setting(conn, "backup_interval_s")
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return config.DEFAULT_BACKUP_INTERVAL_S


def effective_spend_cap(conn) -> tuple[float, str]:
    """(cap in USD, rolling period). A cap of 0 means unlimited — stored
    explicitly rather than as an absent row, so "I turned the cap off" and "I
    have never opened Settings" stay distinguishable."""
    raw = get_setting(conn, "spend_cap_usd")
    try:
        cap = max(0.0, float(raw))
    except (TypeError, ValueError):
        cap = config.DEFAULT_SPEND_CAP_USD
    period = get_setting(conn, "spend_cap_period", config.DEFAULT_SPEND_CAP_PERIOD)
    if period not in config.SPEND_CAP_PERIOD_DAYS:
        period = config.DEFAULT_SPEND_CAP_PERIOD
    return cap, period


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


# A title is "known" once we HAVE the story or Grace has DECIDED on it. A
# `failed` row means neither: it means the reference we were given did not
# yield the story (deleted wiki page, a collection ebook id, a missing id).
# Excluding those titles forever loses real stories to a metadata gap — the
# curator's bad ref for "The Music of Erich Zann" would have blacklisted a
# Lovecraft classic permanently (Entry 24). Failed REFS are still excluded
# (see pool.failed_refs), so nothing is ever retried against the same bad ref.
KNOWN_STATUSES = ("text_ready", "ready", "in_progress", "read", "skipped")


def known_titles(conn) -> list[str]:
    qs = ",".join("?" * len(KNOWN_STATUSES))
    return [r["title"] for r in conn.execute(
        f"SELECT title FROM stories WHERE status IN ({qs}) "
        f"ORDER BY {ACQUISITION_ORDER}", KNOWN_STATUSES)]


def set_status(conn, story_id: str, status: str, failure_note: str | None = None):
    conn.execute(
        "UPDATE stories SET status=?, failure_note=?, "
        "ready_at=CASE WHEN ?='ready' THEN datetime('now') ELSE ready_at END "
        "WHERE id=?",
        (status, failure_note, status, story_id))
    conn.commit()
