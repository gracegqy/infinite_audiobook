# STATE — infinite_audiobook        Reconciled through JOURNAL Entry 42 · 2026-08-09

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
| 6 — Preference adaptation | **RE-OPENED** | Curation demonstrably weighted by ratings | Entry 35 passed a controlled A/A′/B **at batch 12** (noise 1 title, effect 7–8; Lovecraft 7/12 → 0/12). **Entry 37 showed that does not describe production**: the first real build at `POOL_BATCH_SIZE = 40` took **11 of 12** Lovecraft. Mechanism works at the top of the ranking, does not exclude at depth. Grace ruled: record + **re-gate at batch 40** (not yet done) |
| 7 — Hardening | **in progress** | Fresh-session audit + runbook complete | Entry 37 landed the scheduler, the spend cap, and the off-machine backup half (now opt-in). **RUNBOOK completed Entry 38** (cold start / rotation / restore written but NOT executed — the cold-start test IS the gate). **Fresh-session audit DONE 2026-08-07** (`_META_working_knowledge/project_reports/8.7.26_horror_readaloud/`); its FIXES executed Entry 40 — 4 of 5 closed, FIX-5 is a decision on Grace. **Independent code review DONE 2026-08-09** (Entry 42 — fresh session, review completed before any writes; its own fixes, commit `f1394e9`, are the only unreviewed remainder: small, test-covered). Still owed: `/security-review`, cold-start test |

## Confirmed findings

- Sourcing = classics + modern web fiction, private-use only; TTS = Kokoro-local first
  with OpenAI fallback; hosting = Mac + Tailscale; Anthropic + OpenAI keys exist
  (interview, docs/BRIEF_VERBATIM.md).
- Pipeline is channel-driven (editable genre/language/topic criteria), not
  horror-hardcoded (docs/AMENDMENT_01).
- Git identity/remote conventions: personal repos use account `gracegqy`, commit
  identity Grace / gracegumails@gmail.com (this repo's `git config user.email`,
  verified 2026-08-09; the 24 commits from 2026-07 carry graceguqianying@uchicago.edu —
  accepted for publication, Entry 39). GitHub credential present in macOS keychain
  (`git credential fill` returned a password for github.com).
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
- Tailscale installed on Mac + iPhone. The Mac's Tailscale IP is no longer a
  committed constant (Entry 39) — `serve.sh` resolves it via `tailscale ip -4`,
  falls back to `$HR_TAILSCALE_IP`, and **exits 2 rather than guess** if neither
  is available. Probe 5 server ran on it (page 200, range 206 re-verified from
  Mac, Entry 9).
- iOS lock-screen/Media-Session controls work: title shows, skip buttons perform the
  handler's ±10s (AMENDMENT_05 C1 aligned the handler with Apple's default lock-screen
  icons, superseding the probe-era ±15s); playbackRate honored (R13 viable). Sustained ≥5-min backgrounding deferred w/ risk note to the Phase 4
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

Phase 7 is in progress; Phase 6 is re-opened (its gate does not describe
production). Queue is healthy — 3/3 ready, 29 in the pool — so **nothing in the
build track is time-sensitive.**

**But there is now a dated external track (Entry 39).** This repo is the P0 of
`~/Code/ACTIVE/internship_application/PORTFOLIO_TODO.md`: it must be public, with
a link delivered into a dated application packet by **Aug 9** (which packet: that
file — the codename stays out of this soon-public doc; Entry 39 still names it,
which is Grace's append-only ruling to make). That file is the authority for the
publication checklist; do not duplicate it here. Its Claude-able items are
**done** (README, LICENSE, the env-var scrub, the numbers ledger; Entry 42 added
the independent code review + fixes and the README restructure). What remains is
Grace's by rule and blocks the flip:

- **`/security-review`, in a fresh session** — the app drives HTTP fetches, file
  writes and subprocess TTS from model output, and no review has covered that
  surface (Entry 42's swept secrets, history and binding only). The independent
  `/code-review` half is DONE (Entry 42).
- **Screenshots + a ~60s screen recording from the phone.** Nobody can run this
  repo, so visuals are the only evaluation a reader gets. `README.md` carries a
  `<!-- SCREENSHOTS -->` block ready to uncomment; shot list is inside it.
  Start the server first.
- **Flip public, then verify from logged-out** — and re-run
  `bash scripts/repo_stats.sh` as the final gate: its `never-committed` check is
  the one that proves no story text, audio or `.env` was ever committed.

**Any number leaving this project** — README, résumé, application — now goes
through `docs/REPORTABLE_NUMBERS.md` first. Entry 39 seeded it and it immediately
superseded a wrong LOC figure that had already been drafted into an application.

1. **RULE ON THE THIN PROFILE (Entry 38).** The evidence floor fixed `weird` but
   cut the profile from 16 reported tags to 5, and the liked side from 8 to
   **one** (`supernatural`, n=4). It is now nearly dislike-only. Options:
   (a) state the real preferences by hand from Trends — gothic, cosmic horror —
   which bypass the floor and are used verbatim; (b) rate more stories and let
   it refill; (c) lower `TASTE_MIN_N_PER_TAG`, which re-admits the defect.
   **(a) is the recommendation, and it gates item 2.**
2. **Re-gate Phase 6 at batch 40** (Grace's ruling, Entry 37). Same A/A′/B
   design as Entry 35, run at `POOL_BATCH_SIZE`, sandboxed via `HR_DATA_DIR`.
   ~$0.15. **Do item 1 first** — re-gating a nearly-dislike-only profile
   measures a weaker instrument than Entry 35 used and would not be comparable.
3. `/security-review`, then the **cold-start test from the RUNBOOK alone** —
   that last one is the literal Phase 7 gate and has never been run. (The
   fresh-session audit is DONE, 2026-08-07, and its fixes are executed; the
   independent code review is DONE, Entry 42.)
4. **RULE ON FIX-5 (Entry 40).** Tag-at-ingest (~$0.01/story) and the OpenAI
   TTS fallback (~$0.32/story) spend on the worker's path without passing
   through `budget.check` or the `curation_runs` ledger. Options: (a) leave
   them documented-but-outside, which Entry 40's wording edits already do;
   (b) ledger-only, so spend is visible but not gated; (c) full cap coverage,
   which needs a ruling on what a cap-exhausted TTS fallback does to a
   renderable story. B/C need a JOURNAL spec first and possibly an AMENDMENT.
   The task text is in `FIXES_HORROR_READALOUD.md`.
5. **Decide where snapshots live (Entry 40).** `backup.BACKUP_DIR` is rooted at
   the repo, not under `DATA_DIR`, so `HR_DATA_DIR` does not redirect it — a
   sandboxed `worker --loop` now writes sandbox snapshots into the real
   `backups/`. Unfixed on purpose: it is a judgement call whether snapshots
   belong to the machine or to the dataset.
6. **Open ruling: the profile displays the raw average, and the model reads the
   display** (Entry 38). Shrinkage protects the ranking only, so a lone 1 still
   arrives looking like the strongest dislike. Fixing it means rendering the
   shrunk figure — which contradicts FROZEN DESIGN §8 ("display the raw one")
   and therefore needs an AMENDMENT, not a scope call. The evidence floor
   mitigates it (surviving tags have small raw-vs-shrunk gaps) but does not
   remove it.

(The former item 1, the independent `/code-review`, is DONE — Entry 42; items
renumbered.)

**Standing debts (no deadline):**

1. **PAID OFF (Entry 38)** — `taste.has_evidence` + `config.TASTE_MIN_N_PER_TAG
   = 2`. `weird` no longer reaches the profile. **The deeper half is NOT fixed
   and no floor can fix it:** a 1–5 rating conflates "this story was badly made"
   with "I dislike this kind of story", and only the second belongs in a taste
   profile. Separating them needs a second signal from the player — a design
   decision, not a tuning one. Also unfixed and feeding this: the tagger emits
   near-duplicate themes, so one story (The Monkey's Paw) produced eleven
   overlapping n=1 theme rows.
2. **Off-machine backup is OFF.** The code half landed (Entry 37,
   `pipeline.backup`, verified at the destination) but it is **opt-in by
   design** — nothing leaves the Mac until a path is set in Settings. Local
   snapshots in `backups/` run **while a worker loop is running**, and cover
   corruption and bad migrations, **not losing the Mac**. Nothing has kept a
   loop alive (standing debt 3), and until Entry 40 the loop crashed on its
   first iteration anyway, so no automatic snapshot has ever been taken:
   every file in `backups/` is a hand-run one.
3. **Nothing schedules the worker unless Grace installs it.**
   `scripts/scheduler.sh install` exists and works (verified end-to-end: launchd
   → loop → acquire → render, unbuffered log) but it **refuses to run
   non-interactively** and Claude must never run it. Until Grace runs it, the
   queue only advances when a worker is run by hand.
4. Entry-16: edge-tts fallback granularity, vocab-genre coupling. (The
   source-class registry half is paid off — `pipeline/sources.py`, Entry 32.)
   Entry-21: two fuzzy title-match semantics (mark.py vs pool.find_candidate) —
   centralize on the third user; curation-prompt exclusion list grows with
   all-time history (an R11 cost lever, and now only on the `llm` path).
5. Free-source residuals (Entries 29, 32): a Gutenberg collection with an
   innocent title ("The Parenticide Club") still passes the title and shelf
   filters — the length gate catches it at verify time, and `free_llm` now
   backfills from spares, so it costs a spare rather than a slot. Cheap next
   step if it recurs: a paragraph-count heuristic on the fetched text.
6. Free-source reach: only `gutenberg-catalog` and `creepypasta-wiki` are
   registered. r/nosleep and non-English modern fiction need either `llm` mode
   or a new adapter. Supply is finite — 514 classics + 200 modern ≈ 240 worker
   cycles.

## Library

20 story rows; 20 distinct titles (no all-time repeats). Re-derived from the DB
at Entry-37 close.

- **read (9):** Yellow Wallpaper 32.2 (rated 5) · Monkey's Paw 21.5 (rated 5) ·
  Owl Creek Bridge 19.7 · Willows 107.1 · Russian Sleep Experiment 12.2
  (rated 2) · Ben Drowned 54.4 (rated 3) · Smile Dog 11.3 (rated 2) ·
  Squidward's Suicide 9.9 (rated 1) · The Backrooms 5.3
- **in_progress (2):** Damned Thing 18.0 at 15:33 · The Rake 6.5 at 4:17
- **ready (the queue, 3/3):** NoEnd House 24.0 · The Fall of the House of Usher
  39.2 · The Cask of Amontillado 12.9 (the last two acquired in Entry 37)
- **failed (6):** Tell-Tale Heart · Candle Cove · Ted the Caver · Jeff the
  Killer · Yellow Sign · Music of Erich Zann. All re-verified live in Entry 34
  as correct rejections. **Do not delete them** — `pool.failed_refs` reads these
  rows to keep dead references out of curation; deleting would re-open Entry 16.

**Queue is healthy: 3/3 ready, 29 usable candidates in the pool** (Entry 37's
build; both re-derived from the DB at Entry-38 close). The worker never
initiates *curation* spend, so the refill after that stays an explicit
`run_story --build-pool` — now also gated by the spend cap. It is **not** a $0
path: tag-at-ingest (~$0.01/story, DESIGN §5) and the OpenAI TTS fallback
(~$0.32/story) are paid calls on the worker's path, and both sit outside the
cap and outside the `curation_runs` ledger (Entry 40). **Read the pool order before trusting it:**
ranks 4–14 are eleven consecutive Lovecraft titles, which is the Entry-37
finding, not a queue fault.

**The server IS running** as of Entry 42 (`lsof -i :8123` → LISTEN on the
Tailscale IP, re-checked 2026-08-09 evening) — but it predates the Entry-42
server.py changes and the Player.jsx fixes, so **restart it (and rebuild the
frontend) before the portfolio screenshots**. No live listener at the Entry-40
check: `progress` unwritten since 2026-07-28 06:04 (sampled twice, 45 s apart).
The Trends tab (and so every manual taste override) needs the server up, as do
the screenshots.

**Newest DB snapshot: `backups/app-20260809-190545.db`** (Entry 40, hand-run,
local only — 20 stories / 2 progress / 6 ratings, integrity ok). Before it the
newest was 2026-07-28.

**6 ratings, with real contrast** (1,2,2,3,5,5) — enough for the Phase 6 floor
of 3. Unfinished ≠ disliked: the two in_progress are unrated because Grace
hasn't finished them, so they carry no Phase-6 signal (Entry 22).

Voice gallery: 11 samples in data/voice_samples/. Settings rows in the DB:
`default_voice.en` = am_adam · `curation_mode` = **`free_llm`** (Grace's choice,
set 2026-07-28 via `PUT /api/settings`, verified through
`db.effective_curation_mode`) · `spend_cap_usd` = **8.00** · `spend_cap_period`
= month (both set Entry 37 — 8.00 not 2.00 because the rolling window already
holds $4.86 of July's `llm` experiments; lower it after ~2026-08-27).
`curation_model`, `worker_interval_s`, `backup_interval_s` and
`backup_offsite_dir` have no stored rows and resolve to their code defaults
(`claude-sonnet-5`, 900 s, 86400 s, and OFF respectively).

## Taste (Phase 6)

The live profile, re-rendered at Entry-38 close, **after** the evidence floor:

```
liked: supernatural [subgenre] (3.8/5, n=4)
disliked: contemporary [era] (2.0/5, n=3), found-footage [subgenre] (2.0/5, n=3),
creepypasta [theme] (2.0/5, n=3), psychological-deterioration [theme] (2.0/5, n=2)
```

Five reported tags, every one with ≥2 stories behind it. `language` and `origin`
are correctly absent — one distinct value each across the rated set.

**⚠ This is honest but nearly dislike-only.** `weird 1.0/5` is gone (the Entry-37
complaint is fixed), but so are gothic · 19th-century · early-20th · folk ·
Gilman · Jacobs · descent-into-madness — all were n=1. The profile now says what
to avoid and almost nothing about what to seek. 40 held-back tags remain visible
in a collapsed section on Trends, one tap from being corrected: **a manual score
bypasses the floor and is used verbatim, never shrunk.** See next-action 2.

`taste_overrides` is **empty** — everything shown is computed. Grace can adjust
any score, add a tag the ratings never produced, suppress one they did, or
revert to automatic, from the Trends tab. A manual score is used verbatim (never
shrunk) and is labelled "set by the listener" in the prompt.

**Only `free_llm` and `llm` can use any of this** — `free` makes no model call,
so there is nowhere to put a profile. The Trends screen says so when the mode
cannot use it.

## Spend to date (R11)

Ledger total $4.81 across 4 curation runs, but the first three used list price —
**actually billed ≈ $3.3** (Sonnet 5 intro pricing to 2026-08-31, Entry 28).
Run 4 was the first with caching: $0.2259. One run's cost is **unrecorded** — the
70-minute run killed in Entry 29 never wrote a ledger row (that was the bug);
estimated under $0.50 but not verifiable, so it is not counted above.

**Not in the live ledger:** Entry 32's verification runs cost **$0.0594** of
real API calls ($0.0154 first free_llm build + $0.0176 after the quota/spares
fix + $0.0264 for the channel-edit A/B); Entry 34's first Phase-6 gate cost
**$0.0568**; Entry 35's re-run under the class floor cost **$0.0595** (A $0.0186
· A′ control $0.0179 · B $0.0230). All ran against `HR_DATA_DIR` sandboxes, so
their `curation_runs` rows are in sandbox DBs, not this one. Recorded here
rather than dropped — **$0.1757 of sandbox spend to date.**

Per-batch cost by mode (measured, 2026-07-28): `free` $0 · `free_llm`
**$0.0512 at the production batch of 40** (Entry 37 — this is the number that
matters; the earlier $0.0176 was per-12 and is not what production runs) ·
`llm` ~$2.40 at the coded batch of 40 (~$0.75 at 12).

**A spend cap is now enforced** (Entry 37): rolling window over the
`curation_runs` ledger, checked before every paid path including `free_llm`.
Currently $8.00/month with $4.8562 spent and $3.1438 remaining. `pipeline
.budget.status()` is the single source for both the readout and the guard.

## Open decisions

**Self-heal + budget: SETTLED and built** (Grace approved, Entry 37), with one
binding constraint — **no hardcoded numbers**; every knob is a settings row she
can change and apply at any time.

- **(i) scheduler — built, NOT installed.** `scripts/scheduler.sh` writes a
  launchd job whose only duty is keeping `worker --loop` alive; the cadence is
  `worker_interval_s`, re-read every cycle, so changing it in Settings applies
  on the next tick with no reinstall. Verified end-to-end (launchd → loop →
  acquire → render, unbuffered log — `-u` is load-bearing or the log stays
  empty for hours). **Grace installs it; Claude must not** — it refuses a
  non-interactive install.
- **(ii) spend cap — built and enforced.** `pipeline/budget.py`, rolling window,
  checked before every paid path *including* `free_llm`. Verified refusing a
  build (exit 4, $0 spent).
- **(iii) auto `--build-pool` — NOT built, and needs an AMENDMENT, not a scope
  call.** It contradicts AMENDMENT_04 A, which is BINDING: *"paid pool builds
  are rare, large, and Grace-initiated only… never an automatic build."* The
  honest path is AMENDMENT_07 superseding 04-A. Cheaper alternative that needs
  no amendment: let the scheduler run `--build-pool` on a visible cadence Grace
  sets, so the spend decision stays hers-by-schedule.

Still standing from the original assessment:
- **Recommended against: the API key in Settings.** DESIGN §10 forbids keys
  reaching the frontend; `data/app.db` is copied into `backups/` unencrypted, so
  this turns every snapshot into a credential. `.env` already works. (This is
  also why the Entry-37 iCloud snapshot carried no credentials.)
- **The budget cannot see the Anthropic balance** — only what this app spent, so
  a credit-exhausted API error stays a separate condition.

Settled: the classics/modern quota is a **floor of `CLASS_FLOOR = 2`**, not an
even split (Grace, Entry 35 — supersedes the Entry-32 round-robin).
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
