# STATE — horror_readaloud        Reconciled through JOURNAL Entry 24 · 2026-07-27

> PURE CURRENT STATE. No history (JOURNAL's job), no session summaries. Superseded content
> is DELETED, not annotated.

## Phase table

| Phase | Status | Gate | Gate evidence (command/check + result) |
|---|---|---|---|
| 0 — Scaffold | DONE | Scaffold gate (TASKS.md §0) | all items re-verified from artifacts 2026-07-18 (Entry 3); Grace review approved (Entry 4) |
| 1 — Pre-design probes | DONE | All 6 probe questions answered in probe_results.txt | All six answered (probe_results.txt gate block; Entries 5–11); probe 5 closed on Grace's four phone reports; one deferral w/ risk note (≥5-min backgrounding → Phase 4 gate) |
| 2 — Design | DONE | DESIGN.md frozen; Grace sign-off | Grace signed off v0.3 in session ("I sign off DESIGN v0.3", Entry 15); DESIGN header now FROZEN v1.0; AMENDMENTS 02/03 flipped to BINDING; §11 traceability covers R1–R15 |
| 3 — Pipeline MVP | DONE | One story end-to-end, playable audio + offsets | Grace: "Phase 3 gate passed" (Entry 17); Yellow Wallpaper READY, 32 tests green, offsets 0 ms drift, spot-check OK (Entry 16) |
| 4 — Player MVP | DONE | Full listen on phone over Tailscale | GATE PASSED on phone: Grace's kill+reopen resume report (Entry 20) + "1. >5min backgrounding worked properly" (Entry 21) — probe-5 backgrounding deferral retired; 71 tests; /code-review complete incl. the 3 owed Phase-3 angles |
| 5 — Queue + sync + channels | [IN PROGRESS] | Queue self-heals to 3 (AMENDMENT_02); sync visible on phone | worker + channels editor built, one real cycle proven (Russian Sleep Experiment acquired + rendered 12.2 min, unread 0→1, Entry 24); gate blocked on an empty pool (paid refill = Grace's call) + her phone highlight check |
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
- iOS lock-screen/Media-Session controls work: title shows, skip buttons perform the
  handler's ±15s (icons cosmetically show Apple's default "10s"); playbackRate honored
  (R13 viable). Sustained ≥5-min backgrounding deferred w/ risk note to the Phase 4
  gate (Entry 11).
- iOS resume works on the real target: kill Safari + reopen resumes at saved position,
  scrubbing works (Grace retest, Entry 9). Design rules: apply resume seeks
  loadedmetadata-or-later, never at page init; AND on `ended`, clear/complete the
  resume position and mark the story read — never persist end-of-file as a resume
  point (Entry 10: a finished story "resumed" to its end, causing instant
  ended→pause that looked like broken playback).
- .env exists with both keys (verified gitignored).
- TTS is per-language config, all gates decided (probe 1c, Entries 12–14):
  en = Kokoro · fr = Kokoro ff_siwis (passed) · zh = edge-tts zh-CN-YunxiNeural
  (Grace's "verdict a", Yunxi > Xiaoxiao; Kokoro zh rejected — "weird accents";
  edge-tts caveats accepted: $0 cloud call, undocumented endpoint, degrade rule =
  OpenAI TTS per story on failure) · ja untested, out of scope. edge-tts currently
  installed only in the probe venv — pipeline env must add it (Phase 3).

## Next actions

1. **Grace: decide on a paid pool refill.** The pool is empty and the queue sits
   at 1/3, so the worker has nothing left to acquire. `python -m
   pipeline.run_story --build-pool` is the only way forward and it costs money
   (last two batches: $0.90 and $2.13). Recommend first tightening the curation
   prompt — 5 of 6 candidates from those batches were unusable (stub wiki pages,
   collection ebook ids), so a refill on the current prompt would waste much of
   the spend.
2. **Grace: phone gate for Phase 5** — highlight visibly tracking audio over
   Tailscale (the code ships; only the phone check is owed). Server at
   http://100.117.147.107:8123 (`scripts/serve.sh` to restart). The Russian
   Sleep Experiment (12.2 min) is queued and unplayed.
3. Owed to close Phase 5: live before/after curation diff for the channel-edit
   gate (tests prove it at the prompt level); `/code-review` on the Phase 5 diff.
4. Owed near Phase 5: Entry-16 debts (source-class registry, edge-tts fallback
   granularity, vocab-genre coupling) + Entry-21 notes (two fuzzy title-match
   semantics in mark.py/pool.find_candidate — centralize on the third user;
   curation-prompt exclusion list grows with all-time history, an R11 cost
   lever).
5. `/code-review` on the AMENDMENT_06 + Phase 5 diffs at phase close.

## Library

6 story rows; 5 rendered (Entries 18–19, listening state as of 2026-07-19,
Entry 22): Monkey's Paw 22.0 min kokoro/am_adam **read, rated 5** · Yellow
Wallpaper 32.2 kokoro/af_heart **read, rated 5** · Owl Creek Bridge 20.9
af_heart in_progress 13.9 min · Damned Thing 18.0 af_heart in_progress 4.9 ·
Willows 107.1 af_heart in_progress 1.4. Unfinished ≠ disliked — the three
in_progress are unrated because Grace hasn't finished them (Entry 22), so
they carry no Phase-6 signal. Tell-Tale Heart is `failed` (the 550 KB Poe
collection fetch, Entry 16) — now re-proposable (Entry 24). Russian Sleep
Experiment 12.2 min kokoro/am_adam **ready, unplayed** (worker-acquired).
**1 unread against a depth of 3; candidate pool empty.** Voice gallery:
11 samples in data/voice_samples/. Settings: `default_voice.en` = am_adam.

## Open decisions

None. (AMENDMENT_05 A/B were flipped BINDING and implemented in Entry 21.)

Exclusion rule (Entry 24): a TITLE is excluded from future curation once we
have the story or Grace decided on it; a failed REF is excluded forever but
its title stays available. 6 titles recovered, 6 dead refs blocked.

DESIGN FROZEN v1.0; AMENDMENTS 01–05 FULLY BINDING (Entries 18, 21);
06 BINDING + implemented (Entry 22).
