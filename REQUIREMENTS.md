# REQUIREMENTS — horror_readaloud (working checklist)

> **Authority: derivative.** `docs/BRIEF_VERBATIM.md` + numbered amendments win; this file
> is *wrong* on any conflict. Changing any STATUS requires a JOURNAL entry. ⚠️ (rescoped)
> requires Grace's sign-off and must answer: "does the remaining subset still achieve the
> goal that motivated it?"

## Goals (the "why" every row must serve)

G1. Grace presses play and hears an excellent, well-chosen story — zero manual sourcing.
G2. The library maintains itself (queue of 3 per AMENDMENT_02, no repeats) at ~zero
    marginal cost.
G3. Listening works equally well on phone and laptop, resumable mid-sentence.
G4. Over time the picks get more Grace-shaped.

## Requirement table

| # | Required item (brief ref) | STATUS | Where it lives |
|---|---|---|---|
| R1 | Automated sourcing of highly-reputed stories; high bar: many recommenders, video essays, ratings (brief §1) | ✅ covered | `pipeline/curate.py` + pool flow; 2 curation_runs in DB, evidence strings on every story row (Entries 16–18). *Automatic* replenishment is R4 |
| R2 | Stories stored as pure clean text (brief intro) | ✅ covered | `pipeline/textproc.py`; `data/library/<id>/story.txt` for all 5 rendered stories (Entry 16) |
| R3 | High-quality AI narration (brief intro) | ✅ covered | `pipeline/synthesize.py` Kokoro; 5 stories rendered, Grace listened through the Phase 3 + 4 gates (Entries 16–21) |
| R4 | Queue self-heals to 3 unread, autoplay in acquisition order, skip button triggers replenishment (brief §2 as amended by AMENDMENT_02, 2026-07-18) | ◐ partial | autoplay + skip ship (Phase 4); **worker not built** — queue is at 0 unread (Phase 5, Entry 22) |
| R5 | Accessible on mobile + laptop (brief §3.1) | ✅ covered | Tailscale + PWA; Phase 4 gate passed on the phone (Entries 20–21) |
| R6 | Resume from last pause; read/in-progress history; no re-scraping repeats (brief §3.2) | ✅ covered | progress API + iOS rules; kill-and-reopen resume verified on phone (Entry 20); all-time dedup keys in `stories` |
| R7 | Spotify-like controls: pause/resume, ±10 s, scrubbable timeline, story select (brief §3.3; ±15→±10 by AMENDMENT_05 C1) | ✅ covered | `app/frontend/src/Player.jsx`; exercised in Grace's phone session (Entry 20) |
| R8 | Text script always accessible, synced highlight with audio (brief §3.3) | ◐ partial | text view + current-paragraph class/auto-scroll off the offsets manifest ship (`Player.jsx` `currentPara`/`para-now`, A05 C5); **phone-verified highlight tracking is the Phase 5 gate** |
| R9 | Bookmarks (brief §3.3) | ✅ covered | bookmarks table + API + player UI (add/jump/delete), round-trip tested |
| R10 | Preference adaptation from 1–5 ratings, trend record, weighted curation (brief §4) | ◐ partial | rating + clear-rating UI ship (A05 C8); **weighted curation is Phase 6**. Feasibility answer: YES, cheap — tag-at-ingest (~$0.01/story) + SQLite aggregation + prompt weighting; no ML, no UI latency |
| R11 | Economical: no exorbitant cost, no sprawl, snappy UI (brief §5) | ✅ standing constraint, holding | $0/mo baseline (Kokoro + self-host); pool curation at $0 marginal (AMENDMENT_04 A); audio synthesized once, cached forever |
| R12 | Channels: genre/language/topic editable in UI (AMENDMENT_01) | ◐ partial | `channels` schema + active-channel plumbing ship; **editor UI not built** (Phase 5) |
| R13 | Playback speed control in player (Grace, in-session 2026-07-18, JOURNAL Entry 6) | ✅ covered | `Player.jsx` `playbackRate`; honored on iOS (probe 5) |
| R14 | Curation model selectable in UI; quality-disappointment notice, never auto-escalate (Grace, 2026-07-18, JOURNAL Entry 12) | ✅ covered | Settings tab + `db.effective_curation_model`; skip-rate notice at ≥50% over ≥5 decided (Entry 21) |
| R15 | Multilingual channels en/zh/fr with non-Western sources, TTS-probe-gated per language (AMENDMENT_03) | ◐ partial | per-language engine config decided and probe-gated (fr Kokoro, zh edge-tts Yunxi — Entries 12–14); **no non-English channel has been run** (Phase 5 channels UI) |
| R16 | Render progress bar + pause/cancel on every render (AMENDMENT_06, Grace 2026-07-27) | ✅ covered | `render_jobs` + `/api/renders` + `RenderBar.jsx`; live Kokoro pause/resume/cancel verified (Entry 22) |

Legend: ✅ covered (evidence cited) · ◐ partial (what ships vs. what remains, both named) ·
⚠️ rescoped (sign-off + date) · ❌ not built.
