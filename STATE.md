# STATE — horror_readaloud        Reconciled through JOURNAL Entry 33 · 2026-07-28

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
| 5 — Queue + sync + channels | DONE | Queue self-heals to 3 (AMENDMENT_02); sync visible on phone | **all 3 gate criteria PASSED.** queue: unread 1→3/3 in one worker cycle, 15 rows/15 distinct titles (Entry 27) · phone highlight: Grace (Entry 26) · channel-edit diff: excluding Lovecraft/cosmic horror dropped exactly those 2 titles and replaced them, $0.0264 (Entry 32). Scrubber re-confirmed by Grace. Close review done, 4 resilience bugs fixed + spend guard added (Entry 33); 200 tests green |
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

Phase 5 is CLOSED. Phase 6 (preference adaptation) is the next phase — nothing
blocks starting it.

**Needs Grace (not blocking Phase 6):**

1. **Pick a curation mode in Settings.** Three exist (Entry 32), each labelled
   with its cost, and the free modes list which sources cover the active
   channel. `free` = $0, no model call, but ordering within a source is
   arbitrary. `free_llm` = **$0.0176 measured**, model picks from the free
   shortlist, balance enforced in code — this is the recommended default for
   routine refills. `llm` = ~$2 at the coded batch of 40, and the only mode that
   reaches beyond the registered sources (r/nosleep etc.).
   Currently `free` (her stored `catalog`, aliased). The **paid path is now
   guarded**: a build estimated over $1.00 aborts unless re-run with
   `--yes-spend` (Entry 33), so the old ~$2 footgun is closed.
2. **An independent `/code-review` pass** when convenient. Entry 33's review was
   Claude's own read of code Claude had just written — the weakest kind. It found
   and fixed 4 real defects, but a second pair of eyes is worth having.

**Standing debts (no deadline):**

3. Entry-16: edge-tts fallback granularity, vocab-genre coupling. (The
   source-class registry half is paid off — `pipeline/sources.py`, Entry 32.)
   Entry-21: two fuzzy title-match semantics (mark.py vs pool.find_candidate) —
   centralize on the third user; curation-prompt exclusion list grows with
   all-time history (an R11 cost lever, and now only on the `llm` path).
4. Free-source residuals (Entries 29, 32): a Gutenberg collection with an
   innocent title ("The Parenticide Club") still passes the title and shelf
   filters — the length gate catches it at verify time, and `free_llm` now
   backfills from spares, so it costs a spare rather than a slot. Cheap next
   step if it recurs: a paragraph-count heuristic on the fetched text.
5. Free-source reach: only `gutenberg-catalog` and `creepypasta-wiki` are
   registered. r/nosleep and non-English modern fiction need either `llm` mode
   or a new adapter. Supply is finite — 514 classics + 200 modern ≈ 240 worker
   cycles.

## Library

15 story rows; 9 rendered. Listening state re-read from the DB 2026-07-28
04:12 UTC (Entry 32), not from prose — Grace listened heavily during the
session and finished three stories:

- **read (7):** Yellow Wallpaper 32.2 (rated 5) · Monkey's Paw 21.5 (rated 5) ·
  Owl Creek Bridge 19.7 · **Willows 107.1** · Russian Sleep Experiment 12.2 ·
  **Ben Drowned 54.4** · **Squidward's Suicide 9.9**
- **in_progress (2):** Damned Thing 18.0 at 15:33 · Smile Dog 11.3 at 2:20
- **ready — THE QUEUE IS EMPTY, 0/3.** All three stories that filled it in
  Entry 27 have been consumed. Replenishment is due: the worker can render the
  3 remaining pool candidates at $0, after which the pool is empty too.
- **failed:** Tell-Tale Heart (550 KB Poe collection, Entry 16) + 5 others —
  all now re-proposable by title (Entry 24)

Unfinished ≠ disliked: the two in_progress are unrated because Grace hasn't
finished them, so they carry no Phase-6 signal (Entry 22).

Pool: 3 verified candidates left (The Backrooms, The Rake, NoEnd House) — enough
for one more worker cycle at $0, but **all three are creepypasta**, so that
cycle renders no classics. A `free_llm` pool build (~$0.02) would restore the
mix; not run, because the mode is Grace's to pick. Voice gallery: 11 samples in
data/voice_samples/. Settings rows actually present in the DB:
`default_voice.en` = am_adam · `curation_mode` = **`catalog`**, written
2026-07-28 03:54 when Grace tried the selector — the Entry-32 alias resolves it
to `free`, so the live server now reports `free`. Worth confirming that is what
she wants rather than a leftover from testing the dropdown. `curation_model`
has no stored row and resolves to the code default `claude-sonnet-5`.

## Spend to date (R11)

Ledger total $4.81 across 4 curation runs, but the first three used list price —
**actually billed ≈ $3.3** (Sonnet 5 intro pricing to 2026-08-31, Entry 28).
Run 4 was the first with caching: $0.2259. One run's cost is **unrecorded** — the
70-minute run killed in Entry 29 never wrote a ledger row (that was the bug);
estimated under $0.50 but not verifiable, so it is not counted above.

**Not in the live ledger:** Entry 32's verification runs cost **$0.0594** of
real API calls ($0.0154 first free_llm build + $0.0176 after the quota/spares
fix + $0.0264 for the channel-edit A/B). They ran against `HR_DATA_DIR`
sandboxes, so their `curation_runs` rows are in sandbox DBs, not this one.
Recorded here rather than dropped.

Per-batch cost by mode (measured, 2026-07-28): `free` $0 · `free_llm` **$0.0176**
for 12 candidates · `llm` ~$2.40 at the coded batch of 40 (~$0.75 at 12).

## Open decisions

None. (AMENDMENT_05 A/B were flipped BINDING and implemented in Entry 21.)

Curation cost (Entries 28-29, superseded for the routine path by Entry 32):
prompt caching serves ~93% of input from cache on the `llm` path, so a paid
batch runs ~$0.23 at size 8 instead of ~$1.05. Search budget scales with batch
size (3/candidate, ceiling 150) — which is why the coded batch of 40 costs
~$2.40, not $0.23. Pause-turn loop is capped at 12 turns and records spend even
when aborted. Batch API verified to work with web search + caching (50% discount
available, but a paused batch cannot be resumed). All cost figures before Entry
28 are list-price and ~32% high (Sonnet 5 intro pricing runs to 2026-08-31).

Free curation (Entry 32): `pipeline/sources.py` is a registry of free sources
that DECLARE which channels they cover — Gutenberg's catalog (any genre,
public-domain) and the creepypasta wiki's PotM + Spotlighted Pastas categories
(horror/en only, 209 pages, refs are page titles so they cannot be wrong). A
channel no source covers raises `NoFreeSource` naming the reasons; it never
returns an empty pool and never falls back to the paid path. Classics/modern
balance is enforced in code (`curate.apply_class_quotas`), not asked for in a
prompt — the prompt lost that fight three times (Entries 27, 28, 32).

Exclusion rule (Entry 24): a TITLE is excluded from future curation once we
have the story or Grace decided on it; a failed REF is excluded forever but
its title stays available. 6 titles recovered, 6 dead refs blocked.

DESIGN FROZEN v1.0; AMENDMENTS 01–05 FULLY BINDING (Entries 18, 21);
06 BINDING + implemented (Entry 22).
