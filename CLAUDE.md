# CLAUDE.md — infinite_audiobook

At session start, read STATE.md and JOURNAL.md, then the current phase in TASKS.md, before
acting.

## What this is

A self-hosted "personal audiobook Spotify" for Grace (sole user): a criteria-driven
pipeline finds highly-reputed short fiction (default channel: classic + modern horror),
stores clean text, narrates it with local TTS, and serves it through a web app — resume
positions, text synced to audio, bookmarks, 1–5 ratings that steer future curation, a
standing queue of 3 unread stories (AMENDMENT_02 supersedes the brief's 5 — the single
copy is `config.QUEUE_DEPTH`). Runs on Grace's Mac, reached from laptop/phone via
Tailscale. Private, personal-use only.

## Stack & domain facts (keep current — stale entries here have caused real damage)

- Python + FastAPI + SQLite; frontend React+Vite PWA served statically by FastAPI. All
  state lives in SQLite + `data/library/` on disk.
- TTS: Kokoro locally (free) is primary; OpenAI TTS is the per-story fallback. Audio is
  synthesized per-paragraph and concatenated — the chunk offsets are what powers
  text↔audio sync. Both facts pending Phase 1 probe confirmation.
- Curation is LLM-driven (Anthropic key) against editable **channel** criteria
  (genre/language/topic — see docs/AMENDMENT_01). Never hardcode "horror" anywhere except
  the default channel's config row.
- Content rights posture: classics = public domain; modern web fiction = author-owned,
  stored for private listening only. Never deploy content publicly; never commit story
  text or audio to git.
- API keys live in `.env` (gitignored). Remote: private repo `gracegqy/infinite_audiobook`,
  identity Grace / graceguqianying@uchicago.edu.

## Folder map

```
CLAUDE.md STATE.md JOURNAL.md TASKS.md REQUIREMENTS.md
docs/                # BRIEF_VERBATIM.md + AMENDMENT_*.md (immutable authority), RUNBOOK.md, DESIGN.md (Phase 2)
pre_design_probes/   # throwaway scripts + probe_results.txt — no authority after Phase 1
pipeline/            # curate → fetch → clean → synthesize
app/                 # FastAPI server + web frontend
data/                # NEVER COMMITTED. library/ = per-story text+audio+meta; interim/ = scratch
tests/               # pure-logic unit tests, round-trip tests — exist from day one
scripts/             # one-off tools
```

## Standing rules (never violate)

- **Done = artifact-verified.** A status flips only with the command/check that proves it,
  recorded next to the status ("ran X, saw Y"). Before telling Grace something works,
  re-derive it from the artifact (run it, count it, diff it), never from prose.
- "Working" is defined on the real target: **phone over Tailscale**, not desktop
  localhost. iOS Safari audio behavior is part of every player-facing gate.
- `data/` is never committed; `docs/BRIEF_VERBATIM.md` and amendment docs are never
  edited; `pre_design_probes/` carries no authority after Phase 1.
- Log every plan/scope/schema change in JOURNAL.md with date + reason + a
  "measurements invalidated by this change:" line.
- An unanswerable verification gate is redesigned (tooling/tests), never skipped. If Grace
  proposes moving past an unanswered gate, push back once, explicitly.
- Pure logic (queue replenishment, chunk-offset math, resume/progress, rating aggregation)
  gets unit tests the day it's written. Time-dependent behavior takes `now`/clock as a
  parameter. Every serialized shape (story meta, progress records, offsets manifest) gets
  a `decode(encode(x)) == x` round-trip test.
- Centralize on the second copy of any logic or constant (model IDs, chunk sizes,
  queue depth), not the third.
- **Never point browser automation, probes, or throwaway scripts at the live server or
  `data/`.** Use `scripts/ui_sandbox.sh` (a DB snapshot on 127.0.0.1) or `HR_DATA_DIR`.
  And before restarting the app server or writing to `data/app.db`, check whether Grace
  is listening — `progress.updated_at` advancing means a live client (Entry 26).
- **Never "repair" Grace's data on a hypothesis.** Her listening state is real user data:
  establish the cause from artifacts first (is a client live? can the code even produce
  this?), and prefer leaving a suspicious value alone over overwriting it. A wrong repair
  destroys the evidence that would have corrected the diagnosis.
- Standing checkpoints: `/verify` before nontrivial commits · `/code-review` before a
  phase closes · `/security-review` before the server listens beyond Tailscale (or any
  auth/proxy change) · one fresh-session audit mid-project.

## Session-close ritual (every working session, ~3 minutes)

1. **JOURNAL entry** for anything decided or changed (with the "measurements invalidated"
   line where applicable). JOURNAL.md is **reverse chronological** — PREPEND the new
   entry directly under the header block, never append to the bottom.
2. **STATE reconciled** — next-actions current, completed items deleted, "reconciled
   through Entry N" stamp updated. If STATE wasn't touched, say so explicitly rather than
   assuming it still holds.
3. **Commit and push.** Uncommitted work at session end is work that a sync accident or
   machine loss erases.
4. **If mid-task**, mark it `[IN PROGRESS]` in TASKS.md with a one-line note of where
   things stand — the next session re-inspects rather than assumes.

---
Rules distilled from `~/Code/_META_working_knowledge/claude_bank/`; when a rule
chafes or a new lesson lands, improvements flow back to the bank (per its 08 protocol).
