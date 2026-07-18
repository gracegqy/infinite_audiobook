# JOURNAL — horror_readaloud (append-only; corrections are new entries, never edits)

## Entry 1 — 2026-07-18 — Project scaffolded

Decisions (from Grace's brief + interview, verbatim in docs/BRIEF_VERBATIM.md):
- **Sourcing:** public-domain classics + modern web horror, strictly private-use; content
  never publicly deployed, never committed to git.
- **TTS:** Kokoro locally as primary (free), OpenAI TTS as per-story fallback. Plan:
  per-paragraph synthesis + concatenation so chunk offsets give text↔audio sync for free.
  Both are Phase 1 probe subjects, not yet verified facts.
- **Hosting:** FastAPI + SQLite on Grace's Mac, React+Vite PWA frontend, phone access via
  Tailscale. $0/mo target; only LLM-curation pennies and optional fallback TTS cost money.
- **Preference adaptation (brief item 4) assessed feasible and cheap:** Claude tags each
  story at ingest (~$0.01), ratings aggregate per tag in SQLite, curation prompt receives
  the taste profile. No ML training, no measurable UI latency.
- Governance: lean app stack (CLAUDE/STATE/JOURNAL/TASKS + REQUIREMENTS traceability)
  per CLAUDE_BANK 09; brief is feature-dense enough to warrant the requirements table.

Trigger/reasoning: fresh scaffold from `~/Code/*META_working_knowledge/new_proj_claude_bank/`
(00_GENERATOR + 09_SCAFFOLDER), interview answers in BRIEF_VERBATIM.md §Interview.

Measurements invalidated by this change: none (nothing measured yet).

## Entry 2 — 2026-07-18 — Spec amendment: customizable channels

Grace asked mid-scaffold whether the pipeline could be a customizable scraper
(genre/language/topic editable in the UI) instead of horror-specific. Assessed at ~10–15%
extra work since curation was already criteria-driven LLM work; accepted. Encoded as the
**channel** abstraction (docs/AMENDMENT_01_customizable_channels.md): editable criteria
record in SQLite, default channel = the horror brief, no "horror" hardcoding outside that
config row. Accepted costs: genre-specific fetchers added incrementally; non-English
Kokoro quality added to Phase 1 probes.

Measurements invalidated by this change: none (nothing measured yet).
