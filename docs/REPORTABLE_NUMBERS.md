# REPORTABLE_NUMBERS — horror_readaloud

> The ledger required by `_META_working_knowledge/NUMBERS_PROTOCOL.md`. **This file is
> the only place a number is declared ready-to-report (RTR).** A figure quoted to a
> recruiter, in an application, in `README.md`, or on a résumé must cite a row here whose
> gates re-passed *in the session that quotes it*. Everything else is UNVERIFIED — including
> figures that appear in STATE.md, JOURNAL.md, or a previous session's chat.
>
> **Derivation script:** `bash scripts/repo_stats.sh` (committed — G1 requires that a number
> be reproducible from on-disk artifacts by a script, not by a session snippet).
> Copy figures from its output. Never retype one.
>
> Created 2026-07-30 (Entry 39), when the README made these numbers outbound for the first
> time.

## Rows

### R1 — Source lines of code, tracked at HEAD

| | |
|---|---|
| **Quantity** | Lines in git-tracked source files (`.py`, `.jsx`, `.css`, `.html`, `.sh`) at HEAD. Grain = physical lines incl. blanks and comments; denominator = files tracked by git, so gitignored `data/`, `.venv/`, `node_modules/`, `dist/` are excluded. **Includes** `pre_design_probes/` (794) and `tests/` (3,171). |
| **Value** | **11,107** at commit `b9b8704` (of which probes 794, tests 3,412) |
| **Class** | MEASUREMENT |
| **Derivation** | `bash scripts/repo_stats.sh` → `source-lines-total` |
| **Gate evidence** | ran `bash scripts/repo_stats.sh` 2026-08-09 at commit `b9b8704`, saw `source-lines-total:11107`, `of-which-probes:   794`, `test-lines:        3412`, `clean-worktree:    yes` |
| **Invalidated by** | any commit that adds or removes source files (i.e. constantly). Re-run before every quote. |
| **Last sent** | never |
| **Status** | **RTR 2026-08-09** — as-of-commit must be stated with the figure |

**Conditioning (G5):** LOC is a size signal, not a quality one, and this figure is
*generous* to itself — it counts throwaway probe scripts and blank lines. Quote it with its
composition or not at all. The README deliberately points at the script instead of freezing
a number in prose.

**Reconciliation (G4) — a prior figure did not reproduce.** `internship_application/PORTFOLIO_TODO.md`
(2026-07-29) records **10,654 tracked LOC across 93 files**. The file count reproduces exactly
(93). The line count **does not**: the same repo content at the same commit (`a681ec2`, no
commits between the two measurements) yields **10,753** under this row's definition — a gap of
99 lines that no tested variation of the file set explains (excluding probes → 9,959;
excluding `.html` → 10,582; excluding `.css` → 10,523; none is 10,654). The 2026-07-29
derivation was not scripted, so it cannot be re-run — NUMBERS_PROTOCOL §3 cause 3, exactly.
**Therefore: 10,654 is SUPERSEDED and must not be quoted.** This row's value, from the
committed script, is canonical.

**Movement since the 2026-07-30 gate reconciles exactly (G4).** 10,836 at `575ab9a` →
**11,107** at `b9b8704`. `git diff --numstat 575ab9a HEAD` over this row's extension list
gives **+296 / −25 = +271**, which is the whole difference and nothing else: `test_backup.py`
+182, `test_worker.py` +60/−1, `worker.py` +39/−18, `budget.py` +10/−3, `server.py` +5/−3 —
the four fix commits of 2026-08-09. The tests component moves +241 by the same arithmetic
(3,171 → 3,412). The three intervening commits (`268d4cb`, `73325c2`, `e40bdd4`) touched only
`.md` files, which this row excludes by definition. Worktree clean at the gate run.

The 2026-07-30 movement, retained: **10,753** at `a681ec2` (session start) →
**10,836** at `575ab9a`, the difference being this session's own commits (the env-var scrub,
`README.md`, `LICENSE`, and `repo_stats.sh`; only the `.sh` and `.py` changes enter this
figure — `.md` files do not). At the moment the script was run for the gate evidence above,
the only uncommitted file in the tree was `docs/REPORTABLE_NUMBERS.md` itself, which is `.md`
and therefore excluded from `source-lines-total` by definition; the figure is unaffected.

### R2 — Automated tests

| | |
|---|---|
| **Quantity** | Test cases collected and passing under `pytest` at repo root. Grain = pytest test items (parametrized cases count individually), not test functions or files. |
| **Value** | **282 collected, 282 passing** at commit `b9b8704` |
| **Class** | MEASUREMENT |
| **Derivation** | `.venv/bin/python -m pytest -q` (count also in `scripts/repo_stats.sh` → `tests-collected`) |
| **Gate evidence** | ran `.venv/bin/python -m pytest -q` 2026-08-09, saw `282 passed, 1 warning in 20.30s`; `repo_stats.sh` agrees at `tests-collected:     282` |
| **Invalidated by** | any test added/removed; any dependency bump that changes collection |
| **Last sent** | never |
| **Status** | **RTR 2026-08-09** — as-of-commit must be stated with the figure |

**Movement (G4):** 267 → 282 = the 15 tests added on 2026-08-09 (3 in `test_worker.py`
covering the `--loop` body, 12 in the new `test_backup.py`). No test was removed or renamed.

**Conditioning (G5):** these are unit and round-trip tests over pure logic (offset math, queue
replenishment, resume/progress, rating aggregation, serialization) plus FastAPI route tests.
**They do not test the TTS engines, the live API calls, or iOS Safari playback** — those are
covered by phone-over-Tailscale gates recorded in JOURNAL, not by pytest. A green suite is not
a claim that the system works end to end.

### R3 — "No story text, audio, or secret was ever committed"

| | |
|---|---|
| **Quantity** | Boolean over all commits on all branches: whether any path under `data/` or matching `.env` was ever ADDED. Grain = git object history, not working tree. |
| **Value** | **CONFIRMED — none, ever** |
| **Class** | MEASUREMENT |
| **Derivation** | `bash scripts/repo_stats.sh` → `never-committed` (script exits 1 if it ever fails) |
| **Gate evidence** | re-passed 2026-08-09 at commit `b9b8704` (`bash scripts/repo_stats.sh`, exit 0): `never-committed:   CONFIRMED — no data/ or .env path was ever added in any commit on any branch`. First passed 2026-07-30. |
| **Invalidated by** | any commit that adds such a path; any history rewrite |
| **Last sent** | never |
| **Status** | **RTR 2026-08-09** — this row is *invalidated by every subsequent commit*, so today's pass does **not** discharge the pre-flip run: **re-run immediately before flipping the repo public** (PORTFOLIO_TODO P0 #7) |

**Conditioning (G5):** this checks *paths*, not content. It proves `data/` and `.env` were
never added; it does not prove no secret was ever pasted into some other file. That is the
`/security-review`'s job (PORTFOLIO_TODO P0 #3), which is still owed.

### R4 — Curation cost per pool build

| | |
|---|---|
| **Quantity** | USD billed per `--build-pool` run at `POOL_BATCH_SIZE = 40`, by `curation_mode`. Grain = one pool build; denominator = the 40-candidate batch actually run in production. |
| **Value** | `free` **$0** · `free_llm` **$0.0512** · `llm` **~$2.40** (the last is an ESTIMATE) |
| **Class** | MEASUREMENT (`free`, `free_llm`) / ESTIMATE (`llm`) |
| **Derivation** | `NOT SCRIPTED — must be scripted before next RTR.` Source: the `curation_runs` ledger row for Entry 37's build. |
| **Gate evidence** | **none re-passed this session** |
| **Invalidated by** | `POOL_BATCH_SIZE`, `curation_model`, provider pricing (Sonnet 5 intro pricing ends 2026-08-31 — figures before Entry 28 are list price and ~32% high), web-search fee schedule, prompt-cache hit rate |
| **Last sent** | never |
| **Status** | **UNVERIFIED** — seeded honestly per NUMBERS_PROTOCOL §5. Do not quote outward. |

**Why it is here while unverified:** cost-per-batch is the most quotable number in the project
("cut curation cost 47× by replacing a paid search path with a free source registry") and is
therefore the most likely to travel by accident. It gets a row so the row can say *no*.

### Historical experimental figures (the class the README quotes most)

`README.md` §The measurement story quotes results from specific curation runs: A/A′/B title
differences (1 / 8 / 7), Lovecraft picks (7/12 → 7/12 → 0/12, then 11/12), the stored profile
length (760 chars), the unused-alternatives check (~92 of 120 offered), and the profile
shrinking from 16 reported tags to 5.

These are **HISTORY-class**: each describes one completed run under a configuration that is
named beside it, and a completed run's result does not drift. NUMBERS_PROTOCOL G3 permits
this — *"a number describing a superseded config is reportable only as history, labeled as
such"* — and every one is cited to its JOURNAL entry (34, 35, 37, 38) in the text.

They get no individual rows because they are not re-derivable without re-running paid
curation. **The rule that follows: they may be quoted only with their entry citation and only
in the past tense.** Any of them restated as a current property of the system (e.g. "the taste
profile changes 8 of 12 picks") becomes an unverified present-tense claim and needs its own
row and its own re-run. The Phase 6 re-gate at batch 40 will produce exactly such a number.

---

## Standing rules for this project

1. **Before any outbound draft** (README, application, résumé, email): open this file, re-run
   `scripts/repo_stats.sh`, and either re-pass the row's gates or cut the number.
2. **Never retype a figure.** Copy from script output. No arithmetic, rounding, or unit
   conversion in prose — extend the script instead.
3. **A discrepancy is never "noise."** Two values for one quantity → reconcile to exactly
   zero and name the cause, or mark the number UNVERIFIED and stop. R1 is the worked example.
4. `README.md` is now an outbound document. Any number added to it needs a row here first.
