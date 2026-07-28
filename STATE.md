# STATE — horror_readaloud        Reconciled through JOURNAL Entry 30 · 2026-07-28

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
| 5 — Queue + sync + channels | [IN PROGRESS] | Queue self-heals to 3 (AMENDMENT_02); sync visible on phone | **queue gate PASSED** — Grace finished 2 stories, one worker cycle returned unread 1→3/3 (Ben Drowned 54.4 · Smile Dog 11.3 · Squidward's 9.9, all files present, 15 rows/15 distinct titles, Entry 27); **phone highlight gate PASSED** (Grace, Entry 26). Owed: channel-edit curation diff (needs next authorized batch) + scrubber re-check after the view lock |
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

**Needs Grace (blocking):**

1. **Confirm the scrubber still drags on the phone.** The view lock (no
   zoom/pan, Entry 26) is the one change that could plausibly have hurt it;
   everything else in her two UI reports is fixed and measured.
2. **Pick a curation mode in Settings** — both exist now (Entry 29).
   `catalog` = $0, no API call, ebook ids always correct, classics only, thin
   reputation signal (expect obscure pulp beside the canon). `llm` = ~$0.2–0.5
   per batch, verified named lists, covers creepypasta, can still get an ebook
   id wrong. Currently `llm`; nothing changed without her say.

**Owed to close Phase 5 (Claude, needs a batch — so needs her spend approval):**

3. **Verify the Entry-28 prompt rebalance end-to-end.** Never proven: the run
   that would have shown a balanced classics/modern mix is the one that exposed
   the unbounded-loop bug and was killed at 70 min. Re-run
   `run_story --build-pool` in `llm` mode (now capped at 12 turns).
4. **Channel-edit curation diff** — the last Phase 5 gate criterion. Tests prove
   the edit reaches the prompt; a live before/after batch would close it. Pair
   with #3 to spend once.
5. `/code-review` on the AMENDMENT_06 + Phase 5 + Entry 28–29 diffs at phase close.

**Standing debts (no deadline):**

6. Entry-16: source-class registry, edge-tts fallback granularity, vocab-genre
   coupling. Entry-21: two fuzzy title-match semantics (mark.py vs
   pool.find_candidate) — centralize on the third user; curation-prompt
   exclusion list grows with all-time history (an R11 cost lever).
7. Catalog mode residual (Entry 29): a collection with an innocent title
   ("The Parenticide Club") still passes both filters. Cheap next step if it
   recurs — a paragraph-count or per-story heuristic on the fetched text.

## Library

15 story rows; 9 rendered. Listening state re-read from the DB 2026-07-28
03:43 UTC (Entry 30), not from prose:

- **read:** Monkey's Paw 22.0 min am_adam (rated 5) · Yellow Wallpaper 32.2
  af_heart (rated 5) · Owl Creek Bridge 20.9 af_heart · Russian Sleep
  Experiment 12.2 am_adam
- **in_progress:** Damned Thing 18.0 af_heart at 7:36 · Willows 107.1 af_heart
  at 3:12
- **ready (the queue, 3/3):** Ben Drowned 54.4 am_adam · Smile Dog 11.3 am_adam
  · Squidward's Suicide 9.9 am_adam
- **failed:** Tell-Tale Heart (550 KB Poe collection, Entry 16) + 5 others —
  all now re-proposable by title (Entry 24)

Unfinished ≠ disliked: the two in_progress are unrated because Grace hasn't
finished them, so they carry no Phase-6 signal (Entry 22).

Pool: 3 verified candidates left (The Backrooms, The Rake, NoEnd House) — enough
for one more worker cycle at $0. Voice gallery: 11 samples in
data/voice_samples/. Settings: `default_voice.en` = am_adam · `curation_mode` =
llm · `curation_model` = claude-sonnet-5.

## Spend to date (R11)

Ledger total $4.81 across 4 curation runs, but the first three used list price —
**actually billed ≈ $3.3** (Sonnet 5 intro pricing to 2026-08-31, Entry 28).
Run 4 was the first with caching: $0.2259. One run's cost is **unrecorded** — the
70-minute run killed in Entry 29 never wrote a ledger row (that was the bug);
estimated under $0.50 but not verifiable, so it is not counted above.

## Open decisions

None. (AMENDMENT_05 A/B were flipped BINDING and implemented in Entry 21.)

Curation cost (Entries 28-29): prompt caching serves ~93% of input from cache, so
a batch runs ~$0.23 instead of ~$1.05. Search budget scales with batch size
(3/candidate, ceiling 150). Pause-turn loop is capped at 12 turns and records
spend even when aborted — it was previously unbounded AND invisible. Batch API
verified to work with web search + caching (50% discount available, but a paused
batch cannot be resumed). Catalog mode costs $0. All cost figures before Entry 28 are list-price
and ~32% high (Sonnet 5 intro pricing runs to 2026-08-31).

Exclusion rule (Entry 24): a TITLE is excluded from future curation once we
have the story or Grace decided on it; a failed REF is excluded forever but
its title stays available. 6 titles recovered, 6 dead refs blocked.

DESIGN FROZEN v1.0; AMENDMENTS 01–05 FULLY BINDING (Entries 18, 21);
06 BINDING + implemented (Entry 22).
