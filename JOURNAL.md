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

Trigger/reasoning: fresh scaffold from `~/Code/*META_working_knowledge/new_proj_claude_bank/`
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
