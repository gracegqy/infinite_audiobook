# DESIGN — infinite_audiobook

> **STATUS: FROZEN v1.0 (2026-07-18)** — Grace signed off v0.3 in session ("I sign off
> DESIGN v0.3", JOURNAL Entry 15). Changes from here happen via amendment docs +
> journal line only. Authority: below BRIEF_VERBATIM.md + amendments, above everything
> else. History: v0.2 incorporated Grace's rulings on v0.1 §9 + AMENDMENT_02 (queue =
> 3 + skip) + AMENDMENT_03 (zh/fr multilingual scope); v0.3 added her probe-1c TTS
> verdicts: per-language engines, zh = edge-tts (verdict a, Entry 14). AMENDMENTS
> 02/03 became BINDING at this sign-off.

## 1. Architecture

Two processes on Grace's Mac, sharing one SQLite database (WAL mode) and one library
directory:

- **App server** (`app/`): FastAPI. Serves the REST API, the built React PWA as static
  files, and story audio with HTTP range support (verified mechanism, probe 5). Binds the
  Mac's Tailscale IP only — never `0.0.0.0`.
- **Pipeline worker** (`pipeline/`): replenishment loop. When the active channel's unread
  count < 3 (AMENDMENT_02): curate → dedup → fetch → clean → tag → synthesize until back
  to 3. Runs as a separate process (launchd/manual per RUNBOOK); failures mark the story
  `failed` and continue, never wedge the loop.

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
  source_class TEXT NOT NULL,                                -- gutenberg|creepypasta|nosleep|scp_cn|local_import|other
  source_url TEXT NOT NULL,                                  -- provenance, always (file:// for local_import)
  license_class TEXT NOT NULL,                               -- pd|modern_private|cc_by_sa
  language TEXT NOT NULL DEFAULT 'en',                       -- en|zh|fr (TTS-probe-gated)
  curation_evidence_json TEXT,                               -- named lists/essays/ratings
  status TEXT NOT NULL,                                      -- queued|fetching|text_ready|ready|in_progress|read|skipped|failed
  tts_engine TEXT, voice TEXT, duration_s REAL, paragraph_count INTEGER,
  failure_note TEXT, created_at TEXT, ready_at TEXT
)
-- Rows are NEVER deleted: this table is the all-time history that guarantees
-- "no repeats" (R6). Curation candidates are dedup-checked against it before fetch.
-- 'skipped' (AMENDMENT_02) is permanent history too — a skipped story is never
-- re-proposed, exactly like 'read'.

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
  taste profile (Phase 6+). Language-aware (AMENDMENT_03): zh channels search Chinese-web
  reputation signals (豆瓣 ratings, 知乎 threads, bilibili 解说 essays) — same mechanism.
  Returns candidates with named evidence, license classification, honest unverified
  flags. **Cost levers from probe 3** ($1.65/batch at Opus is over budget): model
  `claude-sonnet-5`, max ~6 searches, batch of 8, criteria cached in the prompt. Target
  ≤$0.40/batch, measured via curation_runs. **Model policy (Grace, 2026-07-18): never
  auto-escalate.** If quality consistently disappoints — trigger: skip-rate of recent
  batches over a threshold — the UI shows a notice prompting Grace to change the model
  in settings (§6); the choice is always hers.
- **fetch** — per source_class (AMENDMENT_03 tiers):
  - gutenberg: `/cache/epub/<id>/pg<id>.txt`, strip `*** START/END ***` (10/10 probe 4).
    Same fetcher covers zh/fr collections (聊斋志异, Maupassant) — near-zero extra work.
  - creepypasta: MediaWiki `action=parse` + HTML strip; MUST validate min length and
    detect deleted/redirect pages (probe 4 findings).
  - nosleep: **Reddit OAuth script app** (§9.2, approved) — anonymous JSON is dead
    (probe 4). Until the app exists, the source class is disabled and curation is told
    not to propose it.
  - scp_cn: wikidot fetcher for the CC BY-SA-licensed SCP-CN branch (oobmab et al.);
    attribution kept in meta. New fetcher, Phase 5+.
  - local_import: Grace drops legitimately-obtained .txt/.epub into a watched folder;
    pipeline runs clean→tag→synthesize. The lawful route to commercial authors
    (周德东-class) and translated Japanese fiction. **Scraping DRM'd platforms
    (微信读书 etc.) is declined — that's DRM circumvention, not scraping** (§10).
  - Tier B (probe before any design relies on them): X岛-successor boards, 知乎 columns.
- **clean** — strip boilerplate; **unwrap hard-wrapped lines within paragraphs**
  (probe 1b — mandatory, Gutenberg wraps at ~70 cols and wrapped lines cause chunk-break
  pauses); collapse whitespace; blank-line paragraph segmentation; min-length sanity.
- **tag** — one cheap Claude call (Haiku-class) at ingest (~$0.01, R10 feasibility):
  controlled-vocab tags per kind + verbatim labels; missing values stay NULL with
  `_present=0`.
- **synthesize** — per paragraph → butt-join concat → `afconvert` to 64k AAC m4a →
  offsets manifest. **Engine is per-language configuration** (Grace's probe-1c
  verdicts, Entries 13–14), recorded per story in `tts_engine`/`voice`:
  - **en**: Kokoro (passed, probe 1; 6.9x realtime).
  - **fr**: Kokoro `ff_siwis` (passed, probe 1c; 5.0x realtime).
  - **zh**: **edge-tts**, preferred voice `zh-CN-YunxiNeural` (Grace: Yunxi > Xiaoxiao;
    Kokoro zh failed her native ear). Accepted caveats, on record: each render is a
    cloud call to Microsoft's undocumented Edge endpoint (story text leaves the Mac —
    acceptable: story text is not personal data), and the endpoint can rate-limit or
    break — so synthesize must degrade gracefully: edge-tts failure → OpenAI TTS for
    that story (never block the queue on the endpoint). Offsets still come from
    per-paragraph renders (edge-tts returns per-call audio; concat math unchanged —
    mp3/AAC durations read via afinfo/soundfile, worth a unit test).
  - **ja**: untested; no ja channels (translated works arrive via local_import in zh/en).
  - Per-story fallback for every language: OpenAI TTS (`gpt-4o-mini-tts`,
    ~$0.32/30-min story, probe 6).

## 6. Server + player (Phase 4 scope)

API: `GET /api/stories` (library list + status), `GET /api/stories/{id}` (meta + text +
offsets), `GET /api/stories/{id}/audio` (range-capable), `GET|PUT /api/progress/{id}`,
`PUT /api/ratings/{id}`, bookmarks CRUD, channels CRUD + activate (Phase 5).

Player: queue view (autoplay order) + library list, play/pause, ±15 s, scrubber, story
select, **skip/remove button** (AMENDMENT_02 — marks `skipped`, triggers replenishment),
text view, speed selector 0.75–2x (R13 — iOS honors playbackRate, probe 5), Media
Session metadata. Settings: curation model selector + the §5 quality notice (R14 —
never auto-switched).

**iOS rules (probe 5, binding):**
1. Resume seeks apply on `loadedmetadata` or later — never at page init.
2. `ended` ⇒ clear progress row + mark read — never resume to end-of-file.
3. Progress saved server-side on pause/visibility-change + every ~5 s while playing;
   saves suppressed until a pending resume has applied.
4. Skip = ±15 s via Media Session handlers; lock-screen icon may cosmetically show
   "10s" (Apple default) — accepted, revisit with `details.seekOffset` only if it grates.

## 7. Queue + worker (Phase 5 scope)

**Queue semantics (AMENDMENT_02): 3 unread for the ACTIVE channel**, autoplayed in
acquisition order, every queued story selectable from a menu. Switching channels
re-targets replenishment; other channels' unread stories stay in the library but don't
count. **Skip** removes a story permanently (status `skipped`, counts as history for
no-repeats) and triggers immediate replenishment.

Stories appear in the queue (title/author/evidence, skippable) at `text_ready` —
before synthesis. The synthesis worker renders in queue order, so a skip before
rendering costs one fetch, not a ~4.5-min render; autoplay only advances to `ready`
stories. Skip-rate is also the §5 curation-quality signal.

Worker cycle: check unread(active) < 3 → curate batch → dedup against all-time stories
table → fetch/clean/tag each (queue-visible) → synthesize in order until healed. Pure
logic (replenishment decision, dedup, skip transitions) takes `now` and DB state as
parameters — unit-tested from day one.

## 8. Preference adaptation (Phase 6 scope)

Ratings aggregate per (kind, value_norm): avg score + count. Taste profile rendered as a
short text block ("liked: cosmic-dread (4.7/5, n=3)... disliked: gore (1.5/5, n=2)")
injected into the curation prompt and stored on curation_runs for the gate's
before/after diff. Trends screen reads the same aggregation.

Implemented in `pipeline/taste.py` (Entry 34). Four rules the paragraph above did not
specify, each because the naive reading is wrong:
- **Rank on a shrunk mean, display the raw one.** Ranking uses the average shrunk toward
  the listener's own global mean by `PRIOR_WEIGHT` pseudo-observations, so a lone 5 does
  not outrank a 4.5 over four stories; the figure SHOWN stays the raw avg + n as above.
- **A kind must vary to be reported.** A kind whose rated stories give it fewer than two
  distinct values (language, origin in a single-language channel) is dropped — it
  expresses no preference. Counted before the placeholder filter below.
- **Placeholders are not preferences.** `author: unknown` is dropped; other kinds keep
  "unknown" as a legitimate value.
- **A floor of `config.TASTE_MIN_RATED_STORIES` rated stories**, below which no profile
  is built. The prior is centred on the listener's own mean, so at n=1 every tag's shrunk
  mean equals it and one story would mark everything it touched as liked.

Known limit (Entry 34, gate not passed): the profile reaches the model but does not
measurably change picks, because candidate records carry almost none of the fields the
profile speaks in (all creepypasta candidates have no author, no year and two distinct
evidence strings) and `curate.apply_class_quotas` pins the axis the ratings are clearest
on. Any re-run of the gate MUST include a same-prompt control run — the first attempt
read as a pass until the control showed the diff was noise.

## 9. Decisions (Grace's rulings, 2026-07-18 — encoded in v0.2)

1. **Queue:** Grace's redesign adopted — 3-per-active-channel + autoplay in acquisition
   order + skip button (AMENDMENT_02, with the two accepted refinements: skips are
   permanent history; queue-visible at text_ready with synthesis in queue order).
2. **Reddit/NoSleep:** APPROVED — OAuth script app. Grace creates it at
   reddit.com/prefs/apps (~5 min, runbook step, Phase 3). NoSleep disabled until then.
3. **Curation model:** APPROVED — Sonnet, capped searches, ≤$0.40/batch target. Grace's
   condition encoded: no auto-escalation ever; sustained quality disappointment surfaces
   a UI notice pointing at the model setting (§5, §6).
4. **Offline PWA audio caching:** APPROVED — out of MVP.
5. **NEW (AMENDMENT_03):** en/zh/fr in scope, each TTS-probe-gated; source tiers incl.
   scp_cn + local_import; DRM'd platforms declined.
6. **zh TTS (Grace, 2026-07-18, "verdict a"):** edge-tts with `zh-CN-YunxiNeural`
   preferred (Yunxi > Xiaoxiao); cloud/unofficial-endpoint caveats accepted with
   OpenAI TTS as the per-story fallback. fr = Kokoro `ff_siwis` (passed). TTS is
   per-language config (§5).

## 10. What This Is Not (negative spec)

- No accounts, auth, or multi-user anything — Tailscale is the entire perimeter; the
  server never binds beyond the Tailscale interface.
- No public deployment of content, ever; no story text/audio in git; `data/` never
  committed. Modern web fiction stays private personal use.
- No recommendation engine beyond ratings-weighted curation; no ML training.
- No cloud storage; no analytics/telemetry; no per-listen API calls — audio is
  synthesized once and cached forever (R11).
- No social features, sharing, or comments.
- No offline audio caching in MVP (§9.4). No channel in a language without a passed
  TTS probe (ja currently; en/fr/zh passed — §5).
- No paid TTS as primary — OpenAI is per-story fallback only.
- No API keys in frontend code or responses, ever.
- **No DRM circumvention**: DRM'd reading platforms (微信读书 etc.) are never scraping
  targets; their content enters only via local_import of legitimately-obtained copies.
- No silent model changes: curation model switches are Grace-initiated only (§9.3).

## 11. Requirements traceability (Phase 2 gate condition)

| Req | Design element |
|---|---|
| R1 curation | §5 curate + reputation bar + curation_evidence_json |
| R2 clean text | §5 fetch/clean; story.txt |
| R3 narration | §5 synthesize (Kokoro primary, OpenAI fallback) |
| R4 queue (3, AMENDMENT_02) | §7 worker + skip semantics |
| R5 mobile+laptop | §1 Tailscale binding + §6 PWA (probe-5-proven mechanism) |
| R6 resume/history/no-repeats | §3 progress + append-only stories + dedup_key |
| R7 Spotify-like controls | §6 player |
| R8 synced text | §4 offsets + §7 highlight |
| R9 bookmarks | §3 bookmarks + §6 API |
| R10 preference adaptation | §8 |
| R11 economical | §5 cost levers, tag-at-ingest ~$0.01, synth-once cache, SQLite-local reads, curation_runs cost ledger |
| R12 channels | §3 channels + §7 re-targeting + Phase 5 editor UI |
| R13 speed control | §6 player (iOS-verified, probe 5) |
| R14 model selection UI + quality notice | §5 policy + §6 settings |
| R15 multilingual sources (zh/fr) | §5 fetch tiers + language gating (AMENDMENT_03) |

Deferrals: offline caching (§9.4, nice-to-have) · ja TTS untested (§5; zh/fr passed
probe 1c) · sustained ≥5-min backgrounding evidence (re-proven by Phase 4 gate
itself) · Tier-B sources (X岛-successors, 知乎) unprobed.
