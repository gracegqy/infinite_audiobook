# TASKS — horror_readaloud

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
      private: True`; `git push -u origin main` succeeded, `## main...origin/main` clean;
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
**Goal:** The self-sustaining part of the brief.
**Actions:** replenishment worker (unread < 5 → curate/fetch/synthesize; dedup against
full history so nothing repeats); paragraph-level text highlight synced to playback via
offsets; bookmarks; channel criteria editor UI (create/edit channels; switching channels
re-targets the queue); read/in-progress/unread status tracking.
**Output:** worker + UI features; unit tests for replenishment + dedup logic (clock/queue
state injected).
**Gate:** mark 2 stories read → within one worker cycle library returns to 5 unread, no
title repeats all-time (checked against history table); highlight visibly tracks audio on
phone; a channel edit demonstrably changes the next curation batch.
> Prompt: *"Read STATE, JOURNAL, DESIGN.md. Build Phase 5 per TASKS; run the queue gate
> end-to-end and show me the worker log."*

## Phase 6 — Preference adaptation   · Owner: Claude Code
**Goal:** Ratings steer curation (brief item 4).
**Actions:** 1–5 rating UI; per-tag aggregation (author, era, subgenre, themes, origin,
language); taste profile injected into curation prompt; trends viewable in UI.
**Output:** rating flow + weighted curation; aggregation unit-tested.
**Gate:** seed contrasting ratings on ≥6 stories → next curation batch's tag distribution
shifts toward liked tags (shown by diffing two curation runs' candidate lists).
> Prompt: *"Read STATE, JOURNAL, DESIGN.md. Build Phase 6 per TASKS; demonstrate the gate
> with a before/after curation diff."*

## Phase 7 — Hardening & audit   · Owner: Both
**Goal:** Close the drift gap; make the system survivable across gaps.
**Actions:** complete RUNBOOK.md (cold start, Tailscale, key rotation, backup of SQLite +
library); `/security-review` (server bound to Tailscale interface only; no key ever
reaches the frontend); commission a fresh-session read-only audit re-deriving STATE claims
from artifacts; fix or journal every finding.
**Gate:** audit report exists; every severe finding fixed or explicitly risk-accepted in
JOURNAL; cold-start test from the runbook alone succeeds.
> Prompt: *"Fresh session, read-only: audit horror_readaloud. Trust nothing in prose;
> re-derive every STATE/TASKS claim from artifacts. Report gaps."*

---

## Standing rules applied every phase

`/verify` before nontrivial commits · `/code-review` at phase close · session-close ritual
(CLAUDE.md) every session · journal line for every scope/schema change with
"measurements invalidated:" · done = artifact-verified on the phone-over-Tailscale target.
