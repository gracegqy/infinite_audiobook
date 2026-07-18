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
