# STATE — horror_readaloud        Reconciled through JOURNAL Entry 34 · 2026-07-28

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
| 6 — Preference adaptation | **IN PROGRESS — gate not passed** | Curation demonstrably weighted by ratings | BUILT + 228 tests green (Entry 34). Gate FAILS its control: A vs A′ (both no-profile) differ by 2 titles, A′ vs B (profile) by 1, B rank-identical to A′ — no effect beyond noise. Profile does reach the model (B cites "19th-century gothic", "descent-into-madness"). Blocked on Grace's ruling re: the class quota |
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

Phase 5 CLOSED. Phase 6 is BUILT but its **gate is not passed** (Entry 34).

**Blocking Phase 6 — needs Grace's ruling:**

1. **Does the classics/modern quota stay fixed at 1:1?** This is the thing
   stopping ratings from steering anything. Grace rates classics 5.0 and
   creepypasta 2.0 (n=3, her best-evidenced signal); the model already ranks
   gutenberg ~2:1; `curate.apply_class_quotas` pulls it back to 1:1 every time.
   Entry 32 introduced that quota for good reason — the model lost the balance
   fight three times — so **relaxing it reverses a prior decision and is not
   Claude's to make.** Three options:
   - **(a) a floor, not a split** (e.g. ≥2 of each per batch) — variety
     preserved, taste free to move the rest. Recommended.
   - **(b) weight the ratio by the ratings** — most responsive, least
     predictable; a run of bad creepypasta ratings could starve that half.
   - **(c) keep 1:1** — accept that taste steers only *within* each half, and
     close Phase 6 on the narrower claim.
2. **Then re-run the gate with its control.** ~$0.06, sandboxed. The control
   (a second no-profile run) is not optional — without it the noise reads as a
   pass, which is exactly what happened the first time.

**Needs Grace (not blocking):**

3. **Server restart + phone check.** Deferred because she was listening when
   the work landed (Entry 34). Until it happens the running process has no
   `/api/taste`, so a reload would error in Trends only. The header now carries
   **6 tabs**; the 5-tab row already wrapped once and broke the sticky header,
   so the new 430/380px breakpoints need confirming on the phone.
4. **An independent `/code-review` pass** when convenient. Entry 33's review was
   Claude's own read of code Claude had just written — the weakest kind. It found
   and fixed 4 real defects, but a second pair of eyes is worth having.

**Standing debts (no deadline):**

1. **Backups are same-machine only.** `scripts/backup_db.py` takes a
   WAL-consistent, integrity-checked snapshot into `backups/` (gitignored,
   keeps 10) — first one taken at Entry-33 close: 18 stories, 2 progress rows,
   2 ratings. That covers corruption and bad migrations, **not losing the Mac**.
   An off-machine copy is Phase 7. Nothing runs it on a schedule yet.
2. Entry-16: edge-tts fallback granularity, vocab-genre coupling. (The
   source-class registry half is paid off — `pipeline/sources.py`, Entry 32.)
   Entry-21: two fuzzy title-match semantics (mark.py vs pool.find_candidate) —
   centralize on the third user; curation-prompt exclusion list grows with
   all-time history (an R11 cost lever, and now only on the `llm` path).
3. Free-source residuals (Entries 29, 32): a Gutenberg collection with an
   innocent title ("The Parenticide Club") still passes the title and shelf
   filters — the length gate catches it at verify time, and `free_llm` now
   backfills from spares, so it costs a spare rather than a slot. Cheap next
   step if it recurs: a paragraph-count heuristic on the fetched text.
4. Free-source reach: only `gutenberg-catalog` and `creepypasta-wiki` are
   registered. r/nosleep and non-English modern fiction need either `llm` mode
   or a new adapter. Supply is finite — 514 classics + 200 modern ≈ 240 worker
   cycles.

## Library

18 story rows; 18 distinct titles (no all-time repeats). Re-derived from the DB
at Entry-34 close — Grace listened through the session and finished two more
(Smile Dog, The Backrooms):

- **read (9):** Yellow Wallpaper 32.2 (rated 5) · Monkey's Paw 21.5 (rated 5) ·
  Owl Creek Bridge 19.7 · Willows 107.1 · Russian Sleep Experiment 12.2
  (rated 2) · Ben Drowned 54.4 (rated 3) · Smile Dog 11.3 (rated 2) ·
  Squidward's Suicide 9.9 (rated 1) · The Backrooms 5.3
- **in_progress (2):** Damned Thing 18.0 at 15:33 · The Rake 6.5 at 3:21
- **ready (the queue, 1/3):** NoEnd House 24.0
- **failed (6):** Tell-Tale Heart · Candle Cove · Ted the Caver · Jeff the
  Killer · Yellow Sign · Music of Erich Zann. All re-verified live in Entry 34
  as correct rejections. **Do not delete them** — `pool.failed_refs` reads these
  rows to keep dead references out of curation; deleting would re-open Entry 16.

**⚠ The queue is 1/3 and the pool is empty (0 candidates).** The worker cannot
self-heal — it never spends — so the next refill needs an explicit
`run_story --build-pool`. On `free_llm` that is ~$0.02 and the Entry-33 spend
guard never fires.

**6 ratings, with real contrast** (1,2,2,3,5,5) — enough for the Phase 6 floor
of 3. Unfinished ≠ disliked: the two in_progress are unrated because Grace
hasn't finished them, so they carry no Phase-6 signal (Entry 22).

Voice gallery: 11 samples in data/voice_samples/. Settings rows in the DB:
`default_voice.en` = am_adam · `curation_mode` = **`free_llm`** (Grace's choice,
set 2026-07-28 via `PUT /api/settings`, verified through
`db.effective_curation_mode`). `curation_model` has no stored row and resolves
to the code default `claude-sonnet-5`.

## Spend to date (R11)

Ledger total $4.81 across 4 curation runs, but the first three used list price —
**actually billed ≈ $3.3** (Sonnet 5 intro pricing to 2026-08-31, Entry 28).
Run 4 was the first with caching: $0.2259. One run's cost is **unrecorded** — the
70-minute run killed in Entry 29 never wrote a ledger row (that was the bug);
estimated under $0.50 but not verifiable, so it is not counted above.

**Not in the live ledger:** Entry 32's verification runs cost **$0.0594** of
real API calls ($0.0154 first free_llm build + $0.0176 after the quota/spares
fix + $0.0264 for the channel-edit A/B), and Entry 34's Phase-6 gate cost
**$0.0568** (4 selection calls: A $0.0181 · B $0.0202 · A′ control $0.0185).
All ran against `HR_DATA_DIR` sandboxes, so their `curation_runs` rows are in
sandbox DBs, not this one. Recorded here rather than dropped —
**$0.1162 of sandbox spend to date.**

Per-batch cost by mode (measured, 2026-07-28): `free` $0 · `free_llm` **$0.0176**
for 12 candidates · `llm` ~$2.40 at the coded batch of 40 (~$0.75 at 12).

## Open decisions

**One, and it blocks Phase 6: does the classics/modern quota stay 1:1?**
See Next actions item 1 — options (a) floor / (b) rating-weighted / (c) keep.
Entry 32 introduced the quota after the model lost the balance fight three
times, so relaxing it reverses that ruling and is Grace's call. Recommended:
(a) a floor of ≥2 per class, which keeps the Entry-32 guarantee (a class is
never starved) while leaving the remaining slots free to follow the ratings.

(AMENDMENT_05 A/B were flipped BINDING and implemented in Entry 21.)

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
