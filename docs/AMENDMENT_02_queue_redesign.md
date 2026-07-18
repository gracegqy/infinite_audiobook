# AMENDMENT 02 — Queue redesign: 3 + skip + autoplay (2026-07-18)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENT_01.
> Status: **BINDING** as of Grace's DESIGN sign-off (v0.3 → frozen v1.0, 2026-07-18,
> JOURNAL Entry 15). Never edited from here; further changes are new amendment docs.
> Supersedes brief §2's "queue of 5".

## Verbatim (Grace, 2026-07-18)

would 5 be too much to cache? here's a design I propose: 3 unread for the active
channel, autoplayed in acquisition order (but also selectable from a menu); if I see a
title I'm not interested in or have already read, I click a button to remove it and new
acquisition happens. does this sound more efficient? assess critically.

## Assessment given, and agreed interpretation

Assessment: raw cost of 5 vs 3 is negligible (~2 MB audio + free local synthesis per
story) — but 3 is still the better design for a different reason: with 5 pre-acquired
stories, rating feedback only influences story 6+; with 3, taste adaptation reaches the
queue ~40% sooner. The skip button is the strongest part: it supplies a direct
curation-quality signal ratings can't (ratings judge stories she chose to hear; skips
judge the curator's picks). Accepted with two refinements:

- **Skips are permanent history.** A skipped story keeps its `stories` row with
  status `skipped` — the no-repeats guarantee (R6) must cover skips, or the curator
  will re-propose them.
- **Stories enter the queue at text-ready, synthesis follows in queue order.** Titles
  are visible (and skippable) after fetch+clean, before TTS. A skip before synthesis
  costs one fetch instead of a full render; autoplay only advances to synthesized
  stories. Accepted risk: back-to-back skips can briefly leave 1–2 playable stories
  (re-render is ~4.5 min/story, acceptable).

Queue = 3 unread for the **active** channel; autoplay in acquisition order; any queued
story selectable from a menu; skip → replenishment triggers immediately.
