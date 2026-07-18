# STATE — horror_readaloud        Reconciled through JOURNAL Entry 10 · 2026-07-18

> PURE CURRENT STATE. No history (JOURNAL's job), no session summaries. Superseded content
> is DELETED, not annotated.

## Phase table

| Phase | Status | Gate | Gate evidence (command/check + result) |
|---|---|---|---|
| 0 — Scaffold | DONE | Scaffold gate (TASKS.md §0) | all items re-verified from artifacts 2026-07-18 (Entry 3); Grace review approved (Entry 4) |
| 1 — Pre-design probes | IN PROGRESS | All 6 probe questions answered in probe_results.txt | 1, 2, 3, 4, 6 answered with recorded evidence (probe_results.txt, Entries 5–9); 5: resume retest passed (Entry 9), awaits only lock-screen / ≥5-min backgrounding / speed-selector reports |
| 2 — Design | not started | DESIGN.md frozen; Grace sign-off | — |
| 3 — Pipeline MVP | not started | One story end-to-end, playable audio + offsets | — |
| 4 — Player MVP | not started | Full listen on phone over Tailscale | — |
| 5 — Queue + sync + channels | not started | Queue self-heals to 5; sync visible on phone | — |
| 6 — Preference adaptation | not started | Curation demonstrably weighted by ratings | — |
| 7 — Hardening | not started | Fresh-session audit + runbook complete | — |

## Confirmed findings

- Sourcing = classics + modern web fiction, private-use only; TTS = Kokoro-local first
  with OpenAI fallback; hosting = Mac + Tailscale; Anthropic + OpenAI keys exist
  (interview, docs/BRIEF_VERBATIM.md).
- Pipeline is channel-driven (editable genre/language/topic criteria), not
  horror-hardcoded (docs/AMENDMENT_01).
- Git identity/remote conventions: personal repos use account `gracegqy`, identity
  Grace / graceguqianying@uchicago.edu (verified across ACTIVE repos, `git config` +
  `git remote -v`). GitHub credential present in macOS keychain (`git credential fill`
  returned a password for github.com).
- Kokoro runs locally at ~6.9x realtime (probe 1, 2026-07-18); per-paragraph
  synthesis + concat gives exact offsets (probe 2, energy-check verified). Quality
  verdict pending Grace's listen.
- Curation signal is real: named checkable reputation lists for both classic and
  NoSleep channels; PD/modern classification correct on 3 hand spot-checks (probe 3).
- Gutenberg + creepypasta-wiki fetch/clean work (with empty/deleted-page validation
  needed); Reddit anonymous JSON API is dead — OAuth app or HTML parsing required
  (probe 4; decision in Phase 2).
- Kokoro "random pauses" bug root-caused: newline-split chunking from hard-wrapped
  input text, fixed by whitespace normalization (probe 1b). Design constraint: clean
  stage must unwrap lines within paragraphs. Grace re-listens to *_fixed.* files.
- OpenAI TTS fallback confirmed working: $0.004/paragraph, ~$0.32/30-min story
  (probe 6, 2026-07-18).
- Tailscale installed on Mac + iPhone; Mac Tailscale IP 100.117.147.107. Probe 5
  server running on it (page 200, range 206 re-verified from Mac, Entry 9).
- iOS resume works on the real target: kill Safari + reopen resumes at saved position,
  scrubbing works (Grace retest, Entry 9). Design rules: apply resume seeks
  loadedmetadata-or-later, never at page init; AND on `ended`, clear/complete the
  resume position and mark the story read — never persist end-of-file as a resume
  point (Entry 10: a finished story "resumed" to its end, causing instant
  ended→pause that looked like broken playback).
- .env exists with both keys (verified gitignored).

## Next actions

1. Grace: finish probe 5 on iPhone Safari (http://100.117.147.107:8765/, server
   running; page fixed for the resume-to-end bug) — reload the page first. Checks:
   (a) on open, look for the log line "saved position … at the end — restarting
   from 0" (this both confirms the auto-pause diagnosis and proves the story
   played to its end while backgrounded); (b) play → tap the lock screen: story
   title shown? play/pause and ±15s work from there? (c) speed selector at 1.5x
   or 2x: audibly faster? log line "ratechange" with the new rate? (d) one more
   kill+reopen MID-story to confirm mid-story resume still works on the fixed
   page. Report all four.
2. On those three reports: close Phase 1 gate (all six probes answered), start
   Phase 2 design (carry in: line-unwrap clean rule, resume-after-loadedmetadata
   iOS rule, Reddit OAuth-vs-HTML decision, curation cost levers — $1.65/batch at
   Opus needs trimming toward pennies, Media-Session scope per probe-5 findings).

## Open decisions

- Queue semantics under multiple channels: one global queue of 5 vs. 5 per active channel
  (Phase 2; default assumption = queue of 5 for the active channel).
- Frontend PWA offline caching of audio (nice-to-have; decide in Phase 4).
