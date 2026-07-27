# JOURNAL — horror_readaloud (append-only; corrections are new entries, never edits)

## Entry 1 — 2026-07-18 — Project scaffolded

Decisions (from Grace's brief + interview, verbatim in docs/BRIEF_VERBATIM.md):
- **Sourcing:** public-domain classics + modern web horror, strictly private-use; content
  never publicly deployed, never committed to git.
- **TTS:** Kokoro locally as primary (free), OpenAI TTS as per-story fallback. Plan:
  per-paragraph synthesis + concatenation so chunk offsets give text↔audio sync for free.
  Both are Phase 1 probe subjects, not yet verified facts.
- **Hosting:** FastAPI + SQLite on Grace's Mac, React+Vite PWA frontend, phone access via
  Tailscale. $0/mo target; only LLM-curation pennies and optional fallback TTS cost money.
- **Preference adaptation (brief item 4) assessed feasible and cheap:** Claude tags each
  story at ingest (~$0.01), ratings aggregate per tag in SQLite, curation prompt receives
  the taste profile. No ML training, no measurable UI latency.
- Governance: lean app stack (CLAUDE/STATE/JOURNAL/TASKS + REQUIREMENTS traceability)
  per CLAUDE_BANK 09; brief is feature-dense enough to warrant the requirements table.

Trigger/reasoning: fresh scaffold from `~/Code/_META_working_knowledge/claude_bank/` (pre-rename: `*META_working_knowledge/new_proj_claude_bank/`)
(00_GENERATOR + 09_SCAFFOLDER), interview answers in BRIEF_VERBATIM.md §Interview.

Measurements invalidated by this change: none (nothing measured yet).

## Entry 2 — 2026-07-18 — Spec amendment: customizable channels

Grace asked mid-scaffold whether the pipeline could be a customizable scraper
(genre/language/topic editable in the UI) instead of horror-specific. Assessed at ~10–15%
extra work since curation was already criteria-driven LLM work; accepted. Encoded as the
**channel** abstraction (docs/AMENDMENT_01_customizable_channels.md): editable criteria
record in SQLite, default channel = the horror brief, no "horror" hardcoding outside that
config row. Accepted costs: genre-specific fetchers added incrementally; non-English
Kokoro quality added to Phase 1 probes.

Measurements invalidated by this change: none (nothing measured yet).

## Entry 3 — 2026-07-18 — Resume session: Phase 0 evidence re-verified; stopped at review gate

Re-derived every checked Phase 0 gate item from artifacts rather than trusting prose:
- `git log` shows 0f138ca (+ 3d772d5, 1d7cf34); `git status` clean, `## main...origin/main`
  in sync.
- `git check-ignore -v` matches both `data/library/x.mp3` (rule `data/`) and `.env`.
- Remote private re-proven: authenticated `git ls-remote` returns heads while
  unauthenticated `GET api.github.com/repos/gracegqy/horror_readaloud` → HTTP 404.
- Smoke re-run: python3 3.12.12, node v25.8.1 (match Entry-1-era records).

No work started past the gate: the only open Phase 0 item is Grace's review of STATE.md +
CLAUDE.md, and Phase 1 probes sit behind it. Session ends with the review handed to Grace.

Measurements invalidated by this change: none (verification only; nothing changed).

## Entry 4 — 2026-07-18 — Phase 0 closed: Grace approved STATE.md + CLAUDE.md review

Grace gave "Phase 0 review approved" in session. That was the last open gate item; every
other item was re-verified from artifacts the same day (Entry 3). Phase 0 → DONE. Current
phase is now Phase 1 (pre-design probes), starting with Kokoro install/quality per STATE
next actions.

Measurements invalidated by this change: none.

## Entry 5 — 2026-07-18 — Phase 1 probes: 3 answered, 3 blocked on Grace-side inputs

Ran probes per TASKS §1 (throwaway scripts in pre_design_probes/, full evidence in
probe_results.txt). Key results:
- Kokoro installs clean and runs 6.9x realtime on this Mac; 2.5-min horror sample +
  male-voice + Spanish samples rendered for Grace's listening test.
- Chunked synthesis offsets exact by construction AND verified by an independent
  silence/speech energy check (6/6 offsets OK) — text↔audio sync architecture holds.
- Curation signal confirmed: named checkable lists exist for both classic and NoSleep
  channels; 3 candidates spot-checked (Monkey's Paw PD/PG12122, Yellow Wallpaper
  PD/PG1952, Borrasca modern) with correct PD/modern classification.
- Fetch+clean: Gutenberg 10/10; creepypasta wiki 8/10 (fetcher must validate empty/
  deleted pages); Reddit anonymous JSON API is dead (403 everywhere) — HTML works,
  OAuth app is the robust path. Decision deferred to Phase 2 design.
- NEW FACT contradicting the brief's assumption: Tailscale is not installed on this
  Mac. Probe 5 (and later the Phase 4 gate) blocked until Grace installs it on Mac +
  iPhone. Test page + range-verified FastAPI server are ready (206 partial content
  confirmed on localhost).
- API keys not yet in .env (Grace obtained them mid-session; told her the format).
  probe3_curation_api.py and probe6_openai_tts.py are one-command runs once keys land.
- Deferred with risk note: Kokoro CJK quality (needs misaki[ja]/[zh]) — retest before
  designing any CJK channel.

Measurements invalidated by this change: none (first measurements of the project).

## Entry 6 — 2026-07-18 — Pause bug root-caused; speed-control requirement added; keys in; Tailscale live

- Grace reported random mid-sentence pauses in all probe audio. Root cause found and
  verified (probe1b_pause_fix.py): probe scripts fed Kokoro hard-line-wrapped text and
  KPipeline splits chunks on newlines — 27 chunks for the Usher passage, one padded
  boundary per wrapped line. Fixed by whitespace normalization (chunks 27→7; remaining
  ≥500ms gaps verified punctuation/sentence-aligned). Promoted to design constraint:
  the pipeline clean stage must unwrap hard-wrapped lines within paragraphs
  (Gutenberg wraps at ~70 cols).
- SCOPE ADDITION (Grace, in-session): playback speed control in the player. Added as
  R13 in REQUIREMENTS.md; probe5 test page now exercises audio.playbackRate on iOS.
- .env created by Grace with both keys (names verified, file confirmed gitignored).
  Probe 6 ANSWERED: gpt-4o-mini-tts render succeeded, $0.004/paragraph, ~$0.32/30-min
  story. Probe 3 API run in flight.
- Tailscale installed by Grace on Mac + iPhone; Mac IP 100.117.147.107. Blank-page
  report explained: server wasn't running. Server now up on that IP, page 200 +
  range 206 verified from the Mac.

Measurements invalidated by this change: probe-1 speed numbers unaffected (re-render
same ~6.5x); the ORIGINAL probe1 wav/m4a files are superseded by *_fixed.* for quality
judgment — Grace's listening verdict must use the _fixed files.

## Entry 7 — 2026-07-18 — Probe 3 API run complete; Phase 1 now blocked only on Grace's two tests

probe3_curation_api.py succeeded end-to-end (Opus 4.8 + web_search): 10 candidates with
named, checkable evidence and correct PD/modern classification; honest flags on 2
unverified Gutenberg IDs. Actual cost $1.65/batch — above the "pennies" expectation;
cost levers (cheaper model, capped searches, cached criteria) recorded as Phase 2
design inputs. Probes 3 and 6 are now ANSWERED. Remaining for the Phase 1 gate:
Grace's listening test (probe 1/2, on the *_fixed files) and the phone-over-Tailscale
walk-through (probe 5; server live on 100.117.147.107:8765).

Measurements invalidated by this change: none.

## Entry 8 — 2026-07-18 — Probes 1+2 closed by Grace's verdict; iOS resume bug fixed; probe 5 on retest

- Grace approved the fixed Kokoro audio -> probe 1 ANSWERED (Kokoro stays primary
  TTS). Because the fixed files are 7 butt-joined chunks, the approval also closes
  probe 2's seam question: butt-join is the design default.
- Probe 5 first phone run: everything worked on first open; after kill+reopen the
  audio restarted and scrubbing died. Root cause: iOS Safari drops currentTime seeks
  issued before metadata load (gesture-gated), and duration=NaN no-ops the scrubber.
  Fixed in the test page: pending-seek applied on loadedmetadata (backup on
  `playing`), guarded scrubber, save-suppression until resume applies. Promoted to
  Phase 4 design constraint: apply resume seeks loadedmetadata-or-later, never at
  page init. Grace retesting the kill+reopen cycle.
- Phase 1 gate now rests solely on the probe 5 retest.

Measurements invalidated by this change: none.

## Entry 9 — 2026-07-18 — Probe 5 resume retest PASSED; gate narrowed to three sub-checks

- Grace retested http://100.117.147.107:8765/ on the phone: kill+reopen now resumes at
  the saved position and scrubbing works — the loadedmetadata-seek fix holds on the real
  target. Server re-verified from the Mac this session (GET / -> 200; Range request on
  probe1/horror_usher_af_heart_fixed.m4a -> 206, correct content-range).
- Gate NOT closed: probe 5's scope (TASKS §1.5) also covers lock-screen/Media-Session
  controls, backgrounded playback ≥5 min, and the R13 speed selector — no recorded
  evidence for any of the three from either phone run, so per "done = artifact-verified"
  they remain open. Phase 1 gate now rests solely on Grace reporting those three
  (~5 min, server already live). No Phase 2 design work started past the open gate.
- Docs updated: probe_results.txt probe-5 section + gate status, TASKS Phase 1 status
  line, STATE next actions.

Measurements invalidated by this change: none (verification + bookkeeping only).

## Entry 10 — 2026-07-18 — "Play auto-pauses" root-caused: resume-to-end-of-file; page fixed

- Grace's second retest failed: play immediately followed by an auto-triggered pause.
  Root cause: during the ≥5-min backgrounding check the 2:30 sample played to the END;
  timeupdate saved position ≈ duration to localStorage, so the next open faithfully
  resumed to end-of-file and iOS fired ended→pause instantly. Playback itself never
  broke — the resume logic stored a completed story's end as a resume point.
- Test-page fix (live; StaticFiles serves from disk, verified in the served HTML):
  resume targets within 2s of duration are discarded (restart at 0); saved position
  cleared on `ended`; pause log now includes currentTime + ended flag; play()
  rejections logged.
- Promoted to Phase 4/5 design constraint: `ended` must clear/complete the resume
  position and mark the story read — never persist end-of-file as a resume point.
- Backgrounding check reframed: all probe samples are < 5 min, so the literal
  "background ≥5 min" is unmeetable; the real question is "does audio keep playing
  unattended to the end of the story", which the end-of-file evidence suggests is
  already true — the "restarting from 0" log line on Grace's next open confirms it.
- Also corrected in-session: I briefly cited the probe2 concat as 4.6 min; it is
  ~76 s (1,829,400 samples @ 24 kHz). probe_results.txt carries the corrected figure.

Measurements invalidated by this change: Grace's earlier "resume works" verdict
(Entry 9) still stands — this failure was a different path (resume of a *finished*
story), not a regression of mid-story resume. No numeric measurements affected.

## Entry 11 — 2026-07-18 — Phase 1 CLOSED on Grace's four reports; DESIGN.md drafted

- Grace's final probe-5 run (fixed page): (1) no "restarting from 0" log line — the
  end-of-file diagnosis stays plausible-but-unconfirmed (likely her post-failure taps
  moved the saved position off the end before the fixed page loaded); playback works,
  defenses stay. (2) Lock screen: title shows; skip buttons work — icons show Apple's
  default "10s" but after kill+reload they perform the handler's ±15s exactly (the
  pre-reload 30s jumps were stale handler state). (3) Speed selector honored — R13
  viable on iOS. (4) Mid-story kill+reopen resume works on the fixed page.
- Probe 5 ANSWERED; one explicit deferral with risk note: sustained ≥5-min single-track
  backgrounding (all samples < 5 min; lock-screen playback proven; re-tested verbatim by
  the Phase 4 gate on a real story). **Phase 1 gate CLOSED — all six probes answered.**
  pre_design_probes/ authority ends here per CLAUDE.md.
- Standing-rule interpretation, stated for Grace to veto: the "/code-review at phase
  close" checkpoint was not run for Phase 1 — its output is knowledge
  (probe_results.txt), and its code is committed throwaway explicitly stripped of
  authority. First /code-review lands at Phase 3 close (first production code).
- Phase 2 started per STATE next-action 2: docs/DESIGN.md DRAFT v0.1 written from
  probe results + REQUIREMENTS + carry-ins (line-unwrap clean rule, loadedmetadata
  resume rule, ended-clears-resume rule, curation cost levers, lock-screen icon
  quirk). Proposed decisions awaiting Grace: queue = 5-per-active-channel; Reddit via
  OAuth script app (NoSleep disabled until she creates it); curation on Sonnet with
  capped searches (~≤$0.40/batch target vs $1.65 measured at Opus); offline PWA
  caching out of MVP. Gate = Grace sign-off after walkthrough; NOT frozen yet.

Measurements invalidated by this change: none (design is downstream of measurements).

## Entry 12 — 2026-07-18 — Grace's v0.1 rulings: queue redesign, multilingual scope, model policy; DESIGN v0.2

- Grace ruled on the four §9 decisions: Reddit OAuth APPROVED; Sonnet APPROVED with a
  condition (no auto-escalation ever; consistent quality disappointment → UI notice to
  change the model — her choice only → new R14); offline caching out APPROVED.
- Queue: Grace proposed 3-unread + autoplay in acquisition order + skip button and asked
  for critical assessment. Assessment: adopted — cost difference vs 5 is negligible, but
  3 shortens the taste-adaptation feedback lag and the skip button adds a curation-
  quality signal ratings can't provide. Two refinements accepted into the design: skips
  are permanent history (no-repeat guarantee covers them) and stories are queue-visible
  at text_ready with synthesis in queue order (skip before render costs one fetch).
  Encoded as AMENDMENT_02 (PROPOSED status; binds at v0.2 sign-off; supersedes brief
  §2's "queue of 5"). R4 reworded accordingly.
- Multilingual scope (Grace: en/zh natively, learning fr): encoded as AMENDMENT_03
  (PROPOSED). Source tiers: A = Gutenberg zh/fr, SCP-CN (CC BY-SA — oobmab's branch is
  legally fetchable), local_import for legitimately-owned commercial works
  (周德东-class, translated ja fiction); B (probe first) = X岛-successors, 知乎;
  C (declined) = 小红书 scraping and any DRM'd platform (微信读书) — DRM circumvention
  is out regardless of private-use posture, local_import is the lawful route. New R15.
- Probe 1c run (new probe under AMENDMENT_03; its section in probe_results.txt carries
  design authority despite the directory's Phase-1 expiry): misaki[zh] installed clean;
  zh renders 5.3–5.7x realtime (two voices), fr 5.0x (Le Horla, no extra deps); all
  three m4as verified 200 over Tailscale. Grace's listen is the zh/fr channel gate.
- DESIGN.md → v0.2: queue §7 rewritten, schema gains status values text_ready/skipped +
  stories.language + source classes scp_cn/local_import, curation language-aware, model
  policy + settings UI, negative spec gains no-DRM-circumvention and no-silent-model-
  changes, traceability covers R14/R15. Phase 2 gate still open: sign-off pending
  Grace's probe-1c listen + v0.2 review.

Measurements invalidated by this change: none. Probe-3 curation cost ($1.65 at Opus)
was measured on an English channel; zh-channel cost is unmeasured — watch the first
real zh curation_runs rows before trusting the ≤$0.40 target there.

## Entry 13 — 2026-07-18 — Probe 1c verdicts: fr PASSES, zh Kokoro FAILS; zh alternatives rendered

- Grace's verdicts: fr passes (French channels gated open on Kokoro ff_siwis); zh
  fails — "quite off, weird accents" on both first-round voices. Matches Kokoro's own
  low quality grades for zh; model-level, not fixable by our pipeline.
- Rendered for her second listen (same original paragraph, /audio/probe1c/): the six
  remaining Kokoro zh voices (so Kokoro is judged on its best, though the accent
  problem likely persists) and two edge-tts samples (Microsoft Edge neural voices —
  native Azure zh, $0, actively maintained v7.2.8). edge-tts caveats recorded: per-
  render cloud call (story text to Microsoft), undocumented endpoint that can
  rate-limit/break → must keep Kokoro/OpenAI as fallbacks if adopted.
- Fully-local alternatives researched but unprobed: CosyVoice2-0.5B (top Mandarin
  pick), Fish Speech V1.5, IndexTTS-2 — heavier installs, likely sub-realtime on this
  Mac (fine for pre-rendering); each needs its own probe if Grace prefers no-cloud.
- Design change queued for v0.3 (pending Grace's pick): TTS engine becomes
  per-language configuration (en/fr = kokoro; zh = her choice), replacing the single
  global primary.

Measurements invalidated by this change: none (adds measurements; prior en/fr/es
numbers stand).

## Entry 14 — 2026-07-18 — zh TTS decided (verdict a: edge-tts, Yunxi); v0.3; session handoff

- Grace's round-2 verdict: **(a) edge-tts passes**, with zh-CN-YunxiNeural preferred
  over Xiaoxiao. Probe 1c fully ANSWERED: en=Kokoro, fr=Kokoro ff_siwis, zh=edge-tts
  Yunxi (Kokoro zh rejected), ja untested/out.
- DESIGN.md → v0.3: §5 synthesize rewritten to per-language engine config; edge-tts
  caveats accepted on record (cloud render call — story text is not personal data;
  undocumented endpoint) with a binding degrade rule: edge-tts failure → OpenAI TTS
  for that story, never a blocked queue. §9 gains ruling 6. NOT yet frozen.
- Handoff state: Phase 2 gate = Grace's explicit sign-off on v0.3 (single remaining
  step; all §9 decisions are ruled, both amendments stand PROPOSED and bind at
  sign-off). Next session: get sign-off → freeze DESIGN v1.0 + mark amendments
  binding + journal it → stop probe-5 server → Phase 3 per TASKS.
- Note for Phase 3: edge-tts is installed only in pre_design_probes/.venv; the
  pipeline env must add it (and its offsets math needs the §5 duration-read unit
  test, since edge-tts returns mp3 rather than wav).

Measurements invalidated by this change: none.

## Entry 13 — 2026-07-18 — Correction: bank paths updated after meta-folder rename

Grace renamed `~/Code/*META_working_knowledge` → `_META_working_knowledge` and the bank
`new_proj_claude_bank/` → `claude_bank/`. Mechanical path-only edits in this repo:
CLAUDE.md's rules-provenance footer, and Entry 1's scaffold-source path (old path kept in
parentheses there — this entry names that historical edit per the corrections norm).
No rule or design content changed.

Measurements invalidated by this change: none.

## Entry 15 — 2026-07-18 — Phase 2 CLOSED: Grace signed off DESIGN v0.3 → FROZEN v1.0

- Grace's sign-off, verbatim: "I sign off DESIGN v0.3." Per STATE next-action 1:
  DESIGN.md header flipped to **FROZEN v1.0**; AMENDMENTS 02 (queue 3+skip) and 03
  (zh/fr multilingual) flipped PROPOSED → **BINDING** (their status lines updated —
  the flip is the binding act; content untouched, immutable from here).
- Freeze-time reconciliation inside DESIGN (mechanical, no decision content): §10 and
  §11 still said "zh/fr pending probe-1c verdict" — stale since Entries 13–14 recorded
  the verdicts §5/§9 already encode. Updated to "en/fr/zh passed, ja untested".
- Phase 2 gate check: sign-off recorded (this entry) + every REQUIREMENTS row R1–R15
  maps to a design element in §11 with explicit deferrals → **Phase 2 DONE**.
- Numbering note per corrections norm: the meta-folder-rename correction above is
  mislabeled "Entry 13" (second of that number); it is chronologically the 15th entry.
  Left as-is (append-only); this entry takes 15 as its label since STATE's "reconciled
  through Entry 14" already resolves the sequence through the zh-TTS entry.
- Next: stop probe-5 server; Phase 3 pipeline MVP per TASKS (edge-tts into the
  pipeline env; mp3-duration offsets unit test per DESIGN §5).

Measurements invalidated by this change: none (freeze + bookkeeping only).

## Entry 16 — 2026-07-18 — Phase 3 pipeline built; gate story rendered; review fixes; costs

- **Pipeline implemented** against frozen DESIGN v1.0: pipeline/ package (config,
  db schema, models, textproc, fetch, curate, tag, synthesize, ingest, retry,
  run_story driver) + scripts/spot_check_offsets.py + tests/. Project venv at .venv
  (requirements.txt; edge-tts now in the pipeline env per Entry 14's note).
  32 unit/round-trip tests green (offsets math, serialization round-trips, dedup
  keys, clean rules, tag normalization, schema constraints, AAC decode-duration).
- **Gate run lessons (all fixed + regression-tested):**
  1. Curator's "Tell-Tale Heart" Gutenberg ref fetched a 550KB Poe COLLECTION;
     22 min into a ~10h render before kill. → MAX_STORY_CHARS ceiling (120k chars),
     curator prompt demands standalone single-story editions.
  2. The 40-char paragraph floor (probe-4 wiki-chrome rule) dropped 29 real
     paragraphs from The Yellow Wallpaper ("And what can one do?"). → floor now
     applies to HTML sources only; Gutenberg keeps every paragraph.
  3. Anthropic credit balance EXHAUSTED mid-run → every candidate died at the tag
     stage. → tagging made non-fatal (tags are Phase 6 enhancement; render is the
     expensive part), and pipeline/retry.py re-runs a failed/stranded story from
     its stored row without re-paying curation.
- **Gate story READY: The Yellow Wallpaper** (aa80b0587f70, Gilman, PG1952) —
  32.2 min, 269 paras, kokoro/af_heart, 11 tags, meta/offsets/audio on disk.
  Mechanical spot-check: all 269 char spans match story.txt paragraphs exactly;
  audio vs manifest drift 0 ms; ear-check clips (first/middle/last para) in
  data/interim/spotcheck/. **Gate remaining: Grace's listen** (audio served at
  http://100.117.147.107:8765/audio/gate_listen/yellow_wallpaper.m4a; probe-5
  server restarted for this purpose after Entry 15 stopped it).
- **/code-review run (phase-close checkpoint, high effort): 10 confirmed findings,
  all fixed** — worst: pause_turn continuation dropped earlier search results;
  synthesis fallback bypassed on non-SynthesisError (degrade rule §9.6 violated);
  pre-insert failures left no history so curation would re-propose doomed picks
  forever; cost-ledger row skipped on unparseable curation responses. Coverage
  honesty: 5 of 8 review angles completed — three (removed-behavior, reuse,
  efficiency) died on the Claude session usage limit; re-run them at Phase 4 close.
- **Costs (R11):** curation $0.90 and $2.13/batch at Sonnet w/ 6 searches — far
  over the ≤$0.40 target; token volume (search results), not search count, is the
  driver. Tuning pass owed (fewer searches, smaller batch, trimmed results).
  API balance now empty: **Grace must top up credits** before the next curation
  or tagging call. Everything local (Kokoro, tests, retry) runs at $0.
- **Accepted debts (Phase 4/5, from review):** source-class knowledge spread over
  4 sites (curate prompt, SOURCE_HINTS, fetch dispatch, run_story skip) → needs a
  single registry before nosleep/scp_cn; edge-tts asyncio.run-per-paragraph breaks
  under an async caller + story-restart fallback discards free renders (paragraph-
  level retry wanted); candidate_from_row reverse-parses source_ref from URL
  (store source_ref explicitly — needs schema amendment); CONTROLLED_VOCAB
  subgenres are horror-leaning (channel-genre coupling for Phase 5); timestamps
  (created_at/ready_at) don't take a clock param — read as audit stamps, not
  time-dependent behavior; revisit if logic ever branches on them.

Measurements invalidated by this change: the two curation cost figures above
supersede the probe-3 $1.65 Opus figure as the current cost baseline. Probe-era
audio measurements unaffected.

## Entry 17 — 2026-07-18 — Phase 3 CLOSED; Grace's cost/flow rulings → AMENDMENT_04

- **Phase 3 gate PASSED** — Grace, verbatim: "Phase 3 gate passed." (After a
  blank-page detour: server was healthy, phone-side connectivity + a wrong
  folder-URL in my instructions; direct file links worked.) API credits topped up.
  Phase 3 → DONE.
- Grace's three follow-ups, same message (verbatim in AMENDMENT_04): (2a) should
  queued stories be rendered in ~5-min chunks? (asked for assessment); (2b) show
  the next story's title BEFORE extraction so she can pre-mark known/read ones
  (directive); (3) curation cost must drop to ~$0 — try Sonnet cost reduction
  first, else cheaper models (directive).
- Grace added mid-session (4): how does free voice selection square with
  whole-story pre-extraction — real-time synthesis with a few-paragraph cache?
  — explicitly delegating the decision ("you decide, critically").
- Encoded as **AMENDMENT_04**: (A) pool-based curation — replenishment consumes
  stored candidates at $0 marginal; paid pool builds are rare, explicit,
  Grace-initiated (extends R14's no-silent-spend to curation spend); (B)
  pre-extraction announcement + `pipeline.mark` pre-marking (extends
  AMENDMENT_02's skip-history to the candidate stage); (C) chunked audio
  DECLINED-recommended (iOS seams/resume complexity vs $0 local renders +
  Phase 5 pre-rendering), replaced by abort-render-on-skip — awaiting Grace's
  verdict on C specifically; (D) voice policy RULED under her delegation:
  pre-render stays, real-time voice conversion declined (playback-time
  dependence on live render loop + undocumented zh endpoint, iOS streaming
  fragility probe 5 exists to avoid, R11 no-per-listen-calls violation) —
  instead voice chosen at text_ready, audition gallery in Phase 4 settings,
  explicit $0 re-render via retry --voice.
- Economics recorded: today's $2.13 batch has 4 unconsumed candidates + 4
  credit-failure rows retryable at $0 — the next ~8 stories are already paid for.

Measurements invalidated by this change: none yet (implementation follows this
entry; curation cost baseline will change once pool flow lands).

## Entry 18 — 2026-07-18 — AMENDMENT_04 fully binding; queue at 2 ready stories, $0

- Grace, verbatim: "chunking verdict approved" — part C (chunking declined,
  abort-render-on-skip adopted) confirmed; **AMENDMENT_04 is now FULLY BINDING**
  (status flipped in the doc; the flip is the confirmation act).
- AMENDMENT_04 implementation had landed same day (Entry 17 commit 70ea94b):
  pool.py ($0 replenishment draw), mark.py (pre-extraction read/skip),
  record_provisional, AbortRender + should_abort hook, retry --voice,
  run_story --build-pool flow. 39 tests green.
- Flow proven live at $0: The Monkey's Paw retried end-to-end (fetch → clean →
  tag → Kokoro render), READY — 22.0 min, 152 paras. Library: 2 ready stories
  (Yellow Wallpaper 32.2 min + Monkey's Paw 22.0 min); Owl Creek / Damned Thing /
  Willows remain retryable at $0; pool holds 6 candidates (mostly known-dead
  creepypasta stubs that will fail fast into history + 2 iffy gutenberg refs).

Measurements invalidated by this change: none. Curation cost baseline going
forward: $0 marginal per story from the pool; paid builds explicit only.

## Entry 19 — 2026-07-18 — Phase 4 player MVP built + browser-verified; queue at 5 ready

- **Queue build finished, $0 marginal:** Owl Creek Bridge (20.9 min) and The Damned
  Thing (18.0 min) retried READY by this session. The Willows (107.1 min) went READY
  via a `pipeline.retry` process from a PARALLEL session (`-u` invocation, PID 38936,
  started 09:40 local) that was already running it; this session's own willows retry
  was detected as a duplicate and killed at spawn (guard log, "DUPLICATE KILLED").
  Library: 5 ready stories, all kokoro/af_heart. ⚠️ Two sessions worked STATE
  next-action 1 concurrently — coordination hazard worth avoiding next time.
- **Phase 4 app built** per DESIGN §6 + AMENDMENT_04 D: `app/server.py` (FastAPI —
  stories list/detail, range-capable audio, progress GET/PUT, /ended, /skip, ratings,
  bookmarks CRUD, /voices + samples + per-story voice) and `app/frontend/` (React+Vite
  PWA: queue with text_ready voice picker + skip, library, player with play/pause,
  ±15 s, scrubber, 0.75–2× speed, Media Session, text view, bookmarks, 1–5 stars,
  voice audition gallery). Player implements the four binding iOS rules (§6).
  `scripts/serve.sh` = the one runbook command; binds Tailscale IP only.
- **Voice gallery assets:** scripts/render_voice_samples.py rendered 11 samples
  (8 en Kokoro, fr ff_siwis, 2 zh edge-tts) to data/voice_samples/, 0 failures.
- **retry_story honors a stored gallery voice** (new `stored_voice_override`):
  queue-window picks survive to the render; stored fallback voice "onyx" is excluded
  so a $0 retry can never silently re-route onto paid OpenAI.
- **Browser-verified end-to-end** (Playwright chromium against a sandboxed COPY of
  the DB + library — real library state untouched): queue → play (audio advances) →
  +15 s → pause (server progress row written) → reload → resume applied at saved
  16.15 s on loadedmetadata → seek to end → `ended` ⇒ status read + progress row
  cleared ⇒ autoplay advanced to next ready story; text view (269 paras), bookmark
  add/delete, 4-star rating, voices/library tabs. Range request on real audio → 206.
- **/code-review (high; angles run inline): 5 findings, all fixed + regression-tested**
  — worst: a voice re-render of a READ story ended the retry walk at 'ready',
  resurrecting finished history as unread in the queue (fix: retry_story restores
  'read'); late keepalive save racing /ended could re-create a resume row on a read
  story (server now no-ops saves on read/skipped — the Entry-10 symptom via a race);
  queue-window voice pick was ignored by _finalize (now re-read before synthesis);
  full schema re-executed per request (db.connect gained init=False; schema once at
  app startup); Player handlers captured a possibly-null first-render audio ref.
  Tests 39 → 60, all green.
- **Server RUNNING:** http://100.117.147.107:8123 (scripts/serve.sh, Tailscale only).
  Phase 4 gate = Grace's phone test per TASKS §4; instructions given in chat.
- **Deferred, needs Grace (batched in chat):** the §6 settings screen (curation model
  selector, R14) needs a store for the choice — a small `settings` table = schema
  change on the frozen design ⇒ amendment proposal awaiting her go-ahead (could bundle
  the Entry-16 "stored source_ref" debt). Entry-16 debts (source-class registry,
  edge-tts async granularity, stored source_ref, vocab-genre coupling) and the 3
  Phase-3 review angles remain owed at Phase 4 close / Phase 5.

Measurements invalidated by this change: none — the synthesis pipeline and offsets
math are untouched; Phase 3 cost and drift figures stand. (db.connect init flag
changes no persisted state.)

## Entry 20 — 2026-07-18 — Phone-test feedback (10 items) implemented; AMENDMENT_05 drafted

- **Grace ran the Phase 4 phone flow** — her verbatim report is preserved in
  AMENDMENT_05. Gate evidence so far: scrub/±skip/lock-screen exercised; "killing
  safari mid-play reopened with the audio progress saved" (kill+reopen resume ✓);
  "no other issues spotted". Her live session left real state: 4 stories
  in_progress with progress rows, Yellow Wallpaper skipped. **Still owed for the
  gate: explicit ≥5-min backgrounding** (the probe-5 deferral this gate exists to
  retire) — asked in chat; Phase 4 stays [IN PROGRESS] until she confirms.
- **AMENDMENT_05 written** (docs/AMENDMENT_05_settings_sourceref_player_feedback.md):
  part C (her ten player directives, verbatim) BINDING and implemented today;
  parts A (settings table: curation model + per-language default voices) and
  B (stored source_ref) PROPOSED — schema changes awaiting her explicit flip.
  Her "2. approved" green-lit drafting; the flip is asked for in chat.
- **Implemented (all of part C):** ±10 s everywhere (supersedes §6's ±15 — C1);
  mid-play story switch autoplays + play-state icon reset (C2); remove menu
  distinguishes "Not interested (skip)" vs "Already read" — new POST /read
  sharing /ended semantics, so read ≠ dislike reaches Phase 6 untainted (C3);
  POST /unskip restores status from artifacts (audio→ready, text→text_ready,
  none→failed/retryable) with an undo button in the library — the AMENDMENT_02
  carve-out is recorded in A05 C4; text view follows playback (offset binary
  search → highlight + scrollIntoView — Phase 5 sync pulled forward, C5); voice
  picker in the player for rendered stories behind a $0/~min confirmation popup,
  and a text_ready voice pick now spawns the render — an in-flight render aborts
  at the next paragraph via the extended should_abort (gallery-voice mismatch;
  engine-fallback "onyx" can never self-abort a degrade render) and the fresh
  render takes over (C6); last-played story auto-restores paused at its resume
  position via progress_updated_at (C7); capitalized sticky tab header, ratings
  editable only in the player, read-only stars in the library (C8/9).
- **Verified** end-to-end in headless Chromium against a sandboxed `.backup` COPY
  of the live DB (real library untouched): restore landed paused at exactly the
  saved 213.2 s; mid-play switch autoplayed the next story from its own resume
  point; para-28 highlighted + auto-scrolled at the seek position; "Already
  read" flipped status and advanced; Grace's real Yellow Wallpaper skip undone →
  'ready' (artifact-derived) in the sandbox; library stars disabled; voice
  confirm dismiss left voice untouched. Tests 60 → 64, all green. One live-server
  probe of /unskip mutated the real Yellow Wallpaper row; reverted immediately
  (re-skipped — her phone-session state restored).
- Server restarted on http://100.117.147.107:8123 with the new build.

Measurements invalidated by this change: none (synthesis/offsets untouched).
The ±15 s wording in DESIGN §6 rule 4 is superseded by AMENDMENT_05 C1 — DESIGN
itself left unedited per the freeze.

## Entry 21 — 2026-07-18 — Phase 4 GATE PASSED; re-render self-abort bug fixed; AMENDMENT_05 fully binding

- **Phase 4 gate PASSED.** Grace: "1. >5min backgrounding worked properly." —
  combined with Entry 20's kill+reopen resume report and her phone session's
  scrub/±skip use, every TASKS §4 gate criterion has phone-over-Tailscale
  evidence. Probe 5's deferred ≥5-min-backgrounding risk (Entry 11) is retired.
  Phase 4 → DONE.
- **Her re-render bug report root-caused (item 4):** two separate outcomes —
  (a) Monkey's Paw re-render with am_adam actually SUCCEEDED (READY 20:15,
  21.5 min) but gave zero UI feedback, and (b) Damned Thing's re-render
  self-aborted at paragraph 0: my Entry-20 mid-render voice check compared the
  render target against the row's stored voice, which is stale BY DESIGN during
  an explicit --voice retry (it only updates at finalize). The Playwright
  verification had dismissed the confirm dialog, so this exact path never ran —
  the lesson is the ABOUT_ME one again: the probe must exercise the accept path,
  not just the cancel path. Fix: abort only when the stored voice CHANGED since
  render start (and still differs from the target); regression test added.
  Also: retry now restores in_progress (not just read) after a re-render, and
  a mid-render abort message no longer claims "skipped/read" for voice changes.
- **Damned Thing repaired:** the aborted run stranded it text_ready while its
  old audio + Grace's progress row survived on disk — restored to in_progress
  (artifact-derived). Her voice pick wasn't recorded anywhere (by design the
  --voice flag never landed), so she re-picks in the player.
- **AMENDMENT_05 FULLY BINDING** — Grace: "flip A and B." Implemented same
  session: `settings` table + one-time `stories.source_ref` ALTER/backfill
  migration (legacy reverse-parse now lives only in the migration);
  db.get/set_setting + effective_curation_model (curate.py + run_story now
  honor the R14 selector) + effective_voice (render precedence: explicit
  --voice > queue-window row pick > settings default > config default);
  Settings tab (model selector, per-language default voices, R14 quality
  notice at ≥50% skip-rate over the last ≥5 decided stories); DELETE
  /api/ratings + "clear" button (her item 3); re-render progress note in the
  player + 15 s visible-tab auto-refresh so background renders surface without
  manual reload.
- **Owed Phase-3 review angles run at close (removed-behavior, reuse,
  efficiency — Entry 16 debt):** all Entry-16 gate-run guards verified still
  present (MAX_STORY_CHARS, HTML-only paragraph floor, non-fatal tagging,
  ledger-before-parse). One real find, fixed: run_story's pool-empty message
  quoted config.CURATION_MODEL while curation now uses the settings model.
  Noted, not fixed: mark.py (SQL LIKE) and pool.find_candidate (substring)
  carry two fuzzy title-match semantics — centralize when a third user
  appears; curation prompt exclusions list grows with all-time history —
  future R11 cost lever for Phase 5/6 (pool flow makes it rare today).
- **Verified:** 71 tests green (settings round-trip/validation, quality
  notice, clear rating, stale-voice no-self-abort, in_progress restore,
  settings-default-voice reaches render, source_ref stored+used); Settings
  tab + clear-rating driven in Chromium against the sandbox copy; a REAL
  Kokoro re-render of sandbox Owl Creek with --voice am_michael re-ran
  Grace's exact failing scenario end-to-end: sandbox Owl Creek, row voice
  af_heart, `retry_story(--voice am_michael)` → **status stayed 'ready',
  voice='am_michael', 1365 s of real Kokoro audio** (pre-fix this died at
  paragraph 0). source_ref migration confirmed on the real DB too: all rows
  backfilled (tell-tale-heart→2148, yellow-wallpaper→1952, owl-creek→375),
  0 NULLs.
- Server restarted on http://100.117.147.107:8123.

Measurements invalidated by this change: none (offsets math untouched; cost
baselines stand — the model SETTING changes future pool-build cost only when
Grace changes it).

## Entry 22 — 2026-07-27 — Session audit; AMENDMENT_06 render progress + pause/cancel

- **Session-open audit (first work since 7/18).** Re-derived from artifacts, not
  prose: tree clean and pushed at `d140875`, 71 tests green, app server still
  up on the Tailscale IP, 5 stories in the library. Phases 0–4 DONE, Phase 5
  not started. Three drift items found:
  1. **STATE's next-actions were stale** despite the "reconciled through Entry
     21" stamp — it still asked Grace for the two Phase-4 confirmations and the
     AMENDMENT_05 A/B flip, all of which Entry 21 records as resolved. The
     phase table was right; the action list below it was pre-Entry-21. Fixed in
     this session's reconcile. Lesson for the close ritual: reconciling STATE
     means the WHOLE file, not the table that changed.
  2. **Queue depth contradiction in the governing prose.** AMENDMENT_02
     (binding) and `config.QUEUE_DEPTH` say 3; CLAUDE.md's summary line, its
     centralization example, and — worst — the TASKS Phase 5 GATE text all
     still said 5, a gate I would have executed literally. Amendment wins;
     the three prose copies corrected to 3. No code was wrong.
  3. **Un-journaled listening session (2026-07-19).** DB shows Grace played
     after Entry 21 was written: Monkey's Paw + Yellow Wallpaper → read, both
     rated 5; Owl Creek 13.9/20.9 min, Damned Thing 4.9/18.0, Willows
     1.4/107.1 still in_progress; `default_voice.en` set to am_adam. Recorded
     here so the ratings have provenance. Grace's note: the three are simply
     unfinished, so their absent ratings are not signal.
- **Queue is at 0 unread** (2 read, 3 in_progress, 1 failed) against a required
  3 — the Phase 5 worker is now the binding constraint on using the app at all.
- **AMENDMENT_06 BINDING + implemented** (Grace's direct instruction, verbatim
  in docs/AMENDMENT_06): progress bar on every render (new + re-render), with
  pause/resume/cancel from the queue card, library card, and player.
  - New `render_jobs` table = the cross-process control channel between the
    detached render subprocess and the server (WAL already made this safe).
    Pipeline writes phase/progress + reads control; server writes control +
    reads progress. Liveness derived from the pid, never trusted from the row.
  - `synthesize._render_story`'s `should_abort` boolean poll generalized to a
    `checkpoint(done, total)` hook at the same seam — it reports progress, may
    BLOCK (pause), and may raise AbortRender (skip / voice change / cancel).
    One hook, three callers' concerns; the AMENDMENT_04 C skip-abort and
    AMENDMENT_05 C6 voice-abort semantics are unchanged.
  - **Latent bug fixed en route:** a cancelled/aborted re-render left the row
    stranded at `fetching` — exactly the Entry-21 Damned Thing hand-repair.
    Cancel now restores the pre-render status, and because the m4a is written
    only after the LAST paragraph, existing audio is safe by construction.
  - Two limits accepted rather than faked: control granularity is one paragraph
    (a paragraph render is not interruptible), and fetch/tag/encode show an
    indeterminate sweep because there is no honest denominator.
- **Verified:** 87 tests green (16 new: pure progress/control/staleness logic,
  job round-trip, pause loop with sleep injected, stale-cancel clearing, dead-pid
  reaping, cancel-restores-status through the real ingest path, API 200/409/404).
  Beyond the suite, a REAL Kokoro re-render on a sandbox copy of Damned Thing
  drove the ACCEPT paths (the Entry-21 lesson — the cancel dialog is not the
  test): job registered → progress advanced to 2/78 → **pause held it at 3/78
  for 8 s with the process alive** → resume advanced to 5/78 → cancel stopped it
  at 6/78 → status `in_progress`, voice `af_heart`, audio 8897293 B all
  unchanged. Frontend rebuilt (vite, 32 modules); server restarted; `render_jobs`
  confirmed created on the real DB and `/api/renders` answering.

Measurements invalidated by this change: none. Offsets math, chunking, cost
baselines and the iOS rules are all untouched — the checkpoint hook only
observes the paragraph loop it already ran inside. Render wall-clock gains a
sub-second-per-paragraph SQLite write, immaterial against ~4.5 min/story.

## Entry 23 — 2026-07-27 — REQUIREMENTS.md statuses re-derived (4th drift item)

- **Every R-row still read "❌ not built"** — frozen at Phase-1 authoring while
  Phases 0–4 shipped. The traceability spine claimed nothing existed. Statuses
  re-derived from artifacts this session (files/tests/DB/gate evidence, never
  from prose), per the file's own "STATUS change requires a JOURNAL entry" rule:
  - ✅ R1 R2 R3 R5 R6 R7 R9 R11 R13 R14 (+ new R16 for AMENDMENT_06)
  - ◐ R4 (autoplay/skip ship, worker doesn't), R8 (text follow + current-para
    class ship; phone-verified highlight is the Phase 5 gate), R10 (rating UI
    ships, weighted curation is Phase 6), R12 (channel schema ships, editor UI
    doesn't), R15 (per-language TTS decided, no non-English channel run)
  - Legend gained ◐ **partial**, because half these rows were neither "covered"
    nor "not built" and a binary marker was hiding exactly the gaps that matter.
  - R7's text also corrected to ±10 s (AMENDMENT_05 C1 superseded the ±15 s).
  - G2's "queue of 5" corrected to 3 — the same stale number fixed in CLAUDE.md
    and the TASKS Phase 5 gate this session (Entry 22).
- Pattern across all four drift items: the phase table and the code stayed
  honest; the *narrative* files around them went stale, each in a place nobody
  re-read. Cheapest fix is the one already in the close ritual — reconcile the
  whole file, not the line that changed.

Measurements invalidated by this change: none (documentation only).

## Entry 24 — 2026-07-27 — Phase 5 worker + channels editor built; two real bugs found by the gate run

- **Replenishment worker built** (`pipeline/worker.py`, DESIGN §7). Two stages,
  deliberately split: ACQUIRE (fetch/clean/tag → `text_ready`, one HTTP GET per
  story) then RENDER (synthesize in acquisition order). That ordering is the
  design's point — a story is queue-visible and skippable before it costs a
  ~4.5-min render. Required splitting `ingest._finalize` into
  `_write_text_and_tag` + `_render`, with `acquire_candidate` /
  `render_ready_story` as the worker's two entry points; `ingest_candidate` and
  `retry_story` still drive both halves, so nothing else changed behavior
  (87 tests stayed green across the refactor).
- Never spends money: an empty pool ends the cycle with a printed message.
  Paid refill stays Grace's explicit `run_story --build-pool` (AMENDMENT_04 A).
- **Channels editor built** (R12): `/api/channels` CRUD + activate, `Channels`
  tab. Every editable field (genre, language, topics, era, exclusions, extra
  criteria) now reaches the curation prompt — `build_prompt` previously ignored
  topics/era/exclusions entirely, so an editor over those fields would have
  been decorative.

### Bug 1 (found by the gate run): acquisition order was arbitrary

`created_at` is second-granularity, and the worker acquires several stories
inside one second — so "acquisition order", which IS the queue order, the
autoplay order and the render order (DESIGN §7), was effectively random within
a second. Raising precision to milliseconds did not fix it either (the fake-fast
test still tied). Ordering now uses SQLite's `rowid`, which is monotonic per
insert and safe because `stories` is append-only (R6, rows are never deleted);
`db.ACQUISITION_ORDER` is the single copy, used by the worker, the story list,
retry and known_titles. Timestamps keep the new ms precision for debugging but
nothing orders by them.

### Bug 2 (found by the gate run): a bad REFERENCE blacklisted a real STORY

The live cycle acquired 1 of 6 pool candidates. Failure notes, all legitimate:
3 creepypasta pages are stubs (Candle Cove removed for copyright, Ted the Caver
a nav stub, Jeff the Killer deleted by the wiki's quality control — verified by
fetching them by hand; probe 4 predicted exactly this and the validation caught
it), 2 Gutenberg ids were collection volumes (8492 = the King in Yellow
collection), 1 had `source_ref: "unknown"`.

The pipeline handled each correctly — and then did something wrong: every
failure wrote a `failed` row, and `known_titles` excluded ALL rows from future
curation. So "The Music of Erich Zann" and "The Yellow Sign" — real stories that
simply came with a bad reference — were blacklisted permanently. A curator
metadata gap was silently costing Grace stories.

Fixed by separating two questions that had been conflated:
- **Titles** are excluded when we HAVE the story or Grace DECIDED on it
  (`db.KNOWN_STATUSES` — text_ready/ready/in_progress/read/skipped).
- **Refs** are excluded when that source failed (`pool.failed_refs`), so the
  same dead reference is never retried. The Entry-16 lesson is fully preserved:
  ebook 2148 stays blocked forever.
- `fetch.usable_ref` + `worker.eligible` now skip un-fetchable candidates
  BEFORE ingest, so a missing id no longer creates a history row at all.

Effect on the real DB, verified: 6 stories recovered as re-proposable (incl.
The Tell-Tale Heart, the Entry-16 casualty) while all 6 dead refs stay blocked.
No rows deleted — the append-only rule held; the fix was in what we *read*, not
what we erase. This deliberately changes the Entry-16 test's assertion, which
now documents both halves rather than the title-blacklist alone.

### Gate status

Worker mechanism PROVEN end-to-end on the real library: `python -m
pipeline.worker` acquired The Russian Sleep Experiment, rendered it with real
Kokoro to **12.2 min / 30 paragraphs / am_adam** (Grace's settings default
voice reaching the worker path — AMENDMENT_05 A), status ready, unread 0 → 1.
The AMENDMENT_06 progress bar tracked it live at 13/30 — confirming the bar
covers worker-driven NEW renders, not only re-renders.

The gate ("queue returns to 3") CANNOT close on the current pool: it is now
empty, and refilling costs a paid curation batch, which is Grace's decision
alone (AMENDMENT_04 A). Phase 5 stays [IN PROGRESS]. Also owed: her phone check
of highlight tracking, and a live before/after curation diff for the channel-edit
gate (tests prove it at the prompt level).

**Pool quality is the real finding**: 5 of 6 candidates from the paid batches
were unusable. Before spending again, the curation prompt should require
verifying that a Gutenberg id is a STANDALONE edition and that a creepypasta
page actually contains the story — the current prompt asks for the former and
Sonnet still got it wrong 2 of 2 times.

Measurements invalidated by this change: none. Offsets, cost baselines, iOS
rules untouched. Acquisition order changed from arbitrary-within-a-second to
strictly monotonic — no prior measurement depended on the old behavior.
