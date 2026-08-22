# TASKS — infinite_audiobook

Phase blocks with artifact-checkable gates. A gate that can't be answered gets redesigned,
never skipped. Statuses: `not started · [IN PROGRESS] · DONE (evidence)` — a DONE without
recorded evidence is a bug. Keep this file pristine in structure; annotate statuses only.

---

## Phase 0 — Scaffold   · Owner: Claude Code (review: Grace)
**Goal:** Governed, versioned, remotely-backed empty project.
**Actions:** folder tree; seed CLAUDE/STATE/JOURNAL/TASKS/REQUIREMENTS + docs; .gitignore;
.claude/settings.json allowlist; git init + commit; private remote + push; smoke test.
**Output:** this repo, pushed.
**Gate:**
- [x] `git log` shows initial commit (`0f138ca`); `git status` clean (2026-07-18).
- [x] `.gitignore` proven: touched `data/library/x.mp3` + `.env`, `git add -A && git
      status --short` listed neither (2026-07-18).
- [x] Private remote exists: GitHub API returned `HTTP 201, gracegqy/horror_readaloud
      private: True` (the repo's name until the 2026-08-09 rename, and private until
      publication — evidence is left as it was recorded); `git push -u origin main` succeeded, `## main...origin/main` clean;
      `git config user.email` = graceguqianying@uchicago.edu (2026-07-18).
- [x] Smoke test run: `python3 --version` → 3.12.12; `node --version` → v25.8.1
      (2026-07-18).
- [x] STATE.md + CLAUDE.md reviewed by Grace — approval given in session, recorded
      JOURNAL Entry 4 (2026-07-18).
- [x] JOURNAL Entry 1 written (and Entry 2 for the channels amendment).

## Phase 1 — Pre-design probes   · Owner: Claude Code
**Status: DONE (2026-07-18)** — all six probes answered with recorded evidence in
pre_design_probes/probe_results.txt (gate-status block); probe 5 closed on Grace's four
phone reports (JOURNAL Entry 11); one explicit deferral with risk note (sustained ≥5-min
backgrounding → re-tested by the Phase 4 gate). Findings promoted to STATE Confirmed
findings; JOURNAL Entries 5–11.
**Goal:** Kill the assumptions the architecture rests on, with throwaway scripts in
`pre_design_probes/`. **No design work until each is confirmed, corrected, or explicitly
deferred with a risk note.**
**Actions — answer each with a script + recorded result:**
1. **Kokoro on this Mac:** installs? synthesis speed (× realtime)? quality on horror prose
   (Grace listens to ≥2 min)? quality on one non-English sample (channels amendment)?
2. **Chunked synthesis:** per-paragraph render + concat — audible seams? do computed
   offsets match the concatenated audio within ~100 ms?
3. **Curation signal:** can Claude + web search produce 10 horror candidates with checkable
   reputation evidence (named lists/video essays/ratings) and correct public-domain vs.
   modern classification? Spot-check 3 by hand.
4. **Fetch + clean on ~10 real samples per source class:** Gutenberg plain text; Reddit
   (r/NoSleep) via JSON API; creepypasta wiki. Boilerplate stripping, chapter/paragraph
   segmentation, dedup keys.
5. **Phone playback reality:** static test page served from the Mac → iOS Safari over
   Tailscale: range-request seeking, lock-screen/Media-Session controls, backgrounded
   playback, resume. This decides how much PWA work Phase 4 needs.
6. **OpenAI TTS fallback:** 1-call render of one paragraph; cost recorded.
**Output:** `pre_design_probes/probe_results.txt` + findings promoted into STATE.md.
**Gate:** all six answered with evidence; STATE "Confirmed findings" updated; JOURNAL entry.
> Prompt: *"Read STATE.md, JOURNAL.md, TASKS.md Phase 1. Run the six probes in order,
> throwaway code in pre_design_probes/, results in probe_results.txt. Stop and flag if
> Kokoro quality or iOS playback fails — those change the architecture."*

## Phase 2 — Design   · Owner: Both (Grace signs off)
**Status: DONE (2026-07-18)** — Grace signed off DESIGN v0.3 in session (JOURNAL
Entry 15); DESIGN.md frozen v1.0; AMENDMENTS 02/03 BINDING; §11 traceability maps
R1–R15 with explicit deferrals.
**Goal:** Frozen DESIGN.md: architecture, SQLite schema (stories, channels, progress,
bookmarks, ratings, tags), library layout on disk, curation prompt design, negative spec.
**Actions:** draft from probe results; schema checklist from bank 09-B (nullable over
required for LLM-extracted fields; `_present`-style flags; provenance/source URL on every
story; controlled tag vocabulary with verbatim labels kept); write "What This Is Not"
(e.g., no accounts, no social, no recommendations beyond Grace's ratings, no cloud
content, no per-listen API calls); resolve queue-per-channel open decision.
**Output:** docs/DESIGN.md (frozen; later changes = amendment docs + journal line).
**Gate:** Grace sign-off recorded in JOURNAL; every REQUIREMENTS.md row maps to a design
element or an explicit ⚠️ deferral.
> Prompt: *"Read STATE, JOURNAL, probe_results.txt, REQUIREMENTS.md. Draft DESIGN.md per
> TASKS Phase 2; walk me through the schema and negative spec before freezing."*

## Phase 3 — Pipeline MVP   · Owner: Claude Code
**Status: DONE (2026-07-18)** — pipeline/ complete, 39 tests green, Yellow Wallpaper
rendered + mechanically spot-checked (0 ms drift), /code-review done (10 findings
fixed; 3 angles owed at Phase 4 close, Entry 16). Gate closed on Grace's verdict:
"Phase 3 gate passed" (Entry 17). Post-gate: AMENDMENT_04 flow (pool curation at $0,
pre-marking, abort-on-skip, voice re-render) implemented same day.
**Goal:** One story end-to-end: curate → fetch → clean → tag → synthesize → library entry.
**Actions:** implement pipeline/ stages against the frozen schema; per-paragraph synthesis
with offsets manifest; SQLite writes; unit tests for chunking/offset math; round-trip test
for meta + offsets serialization.
**Output:** `data/library/<story>/` with text, meta, audio, offsets; tests green.
**Gate:** run pipeline on a fresh story chosen by the curator → playable audio file Grace
listens to; `pytest` green; offsets spot-checked at 3 paragraphs (audio at offset matches
text). `/verify` before the closing commit.
> Prompt: *"Read STATE, JOURNAL, DESIGN.md. Build Phase 3 per TASKS; end with the gate run
> on one fresh story."*

## Phase 4 — Player MVP   · Owner: Claude Code
**Status: DONE (2026-07-18)** — GATE PASSED on the phone over Tailscale, Grace's
words as evidence: scrub/±skip/lock-screen exercised in her test session;
"killing safari mid-play reopened with the audio progress saved" (kill+reopen
resume); "1. >5min backgrounding worked properly" — retiring probe 5's deferred
≥5-min-backgrounding risk (Entries 20–21). Built: app/server.py + React PWA per
DESIGN §6 + AMENDMENTS 04 D / 05 (voice gallery + pickers, settings screen,
skip-vs-read, unskip, clear rating, synced text follow); 71 tests green;
/code-review on Phase 4 diffs (5 findings fixed, Entry 19) + the 3 Phase-3
angles owed from Entry 16 run at close (1 minor fix, Entry 21); her 10+1
feedback items all implemented (AMENDMENT_05 C).
**Goal:** Spotify-like player usable on phone + laptop.
**Actions:** FastAPI serving library + audio (range requests) + progress API; React PWA:
library list, play/pause, ±15 s, scrubbable timeline, story select, text view; resume
position persisted server-side (SQLite), restored on load; Media Session metadata.
**Output:** app/ running via one runbook command.
**Gate:** on the **phone over Tailscale**: start a story, scrub, ±15 s, background the
app ≥5 min, kill and reopen → resumes within 2 s of pause point. Evidence in JOURNAL.
`/code-review` before phase close.
> Prompt: *"Read STATE, JOURNAL, DESIGN.md. Build Phase 4 per TASKS; gate is on my phone,
> tell me when you need me to test."*

## Phase 5 — Queue automation, sync, channels UI   · Owner: Claude Code
**Status: DONE (2026-07-28)** — worker + channels editor built; 200 tests green.
**ALL THREE gate criteria PASSED:** queue self-healed 1→3/3 in one cycle,
artifact-verified with no all-time title repeats (Entry 27); phone highlight
tracking confirmed by Grace (Entry 26); channel-edit curation diff run live in
free_llm mode — excluding Lovecraft/cosmic horror dropped exactly the two
Lovecraft titles and replaced them, $0.0264 for both halves (Entry 32). Grace
confirmed the scrubber still drags after the view lock. Close review done
(Entry 33): 4 resilience defects found and fixed — a single failing source no
longer kills a whole build, a failed cache refresh falls back to the stale
index, MediaWiki title normalization no longer risks a KeyError, and
/api/settings survives a missing active channel. A spend guard now aborts any
paid build estimated over $1.00 without `--yes-spend`.
Caveat on that review: it was Claude's own read of code Claude wrote the same
session, not the `/code-review` harness command (unavailable as a skill). An
independent pass is listed in STATE.
The Entry-28 paid-path prompt rebalance is still unverified end-to-end and is
now unlikely to be — free_llm reaches the same goal structurally (Entry 32), so
the paid prompt matters only for reach beyond the registered free sources.
Bugs found and fixed across this phase: arbitrary acquisition order (now
`rowid`), failed references blacklisting real story titles (refs and titles now
excluded separately), the sticky player's hardcoded 52 px offset against a 63 px
header, and — the serious one — `run_curation`'s `while True:` pause-turn loop
with the cost ledger written only after it exited, i.e. unbounded AND invisible
spend (now capped at 12 turns and always ledgered).
Curation economics reworked (Entries 28-29, 32): prompt caching serves ~93% of
input from cache ($1.05 → $0.23 per batch) and the search budget scales with
batch size. Then Entry 32 removed the need for search on the routine path — a
registry of free sources (`pipeline/sources.py`) supplies verified references
and reputation as fields, so three modes now sit in Settings: `free` ($0),
`free_llm` (**measured $0.0176** for 12 candidates), and `llm` (~$0.75, the only
one that reaches beyond the registered sources).

**Goal:** The self-sustaining part of the brief.
**Actions:** replenishment worker (unread < 3 → curate/fetch/synthesize; dedup against
full history so nothing repeats); paragraph-level text highlight synced to playback via
offsets; bookmarks; channel criteria editor UI (create/edit channels; switching channels
re-targets the queue); read/in-progress/unread status tracking.
**Output:** worker + UI features; unit tests for replenishment + dedup logic (clock/queue
state injected).
**Gate:** mark 2 stories read → within one worker cycle library returns to 3 unread
(AMENDMENT_02 supersedes the brief's 5 — `config.QUEUE_DEPTH`), no
title repeats all-time (checked against history table); highlight visibly tracks audio on
phone; a channel edit demonstrably changes the next curation batch.
> Prompt: *"Read STATE, JOURNAL, DESIGN.md. Build Phase 5 per TASKS; run the queue gate
> end-to-end and show me the worker log."*

## Phase 6 — Preference adaptation   · Owner: Claude Code   · **DONE**
**Goal:** Ratings steer curation (brief item 4).
**Actions:** 1–5 rating UI; per-tag aggregation (author, era, subgenre, themes, origin,
language); taste profile injected into curation prompt; trends viewable in UI.
**Output:** rating flow + weighted curation; aggregation unit-tested.
**Gate:** seed contrasting ratings on ≥6 stories → next curation batch's tag distribution
shifts toward liked tags (shown by diffing two curation runs' candidate lists).

**GATE PASSED (Entry 35), with a control run.** Sandboxed A/A′/B over one shortlist:
two no-profile runs differ by **1** title (the noise floor); the profile run differs from
them by **7–8**. Lovecraft picks go **7/12 → 0/12** when the profile is applied, replaced
by ghost/gothic stories (Benson, Crawford, Middleton, Chambers) — matching `weird` 1.0/5
against `gothic`/`19th-century`/`folk` 5.0/5. $0.0595.

Built: `pipeline/taste.py` (shrunk-mean ranking, raw-average display, discriminating-kind
rule, rating floor), injection into both curation paths, persistence to
`curation_runs.taste_profile_text`, `/api/taste` + Trends screen, and manual overrides
(`taste_overrides`: adjust / add / suppress / revert). 243 tests green.

**The control is the lesson.** The first attempt (Entry 34) read as a pass — 3/12 titles
changed — until a second no-profile run showed the diff was noise. Any future re-run of
this gate MUST include one.

Phone target confirmed by Grace at close (Entry 36): the 6-tab header renders cleanly —
the tightened 430/380px breakpoints hold, and the sticky player's `--header-h` offset
survived the tab that broke it once before.

**Known limit, carried forward:** creepypasta candidates carry no author, year or theme
(2 distinct evidence strings across all 36), so the profile can only discriminate among
them by title. Enriching that source is unclaimed work, not a Phase 6 debt.

## Phase 7 — Hardening & audit   · Owner: Both
**Goal:** Close the drift gap; make the system survivable across gaps.
**Actions:** complete RUNBOOK.md (cold start, Tailscale, key rotation, **plus: installing
the scheduler, setting the spend cap, turning on off-machine backup**); **backup: DONE
in Entry 37 — `pipeline/backup.py` (moved from scripts/ so the worker can drive it),
off-machine copy verified at the destination but OFF by default and opt-in via Settings;
scheduled by the worker loop on `backup_interval_s`. `data/library/` is deliberately NOT
backed up — it is regenerable from the DB, the DB is not**;
`/security-review` (server bound to Tailscale interface only; no key ever
reaches the frontend); commission a fresh-session read-only audit re-deriving STATE claims
from artifacts; fix or journal every finding. Also owed here: an independent
`/code-review` pass — Entry 33's was Claude reviewing its own same-session code.
**Gate:** audit report exists; every severe finding fixed or explicitly risk-accepted in
JOURNAL; cold-start test from the runbook alone succeeds.
**[IN PROGRESS]** Entry 39 landed the public-readiness work — README.md, MIT LICENSE,
`$HR_TAILSCALE_IP`/`$HR_CONTACT_EMAIL` replacing committed machine-specific values,
`scripts/repo_stats.sh`, and `docs/REPORTABLE_NUMBERS.md`. This does not advance the
Phase 7 gate; it served publication, which has since happened (see STATE).
Entry 37 landed the scheduler, spend cap and backup half.
**Entry 38 completed RUNBOOK.md** and paid off the per-tag evidence floor. Still owed:
independent `/code-review` (now ~1750 lines of same-session code across Entries 33–38,
and Grace must run it — it is blocked on being a fresh session), `/security-review`,
fresh-session audit, and **the cold-start test from the runbook alone — the literal
gate, never run**.
**Status update 2026-08-09 (Entries 40–42):** fresh-session audit DONE 2026-08-07
(report in the private working-knowledge repo; FIXES executed, Entry 40) · independent
`/code-review` DONE (Entry 42 — fresh session, review completed before any writes;
fixes at `f1394e9`) · still owed: `/security-review` and the cold-start test. Phase 6 also re-opened: its gate ran at batch 12, production is
batch 40, and Entry 38's floor changed the profile the re-gate would measure (see
STATE next-action 2 — Grace rules before any re-gate spend).
> Prompt: *"Fresh session, read-only: audit infinite_audiobook. Trust nothing in prose;
> re-derive every STATE/TASKS claim from artifacts. Report gaps."*

**`/security-review` prompt (written 2026-08-22, Entry 49; still owed).** Paste verbatim into
a fresh session. It is long on purpose: it names this project's real surfaces, so the review
starts from the code rather than from a generic checklist, and it lists what has already been
risk-accepted so the report is not padded with them.

> Fresh session, read-only until I say otherwise. Run /security-review on
> infinite_audiobook (~/Code/ACTIVE/infinite_audiobook). Read CLAUDE.md, STATE.md and the
> newest JOURNAL entries first, then work from artifacts — run things, do not trust prose,
> including this prompt.
>
> WHAT THIS IS. A self-hosted read-aloud fiction library on my Mac: an LLM curates short
> fiction, a Python pipeline fetches and cleans it, local TTS narrates it, and a FastAPI
> server serves a React PWA to my phone over Tailscale. Sole user, no accounts, no auth.
> The repo is PUBLIC (github.com/gracegqy/infinite_audiobook); the data is not.
>
> THREAT MODEL, in priority order.
> 1. Untrusted input from the open web reaching code that acts. Curation is model output;
>    story text and source URLs come from Gutenberg and wiki pages. That data reaches
>    urllib fetches, filesystem paths, subprocess arguments, SQL and the browser. This is
>    the review's centre of gravity.
> 2. Anything that could turn tailnet-reachable into internet-reachable, or leak a key.
>    scripts/serve.sh must refuse to start rather than guess a bind address; keys live in
>    .env and must never reach the frontend, a log, or an error body.
> 3. Spend. Paid paths are reachable from unauthenticated HTTP on the tailnet. A bug that
>    uncaps or bypasses pipeline/budget.py costs real money.
>
> SURFACES I ALREADY KNOW ABOUT — start here, then go past this list, and tell me if the
> list itself is wrong:
> - pipeline/fetch.py:25 `_get` — urllib.request.urlopen on URLs the curation model chose.
>   Redirects, non-http schemes, SSRF into the tailnet or localhost, response size.
> - app/server.py:120 and :132 — subprocess.Popen spawning detached jobs; `story_id` and
>   `channel_id` become argv and log filenames (`rerender_{story_id}.log`).
> - app/server.py:208 and every other `{sid}` route — `library_dir / sid / ...`. Traversal
>   appears to be blocked incidentally, because `story_or_404` hits the DB first, not by a
>   path check. Verify that holds on EVERY route that builds a path from a URL parameter,
>   and say whether an incidental guard is good enough.
> - pipeline/db.py:199 and :439 — f-string SQL building column lists and placeholders.
>   Establish whether those fragments can ever come from outside a whitelist.
> - pipeline/synthesize.py:65 and :197 — subprocess into afconvert with paths.
> - app/server.py:571 (paid build), :710 (PUT /api/settings rewrites the spend cap) —
>   unauthenticated on the tailnet by design. Check the cap cannot be raised, bypassed or
>   raced, and that "approve spend" cannot be forged by the client.
> - scripts/export_offline.py, scripts/export_m4b.py — write files from story text and ids.
>   Entry 49 fixed a `</script>` injection in the HTML exporter; check the fix and look for
>   siblings (the m4b exporter builds ffmetadata from titles).
> - The frontend under app/frontend/src/ — story text rendered in React. Confirm nothing
>   reaches innerHTML by any path.
>
> ALREADY ACCEPTED, do not re-report as new (argue with the ruling if you think it is
> wrong, but do it in one paragraph):
> - No authentication anywhere. Deliberate: the server binds a Tailscale interface only.
> - A CGNAT 100.x address and two of my email addresses appear in JOURNAL.md and probe
>   files, and in git history. Ruled acceptable in Entry 39.
> - edge-tts calls an undocumented Microsoft endpoint for Chinese narration.
> - Two paid calls sit outside the spend cap by documented choice (tag-at-ingest, the
>   per-story TTS fallback), pending a design ruling.
>
> HOW TO REPORT. Findings only where you can show the path from input to effect: file,
> line, the input, and what it reaches. For anything you rate high, give me a reproduction
> I can run — a curl, a crafted story file under HR_DATA_DIR, a test — not an argument.
> Rate severity against THIS deployment (one user, tailnet-only, no session to steal), not
> against a public web app; an inflated rating wastes my time and a deflated one costs me
> later, so say which way you are unsure. Explicitly list what you did NOT cover.
>
> RULES OF THIS REPO.
> - data/ is never committed. .env is never committed, never printed, never echoed into a
>   file you create. Never point a script or a browser at the live server or data/ — use
>   HR_DATA_DIR with a copy, or scripts/ui_sandbox.sh. Check whether I am listening first
>   (progress.updated_at advancing means a live client).
> - Do not fix anything during the review. Findings first, all of them, then I decide what
>   gets fixed and in what order. Entry 42 set that rule: a reviewer who starts editing
>   stops reviewing.
> - Read-only means read-only: no commits, no pushes, no launchd install, no paid API call.
>   A pool build costs money — do not trigger one.
>
> WHEN THE REVIEW IS DONE. Write the findings up as a JOURNAL entry (prepended, newest at
> top, with a "measurements invalidated by this change:" line) and a numbered FIXES list I
> can execute later, ordered by severity, each with the artifact check that will prove it
> closed. Then stop and tell me what you found before touching a line of code.
>
> This review has been owed since before the repo went public, and the repo went public
> anyway. Treat it as overdue, not as a formality — and if the honest answer is that the
> surface is smaller than the paperwork implies, say that plainly rather than manufacturing
> findings to justify the exercise.

---

## Phase 8 — Hosting migration to a tailnet host   · Owner: Both   · **CANCELLED 2026-08-20**
**CANCELLED (Entry 47).** No free tier is $0 in perpetuity — Oracle's Always Free ARM came
back quota-blocked at Limit 0, GCP's free tier deletes the instance at 90 days without a
billable account — and `$0/mo` was the binding constraint the whole plan rested on. The app
stays on this Mac. **Always-on is solved without the move:** `scripts/server-agent.sh` is the
launchd wrapper that keeps `serve.sh` answering across reboots (verified 2026-08-22:
`bash scripts/server-agent.sh status` → `loaded: yes`, `200` on the tailnet address). Two
consequences below are void as a result: the `afconvert` → `ffmpeg` port is **not needed**,
and the M5 README edits are **not owed** — nothing moved, so every line they would have
corrected is already true. The block below is left standing unedited as the record of a plan
that was made and then reversed; no item in it is live.
**Authority:** `docs/AMENDMENT_07_hosting_moves_to_a_tailnet_host.md` (2026-08-19, immutable —
it records the decision as taken then; this status records the reversal).
**Goal:** the app is reachable from Grace's phone with her laptop off — on an always-on host
joined to her tailnet, still tailnet-only, no public URL.
**Procedure:** work from `_META_working_knowledge/reference/tailnet_host_migration_CHECKLIST.md`
(self-contained, session by session); the spec beside it holds the reasoning. Do not duplicate
either here.
**BLOCKER found 2026-08-19 (Entry 46):** `pipeline/synthesize.py` calls macOS-only `afconvert`
at `:198` (encode) and `:66` (decode). This app **cannot run on a Linux host as written** — the
migration includes a port to `ffmpeg`, selected by `shutil.which` so the Mac path is unchanged.
**Gated on a probe:** whether Kokoro/misaki/spacy run on ARM Linux at all is answered in
Session 1, before any of this starts.
**Actions:** M1 measure peak render RSS + `du -sh data/` on this Mac (sizes the box) · M2
benchmark Kokoro on a trial box against this repo's measured chars/s and 6.9x-realtime
baselines · M4 move app + `data/` + `.env`, keep port 8123, keep `serve.sh`'s
refuse-to-start-without-a-Tailscale-IP behavior · re-point the scheduler launchd job —
**Grace installs it, not Claude** · M5 the README edits below.
**Gate:** a story played end to end on the phone, laptop off; `scripts/serve.sh` still
refuses to start without a resolved Tailscale IP; no public surface at any point.
**README edits owed at M5 (Grace's instruction, Entry 45) — this is the only public repo, so
these are reader-facing, and they are written after the migration is real, never before:**
`README.md:10-11` "runs on one Mac … not a hosted service" · `:45` the network row · `:154-160`
"Running it" · **`:134-135` the content-rights paragraph, where "listening on one machine
only" stops being true** — the most important of the four, because it is this repo's public
statement of its licensing posture and it must not claim a stricter one than the deployment
has. Also `docs/RUNBOOK.md` (cold start, backup destination).
**Deliberately not in scope:** auth, accounts, sharing, public URL. If any of those is ever
wanted it is a new amendment with `/security-review` in front of it.
**Host settled and free:** Oracle Cloud Always Free ARM (2 OCPU / 12 GB / 200 GB), $0/mo — so
AMENDMENT_07's retirement of the brief's `$0/mo` clause turns out unnecessary and that clause
survives. Open risk is Oracle's reliability (silent term changes, idle reclamation, ARM
capacity), not cost. Also open: what backs up the host (Entry 37's off-machine backup half was
written against this Mac).

## Standing rules applied every phase

`/verify` before nontrivial commits · `/code-review` at phase close · session-close ritual
(CLAUDE.md) every session · journal line for every scope/schema change with
"measurements invalidated:" · done = artifact-verified on the phone-over-Tailscale target.
