# DESIGN — horror_readaloud

> **STATUS: DRAFT v0.1 (2026-07-18) — NOT FROZEN.** Freezes only on Grace's sign-off
> recorded in JOURNAL. After freezing, changes happen via amendment docs + journal line.
> Authority once frozen: below BRIEF_VERBATIM.md + amendments, above everything else.

## 1. Architecture

Two processes on Grace's Mac, sharing one SQLite database (WAL mode) and one library
directory:

- **App server** (`app/`): FastAPI. Serves the REST API, the built React PWA as static
  files, and story audio with HTTP range support (verified mechanism, probe 5). Binds the
  Mac's Tailscale IP only — never `0.0.0.0`.
- **Pipeline worker** (`pipeline/`): replenishment loop. When the active channel's unread
  count < 5: curate → dedup → fetch → clean → tag → synthesize until back to 5. Runs as a
  separate process (launchd/manual per RUNBOOK); failures mark the story `failed` and
  continue, never wedge the loop.

All state in SQLite + `data/library/`. No cloud storage, no external services beyond the
curation/tagging LLM calls and optional OpenAI TTS fallback.

## 2. Disk layout

```
data/
  app.db                      # SQLite (WAL)
  library/<story_id>/
    story.txt                 # clean text; paragraphs separated by blank lines
    meta.json                 # StoryMeta (round-trip tested)
    audio.m4a                 # concatenated narration, 64k AAC (wav interim deleted)
    offsets.json              # paragraph offsets manifest (round-trip tested)
  interim/                    # scratch; disposable at any time
```

`story_id` = first 12 hex chars of the dedup key (probe 4: sha1 of normalized title +
first 500 normalized chars) + `-` + a short title slug for human readability.

## 3. SQLite schema

Schema checklist applied (bank): LLM-extracted fields **nullable** with `_present` flags,
**provenance URL on every story**, controlled tag vocabulary with **verbatim labels
kept**, append-only history.

```sql
channels(
  id INTEGER PK, name TEXT UNIQUE, is_active INTEGER,        -- exactly one active
  genre TEXT, language TEXT NOT NULL DEFAULT 'en',
  topics_json TEXT, era TEXT, exclusions_json TEXT,          -- all criteria nullable
  extra_criteria TEXT,                                       -- free-text escape hatch
  created_at TEXT, updated_at TEXT
)
-- Default row = the horror brief. Reputation bar is channel-independent (lives in the
-- curation prompt template, not per-channel). Nothing outside this row says "horror".

stories(
  id TEXT PK, channel_id INTEGER REFERENCES channels,
  dedup_key TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL, author TEXT, author_present INTEGER,
  year INTEGER, year_present INTEGER,                        -- LLM-extracted → nullable
  source_class TEXT NOT NULL,                                -- gutenberg|creepypasta|nosleep|other
  source_url TEXT NOT NULL,                                  -- provenance, always
  license_class TEXT NOT NULL,                               -- pd|modern_private
  curation_evidence_json TEXT,                               -- named lists/essays/ratings
  status TEXT NOT NULL,                                      -- queued|fetching|ready|in_progress|read|failed
  tts_engine TEXT, voice TEXT, duration_s REAL, paragraph_count INTEGER,
  failure_note TEXT, created_at TEXT, ready_at TEXT
)
-- Rows are NEVER deleted: this table is the all-time history that guarantees
-- "no repeats" (R6). Curation candidates are dedup-checked against it before fetch.

tags(story_id TEXT REFERENCES stories, kind TEXT, value_verbatim TEXT, value_norm TEXT,
     PRIMARY KEY(story_id, kind, value_norm))
-- kind ∈ author|era|subgenre|theme|origin|language (controlled); value_norm from a
-- controlled vocabulary per kind; value_verbatim keeps the LLM's exact label.

progress(story_id TEXT PK REFERENCES stories, position_s REAL NOT NULL, updated_at TEXT)
-- Server-side resume (R6). On `ended`: row deleted + stories.status='read' —
-- end-of-file is NEVER stored as a resume point (probe 5 lesson, Entry 10).

bookmarks(id INTEGER PK, story_id TEXT REFERENCES stories, position_s REAL,
          note TEXT, created_at TEXT)

ratings(story_id TEXT PK REFERENCES stories, score INTEGER CHECK(score BETWEEN 1 AND 5),
        rated_at TEXT)

curation_runs(id INTEGER PK, channel_id INTEGER, model TEXT, cost_usd REAL,
              searches INTEGER, candidates_json TEXT, taste_profile_text TEXT,
              created_at TEXT)
-- Cost visibility (R11) + the before/after diff evidence Phase 6's gate needs.
```

## 4. Offsets manifest (text↔audio sync, R8)

```json
{ "version": 1, "engine": "kokoro", "voice": "af_heart", "sample_rate": 24000,
  "paragraphs": [ { "i": 0, "char_start": 0, "char_end": 812,
                    "t_start_s": 0.0, "t_end_s": 31.4 }, ... ] }
```

Offsets are exact by construction (butt-join concat, probe 2; seams inaudible per
Grace's verdict). Player maps `timeupdate` → binary search on `t_start_s` → highlight
paragraph. Serialization gets a `decode(encode(x)) == x` round-trip test day one.

## 5. Pipeline stages

- **curate** — Messages API + web_search against: standing reputation bar (many named
  recommenders, video essays, ratings — channel-independent) + active channel criteria +
  taste profile (Phase 6+). Returns candidates with named evidence, PD/modern
  classification, and honest unverified flags (verified at fetch). **Cost levers from
  probe 3** ($1.65/batch at Opus is over budget): default model `claude-sonnet-5`,
  max ~6 searches, batch of 8, criteria cached in the prompt. Target ≤$0.40/batch,
  measured via curation_runs; escalate model only if candidate quality disappoints.
- **fetch** — per source_class:
  - gutenberg: `/cache/epub/<id>/pg<id>.txt`, strip `*** START/END ***` (10/10 probe 4).
  - creepypasta: MediaWiki `action=parse` + HTML strip; MUST validate min length and
    detect deleted/redirect pages (probe 4 findings).
  - nosleep: **Reddit OAuth script app** (recommended decision §9.2) — anonymous JSON is
    dead (probe 4). Until the app exists, the NoSleep source class is disabled and
    curation is told not to propose it.
- **clean** — strip boilerplate; **unwrap hard-wrapped lines within paragraphs**
  (probe 1b — mandatory, Gutenberg wraps at ~70 cols and wrapped lines cause chunk-break
  pauses); collapse whitespace; blank-line paragraph segmentation; min-length sanity.
- **tag** — one cheap Claude call (Haiku-class) at ingest (~$0.01, R10 feasibility):
  controlled-vocab tags per kind + verbatim labels; missing values stay NULL with
  `_present=0`.
- **synthesize** — Kokoro per paragraph (6.9x realtime, probe 1) → butt-join concat →
  `afconvert` to 64k AAC m4a → offsets manifest. Per-story OpenAI TTS fallback
  (`gpt-4o-mini-tts`, ~$0.32/30-min story, probe 6) recorded in `tts_engine`.
  Non-English: Kokoro Spanish confirmed; **CJK deferred** — rerun probe 1 with
  misaki[ja]/[zh] before designing any CJK channel (standing risk note).

## 6. Server + player (Phase 4 scope)

API: `GET /api/stories` (library list + status), `GET /api/stories/{id}` (meta + text +
offsets), `GET /api/stories/{id}/audio` (range-capable), `GET|PUT /api/progress/{id}`,
`PUT /api/ratings/{id}`, bookmarks CRUD, channels CRUD + activate (Phase 5).

Player: library list, play/pause, ±15 s, scrubber, story select, text view, speed
selector 0.75–2x (R13 — iOS honors playbackRate, probe 5), Media Session metadata.

**iOS rules (probe 5, binding):**
1. Resume seeks apply on `loadedmetadata` or later — never at page init.
2. `ended` ⇒ clear progress row + mark read — never resume to end-of-file.
3. Progress saved server-side on pause/visibility-change + every ~5 s while playing;
   saves suppressed until a pending resume has applied.
4. Skip = ±15 s via Media Session handlers; lock-screen icon may cosmetically show
   "10s" (Apple default) — accepted, revisit with `details.seekOffset` only if it grates.

## 7. Queue + worker (Phase 5 scope)

**Queue semantics (recommended, resolves the open decision): 5 unread for the ACTIVE
channel only.** Switching channels re-targets replenishment to the new channel; other
channels' unread stories stay in the library but don't count. Rationale: matches the
brief's single-queue mental model, avoids N× curation cost per inactive channel.

Worker cycle: check unread(active) < 5 → curate batch → dedup against all-time stories
table → fetch/clean/tag/synthesize each until healed. Pure logic (replenishment decision,
dedup) takes `now` and DB state as parameters — unit-tested from day one.

## 8. Preference adaptation (Phase 6 scope)

Ratings aggregate per (kind, value_norm): avg score + count. Taste profile rendered as a
short text block ("liked: cosmic-dread (4.7/5, n=3)... disliked: gore (1.5/5, n=2)")
injected into the curation prompt and stored on curation_runs for the gate's
before/after diff. Trends screen reads the same aggregation.

## 9. Decisions resolved by this design (Grace confirms at sign-off)

1. **Queue semantics:** 5-per-active-channel (§7). Alternative rejected: global 5 mixes
   channels unpredictably; 5-per-every-channel multiplies cost.
2. **Reddit/NoSleep:** OAuth script app — free, 100 QPM, robust. Needs Grace to create
   the app at reddit.com/prefs/apps (~5 min, runbook step, Phase 3). Fallback rejected:
   old.reddit HTML parsing is fragile. NoSleep disabled until the app exists.
3. **Curation model:** Sonnet with capped searches, target ≤$0.40/batch (§5); Opus only
   if quality disappoints on real batches.
4. **Offline PWA audio caching:** OUT of MVP (negative spec); revisit after Phase 4 if
   Tailscale-only listening ever chafes.

## 10. What This Is Not (negative spec)

- No accounts, auth, or multi-user anything — Tailscale is the entire perimeter; the
  server never binds beyond the Tailscale interface.
- No public deployment of content, ever; no story text/audio in git; `data/` never
  committed. Modern web fiction stays private personal use.
- No recommendation engine beyond ratings-weighted curation; no ML training.
- No cloud storage; no analytics/telemetry; no per-listen API calls — audio is
  synthesized once and cached forever (R11).
- No social features, sharing, or comments.
- No offline audio caching in MVP (§9.4). No CJK channels before the CJK probe rerun.
- No paid TTS as primary — OpenAI is per-story fallback only.
- No API keys in frontend code or responses, ever.

## 11. Requirements traceability (Phase 2 gate condition)

| Req | Design element |
|---|---|
| R1 curation | §5 curate + reputation bar + curation_evidence_json |
| R2 clean text | §5 fetch/clean; story.txt |
| R3 narration | §5 synthesize (Kokoro primary, OpenAI fallback) |
| R4 queue of 5 | §7 worker |
| R5 mobile+laptop | §1 Tailscale binding + §6 PWA (probe-5-proven mechanism) |
| R6 resume/history/no-repeats | §3 progress + append-only stories + dedup_key |
| R7 Spotify-like controls | §6 player |
| R8 synced text | §4 offsets + §7 highlight |
| R9 bookmarks | §3 bookmarks + §6 API |
| R10 preference adaptation | §8 |
| R11 economical | §5 cost levers, tag-at-ingest ~$0.01, synth-once cache, SQLite-local reads, curation_runs cost ledger |
| R12 channels | §3 channels + §7 re-targeting + Phase 5 editor UI |
| R13 speed control | §6 player (iOS-verified, probe 5) |

Deferrals: offline caching (§9.4, nice-to-have) · CJK channels (risk note, §5) ·
sustained ≥5-min backgrounding evidence (re-proven by Phase 4 gate itself).
