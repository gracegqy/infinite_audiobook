# REQUIREMENTS — horror_readaloud (working checklist)

> **Authority: derivative.** `docs/BRIEF_VERBATIM.md` + numbered amendments win; this file
> is *wrong* on any conflict. Changing any STATUS requires a JOURNAL entry. ⚠️ (rescoped)
> requires Grace's sign-off and must answer: "does the remaining subset still achieve the
> goal that motivated it?"

## Goals (the "why" every row must serve)

G1. Grace presses play and hears an excellent, well-chosen story — zero manual sourcing.
G2. The library maintains itself (queue of 5, no repeats) at ~zero marginal cost.
G3. Listening works equally well on phone and laptop, resumable mid-sentence.
G4. Over time the picks get more Grace-shaped.

## Requirement table

| # | Required item (brief ref) | STATUS | Where it lives |
|---|---|---|---|
| R1 | Automated sourcing of highly-reputed stories; high bar: many recommenders, video essays, ratings (brief §1) | ❌ not built | pipeline/ curate (Phase 3), probe 3 first |
| R2 | Stories stored as pure clean text (brief intro) | ❌ not built | pipeline/ fetch+clean (Phase 3) |
| R3 | High-quality AI narration (brief intro) | ❌ not built | pipeline/ tts (Phase 3); Kokoro probe 1 |
| R4 | Queue self-heals to 5 unread (brief §2) | ❌ not built | worker (Phase 5) |
| R5 | Accessible on mobile + laptop (brief §3.1) | ❌ not built | Tailscale + PWA (Phase 4); probe 5 first |
| R6 | Resume from last pause; read/in-progress history; no re-scraping repeats (brief §3.2) | ❌ not built | progress API + history dedup (Phases 4–5) |
| R7 | Spotify-like controls: pause/resume, ±15 s, scrubbable timeline, story select (brief §3.3) | ❌ not built | app/ player (Phase 4) |
| R8 | Text script always accessible, synced highlight with audio (brief §3.3) | ❌ not built | offsets manifest (Phase 3) + sync UI (Phase 5) |
| R9 | Bookmarks (brief §3.3) | ❌ not built | Phase 5 |
| R10 | Preference adaptation from 1–5 ratings, trend record, weighted curation (brief §4) | ❌ not built | Phase 6. **Feasibility answer: YES, cheap** — tag-at-ingest (~$0.01/story) + SQLite aggregation + prompt weighting; no ML, no UI latency |
| R11 | Economical: no exorbitant cost, no sprawl, snappy UI (brief §5) | ❌ standing constraint | $0/mo baseline (Kokoro + self-host); pennies for curation/tagging; audio synthesized once, cached forever; SQLite keeps UI reads local |
| R12 | Channels: genre/language/topic editable in UI (AMENDMENT_01) | ❌ not built | schema (Phase 2), editor UI (Phase 5) |

Legend: ✅ covered (evidence cited) · ⚠️ rescoped (sign-off + date) · ❌ not built.
